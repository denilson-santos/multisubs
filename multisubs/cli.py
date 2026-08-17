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
    DEFAULT_STYLE,
    LAYOUT_PRESET_CHOICES,
    LAYOUT_PRESETS,
    MODELS,
    POSITION_CHOICES,
    SUPPORTED_LANGUAGES,
    parse_relative_length,
    parse_style_option,
    validate_subtitle_config,
)
from .errors import ArtifactError, MultisubsError, ValidationError
from .layout import resolve_subtitle_config
from .models import RelativeLength, RunArtifacts, RunRequest, TranscriptionPaths
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
            "Override the preset's semantic position; left and right refer to "
            "physical screen directions."
        ),
    )

    relative_group = parser.add_argument_group(
        "Relative layout units",
        "Use percentages or pixels; bare numbers are not accepted.",
    )
    for option, help_text in (
        (
            "--font-size",
            "Font size as a percentage of the shorter render edge or pixels.",
        ),
        (
            "--backdrop-size",
            "Backdrop/outline size as a percentage of the resolved font size "
            "or pixels.",
        ),
        (
            "--shadow-size",
            "Shadow size as a percentage of the resolved font size or pixels.",
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
    ):
        relative_group.add_argument(
            option,
            type=_relative_length_argument_type,
            default=None,
            metavar="LENGTH",
            help=help_text,
        )

    style_group = parser.add_argument_group(
        "Styling",
        "ASS style overrides. Colors use &H followed by 6 or 8 hexadecimal digits.",
    )
    for key, value in DEFAULT_STYLE.items():
        style_group.add_argument(
            f"--style-{key.replace('_', '-')}",
            type=_style_argument_type(key),
            default=None,
            metavar=key.upper(),
            help=f"Default: {value}",
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

    if request.keep_transcriptions:
        print(f"Files saved in: {result_path}")
    else:
        print(f"File saved in: {result_path}")
    return 0


def _style_argument_type(key: str) -> Callable[[str], str | int]:
    def parse(raw_value: str) -> str | int:
        try:
            return parse_style_option(key, raw_value)
        except (ValidationError, ValueError) as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc

    return parse


def _relative_length_argument_type(raw_value: str) -> RelativeLength:
    try:
        return parse_relative_length(raw_value)
    except ValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _build_request(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> RunRequest:
    _validate_translation_request(args.task, args.model, parser)
    input_path = Path(args.input_path).expanduser().resolve(strict=False)
    if not input_path.exists() or not input_path.is_file():
        parser.error(f"Video file not found at '{args.input_path}'")

    output_dir = Path(args.output_dir).expanduser().resolve(strict=False)
    if output_dir.exists() and not output_dir.is_dir():
        parser.error(
            f"Output path '{args.output_dir}' is a file; provide a directory instead"
        )

    style_options = {
        key: value
        for key in DEFAULT_STYLE
        if (value := getattr(args, f"style_{key}")) is not None
    }
    relative_values = {
        key: value
        for key, value in {
            "font_size": args.font_size,
            "outline_weight": args.backdrop_size,
            "shadow_weight": args.shadow_size,
            "margin_left": args.margin_left,
            "margin_right": args.margin_right,
            "margin_top": args.margin_top,
            "margin_bottom": args.margin_bottom,
        }.items()
        if value is not None
    }
    try:
        subtitle_config = validate_subtitle_config(
            style_options,
            position=args.position,
            layout_preset=args.layout,
            relative_values=relative_values,
        )
    except ValidationError as exc:
        parser.error(str(exc))

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


def _run_request(request: RunRequest, progress: ProgressReporter) -> Path:
    """Run in a private directory and publish only completed user artifacts."""
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
    progress(
        "Detected video layout: "
        f"{geometry.render_width}x{geometry.render_height} "
        f"(stream {geometry.stream_index}, rotation "
        f"{geometry.rotation_degrees}°, SAR "
        f"{geometry.sample_aspect_ratio.numerator}:"
        f"{geometry.sample_aspect_ratio.denominator}, position "
        f"{resolved_subtitle_config.layout.position.value}, preset "
        f"{resolved_subtitle_config.layout_preset.value})."
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
