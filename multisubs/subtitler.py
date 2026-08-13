"""FFmpeg boundary for rendering hard ASS subtitles into a copied video."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import ArtifactError, DependencyError, RenderingError, ValidationError
from .utils import get_unique_path

ProgressReporter = Callable[[str], None] | None


def validate_ffmpeg_support() -> None:
    """Ensure FFmpeg and its ``subtitles`` filter are available before work starts."""
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise DependencyError(
            "FFmpeg is not available on PATH. Install FFmpeg with "
            "libass/subtitles support."
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


def embed_subtitles(
    input_path: str | Path,
    ass_path: str | Path,
    output_dir: str | Path,
    lang: str = "en",
    *,
    output_path: str | Path | None = None,
    progress: ProgressReporter = None,
) -> str:
    """Render an ASS subtitle file into a copied video and return its path.

    The established positional interface is unchanged. ``output_path`` is an
    internal-friendly optional override used by the CLI's private work folder.
    """
    source_path = _require_file(input_path, "Input video")
    subtitle_path = _require_file(ass_path, "ASS subtitle file")
    destination_dir = _normalise_output_dir(output_dir)
    final_path = _choose_output_path(source_path, destination_dir, lang, output_path)
    temporary_path = _temporary_media_path(final_path)
    ffmpeg = _load_ffmpeg_python()

    _report(progress, f"Rendering subtitles into '{final_path.name}'...")
    try:
        output_stream = _build_output_stream(
            ffmpeg, source_path, subtitle_path, temporary_path
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
        raise RenderingError(f"FFmpeg could not render '{source_path}': {exc}") from exc

    try:
        if final_path.exists():
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
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass

    _report(progress, "Subtitle video rendered successfully.")
    return str(final_path)


def _require_file(path: str | Path, label: str) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    if not candidate.exists() or not candidate.is_file():
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
) -> Any:
    """Build a mapped graph using structured filter arguments for safe escaping."""
    input_stream = ffmpeg.input(str(input_path))
    video_stream = input_stream.video.filter("subtitles", filename=str(ass_path))
    return ffmpeg.output(
        video_stream, input_stream.audio, str(output_path), acodec="copy"
    )


def _error_output(error: Any) -> str:
    stderr = getattr(error, "stderr", None)
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", errors="replace")
    if isinstance(stderr, str):
        return stderr
    return str(error)


def _short_output(output: str, limit: int = 1_000) -> str:
    compact = " ".join(output.split())
    return compact[:limit] if compact else "no diagnostic output"


def _report(progress: ProgressReporter, message: str) -> None:
    if progress is not None:
        progress(message)
