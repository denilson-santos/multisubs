"""Replay retained schema-3 subtitles locally without importing speech models.

Run from a source checkout with ``python -m scripts.replay_subtitle_layout``.
The selected current template is explicit; saved rendering metadata is evidence,
not a configuration importer. Input files are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from collections.abc import Mapping
from dataclasses import asdict
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from multisubs.config import SUPPORTED_LANGUAGES, validate_subtitle_config
from multisubs.errors import MultisubsError, ValidationError
from multisubs.font_catalog import bundled_font_directory
from multisubs.models import TranscriptDocument, VideoGeometry
from multisubs.subtitler import embed_subtitles, probe_video_geometry
from multisubs.templates import get_subtitle_template
from multisubs.transcriber import write_transcription_artifacts
from multisubs.utils import get_unique_dir_path

MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 100_000
MAX_TEXT = 1_000_000
MAX_DURATION = 3600.0
FIDELITY = (
    "Replay uses retained, already-filtered segments and original saved times. "
    "It cannot recover discarded ASR text, punctuation, or boundaries. "
    "The selected current template is not a reconstruction of saved settings."
)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    return value


def _time(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("Replay times must be finite non-negative numbers")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValidationError("Replay time exceeds the supported range") from exc
    if not math.isfinite(result) or not 0 <= result <= MAX_DURATION:
        raise ValidationError("Replay times must be between 0 and 3600 seconds")
    return result


def load_transcript(path: Path) -> tuple[TranscriptDocument, dict[str, Any], str]:
    """Validate bounded retained data without following embedded file paths."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValidationError("Replay JSON exceeds the 16 MiB limit")
    try:
        payload = _object(json.loads(raw), "Replay JSON")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValidationError("Replay JSON is malformed") from exc
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 3:
        raise ValidationError("Replay requires retained JSON schema version 3")
    metadata = _object(payload.get("metadata"), "metadata")
    transcription = _object(payload.get("transcription"), "transcription")
    language, task = metadata.get("language"), metadata.get("task")
    if (
        not isinstance(language, str)
        or language not in SUPPORTED_LANGUAGES
        or not isinstance(task, str)
        or task not in {"transcribe", "translate"}
    ):
        raise ValidationError("Replay language or task is unsupported")
    full_text = transcription.get("text")
    segments = transcription.get("segments")
    if not isinstance(full_text, str) or not isinstance(segments, list):
        raise ValidationError("Replay requires text and a segment array")
    if not 1 <= len(segments) <= 20_000:
        raise ValidationError("Replay requires 1 through 20000 segments")
    characters, records, previous_start = len(full_text), 0, 0.0
    clean_segments: list[dict[str, Any]] = []
    for value in segments:
        segment = _object(value, "segment")
        start, end = _time(segment.get("start")), _time(segment.get("end"))
        text, words = segment.get("text"), segment.get("words", [])
        if start < previous_start or end < start:
            raise ValidationError("Replay segments must have ordered valid times")
        previous_start = start
        if not isinstance(text, str) or not isinstance(words, list):
            raise ValidationError("Each replay segment needs text and a word array")
        characters += len(text)
        records += len(words)
        last_word_start = start
        for value in words:
            word = _object(value, "word")
            if not isinstance(word.get("word"), str):
                raise ValidationError("Replay word text must be a string")
            characters += len(word["word"])
            # Missing alignment times are retained for the production fallback.
            for key in ("start", "end"):
                if word.get(key) is not None:
                    _time(word[key])
            if word.get("start") is not None and word.get("end") is not None:
                word_start, word_end = _time(word["start"]), _time(word["end"])
                if not last_word_start <= word_start <= word_end <= end:
                    raise ValidationError("Replay word times are outside their segment")
                last_word_start = word_start
        if records > MAX_RECORDS or characters > MAX_TEXT:
            raise ValidationError("Replay exceeds its word or text budget")
        # Do not accept serialized private compiler keys or user-supplied paths.
        clean_segments.append(
            {"text": text, "start": start, "end": end, "words": words}
        )
    document = TranscriptDocument(
        source_path=Path("replay.mp4"),
        language=language,
        task=task,
        model_name=str(metadata.get("model", "unknown")),
        full_text=full_text,
        segments=tuple(clean_segments),
    )
    return document, metadata, hashlib.sha256(raw).hexdigest()


def _geometry(
    metadata: Mapping[str, Any], document: TranscriptDocument
) -> VideoGeometry:
    rendering = _object(metadata.get("rendering"), "metadata.rendering")
    width, height = rendering.get("render_width"), rendering.get("render_height")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or not 1 <= width <= 4096
        or not 1 <= height <= 4096
    ):
        raise ValidationError(
            "Replay canvas dimensions must be integers from 1 to 4096"
        )
    duration = max(float(segment["end"]) for segment in document.segments)
    return VideoGeometry(
        0,
        width,
        height,
        width,
        height,
        0,
        Fraction(1),
        Fraction(width, height),
        max(duration, 0.1),
    )


def _command_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = result.stdout.splitlines()
    return lines[0][:300] if result.returncode == 0 and lines else None


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def replay(
    transcript: Path,
    output_dir: Path,
    *,
    template: str = "amber-word",
    font: str | None = None,
    render: bool = False,
    uncaptioned_video: Path | None = None,
) -> Path:
    """Publish diagnostic artifacts into a fresh directory, preserving failures."""
    document, metadata, digest = load_transcript(transcript)
    selected = get_subtitle_template(template)
    config = validate_subtitle_config(
        None,
        defaults=selected.config,
        position="center",
        appearance_values={"font": font} if font else None,
    )
    geometry = _geometry(metadata, document)
    if uncaptioned_video is not None:
        if not render:
            raise ValidationError("--uncaptioned-video requires --render")
        geometry = probe_video_geometry(uncaptioned_video)
        if geometry.duration_seconds is not None and geometry.duration_seconds < max(
            float(s["end"]) for s in document.segments
        ):
            raise ValidationError(
                "Uncaptioned video is shorter than the retained timeline"
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    while True:
        destination = Path(get_unique_dir_path(output_dir / "subtitle-replay"))
        try:
            destination.mkdir()
            break
        except FileExistsError:
            continue
    with bundled_font_directory(config.style.typography.font) as fonts_dir:
        artifacts = write_transcription_artifacts(
            document,
            destination,
            config,
            geometry=geometry,
            template_requested=template,
            template_resolved=selected.name,
        )
        font_hashes = (
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(fonts_dir.glob("*.ttf"))
            }
            if fonts_dir
            else {}
        )
        evidence = {
            "fidelity": FIDELITY,
            "source_sha256": digest,
            "base_sha": _command_version(["git", "rev-parse", "HEAD"]),
            "python": platform.python_version(),
            "packages": {p: _package_version(p) for p in ("Pillow", "whisperx")},
            "ffmpeg": _command_version(["ffmpeg", "-version"]),
            "template": template,
            "font_override": font,
            "geometry": {k: str(v) for k, v in asdict(geometry).items()},
            "bundled_font_sha256": font_hashes,
            "artifacts_sha256": {
                Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                for p in artifacts
            },
            "render_status": "pending" if render else "not-requested",
        }
        manifest = destination / "evidence.json"
        manifest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        if render:
            background = uncaptioned_video
            if background is None:
                # Developer fixture generation only; production filtering stays
                # inside embed_subtitles/subtitler.py.
                background = destination / "synthetic-background.mp4"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=white:s={geometry.render_width}x{geometry.render_height}:r=30",
                        "-t",
                        str(geometry.duration_seconds),
                        "-an",
                        "-c:v",
                        "mpeg4",
                        str(background),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
            video = embed_subtitles(
                background,
                artifacts[2],
                destination,
                document.language,
                geometry=geometry,
                fonts_dir=fonts_dir,
            )
            evidence["render_status"] = "complete"
            evidence["video_sha256"] = hashlib.sha256(
                Path(video).read_bytes()
            ).hexdigest()
            manifest.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
            )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--template", default="amber-word")
    parser.add_argument("--font")
    parser.add_argument("--render", action="store_true")
    parser.add_argument(
        "--uncaptioned-video",
        type=Path,
        help="Explicit original input; must have no burned-in subtitles",
    )
    args = parser.parse_args(argv)
    try:
        destination = replay(
            args.transcript,
            args.output_dir,
            template=args.template,
            font=args.font,
            render=args.render,
            uncaptioned_video=args.uncaptioned_video,
        )
    except (MultisubsError, OSError, subprocess.SubprocessError) as exc:
        # Subprocess stderr may include local text/paths; do not print it here.
        print(f"Replay failed ({type(exc).__name__}); input files were preserved.")
        return 1
    print(FIDELITY)
    print(f"Replay artifacts: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
