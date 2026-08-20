"""FFmpeg boundary for rendering hard ASS subtitles into a copied video."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

from .errors import ArtifactError, DependencyError, RenderingError, ValidationError
from .models import VideoGeometry
from .utils import get_unique_path

ProgressReporter = Callable[[str], None] | None
MAX_VIDEO_DIMENSION = 32_768
MAX_ASPECT_RATIO_COMPONENT = 1_000_000
FFPROBE_TIMEOUT_SECONDS = 30


def validate_ffmpeg_support() -> None:
    """Ensure FFmpeg, ffprobe, and the subtitles filter are available."""
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise DependencyError(
            "FFmpeg is not available on PATH. Install FFmpeg with "
            "libass/subtitles support."
        )
    if shutil.which("ffprobe") is None:
        raise DependencyError(
            "ffprobe is not available on PATH. Install the complete FFmpeg toolset."
        )

    try:
        completed = subprocess.run(
            [executable, "-hide_banner", "-filters"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise DependencyError(f"Could not run FFmpeg at '{executable}': {exc}") from exc

    if completed.returncode != 0:
        details = _short_output(completed.stderr or completed.stdout)
        raise DependencyError(f"FFmpeg could not list its supported filters: {details}")

    filters = f"{completed.stdout}\n{completed.stderr}"
    if not any("subtitles" in line.split() for line in filters.splitlines()):
        raise DependencyError(
            "FFmpeg does not provide the required subtitles filter; install "
            "a build with libass support."
        )


def probe_video_geometry(input_path: str | Path) -> VideoGeometry:
    """Probe and normalize the first renderable video stream.

    FFmpeg autorotation is enabled by the render graph. Consequently, right-angle
    rotation swaps the dimensions and pixel aspect ratio used to calculate the
    displayed frame geometry.
    """
    source_path = _require_file(input_path, "Input video")
    executable = shutil.which("ffprobe")
    if executable is None:
        raise DependencyError(
            "ffprobe is not available on PATH. Install the complete FFmpeg toolset."
        )

    command = [
        executable,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "stream=index,codec_type,width,height,sample_aspect_ratio:"
        "stream_tags=rotate:stream_side_data_list:"
        "stream_disposition=attached_pic:format=duration",
        str(source_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderingError(
            f"ffprobe timed out while inspecting '{source_path}'."
        ) from exc
    except OSError as exc:
        raise DependencyError(
            f"Could not run ffprobe at '{executable}': {exc}"
        ) from exc

    if completed.returncode != 0:
        details = _short_output(completed.stderr or completed.stdout)
        raise RenderingError(
            f"ffprobe could not inspect video geometry for '{source_path}': {details}"
        )
    return _parse_probe_payload(completed.stdout)


def _parse_probe_payload(payload: str) -> VideoGeometry:
    """Validate the narrow subset of ffprobe JSON used by the render policy."""
    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationError("ffprobe returned invalid JSON video metadata") from exc
    if not isinstance(decoded, Mapping):
        raise ValidationError("ffprobe returned an invalid metadata object")

    streams = decoded.get("streams")
    if not isinstance(streams, Sequence) or isinstance(streams, (str, bytes)):
        raise ValidationError("ffprobe metadata does not contain a stream list")

    candidates: list[tuple[int, Mapping[str, Any]]] = []
    for stream in streams:
        if not isinstance(stream, Mapping) or stream.get("codec_type") != "video":
            continue
        disposition = stream.get("disposition")
        if isinstance(disposition, Mapping) and disposition.get("attached_pic") == 1:
            continue
        index = _probe_integer(stream.get("index"), "video stream index", minimum=0)
        candidates.append((index, stream))

    if not candidates:
        raise ValidationError("Input media does not contain a usable video stream")
    candidates.sort(key=lambda item: item[0])
    if len({index for index, _ in candidates}) != len(candidates):
        raise ValidationError("ffprobe returned duplicate video stream indexes")

    stream_index, stream = candidates[0]
    coded_width = _probe_integer(
        stream.get("width"),
        "coded video width",
        minimum=1,
        maximum=MAX_VIDEO_DIMENSION,
    )
    coded_height = _probe_integer(
        stream.get("height"),
        "coded video height",
        minimum=1,
        maximum=MAX_VIDEO_DIMENSION,
    )
    rotation = _probe_rotation(stream)
    sample_aspect_ratio = _probe_aspect_ratio(stream.get("sample_aspect_ratio"))

    if rotation in (90, 270):
        render_width, render_height = coded_height, coded_width
        render_sample_aspect_ratio = Fraction(
            sample_aspect_ratio.denominator,
            sample_aspect_ratio.numerator,
        )
    else:
        render_width, render_height = coded_width, coded_height
        render_sample_aspect_ratio = sample_aspect_ratio

    display_aspect_ratio = Fraction(render_width, render_height) * (
        render_sample_aspect_ratio
    )
    return VideoGeometry(
        stream_index=stream_index,
        coded_width=coded_width,
        coded_height=coded_height,
        render_width=render_width,
        render_height=render_height,
        rotation_degrees=rotation,
        sample_aspect_ratio=sample_aspect_ratio,
        display_aspect_ratio=display_aspect_ratio,
        duration_seconds=_probe_duration(decoded.get("format")),
    )


def _probe_integer(
    value: object,
    label: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"ffprobe returned an invalid {label}")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(f"ffprobe returned an invalid {label}: {value}")
    return value


def _probe_rotation(stream: Mapping[str, Any]) -> int:
    rotations: set[int] = set()
    tags = stream.get("tags")
    if tags is not None and not isinstance(tags, Mapping):
        raise ValidationError("ffprobe returned invalid video tags metadata")
    if isinstance(tags, Mapping) and "rotate" in tags:
        # The legacy rotate tag uses the opposite sign convention from the
        # display-matrix rotation emitted by ffprobe.
        rotations.add(_normalise_rotation(tags["rotate"], invert=True))
    side_data = stream.get("side_data_list")
    if side_data is not None and (
        not isinstance(side_data, Sequence) or isinstance(side_data, (str, bytes))
    ):
        raise ValidationError("ffprobe returned invalid display-matrix metadata")
    if isinstance(side_data, Sequence) and not isinstance(side_data, (str, bytes)):
        for item in side_data:
            if not isinstance(item, Mapping):
                raise ValidationError(
                    "ffprobe returned invalid display-matrix metadata"
                )
            if "rotation" in item:
                rotations.add(_normalise_rotation(item["rotation"]))
    if not rotations:
        return 0
    if len(rotations) != 1:
        raise ValidationError("ffprobe returned contradictory rotation metadata")
    return rotations.pop()


def _normalise_rotation(value: object, *, invert: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValidationError("ffprobe returned invalid rotation metadata")
    try:
        rotation = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("ffprobe returned invalid rotation metadata") from exc
    if not math.isfinite(rotation) or not rotation.is_integer():
        raise ValidationError("ffprobe returned invalid rotation metadata")
    normalised = int(rotation) % 360
    if normalised not in (0, 90, 180, 270):
        raise ValidationError(
            f"Unsupported video rotation {normalised} degrees; expected a right angle"
        )
    return (-normalised) % 360 if invert else normalised


def _probe_aspect_ratio(value: object) -> Fraction:
    if value in (None, "", "N/A"):
        return Fraction(1, 1)
    if not isinstance(value, str) or value.count(":") != 1:
        raise ValidationError("ffprobe returned an invalid sample aspect ratio")
    numerator_text, denominator_text = value.split(":", maxsplit=1)
    try:
        numerator = int(numerator_text)
        denominator = int(denominator_text)
    except ValueError as exc:
        raise ValidationError(
            "ffprobe returned an invalid sample aspect ratio"
        ) from exc
    if (
        numerator <= 0
        or denominator <= 0
        or numerator > MAX_ASPECT_RATIO_COMPONENT
        or denominator > MAX_ASPECT_RATIO_COMPONENT
    ):
        raise ValidationError("ffprobe returned an invalid sample aspect ratio")
    return Fraction(numerator, denominator)


def _probe_duration(format_value: object) -> float | None:
    if format_value is None:
        return None
    if not isinstance(format_value, Mapping):
        raise ValidationError("ffprobe returned invalid container metadata")
    raw_duration = format_value.get("duration")
    if raw_duration in (None, "", "N/A"):
        return None
    if isinstance(raw_duration, bool):
        raise ValidationError("ffprobe returned an invalid container duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError) as exc:
        raise ValidationError("ffprobe returned an invalid container duration") from exc
    if not math.isfinite(duration) or duration < 0:
        raise ValidationError("ffprobe returned an invalid container duration")
    return duration


def embed_subtitles(
    input_path: str | Path,
    ass_path: str | Path,
    output_dir: str | Path,
    lang: str = "en",
    *,
    output_path: str | Path | None = None,
    geometry: VideoGeometry | None = None,
    fonts_dir: str | Path | None = None,
    progress: ProgressReporter = None,
) -> str:
    """Render an ASS subtitle file into a copied video and return its path.

    The established positional interface is unchanged. ``output_path`` is an
    internal-friendly optional override used by the CLI's private work folder.
    """
    source_path = _require_file(input_path, "Input video")
    subtitle_path = _require_file(ass_path, "ASS subtitle file")
    resolved_geometry = geometry or probe_video_geometry(source_path)
    resolved_fonts_dir = _require_directory(fonts_dir, "Fonts directory")
    destination_dir = _normalise_output_dir(output_dir)
    final_path = _choose_output_path(source_path, destination_dir, lang, output_path)
    temporary_path = _temporary_media_path(final_path)
    try:
        ffmpeg = _load_ffmpeg_python()

        _report(progress, f"Rendering subtitles into '{final_path.name}'...")
        try:
            output_stream = _build_output_stream(
                ffmpeg,
                source_path,
                subtitle_path,
                temporary_path,
                resolved_geometry,
                resolved_fonts_dir,
            )
            output_stream.run(
                overwrite_output=True, capture_stdout=True, capture_stderr=True
            )
        except ffmpeg.Error as exc:
            raise RenderingError(
                f"FFmpeg could not render subtitles into '{final_path}': "
                f"{_short_output(_error_output(exc))}"
            ) from exc
        except OSError as exc:
            raise RenderingError(
                f"FFmpeg could not render '{source_path}': {exc}"
            ) from exc

        try:
            if os.path.lexists(final_path):
                if output_path is not None:
                    raise ArtifactError(
                        f"Refusing to overwrite existing output '{final_path}'"
                    )
                final_path = Path(get_unique_path(final_path))
            os.replace(temporary_path, final_path)
        except OSError as exc:
            raise ArtifactError(
                f"Could not publish rendered video '{final_path}': {exc}"
            ) from exc

        _report(progress, "Subtitle video rendered successfully.")
        return str(final_path)
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def _require_file(path: str | Path, label: str) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    if not candidate.exists() or not candidate.is_file():
        raise ValidationError(f"{label} not found at '{path}'")
    return candidate


def _require_directory(path: str | Path | None, label: str) -> Path | None:
    if path is None:
        return None
    candidate = Path(path).expanduser().resolve(strict=False)
    if not candidate.exists() or not candidate.is_dir():
        raise ValidationError(f"{label} not found at '{path}'")
    return candidate


def _normalise_output_dir(output_dir: str | Path) -> Path:
    destination = Path(output_dir).expanduser().resolve(strict=False)
    if destination.exists() and not destination.is_dir():
        raise ValidationError(
            f"Output path '{output_dir}' is a file; provide a directory instead"
        )
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArtifactError(
            f"Could not create output directory '{destination}': {exc}"
        ) from exc
    return destination


def _choose_output_path(
    source_path: Path,
    output_dir: Path,
    lang: str,
    output_path: str | Path | None,
) -> Path:
    if output_path is not None:
        candidate = Path(output_path).expanduser().resolve(strict=False)
        if candidate.parent != output_dir:
            raise ValidationError("Explicit output_path must be inside output_dir")
        return candidate
    return Path(
        get_unique_path(output_dir / f"{source_path.stem}-{lang}{source_path.suffix}")
    )


def _temporary_media_path(final_path: Path) -> Path:
    descriptor: int | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{final_path.stem}.",
            suffix=final_path.suffix,
            dir=final_path.parent,
        )
        return Path(name)
    except OSError as exc:
        raise ArtifactError(
            f"Could not create temporary video near '{final_path}': {exc}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _load_ffmpeg_python() -> Any:
    try:
        import ffmpeg
    except ImportError as exc:
        raise DependencyError("ffmpeg-python is required to render subtitles") from exc
    return ffmpeg


def _build_output_stream(
    ffmpeg: Any,
    input_path: Path,
    ass_path: Path,
    output_path: Path,
    geometry: VideoGeometry,
    fonts_dir: Path | None = None,
) -> Any:
    """Build an autorotated graph using the stream and canvas selected by probe."""
    input_stream = ffmpeg.input(str(input_path), autorotate=1)
    filter_options = {
        "filename": str(ass_path),
        "original_size": geometry.original_size,
    }
    if fonts_dir is not None:
        filter_options["fontsdir"] = str(fonts_dir)
    video_stream = input_stream[str(geometry.stream_index)].filter(
        "subtitles", **filter_options
    )
    audio_stream = input_stream["a?"]
    return ffmpeg.output(video_stream, audio_stream, str(output_path), acodec="copy")


def _error_output(error: Any) -> str:
    stderr = getattr(error, "stderr", None)
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", errors="replace")
    if isinstance(stderr, str):
        return stderr
    return str(error)


def _short_output(output: str, limit: int = 1_000) -> str:
    compact = " ".join(output.split())
    if not compact:
        return "no diagnostic output"
    if len(compact) <= limit:
        return compact
    separator = " ... "
    if limit <= len(separator):
        return compact[:limit]
    head_length = (limit - len(separator)) // 2
    tail_length = limit - len(separator) - head_length
    return f"{compact[:head_length]}{separator}{compact[-tail_length:]}"


def _report(progress: ProgressReporter, message: str) -> None:
    if progress is not None:
        progress(message)
