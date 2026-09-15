"""Command-line orchestration for the multisubs pipeline."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Protocol, TextIO, cast

import typer
from typer import _click as typer_click
from typer.main import get_command

from . import __version__
from .asr import (
    ASR_CHOICES,
    normalise_language_code,
    parse_backend,
    resolve_model,
    validate_request,
)
from .config import (
    BACKDROP_CHOICES,
    CUE_EMPHASIS_ANIMATION_CHOICES,
    CUE_ENTRANCE_ANIMATION_CHOICES,
    CUE_EXIT_ANIMATION_CHOICES,
    POSITION_CHOICES,
    WORD_ANIMATION_MODE_CHOICES,
    WORD_BACKDROP_EMPHASIS_ANIMATION_CHOICES,
    WORD_ENTRANCE_ANIMATION_CHOICES,
    WORD_EXIT_ANIMATION_CHOICES,
    WORD_TEXT_EMPHASIS_ANIMATION_CHOICES,
    parse_line_height,
    parse_opacity,
    parse_relative_length,
    parse_text_case,
    validate_subtitle_config,
)
from .custom_templates import ResolvedSubtitleTemplate, resolve_subtitle_template
from .errors import ArtifactError, MultisubsError, TemplateError, ValidationError
from .layout import (
    resolve_cue_placement,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
)
from .models import (
    PreviewMode,
    PreviewRequest,
    RelativeLength,
    RunArtifacts,
    RunRequest,
    SubtitleConfig,
    SubtitleElementAnimation,
    SubtitleOpacity,
    TextCase,
    TranscriptionPaths,
)
from .preview import (
    DEFAULT_PREVIEW_DURATION_MS,
    DEFAULT_PREVIEW_TEXT,
    parse_preview_duration,
    parse_preview_timestamp,
)
from .templates import (
    DEFAULT_SUBTITLE_TEMPLATE,
    TEMPLATE_CHOICES,
    require_template_catalog,
)
from .utils import (
    create_unique_dir,
    create_work_dir,
    find_unique_stem,
    publish_files,
    with_language_suffix,
)

LOGGER = logging.getLogger(__name__)
ProgressReporter = Callable[[str], None]


class _ValidationContext(Protocol):
    """Minimal context contract needed while validating a request."""

    def fail(self, message: str) -> None:
        """Abort request validation with a user-facing error."""


_DETAIL_PROGRESS_PREFIXES = (
    "Resolved subtitle animations:",
    "Preparing 16 kHz mono audio",
    "Completed JSON transcript.",
    "Completed SRT transcript.",
    "Completed ASS transcript.",
)


@contextmanager
def _cli_logging(verbose: bool):
    """Scope CLI logging changes to one processing invocation."""
    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    previous_disabled_level = root_logger.manager.disable
    debug_handler: logging.Handler | None = None
    if verbose:
        logging.disable(logging.NOTSET)
        debug_handler = logging.StreamHandler(sys.stderr)
        debug_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        root_logger.addHandler(debug_handler)
        root_logger.setLevel(logging.DEBUG)
    else:
        logging.disable(logging.INFO)
        root_logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        root_logger.setLevel(previous_root_level)
        logging.disable(previous_disabled_level)
        if debug_handler is not None:
            root_logger.removeHandler(debug_handler)
            debug_handler.close()


class _MutedPythonOutput:
    """Keep streams captured by new backend loggers usable after this run."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._muted = True

    def write(self, text: str) -> int:
        return len(text) if self._muted else self._stream.write(text)

    def flush(self) -> None:
        if not self._muted:
            self._stream.flush()

    def restore(self) -> None:
        self._muted = False

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


@contextmanager
def _quiet_external_output() -> Iterator[TextIO]:
    """Discard Python and native runtime output for a routine CLI run."""
    original_python_stdout = sys.stdout
    python_stdout = _MutedPythonOutput(original_python_stdout)
    python_stderr = _MutedPythonOutput(sys.stderr)
    with open(os.devnull, "wb") as sink:
        original_stdout_fd = os.dup(1)
        original_stderr_fd = os.dup(2)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            try:
                python_stdout_fd = original_python_stdout.fileno()
            except (AttributeError, OSError, ValueError):
                python_stdout_fd = None
            if python_stdout_fd == 1:
                progress_context = os.fdopen(
                    os.dup(original_stdout_fd),
                    "w",
                    encoding=original_python_stdout.encoding or "utf-8",
                    buffering=1,
                )
            else:
                progress_context = nullcontext(original_python_stdout)
            with progress_context as progress_output:
                with redirect_stdout(python_stdout), redirect_stderr(python_stderr):
                    yield progress_output
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(original_stdout_fd, 1)
            os.dup2(original_stderr_fd, 2)
            os.close(original_stdout_fd)
            os.close(original_stderr_fd)
            python_stdout.restore()
            python_stderr.restore()


def _cli_progress(message: str, *, verbose: bool, output: TextIO | None = None) -> None:
    """Show processing stages by default and details on request."""
    if not verbose and message.startswith(_DETAIL_PROGRESS_PREFIXES):
        return
    if not verbose and message.startswith("Detected video layout:"):
        print(message.split(" (", 1)[0].rstrip() + ".", file=output)
        return
    print(message, file=output)


app = typer.Typer(
    help="Generate and embed subtitles into a local video.",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)


def _choice_parser(choices: Sequence[str]) -> Callable[[str], str]:
    """Validate a CLI choice before resolving the request."""

    def parse(value: str) -> str:
        if value not in choices:
            raise typer.BadParameter(
                f"invalid choice: {value!r} (choose from {', '.join(choices)})"
            )
        return value

    return parse


def _version_callback(value: bool) -> None:
    """Print the version before required option validation."""
    if value:
        typer.echo(f"multisubs {__version__}")
        raise typer.Exit()


def _relative_length_argument_type(raw_value: str) -> RelativeLength:
    try:
        return parse_relative_length(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _language_argument_type(raw_value: str) -> str:
    try:
        return normalise_language_code(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _line_height_argument_type(raw_value: str) -> str | RelativeLength:
    try:
        return parse_line_height(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _opacity_argument_type(raw_value: str) -> SubtitleOpacity:
    try:
        return parse_opacity(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _text_case_argument_type(raw_value: str) -> TextCase:
    try:
        return parse_text_case(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _preview_timestamp_argument_type(raw_value: str) -> float:
    try:
        return parse_preview_timestamp(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _preview_duration_argument_type(raw_value: str) -> int:
    try:
        return parse_preview_duration(raw_value)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command(epilog="ASR language and model support depends on the selected backend.")
def _cli_command(
    ctx: typer.Context,
    # options
    input_path: Annotated[
        str,
        typer.Option(
            "-i",
            "--input-path",
            metavar="PATH",
            help="Path to one input video file.",
            show_default=False,
        ),
    ],
    version: Annotated[
        bool,
        typer.Option(
            "-v",
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the package version and exit.",
            show_default=False,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show detailed processing progress and backend logs.",
            show_default=False,
        ),
    ] = False,
    output_dir: Annotated[
        str,
        typer.Option(
            "-o",
            "--output-dir",
            metavar="DIR",
            help="Directory for generated files (default: current directory).",
            show_default=False,
        ),
    ] = ".",
    asr: Annotated[
        str,
        typer.Option(
            "--asr",
            metavar="BACKEND",
            parser=_choice_parser(ASR_CHOICES),
            help="Speech-recognition backend (default: whisperx).",
            show_default=False,
        ),
    ] = "whisperx",
    lang: Annotated[
        str | None,
        typer.Option(
            "-l",
            "--lang",
            metavar="CODE",
            parser=_language_argument_type,
            help=(
                "Source language code (default: automatic detection where the selected "
                "ASR exposes it)."
            ),
            show_default=False,
        ),
    ] = None,
    task: Annotated[
        str,
        typer.Option(
            "-t",
            "--task",
            metavar="TASK",
            parser=_choice_parser(("transcribe", "translate")),
            help="Transcribe or translate speech to English (default: transcribe).",
            show_default=False,
        ),
    ] = "transcribe",
    model: Annotated[
        str | None,
        typer.Option(
            "-m",
            "--model",
            metavar="MODEL",
            help="Model for the selected ASR backend (default: backend-specific).",
            show_default=False,
        ),
    ] = None,
    keep_transcriptions: Annotated[
        bool,
        typer.Option(
            "-k",
            "--keep-transcriptions",
            help="Retain JSON, SRT, and ASS files in a subtitles directory.",
            show_default=False,
        ),
    ] = False,
    template: Annotated[
        str | None,
        typer.Option(
            "--template",
            metavar="NAME",
            help=(
                "Subtitle presentation selected by template name; built-ins are "
                "available by default and --template-dir adds custom JSON templates "
                f"(default: {DEFAULT_SUBTITLE_TEMPLATE}). Built-ins: "
                + ", ".join(TEMPLATE_CHOICES)
                + "."
            ),
            show_default=False,
        ),
    ] = None,
    template_dir: Annotated[
        str | None,
        typer.Option(
            "--template-dir",
            metavar="DIR",
            help=(
                "Directory of custom subtitle template JSON files. The selected "
                "template name is resolved from this directory before built-ins."
            ),
            show_default=False,
        ),
    ] = None,
    position: Annotated[
        str | None,
        typer.Option(
            "--position",
            metavar="POSITION",
            parser=_choice_parser(POSITION_CHOICES),
            help=(
                "Use native ASS alignment and margins at the selected screen position; "
                "left and right are physical screen directions (default: "
                "bottom-center)."
            ),
            show_default=False,
        ),
    ] = None,
    # Subtitle preview
    preview_layout: Annotated[
        bool,
        typer.Option(
            "--preview-layout",
            rich_help_panel="Subtitle preview",
            help="Render a transcription-free subtitle layout preview PNG.",
            show_default=False,
        ),
    ] = False,
    preview_animation: Annotated[
        bool,
        typer.Option(
            "--preview-animation",
            rich_help_panel="Subtitle preview",
            help="Render a silent MP4 with deterministic simulated word timing.",
            show_default=False,
        ),
    ] = False,
    preview_at: Annotated[
        float | None,
        typer.Option(
            "--preview-at",
            metavar="HH:MM:SS.mmm",
            parser=_preview_timestamp_argument_type,
            rich_help_panel="Subtitle preview",
            help=(
                "Frame timestamp for the preview (default: video midpoint; format "
                "HH:MM:SS.mmm)."
            ),
            show_default=False,
        ),
    ] = None,
    preview_text: Annotated[
        str | None,
        typer.Option(
            "--preview-text",
            metavar="TEXT",
            rich_help_panel="Subtitle preview",
            help=f"Sample subtitle text (default: {DEFAULT_PREVIEW_TEXT!r}).",
            show_default=False,
        ),
    ] = None,
    preview_guides: Annotated[
        bool,
        typer.Option(
            "--preview-guides",
            rich_help_panel="Subtitle preview",
            help="Draw non-production placement, envelope, and canvas guides.",
            show_default=False,
        ),
    ] = False,
    preview_duration: Annotated[
        int | None,
        typer.Option(
            "--preview-duration",
            metavar="DURATION",
            parser=_preview_duration_argument_type,
            rich_help_panel="Subtitle preview",
            help=(
                "Animated preview cue duration in ms or s, from 1s through 15s "
                "(default: 4s)."
            ),
            show_default=False,
        ),
    ] = None,
    # Subtitle appearance
    font: Annotated[
        str | None,
        typer.Option(
            "--font",
            metavar="NAME",
            rich_help_panel="Subtitle appearance",
            help="Font family (default: Roboto).",
            show_default=False,
        ),
    ] = None,
    text_color: Annotated[
        str | None,
        typer.Option(
            "--text-color",
            metavar="COLOR",
            rich_help_panel="Subtitle appearance",
            help="Subtitle text color (default: #FFFFFF).",
            show_default=False,
        ),
    ] = None,
    font_weight: Annotated[
        str | None,
        typer.Option(
            "--font-weight",
            metavar="WEIGHT",
            rich_help_panel="Subtitle appearance",
            help=(
                "Font weight name or numeric rank. Names: thin, extra-light, light, "
                "regular, medium, semi-bold, bold, extra-bold, black. Numeric ranks: "
                "100, 200, 300, 400, 500, 600, 700, 800, 900. Aliases: hairline, "
                "ultra-light, normal, book, demi-bold, ultra-bold, heavy. Names are "
                "case-insensitive; spaces and underscores normalize to hyphens "
                "(default: regular)."
            ),
            show_default=False,
        ),
    ] = None,
    bold: Annotated[
        bool | None,
        typer.Option(
            "--bold/--no-bold",
            rich_help_panel="Subtitle appearance",
            help=(
                "Compatibility shorthand: --bold selects bold (700); --no-bold selects "
                "regular (400) (default: regular)."
            ),
            show_default=False,
        ),
    ] = None,
    italic: Annotated[
        bool | None,
        typer.Option(
            "--italic/--no-italic",
            rich_help_panel="Subtitle appearance",
            help="Enable or disable italic text (default: False).",
            show_default=False,
        ),
    ] = None,
    backdrop: Annotated[
        str | None,
        typer.Option(
            "--backdrop",
            metavar="{none,outline,box}",
            parser=_choice_parser(BACKDROP_CHOICES),
            rich_help_panel="Subtitle appearance",
            help="Subtitle backdrop: none, outline, or box (default: box).",
            show_default=False,
        ),
    ] = None,
    backdrop_color: Annotated[
        str | None,
        typer.Option(
            "--backdrop-color",
            metavar="COLOR",
            rich_help_panel="Subtitle appearance",
            help="Outline, box, and shadow color (default: #00000099).",
            show_default=False,
        ),
    ] = None,
    word_backdrop: Annotated[
        str | None,
        typer.Option(
            "--word-backdrop",
            metavar="{none,outline,box}",
            parser=_choice_parser(BACKDROP_CHOICES),
            rich_help_panel="Subtitle appearance",
            help="Timed word decoration: none, outline, or box (default: none).",
            show_default=False,
        ),
    ] = None,
    word_backdrop_color: Annotated[
        str | None,
        typer.Option(
            "--word-backdrop-color",
            metavar="COLOR",
            rich_help_panel="Subtitle appearance",
            help="Word-box color using #RRGGBB or #RRGGBBAA (default: #111827E6).",
            show_default=False,
        ),
    ] = None,
    opacity: Annotated[
        SubtitleOpacity | None,
        typer.Option(
            "--opacity",
            metavar="PERCENT",
            parser=_opacity_argument_type,
            rich_help_panel="Subtitle appearance",
            help=(
                "Global subtitle opacity from 0% through 100%, multiplied with each "
                "component color alpha (default: 100%)."
            ),
            show_default=False,
        ),
    ] = None,
    text_case: Annotated[
        TextCase | None,
        typer.Option(
            "--text-case",
            metavar="{original,uppercase,lowercase}",
            parser=_text_case_argument_type,
            rich_help_panel="Subtitle appearance",
            help=(
                "Subtitle display casing: original, uppercase, or lowercase (default: "
                "original)."
            ),
            show_default=False,
        ),
    ] = None,
    fonts_dir: Annotated[
        str | None,
        typer.Option(
            "--fonts-dir",
            metavar="DIR",
            rich_help_panel="Subtitle appearance",
            help="Directory containing additional fonts for FFmpeg/libass.",
            show_default=False,
        ),
    ] = None,
    # Subtitle animations
    animation_cue_text_entrance: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-text-entrance",
            metavar="{" + ",".join(CUE_ENTRANCE_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(CUE_ENTRANCE_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Cue text entrance animation; omission inherits the template.",
            show_default=False,
        ),
    ] = None,
    animation_cue_text_entrance_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-text-entrance-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_cue_text_emphasis: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-text-emphasis",
            metavar="{" + ",".join(CUE_EMPHASIS_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(CUE_EMPHASIS_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Cue text emphasis animation; omission inherits the template.",
            show_default=False,
        ),
    ] = None,
    animation_cue_text_emphasis_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-text-emphasis-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_cue_text_exit: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-text-exit",
            metavar="{" + ",".join(CUE_EXIT_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(CUE_EXIT_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Cue text exit animation; omission inherits the selected template.",
            show_default=False,
        ),
    ] = None,
    animation_cue_text_exit_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-text-exit-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_cue_backdrop_entrance: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-backdrop-entrance",
            metavar="{" + ",".join(CUE_ENTRANCE_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(CUE_ENTRANCE_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help=(
                "Cue backdrop entrance animation; omission inherits the selected "
                "template."
            ),
            show_default=False,
        ),
    ] = None,
    animation_cue_backdrop_entrance_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-backdrop-entrance-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_cue_backdrop_emphasis: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-backdrop-emphasis",
            metavar="{" + ",".join(CUE_EMPHASIS_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(CUE_EMPHASIS_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help=(
                "Cue backdrop emphasis animation; omission inherits the selected "
                "template."
            ),
            show_default=False,
        ),
    ] = None,
    animation_cue_backdrop_emphasis_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-backdrop-emphasis-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_cue_backdrop_exit: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-backdrop-exit",
            metavar="{" + ",".join(CUE_EXIT_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(CUE_EXIT_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Cue backdrop exit animation; omission inherits the template.",
            show_default=False,
        ),
    ] = None,
    animation_cue_backdrop_exit_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-cue-backdrop-exit-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_entrance: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-entrance",
            metavar="{" + ",".join(WORD_ENTRANCE_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(WORD_ENTRANCE_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Word text entrance animation; omission inherits the template.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_entrance_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-entrance-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_emphasis: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-emphasis",
            metavar="{" + ",".join(WORD_TEXT_EMPHASIS_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(WORD_TEXT_EMPHASIS_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Word text emphasis animation; omission inherits the template.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_emphasis_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-emphasis-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_exit: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-exit",
            metavar="{" + ",".join(WORD_EXIT_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(WORD_EXIT_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Word text exit animation; omission inherits the selected template.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_exit_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-exit-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_entrance: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-entrance",
            metavar="{" + ",".join(WORD_ENTRANCE_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(WORD_ENTRANCE_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help=(
                "Word backdrop entrance animation; omission inherits the selected "
                "template."
            ),
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_entrance_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-entrance-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_emphasis: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-emphasis",
            metavar="{" + ",".join(WORD_BACKDROP_EMPHASIS_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(WORD_BACKDROP_EMPHASIS_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help=(
                "Word backdrop emphasis animation; omission inherits the selected "
                "template."
            ),
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_emphasis_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-emphasis-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_exit: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-exit",
            metavar="{" + ",".join(WORD_EXIT_ANIMATION_CHOICES) + "}",
            parser=_choice_parser(WORD_EXIT_ANIMATION_CHOICES),
            rich_help_panel="Subtitle animations",
            help="Word backdrop exit animation; omission inherits the template.",
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_exit_duration: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-exit-duration",
            metavar="DURATION",
            rich_help_panel="Subtitle animations",
            help="Override this effect duration with a value such as 150ms or 0.15s.",
            show_default=False,
        ),
    ] = None,
    animation_word_text_mode: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-mode",
            metavar="{progressive,active-word}",
            parser=_choice_parser(WORD_ANIMATION_MODE_CHOICES),
            rich_help_panel="Subtitle animations",
            help=(
                "Timed word text behavior: progressive or active-word (default: "
                "active-word)."
            ),
            show_default=False,
        ),
    ] = None,
    animation_word_backdrop_mode: Annotated[
        str | None,
        typer.Option(
            "--animation-word-backdrop-mode",
            metavar="{progressive,active-word}",
            parser=_choice_parser(WORD_ANIMATION_MODE_CHOICES),
            rich_help_panel="Subtitle animations",
            help=(
                "Timed word backdrop behavior: progressive or active-word (default: "
                "active-word)."
            ),
            show_default=False,
        ),
    ] = None,
    animation_word_text_highlight_color: Annotated[
        str | None,
        typer.Option(
            "--animation-word-text-highlight-color",
            metavar="COLOR",
            rich_help_panel="Subtitle animations",
            help=(
                "Highlight color using #RRGGBB or #RRGGBBAA (default when enabled: "
                "#FFD54F)."
            ),
            show_default=False,
        ),
    ] = None,
    # Relative layout units
    font_size: Annotated[
        RelativeLength | None,
        typer.Option(
            "--font-size",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Font size as a percentage of the render height or pixels (default: "
                "4%)."
            ),
            show_default=False,
        ),
    ] = None,
    letter_spacing: Annotated[
        RelativeLength | None,
        typer.Option(
            "--letter-spacing",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Space between grapheme clusters as a percentage of "
                "the resolved font size or in PlayRes pixels (default: 0px)."
            ),
            show_default=False,
        ),
    ] = None,
    line_height: Annotated[
        str | None,
        typer.Option(
            "--line-height",
            metavar="auto|LENGTH",
            parser=_line_height_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Vertical baseline distance: auto uses measured font metrics; explicit "
                "percentages use natural line height and pixels use PlayRes space "
                "(default: auto)."
            ),
            show_default=False,
        ),
    ] = None,
    backdrop_size: Annotated[
        RelativeLength | None,
        typer.Option(
            "--backdrop-size",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Backdrop/outline size as a percentage of the resolved font size or "
                "pixels (default: 25%)."
            ),
            show_default=False,
        ),
    ] = None,
    word_backdrop_size: Annotated[
        RelativeLength | None,
        typer.Option(
            "--word-backdrop-size",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Timed word-box padding as a percentage of the resolved font size or "
                "pixels (default: 25%)."
            ),
            show_default=False,
        ),
    ] = None,
    shadow_size: Annotated[
        RelativeLength | None,
        typer.Option(
            "--shadow-size",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Shadow size as a percentage of the resolved font size or pixels "
                "(default: 0px)."
            ),
            show_default=False,
        ),
    ] = None,
    margin_left: Annotated[
        RelativeLength | None,
        typer.Option(
            "--margin-left",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help="Left margin as a percentage of width or pixels (default: 18%).",
            show_default=False,
        ),
    ] = None,
    margin_right: Annotated[
        RelativeLength | None,
        typer.Option(
            "--margin-right",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help="Right margin as a percentage of width or pixels (default: 18%).",
            show_default=False,
        ),
    ] = None,
    margin_top: Annotated[
        RelativeLength | None,
        typer.Option(
            "--margin-top",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Top-position margin as a percentage of render height or pixels; an "
                "explicit value is rejected for middle and bottom positions (default: "
                "0%)."
            ),
            show_default=False,
        ),
    ] = None,
    margin_bottom: Annotated[
        RelativeLength | None,
        typer.Option(
            "--margin-bottom",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Bottom-position margin as a percentage of render height or pixels; an "
                "explicit value is rejected for top and middle positions (default: 3%)."
            ),
            show_default=False,
        ),
    ] = None,
    max_width: Annotated[
        RelativeLength | None,
        typer.Option(
            "--max-width",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Maximum subtitle line width. Native percentages use the width after "
                "horizontal margins; explicit percentages use render width (native "
                "default: 100%)."
            ),
            show_default=False,
        ),
    ] = None,
    max_height: Annotated[
        RelativeLength | None,
        typer.Option(
            "--max-height",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Relative layout units",
            help=(
                "Maximum subtitle box height. Native percentages use the height after "
                "the active margin; explicit percentages use the render height "
                "(native default: 12%)."
            ),
            show_default=False,
        ),
    ] = None,
    # Custom subtitle coordinates
    position_x: Annotated[
        RelativeLength | None,
        typer.Option(
            "--position-x",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Custom subtitle coordinates",
            help="Horizontal anchor coordinate measured from the PlayRes left edge.",
            show_default=False,
        ),
    ] = None,
    position_y: Annotated[
        RelativeLength | None,
        typer.Option(
            "--position-y",
            metavar="LENGTH",
            parser=_relative_length_argument_type,
            rich_help_panel="Custom subtitle coordinates",
            help="Vertical anchor coordinate measured from the PlayRes top edge.",
            show_default=False,
        ),
    ] = None,
    anchor: Annotated[
        str | None,
        typer.Option(
            "--anchor",
            metavar="POSITION",
            parser=_choice_parser(POSITION_CHOICES),
            rich_help_panel="Custom subtitle coordinates",
            help="Required subtitle-box anchor for custom coordinates.",
            show_default=False,
        ),
    ] = None,
) -> int:
    """Generate and embed subtitles into a local video."""
    with _cli_logging(verbose):
        try:
            require_template_catalog()
            args = SimpleNamespace(
                **{name: value for name, value in locals().items() if name != "ctx"}
            )
            request = _build_request(args, ctx)
            if verbose:
                result_path = _run_request(
                    request,
                    lambda message: _cli_progress(message, verbose=True),
                    verbose=True,
                )
            else:
                with _quiet_external_output() as progress_output:
                    result_path = _run_request(
                        request,
                        lambda message: _cli_progress(
                            message, verbose=False, output=progress_output
                        ),
                        verbose=False,
                    )
        except Exception:
            if verbose:
                LOGGER.exception("multisubs command failed")
            raise
    if isinstance(request, PreviewRequest):
        label = (
            "Animated preview saved to"
            if request.preview_mode is PreviewMode.ANIMATION
            else "Preview saved to"
        )
        print(f"{label}: {result_path}")
    elif request.keep_transcriptions:
        print(f"Files saved in: {result_path}")
    else:
        print(f"File saved in: {result_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process-appropriate exit status."""
    try:
        require_template_catalog()
        result = get_command(app).main(
            args=list(argv) if argv is not None else None,
            prog_name="multisubs",
            standalone_mode=False,
        )
        return 0 if result is None else result
    except typer_click.ClickException as exc:
        exc.show(file=sys.stderr)
        raise SystemExit(exc.exit_code) from exc
    except MultisubsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # Keep routine CLI diagnostics terse.
        print(f"Error: Unexpected failure: {exc}", file=sys.stderr)
        return 1


def _build_request(
    args: SimpleNamespace, parser: _ValidationContext
) -> RunRequest | PreviewRequest:
    preview_mode_requested = args.preview_layout or args.preview_animation
    _validate_preview_options(args, parser, preview_mode_requested)
    selection, subtitle_config = _resolve_request_config(args, parser)

    language = args.lang
    backend = args.asr
    model_name = args.model
    if not preview_mode_requested:
        language, backend, model_name = _validate_normal_request(
            args, subtitle_config, parser
        )

    input_path, output_dir = _resolve_request_paths(args, parser)
    if preview_mode_requested:
        return _build_preview_request(
            args,
            input_path,
            output_dir,
            subtitle_config,
            selection,
        )
    return RunRequest(
        input_path=input_path,
        output_dir=output_dir,
        language=language,
        task=args.task,
        model_name=model_name,
        subtitle_config=subtitle_config,
        keep_transcriptions=args.keep_transcriptions,
        asr_backend=backend,
        subtitle_template_requested=args.template,
        subtitle_template_resolved=selection.template.name,
        subtitle_template_source=selection.source,
        subtitle_template_base=selection.base,
    )


def _validate_preview_options(
    args: SimpleNamespace,
    parser: typer.Context,
    preview_mode_requested: bool,
) -> None:
    """Reject preview-only options and artifact conflicts before file access."""
    if args.preview_layout and args.preview_animation:
        parser.fail("--preview-layout and --preview-animation cannot be combined")
    preview_options_used = (
        args.preview_at is not None
        or args.preview_text is not None
        or args.preview_guides
        or args.preview_duration is not None
    )
    if preview_options_used and not preview_mode_requested:
        parser.fail(
            "--preview-at, --preview-text, --preview-guides, and "
            "--preview-duration require --preview-layout or --preview-animation"
        )
    if args.preview_duration is not None and not args.preview_animation:
        parser.fail("--preview-duration can only be used with --preview-animation")
    if preview_mode_requested and args.keep_transcriptions:
        parser.fail(
            "--keep-transcriptions cannot be used with --preview-layout or "
            "--preview-animation"
        )


def _resolve_request_config(
    args: SimpleNamespace,
    parser: typer.Context,
) -> tuple[ResolvedSubtitleTemplate, SubtitleConfig]:
    """Resolve template and explicit overrides into one typed configuration."""
    appearance_values = _defined_values(
        {
            "font": args.font,
            "text_color": args.text_color,
            "font_weight": args.font_weight,
            "bold": args.bold,
            "italic": args.italic,
            "backdrop": args.backdrop,
            "backdrop_color": args.backdrop_color,
            "word_backdrop": args.word_backdrop,
            "word_backdrop_color": args.word_backdrop_color,
            "opacity": args.opacity,
            "text_case": args.text_case,
            "fonts_dir": args.fonts_dir,
        }
    )
    animation_values = _animation_values(args)
    relative_values = cast(
        dict[str, RelativeLength | str],
        _defined_values(
            {
                "font_size": args.font_size,
                "letter_spacing": args.letter_spacing,
                "line_height": args.line_height,
                "outline_weight": args.backdrop_size,
                "word_backdrop_size": args.word_backdrop_size,
                "shadow_weight": args.shadow_size,
                "margin_left": args.margin_left,
                "margin_right": args.margin_right,
                "margin_top": args.margin_top,
                "margin_bottom": args.margin_bottom,
                "max_width": args.max_width,
                "max_height": args.max_height,
                "position_x": args.position_x,
                "position_y": args.position_y,
            }
        ),
    )
    try:
        selection = resolve_subtitle_template(args.template, args.template_dir)
        subtitle_config = validate_subtitle_config(
            None,
            defaults=selection.template.config,
            appearance_values=appearance_values,
            animation_values=animation_values,
            position=args.position,
            relative_values=relative_values,
            anchor=args.anchor,
        )
    except (TemplateError, ValidationError) as exc:
        parser.fail(str(exc))
    return selection, subtitle_config


def _defined_values(values: dict[str, object | None]) -> dict[str, object]:
    """Drop omitted CLI values while retaining explicit false and zero values."""
    return {key: value for key, value in values.items() if value is not None}


def _animation_values(args: SimpleNamespace) -> dict[str, object]:
    values: dict[str, object | None] = {}
    for scope in ("cue", "word"):
        for element in ("text", "backdrop"):
            for phase in ("entrance", "emphasis", "exit"):
                key = f"{scope}_{element}_{phase}"
                values[key] = getattr(args, f"animation_{key}")
                values[f"{key}_duration"] = getattr(args, f"animation_{key}_duration")
    values.update(
        word_text_mode=args.animation_word_text_mode,
        word_backdrop_mode=args.animation_word_backdrop_mode,
        word_text_highlight_color=args.animation_word_text_highlight_color,
    )
    return _defined_values(values)


def _validate_normal_request(
    args: SimpleNamespace,
    subtitle_config: SubtitleConfig,
    parser: typer.Context,
) -> tuple[str | None, str, str]:
    """Validate and resolve the selected ASR, model, task, and language."""
    _validate_animation_request(
        subtitle_config,
        task=args.task,
        parser=parser,
    )
    try:
        backend = parse_backend(args.asr)
        model_name = resolve_model(backend, args.model)
        language = validate_request(backend, args.lang, args.task, model_name)
    except ValidationError as exc:
        parser.fail(str(exc))
    return language, backend.value, model_name


def _resolve_request_paths(
    args: SimpleNamespace,
    parser: typer.Context,
) -> tuple[Path, Path]:
    """Resolve and validate user paths without creating output directories."""
    input_path = Path(args.input_path).expanduser().resolve(strict=False)
    if not input_path.exists() or not input_path.is_file():
        parser.fail(f"Video file not found at '{args.input_path}'")

    output_dir = Path(args.output_dir).expanduser().resolve(strict=False)
    if output_dir.exists() and not output_dir.is_dir():
        parser.fail(
            f"Output path '{args.output_dir}' is a file; provide a directory instead"
        )
    return input_path, output_dir


def _build_preview_request(
    args: SimpleNamespace,
    input_path: Path,
    output_dir: Path,
    subtitle_config: SubtitleConfig,
    selection: ResolvedSubtitleTemplate,
) -> PreviewRequest:
    """Build a transcription-free request from validated CLI values."""
    return PreviewRequest(
        input_path=input_path,
        output_dir=output_dir,
        subtitle_config=subtitle_config,
        preview_at=args.preview_at,
        preview_text=(
            DEFAULT_PREVIEW_TEXT if args.preview_text is None else args.preview_text
        ),
        guides=args.preview_guides,
        subtitle_template_requested=args.template,
        subtitle_template_resolved=selection.template.name,
        subtitle_template_source=selection.source,
        subtitle_template_base=selection.base,
        preview_mode=(
            PreviewMode.ANIMATION if args.preview_animation else PreviewMode.LAYOUT
        ),
        preview_duration_ms=(
            DEFAULT_PREVIEW_DURATION_MS
            if args.preview_duration is None
            else args.preview_duration
        ),
    )


def _validate_animation_request(
    subtitle_config: SubtitleConfig,
    *,
    task: str,
    parser: typer.Context,
) -> None:
    needs_word_timing = (
        subtitle_config.animation.word.text.enabled
        or subtitle_config.style.word_backdrop.kind.value != "none"
    )
    if needs_word_timing and task == "translate":
        parser.fail(
            "word animation cannot be combined with --task translate because "
            "source-language word timings do not map losslessly to translated text"
        )


def _run_request(
    request: RunRequest | PreviewRequest,
    progress: ProgressReporter,
    *,
    verbose: bool = False,
) -> Path:
    """Keep a selected bundled family alive through measurement and rendering."""
    from .font_catalog import bundled_font_directory

    with bundled_font_directory(
        request.subtitle_config.style.typography.font
    ) as directory:
        return _run_request_with_fonts(
            request,
            progress,
            bundled_fonts_dir=directory,
            verbose=verbose,
        )


def _format_animation_track(track: SubtitleElementAnimation) -> str:
    """Format one validated animation track for progress output."""
    return "/".join(
        getattr(track, phase).type.value for phase in ("entrance", "emphasis", "exit")
    )


def _run_request_with_fonts(
    request: RunRequest | PreviewRequest,
    progress: ProgressReporter,
    *,
    bundled_fonts_dir: Path | None,
    verbose: bool = False,
) -> Path:
    """Run in a private directory and publish only completed user artifacts."""
    if request.subtitle_template_source == "custom":
        progress(
            f"Using custom subtitle template: {request.subtitle_template_resolved}"
            + (
                f" (base: {request.subtitle_template_base})."
                if request.subtitle_template_base is not None
                else "."
            )
        )
    else:
        progress(f"Using subtitle template: {request.subtitle_template_resolved}.")
    animation = request.subtitle_config.animation
    progress(
        "Resolved subtitle animations: "
        f"cue.text={_format_animation_track(animation.cue.text)}, "
        f"cue.backdrop={_format_animation_track(animation.cue.backdrop)}, "
        f"word.text={_format_animation_track(animation.word.text)}, "
        f"word.backdrop={_format_animation_track(animation.word.backdrop)}."
    )
    if isinstance(request, PreviewRequest):
        return _run_preview_request(
            request,
            progress,
            bundled_fonts_dir=bundled_fonts_dir,
        )

    from .subtitler import (
        embed_subtitles,
        probe_video_geometry,
        validate_ffmpeg_support,
    )
    from .transcriber import transcribe_video, write_transcription_artifacts
    from .wrapping import transform_display_text

    validate_ffmpeg_support()
    geometry = probe_video_geometry(request.input_path)
    resolved_subtitle_config = resolve_subtitle_config(
        request.subtitle_config,
        geometry,
        bundled_fonts_dir=bundled_fonts_dir,
    )
    wrapping_metrics = resolve_wrapping_metrics(
        resolved_subtitle_config,
        geometry,
        language=request.language,
        bundled_fonts_dir=bundled_fonts_dir,
    )
    placement = resolve_cue_placement(resolved_subtitle_config, geometry)
    if placement is not None:
        placement_description = (
            f"anchor {placement.anchor.value} at "
            f"({placement.position_x}, {placement.position_y}) with envelope "
            f"{wrapping_metrics.max_width}x{wrapping_metrics.max_height}px"
        )
    else:
        placement_description = (
            f"native position {resolved_subtitle_config.layout.position.value} "
            f"with {wrapping_metrics.max_width}x"
            f"{wrapping_metrics.max_height}px limits"
        )
    progress(
        "Detected video layout: "
        f"{geometry.render_width}x{geometry.render_height} "
        f"(stream {geometry.stream_index}, rotation "
        f"{geometry.rotation_degrees}°, SAR "
        f"{geometry.sample_aspect_ratio.numerator}:"
        f"{geometry.sample_aspect_ratio.denominator}, {placement_description})."
    )
    work_dir = create_work_dir(request.output_dir)
    try:
        document = transcribe_video(
            request.input_path,
            request.language,
            request.task,
            request.model_name,
            asr_backend=request.asr_backend,
            progress=progress,
            verbose=verbose,
        )
        request = replace(request, language=document.language)
        wrapping_metrics = resolve_wrapping_metrics(
            resolved_subtitle_config,
            geometry,
            language="en" if request.task == "translate" else document.language,
            bundled_fonts_dir=bundled_fonts_dir,
            sample_text=[
                transform_display_text(
                    str(segment.get("text", "")),
                    resolved_subtitle_config.style.typography.text_case,
                )
                for segment in document.segments
            ],
            verify_font_coverage=True,
        )
        artifact_options = {
            "geometry": geometry,
            "resolved_subtitle_config": resolved_subtitle_config,
            "wrapping_metrics": wrapping_metrics,
            "verify_font_coverage": True,
            "template_requested": request.subtitle_template_requested,
            "template_resolved": request.subtitle_template_resolved,
            "progress": progress,
        }
        if request.subtitle_template_source != "builtin":
            artifact_options.update(
                template_source=request.subtitle_template_source,
                template_base=request.subtitle_template_base,
            )
        json_path, srt_path, ass_path = write_transcription_artifacts(
            document,
            work_dir,
            request.subtitle_config,
            **artifact_options,
        )
        transcripts = TranscriptionPaths(
            json_path=Path(json_path), srt_path=Path(srt_path), ass_path=Path(ass_path)
        )
        video_path = work_dir / (
            f"{with_language_suffix(request.input_path.stem, request.language)}"
            f"{request.input_path.suffix}"
        )
        rendered_path = Path(
            embed_subtitles(
                request.input_path,
                transcripts.ass_path,
                work_dir,
                document.language,
                output_path=video_path,
                geometry=geometry,
                fonts_dir=(wrapping_metrics.text_measurer.info.renderer_fonts_dir),
                progress=progress,
            )
        )
        artifacts = RunArtifacts(work_dir, transcripts, rendered_path)
        result_path = _publish_run(artifacts, request)
    except MultisubsError as exc:
        raise ArtifactError(
            f"{exc} Working artifacts were kept in '{work_dir}'."
        ) from exc
    except Exception as exc:
        raise ArtifactError(
            f"Unexpected pipeline failure: {exc} Working artifacts were kept in "
            f"'{work_dir}'."
        ) from exc
    else:
        _cleanup_work_dir(work_dir)
        return result_path


def _run_preview_request(
    request: PreviewRequest,
    progress: ProgressReporter,
    *,
    bundled_fonts_dir: Path | None = None,
) -> Path:
    """Render a transcription-free PNG or animated clip."""
    from .preview import (
        build_animation_preview_ass,
        build_preview_ass,
        normalise_preview_text,
        preview_word_effect_fallback_reason,
        resolve_preview_timestamp,
    )
    from .subtitler import (
        probe_video_geometry,
        render_subtitle_animation_preview,
        render_subtitle_preview,
        validate_animation_preview_support,
        validate_ffmpeg_support,
    )
    from .wrapping import transform_display_text

    validate_ffmpeg_support()
    if request.preview_mode is PreviewMode.ANIMATION:
        validate_animation_preview_support()
    geometry = probe_video_geometry(request.input_path)
    timestamp = resolve_preview_timestamp(request.preview_at, geometry)
    resolved_config = resolve_subtitle_config(
        request.subtitle_config,
        geometry,
        bundled_fonts_dir=bundled_fonts_dir,
    )
    wrapping_metrics = resolve_wrapping_metrics(
        resolved_config,
        geometry,
        bundled_fonts_dir=bundled_fonts_dir,
        sample_text=transform_display_text(
            request.preview_text,
            resolved_config.style.typography.text_case,
        ),
        verify_font_coverage=True,
    )
    if wrapping_metrics.text_measurer.diagnostic is not None:
        progress(wrapping_metrics.text_measurer.diagnostic)
    progress(
        "Detected video layout: "
        f"{geometry.render_width}x{geometry.render_height} "
        f"(stream {geometry.stream_index}, rotation "
        f"{geometry.rotation_degrees}°, preview at {timestamp:.3f}s, "
        f"{wrapping_metrics.max_width}x{wrapping_metrics.max_height}px limits)."
    )
    work_dir = create_work_dir(request.output_dir)
    try:
        ass_path = work_dir / "subtitle-preview.ass"
        if request.preview_mode is PreviewMode.ANIMATION:
            _, display_text = build_animation_preview_ass(
                ass_path,
                request,
                geometry,
                timestamp,
                resolved_config=resolved_config,
                wrapping_metrics=wrapping_metrics,
            )
            fallback_reason = preview_word_effect_fallback_reason(
                display_text, resolved_config
            )
            if fallback_reason is not None:
                progress(
                    "Warning: Preview word effects were suppressed so libass can "
                    "render the sample as complete shaping-safe logical lines "
                    f"({fallback_reason})."
                )
            source_text = transform_display_text(
                normalise_preview_text(request.preview_text),
                resolved_config.style.typography.text_case,
            )
            if normalise_preview_text(display_text) != normalise_preview_text(
                source_text
            ):
                progress(
                    "Animated preview sample was shortened to the first fitting "
                    "cue; simulated word timings are not speech-synchronized."
                )
            else:
                progress(
                    "Animated preview uses deterministic simulated word timings; "
                    "it is not synchronized to source speech."
                )
            return Path(
                render_subtitle_animation_preview(
                    request.input_path,
                    ass_path,
                    request.output_dir,
                    timestamp=timestamp,
                    duration_ms=request.preview_duration_ms,
                    geometry=geometry,
                    fonts_dir=(wrapping_metrics.text_measurer.info.renderer_fonts_dir),
                    progress=progress,
                )
            )

        _, display_text = build_preview_ass(
            ass_path,
            request,
            geometry,
            timestamp,
            resolved_config=resolved_config,
            wrapping_metrics=wrapping_metrics,
        )
        fallback_reason = preview_word_effect_fallback_reason(
            display_text, resolved_config
        )
        if fallback_reason is not None:
            progress(
                "Warning: Preview word effects were suppressed so libass can "
                "render the sample as complete shaping-safe logical lines "
                f"({fallback_reason})."
            )
        return Path(
            render_subtitle_preview(
                request.input_path,
                ass_path,
                request.output_dir,
                timestamp=timestamp,
                geometry=geometry,
                fonts_dir=(wrapping_metrics.text_measurer.info.renderer_fonts_dir),
                progress=progress,
            )
        )
    except MultisubsError:
        raise
    except Exception as exc:
        raise ArtifactError(f"Unexpected preview failure: {exc}") from exc
    finally:
        _cleanup_work_dir(work_dir)


def _publish_run(artifacts: RunArtifacts, request: RunRequest) -> Path:
    if request.keep_transcriptions:
        return _publish_retained_artifacts(artifacts, request)
    return _publish_default_artifacts(artifacts, request)


def _publish_default_artifacts(artifacts: RunArtifacts, request: RunRequest) -> Path:
    stem = with_language_suffix(request.input_path.stem, request.language)
    suffixes = (request.input_path.suffix,)
    while True:
        candidate = find_unique_stem(request.output_dir, stem, suffixes)
        video_target = request.output_dir / f"{candidate}{request.input_path.suffix}"
        try:
            publish_files({artifacts.video_path: video_target})
        except FileExistsError:
            continue
        return video_target


def _publish_retained_artifacts(artifacts: RunArtifacts, request: RunRequest) -> Path:
    final_dir = create_unique_dir(request.output_dir / request.input_path.stem)
    subtitles_dir = final_dir / "subtitles"
    try:
        publish_files(
            {
                artifacts.video_path: final_dir / artifacts.video_path.name,
                artifacts.transcripts.json_path: subtitles_dir
                / artifacts.transcripts.json_path.name,
                artifacts.transcripts.srt_path: subtitles_dir
                / artifacts.transcripts.srt_path.name,
                artifacts.transcripts.ass_path: subtitles_dir
                / artifacts.transcripts.ass_path.name,
            }
        )
    except Exception:
        try:
            shutil.rmtree(final_dir)
        except OSError:
            pass
        raise
    return final_dir


def _cleanup_work_dir(work_dir: Path) -> None:
    try:
        shutil.rmtree(work_dir)
    except OSError as exc:
        print(
            f"Warning: Could not remove temporary artifacts in '{work_dir}': {exc}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
