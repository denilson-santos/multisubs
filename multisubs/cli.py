"""Command-line orchestration for the multisubs pipeline."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from . import __version__
from .config import (
    BACKDROP_CHOICES,
    DEFAULT_BACKDROP,
    DEFAULT_BACKDROP_COLOR,
    DEFAULT_BACKDROP_SIZE,
    DEFAULT_FONT,
    DEFAULT_FONT_SIZE,
    DEFAULT_FONT_WEIGHT,
    DEFAULT_ITALIC,
    DEFAULT_KARAOKE_HIGHLIGHT_COLOR,
    DEFAULT_KARAOKE_MODE,
    DEFAULT_LETTER_SPACING,
    DEFAULT_LINE_HEIGHT,
    DEFAULT_OPACITY,
    DEFAULT_SHADOW_SIZE,
    DEFAULT_TEXT_CASE,
    DEFAULT_TEXT_COLOR,
    FONT_WEIGHT_ALIASES,
    FONT_WEIGHT_NAMES,
    FONT_WEIGHT_RANKS,
    KARAOKE_MODE_CHOICES,
    LAYOUT_PRESET_CHOICES,
    LAYOUT_PRESETS,
    MODELS,
    POSITION_CHOICES,
    SUPPORTED_LANGUAGES,
    TEXT_CASE_CHOICES,
    parse_line_height,
    parse_opacity,
    parse_relative_length,
    parse_text_case,
    validate_subtitle_config,
)
from .errors import ArtifactError, MultisubsError, ValidationError
from .layout import (
    resolve_cue_placement,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
)
from .models import (
    PreviewRequest,
    RelativeLength,
    RunArtifacts,
    RunRequest,
    SubtitleOpacity,
    TextCase,
    TranscriptionPaths,
)
from .preview import DEFAULT_PREVIEW_TEXT, parse_preview_timestamp
from .utils import (
    create_unique_dir,
    create_work_dir,
    find_unique_stem,
    publish_files,
)

LOGGER = logging.getLogger(__name__)
ProgressReporter = Callable[[str], None]


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser without importing model runtime dependencies."""
    parser = argparse.ArgumentParser(
        description="Generate and embed subtitles into a local video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Supported language codes: " + ", ".join(SUPPORTED_LANGUAGES),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Print the package version and exit.",
    )
    parser.add_argument(
        "-i",
        "--input-path",
        required=True,
        metavar="PATH",
        help="Path to one input video file.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        metavar="DIR",
        help="Directory for generated files (default: current directory).",
    )
    parser.add_argument(
        "-l",
        "--lang",
        default="en",
        choices=SUPPORTED_LANGUAGES,
        metavar="CODE",
        help=(
            "Source language code; translation output is always English (default: en)."
        ),
    )
    parser.add_argument(
        "-t",
        "--task",
        default="transcribe",
        choices=("transcribe", "translate"),
        metavar="TASK",
        help="Transcribe or translate speech to English (default: transcribe).",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="turbo",
        choices=MODELS,
        metavar="MODEL",
        help="Whisper model; translation requires a multilingual non-Turbo model.",
    )
    parser.add_argument(
        "-k",
        "--keep-transcriptions",
        action="store_true",
        help="Retain JSON, SRT, and ASS files in a subtitles directory.",
    )
    preview_group = parser.add_argument_group(
        "Subtitle layout preview",
        "Render one frame without transcription or a final subtitle video.",
    )
    preview_group.add_argument(
        "--preview-layout",
        action="store_true",
        help="Render a transcription-free subtitle layout preview PNG.",
    )
    preview_group.add_argument(
        "--preview-at",
        type=_preview_timestamp_argument_type,
        default=None,
        metavar="HH:MM:SS.mmm",
        help=(
            "Frame timestamp for the preview (default: video midpoint; "
            "format HH:MM:SS.mmm)."
        ),
    )
    preview_group.add_argument(
        "--preview-text",
        default=None,
        metavar="TEXT",
        help=(f"Sample subtitle text (default: {DEFAULT_PREVIEW_TEXT!r})."),
    )
    preview_group.add_argument(
        "--preview-guides",
        action="store_true",
        help="Draw non-production placement, envelope, and canvas guides.",
    )
    parser.add_argument(
        "--layout",
        choices=LAYOUT_PRESET_CHOICES,
        default="auto",
        help=(
            "Named subtitle layout preset. auto selects landscape, portrait, or "
            "square from the autorotated video geometry (default: auto). "
            + " ".join(
                f"{preset.value}: {LAYOUT_PRESETS[preset].description}"
                for preset in LAYOUT_PRESETS
            )
        ),
    )
    parser.add_argument(
        "--position",
        choices=POSITION_CHOICES,
        default=None,
        help=(
            "Use native ASS alignment and margins at the selected screen "
            "position; left and right are physical screen directions."
        ),
    )

    appearance_group = parser.add_argument_group(
        "Subtitle appearance",
        "Semantic appearance controls; colors use #RRGGBB or #RRGGBBAA.",
    )
    appearance_group.add_argument(
        "--font",
        default=None,
        metavar="NAME",
        help=f"Font family (default: {DEFAULT_FONT}).",
    )
    appearance_group.add_argument(
        "--text-color",
        default=None,
        metavar="COLOR",
        help=f"Subtitle text color (default: {DEFAULT_TEXT_COLOR}).",
    )
    appearance_group.add_argument(
        "--font-weight",
        default=None,
        metavar="WEIGHT",
        help=(
            "Font weight name or numeric rank. Names: "
            + ", ".join(FONT_WEIGHT_NAMES)
            + ". Numeric ranks: "
            + ", ".join(str(rank) for rank in FONT_WEIGHT_RANKS)
            + ". Aliases: "
            + ", ".join(FONT_WEIGHT_ALIASES)
            + ". Names are case-insensitive; spaces and underscores normalize "
            "to hyphens" + f" (default: {DEFAULT_FONT_WEIGHT.canonical_name})."
        ),
    )
    appearance_group.add_argument(
        "--bold",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Compatibility shorthand: --bold selects bold (700); --no-bold "
            "selects regular (400) (default: regular)."
        ),
    )
    appearance_group.add_argument(
        "--italic",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=f"Enable or disable italic text (default: {DEFAULT_ITALIC}).",
    )
    appearance_group.add_argument(
        "--backdrop",
        choices=BACKDROP_CHOICES,
        default=None,
        help=(
            "Subtitle backdrop: none, outline, or box "
            f"(default: {DEFAULT_BACKDROP.value})."
        ),
    )
    appearance_group.add_argument(
        "--backdrop-color",
        default=None,
        metavar="COLOR",
        help=f"Outline, box, and shadow color (default: {DEFAULT_BACKDROP_COLOR}).",
    )
    appearance_group.add_argument(
        "--opacity",
        type=_opacity_argument_type,
        default=None,
        metavar="PERCENT",
        help=(
            "Global subtitle opacity from 0%% through 100%%, multiplied with each "
            f"component color alpha (default: {DEFAULT_OPACITY.replace('%', '%%')})."
        ),
    )
    appearance_group.add_argument(
        "--text-case",
        type=_text_case_argument_type,
        default=None,
        metavar="{" + ",".join(TEXT_CASE_CHOICES) + "}",
        help=(
            "Subtitle display casing: original, uppercase, or lowercase "
            f"(default: {DEFAULT_TEXT_CASE.value})."
        ),
    )
    appearance_group.add_argument(
        "--fonts-dir",
        default=None,
        metavar="DIR",
        help="Directory containing additional fonts for FFmpeg/libass.",
    )

    effects_group = parser.add_argument_group(
        "Subtitle effects",
        "Optional effects applied to transcription cues.",
    )
    effects_group.add_argument(
        "--karaoke",
        action="store_true",
        help="Highlight aligned words using a karaoke effect.",
    )
    effects_group.add_argument(
        "--karaoke-mode",
        choices=KARAOKE_MODE_CHOICES,
        default=None,
        metavar="MODE",
        help=(
            "Karaoke highlight behavior: progressive or active-word "
            f"(default when enabled: {DEFAULT_KARAOKE_MODE.value})."
        ),
    )
    effects_group.add_argument(
        "--karaoke-highlight-color",
        default=None,
        metavar="COLOR",
        help=(
            "Karaoke highlight color using #RRGGBB or #RRGGBBAA "
            f"(default when enabled: {DEFAULT_KARAOKE_HIGHLIGHT_COLOR})."
        ),
    )

    relative_group = parser.add_argument_group(
        "Relative layout units",
        "Use percentages or pixels; bare numbers are not accepted.",
    )
    for option, help_text in (
        (
            "--font-size",
            "Font size as a percentage of the shorter render edge or pixels "
            f"(default: {DEFAULT_FONT_SIZE.replace('%', '%%')}).",
        ),
        (
            "--letter-spacing",
            "Additional space between rendered grapheme clusters as a percentage "
            "of the resolved font size or in PlayRes pixels "
            f"(default: {DEFAULT_LETTER_SPACING.replace('%', '%%')}).",
        ),
        (
            "--line-height",
            "Vertical baseline distance: auto uses measured font metrics; explicit "
            "percentages use natural line height and pixels use PlayRes space "
            f"(default: {DEFAULT_LINE_HEIGHT}).",
        ),
        (
            "--backdrop-size",
            "Backdrop/outline size as a percentage of the resolved font size "
            f"or pixels (default: {DEFAULT_BACKDROP_SIZE.replace('%', '%%')}).",
        ),
        (
            "--shadow-size",
            "Shadow size as a percentage of the resolved font size or pixels "
            f"(default: {DEFAULT_SHADOW_SIZE.replace('%', '%%')}).",
        ),
        (
            "--margin-left",
            "Left margin as a percentage of render width or pixels.",
        ),
        (
            "--margin-right",
            "Right margin as a percentage of render width or pixels.",
        ),
        (
            "--margin-top",
            "Top margin as a percentage of render height or pixels.",
        ),
        (
            "--margin-bottom",
            "Bottom margin as a percentage of render height or pixels.",
        ),
        (
            "--max-width",
            "Maximum subtitle line width. Native percentages use the width "
            "after horizontal margins; explicit percentages use render width.",
        ),
        (
            "--max-height",
            "Maximum subtitle box height. Native percentages use the height "
            "after the active vertical margin; explicit percentages use the "
            "render height.",
        ),
    ):
        relative_group.add_argument(
            option,
            type=(
                _line_height_argument_type
                if option == "--line-height"
                else _relative_length_argument_type
            ),
            default=None,
            metavar="auto|LENGTH" if option == "--line-height" else "LENGTH",
            help=help_text,
        )

    coordinate_group = parser.add_argument_group(
        "Custom subtitle coordinates",
        "Attach an explicit anchor to global PlayRes X/Y coordinates. Margins "
        "are ignored; max-width and max-height are required.",
    )
    coordinate_group.add_argument(
        "--position-x",
        type=_relative_length_argument_type,
        default=None,
        metavar="LENGTH",
        help="Horizontal anchor coordinate measured from the PlayRes left edge.",
    )
    coordinate_group.add_argument(
        "--position-y",
        type=_relative_length_argument_type,
        default=None,
        metavar="LENGTH",
        help="Vertical anchor coordinate measured from the PlayRes top edge.",
    )
    coordinate_group.add_argument(
        "--anchor",
        choices=POSITION_CHOICES,
        default=None,
        help="Required subtitle-box anchor for custom coordinates.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process-appropriate exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    request = _build_request(args, parser)

    try:
        result_path = _run_request(request, print)
    except MultisubsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # Keep the CLI terse while retaining a log traceback.
        LOGGER.exception("Unexpected multisubs failure")
        print(f"Error: Unexpected failure: {exc}", file=sys.stderr)
        return 1

    if isinstance(request, PreviewRequest):
        print(f"Preview saved to: {result_path}")
    elif request.keep_transcriptions:
        print(f"Files saved in: {result_path}")
    else:
        print(f"File saved in: {result_path}")
    return 0


def _relative_length_argument_type(raw_value: str) -> RelativeLength:
    try:
        return parse_relative_length(raw_value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _line_height_argument_type(raw_value: str) -> str | RelativeLength:
    try:
        return parse_line_height(raw_value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _opacity_argument_type(raw_value: str) -> SubtitleOpacity:
    try:
        return parse_opacity(raw_value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _text_case_argument_type(raw_value: str) -> TextCase:
    try:
        return parse_text_case(raw_value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _preview_timestamp_argument_type(raw_value: str) -> float:
    try:
        return parse_preview_timestamp(raw_value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _build_request(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> RunRequest | PreviewRequest:
    preview_options_used = (
        args.preview_at is not None
        or args.preview_text is not None
        or args.preview_guides
    )
    if preview_options_used and not args.preview_layout:
        parser.error(
            "--preview-at, --preview-text, and --preview-guides require "
            "--preview-layout"
        )
    if args.preview_layout and args.keep_transcriptions:
        parser.error("--keep-transcriptions cannot be used with --preview-layout")
    _validate_effect_request(args, parser)
    if not args.preview_layout:
        _validate_translation_request(args.task, args.model, parser)
    input_path = Path(args.input_path).expanduser().resolve(strict=False)
    if not input_path.exists() or not input_path.is_file():
        parser.error(f"Video file not found at '{args.input_path}'")

    output_dir = Path(args.output_dir).expanduser().resolve(strict=False)
    if output_dir.exists() and not output_dir.is_dir():
        parser.error(
            f"Output path '{args.output_dir}' is a file; provide a directory instead"
        )

    appearance_values = {
        key: value
        for key, value in {
            "font": args.font,
            "text_color": args.text_color,
            "font_weight": args.font_weight,
            "bold": args.bold,
            "italic": args.italic,
            "backdrop": args.backdrop,
            "backdrop_color": args.backdrop_color,
            "opacity": args.opacity,
            "text_case": args.text_case,
            "fonts_dir": args.fonts_dir,
        }.items()
        if value is not None
    }
    effects_values = {
        "karaoke": args.karaoke,
        "karaoke_mode": args.karaoke_mode,
        "highlight_color": args.karaoke_highlight_color,
    }
    effects_values = {
        key: value for key, value in effects_values.items() if value is not None
    }
    relative_values = {
        key: value
        for key, value in {
            "font_size": args.font_size,
            "letter_spacing": args.letter_spacing,
            "line_height": args.line_height,
            "outline_weight": args.backdrop_size,
            "shadow_weight": args.shadow_size,
            "margin_left": args.margin_left,
            "margin_right": args.margin_right,
            "margin_top": args.margin_top,
            "margin_bottom": args.margin_bottom,
            "max_width": args.max_width,
            "max_height": args.max_height,
            "position_x": args.position_x,
            "position_y": args.position_y,
        }.items()
        if value is not None
    }
    try:
        subtitle_config = validate_subtitle_config(
            None,
            appearance_values=appearance_values,
            effects_values=effects_values,
            position=args.position,
            layout_preset=args.layout,
            relative_values=relative_values,
            anchor=args.anchor,
        )
    except ValidationError as exc:
        parser.error(str(exc))

    if args.preview_layout:
        return PreviewRequest(
            input_path=input_path,
            output_dir=output_dir,
            subtitle_config=subtitle_config,
            preview_at=args.preview_at,
            preview_text=(
                DEFAULT_PREVIEW_TEXT if args.preview_text is None else args.preview_text
            ),
            guides=args.preview_guides,
        )

    return RunRequest(
        input_path=input_path,
        output_dir=output_dir,
        language=args.lang,
        task=args.task,
        model_name=args.model,
        subtitle_config=subtitle_config,
        keep_transcriptions=args.keep_transcriptions,
    )


def _validate_translation_request(
    task: str, model_name: str, parser: argparse.ArgumentParser
) -> None:
    if task != "translate":
        return
    if model_name == "turbo":
        parser.error(
            f'Model "{model_name}" does not support translation. Use a multilingual '
            'non-Turbo model, such as "medium" or "large". Whisper translations are '
            "always generated in English."
        )
    if model_name.endswith(".en"):
        parser.error(
            f'Model "{model_name}" is English-only and cannot translate. Use a '
            'multilingual non-Turbo model, such as "medium" or "large". Whisper '
            "translations are always generated in English."
        )


def _validate_effect_request(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if args.karaoke_highlight_color is not None and not args.karaoke:
        parser.error("--karaoke-highlight-color requires --karaoke")
    if args.karaoke_mode is not None and not args.karaoke:
        parser.error("--karaoke-mode requires --karaoke")
    if args.preview_layout and (
        args.karaoke
        or args.karaoke_mode is not None
        or args.karaoke_highlight_color is not None
    ):
        parser.error("--karaoke options cannot be used with --preview-layout")
    if args.karaoke and args.task == "translate":
        parser.error(
            "--karaoke cannot be combined with --task translate because "
            "source-language word timings do not map losslessly to translated text"
        )


def _run_request(
    request: RunRequest | PreviewRequest, progress: ProgressReporter
) -> Path:
    """Run in a private directory and publish only completed user artifacts."""
    if isinstance(request, PreviewRequest):
        return _run_preview_request(request, progress)

    from .subtitler import (
        embed_subtitles,
        probe_video_geometry,
        validate_ffmpeg_support,
    )
    from .transcriber import transcribe_video, write_transcription_artifacts

    validate_ffmpeg_support()
    geometry = probe_video_geometry(request.input_path)
    resolved_subtitle_config = resolve_subtitle_config(
        request.subtitle_config, geometry
    )
    wrapping_metrics = resolve_wrapping_metrics(
        resolved_subtitle_config,
        geometry,
        language=request.language,
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
        f"{geometry.sample_aspect_ratio.denominator}, {placement_description}, "
        f"preset {resolved_subtitle_config.layout_preset.value})."
    )
    work_dir = create_work_dir(request.output_dir)
    try:
        document = transcribe_video(
            request.input_path,
            request.language,
            request.task,
            request.model_name,
            progress=progress,
        )
        json_path, srt_path, ass_path = write_transcription_artifacts(
            document,
            work_dir,
            request.subtitle_config,
            geometry=geometry,
            resolved_subtitle_config=resolved_subtitle_config,
            wrapping_metrics=wrapping_metrics,
            progress=progress,
        )
        transcripts = TranscriptionPaths(
            json_path=Path(json_path), srt_path=Path(srt_path), ass_path=Path(ass_path)
        )
        video_path = (
            work_dir
            / f"{request.input_path.stem}-{request.language}{request.input_path.suffix}"
        )
        rendered_path = Path(
            embed_subtitles(
                request.input_path,
                transcripts.ass_path,
                work_dir,
                request.language,
                output_path=video_path,
                geometry=geometry,
                fonts_dir=resolved_subtitle_config.appearance.fonts_dir,
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


def _run_preview_request(request: PreviewRequest, progress: ProgressReporter) -> Path:
    """Render a single preview frame before any transcription runtime import."""
    from .preview import build_preview_ass, resolve_preview_timestamp
    from .subtitler import (
        probe_video_geometry,
        render_subtitle_preview,
        validate_ffmpeg_support,
    )

    validate_ffmpeg_support()
    geometry = probe_video_geometry(request.input_path)
    timestamp = resolve_preview_timestamp(request.preview_at, geometry)
    resolved_config = resolve_subtitle_config(request.subtitle_config, geometry)
    wrapping_metrics = resolve_wrapping_metrics(resolved_config, geometry)
    progress(
        "Detected video layout: "
        f"{geometry.render_width}x{geometry.render_height} "
        f"(stream {geometry.stream_index}, rotation "
        f"{geometry.rotation_degrees}°, preview at {timestamp:.3f}s, "
        f"{wrapping_metrics.max_width}x{wrapping_metrics.max_height}px limits, "
        f"preset {resolved_config.layout_preset.value})."
    )
    work_dir = create_work_dir(request.output_dir)
    try:
        ass_path = work_dir / "subtitle-preview.ass"
        build_preview_ass(ass_path, request, geometry, timestamp)
        return Path(
            render_subtitle_preview(
                request.input_path,
                ass_path,
                request.output_dir,
                timestamp=timestamp,
                geometry=geometry,
                fonts_dir=resolved_config.appearance.fonts_dir,
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
    stem = f"{request.input_path.stem}-{request.language}"
    suffixes = (request.input_path.suffix, ".json", ".srt", ".ass")
    while True:
        candidate = find_unique_stem(request.output_dir, stem, suffixes)
        json_target = request.output_dir / f"{candidate}.json"
        video_target = request.output_dir / f"{candidate}{request.input_path.suffix}"
        try:
            publish_files(
                {
                    artifacts.transcripts.json_path: json_target,
                    artifacts.video_path: video_target,
                }
            )
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
