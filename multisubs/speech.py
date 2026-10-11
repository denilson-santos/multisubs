"""Public source-transcript interchange and ASR-free rendering."""

from __future__ import annotations

import math
import re
import shutil
import warnings
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .models import SubtitleConfig
from .timed_cues import GeneratedSubtitleArtifacts

_LANGUAGE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z", re.ASCII)
_FIELDS = {
    "format",
    "schema_version",
    "language",
    "task",
    "asr_backend",
    "model_name",
    "full_text",
    "segments",
}


@dataclass(frozen=True)
class SpeechTranscript:
    """Source ASR segments before semantic cue selection or visual layout.

    Segment and word mappings retain their source text, optional fields, and
    observed timestamps. Use to_dict() for a detached editable JSON value.
    """

    language: str | None
    task: str
    asr_backend: str
    model_name: str
    full_text: str
    segments: tuple[Mapping[str, Any], ...]

    @property
    def duration(self) -> float:
        """Latest observed segment end, including leading silence."""
        return max((float(segment["end"]) for segment in self.segments), default=0.0)

    def to_dict(self) -> dict[str, Any]:
        """Return lossless, detached format-1 data for caching or time edits."""
        return {
            "format": "multisubs-speech",
            "schema_version": 1,
            "language": self.language,
            "task": self.task,
            "asr_backend": self.asr_backend,
            "model_name": self.model_name,
            "full_text": self.full_text,
            "segments": deepcopy([dict(segment) for segment in self.segments]),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SpeechTranscript:
        """Validate format-1 data, preserving absent and null word fields.

        Inputs are bounded to 20,000 segments, 100,000 words, 1,000,000 text
        characters, nesting depth 16, and finite times in [0, 86,400]. Word
        overlap is allowed; source mapping chooses the normal safe fallback.
        """
        _validate_json_value(value)
        if not isinstance(value, Mapping) or set(value) != _FIELDS:
            raise ValidationError("Speech transcript has missing or unknown fields")
        if (
            value["format"] != "multisubs-speech"
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
        ):
            raise ValidationError("Expected multisubs-speech schema_version 1")
        language = value["language"]
        if language is not None and (
            not isinstance(language, str)
            or len(language) > 35
            or not _LANGUAGE.fullmatch(language)
        ):
            raise ValidationError("Speech transcript language must be a tag or null")
        if value["task"] != "transcribe":
            raise ValidationError("Speech transcripts support only task='transcribe'")
        for name in ("asr_backend", "model_name"):
            if not isinstance(value[name], str) or not value[name].strip():
                raise ValidationError(f"Speech transcript {name} must be text")
        if not isinstance(value["full_text"], str):
            raise ValidationError("Speech transcript full_text must be text")
        segments = value["segments"]
        if not isinstance(segments, (list, tuple)) or len(segments) > 20_000:
            raise ValidationError("Speech transcript requires at most 20,000 segments")
        previous_start = -1.0
        word_count = 0
        for index, segment in enumerate(segments):
            label = f"segment {index}"
            if not isinstance(segment, Mapping) or not isinstance(
                segment.get("text"), str
            ):
                raise ValidationError(f"{label} must contain source text")
            start = _time(segment.get("start"), f"{label}.start")
            end = _time(segment.get("end"), f"{label}.end")
            if end < start or start < previous_start:
                raise ValidationError(f"{label} has invalid or unordered times")
            previous_start = start
            words = segment.get("words", [])
            if words is None:
                words = []
            if not isinstance(words, (list, tuple)):
                raise ValidationError(f"{label}.words must be an array when present")
            word_count += len(words)
            if word_count > 100_000:
                raise ValidationError("Speech transcript exceeds 100,000 words")
            for word_index, word in enumerate(words):
                word_label = f"{label}.words[{word_index}]"
                if not isinstance(word, Mapping) or not isinstance(
                    word.get("word"), str
                ):
                    raise ValidationError(f"{word_label} must contain word text")
                times = {
                    name: _time(word[name], f"{word_label}.{name}")
                    for name in ("start", "end")
                    if word.get(name) is not None
                }
                if len(times) == 2 and times["end"] < times["start"]:
                    raise ValidationError(f"{word_label} has reversed times")
        return cls(
            language=language,
            task=value["task"],
            asr_backend=value["asr_backend"],
            model_name=value["model_name"],
            full_text=value["full_text"],
            segments=tuple(deepcopy(dict(segment)) for segment in segments),
        )


def _time(value: Any, label: str) -> float:
    if (
        type(value) not in (int, float)
        or not 0 <= value <= 86_400
        or not math.isfinite(value)
    ):
        raise ValidationError(f"{label} must be finite seconds from 0 to 86,400")
    return float(value)


def _validate_json_value(value: Any) -> None:
    pending = [(value, 0)]
    characters = 0
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 16 or nodes > 1_000_000:
            raise ValidationError("Speech transcript exceeds nesting or size limits")
        if isinstance(item, str):
            characters += len(item)
            if characters > 1_000_000:
                raise ValidationError("Speech transcript exceeds text size limit")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in item):
                raise ValidationError("Speech transcript contains invalid Unicode")
        elif isinstance(item, Mapping):
            if len(item) > 1_000_000:
                raise ValidationError("Speech transcript exceeds size limits")
            if not all(isinstance(key, str) for key in item):
                raise ValidationError("Speech transcript keys must be strings")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, (list, tuple)):
            if len(item) > 1_000_000:
                raise ValidationError("Speech transcript exceeds size limits")
            pending.extend((child, depth + 1) for child in item)
        elif item is None or isinstance(item, bool):
            continue
        elif type(item) not in (int, float) or (
            isinstance(item, float) and not math.isfinite(item)
        ):
            raise ValidationError("Speech transcript must contain finite JSON values")


def render_transcript(
    transcript: SpeechTranscript | Mapping[str, Any],
    video_path: str | Path,
    output_dir: str | Path,
    *,
    template: str | None = None,
    template_dir: str | Path | None = None,
    subtitle_config: SubtitleConfig | None = None,
    progress: Callable[[str], None] | None = None,
) -> GeneratedSubtitleArtifacts:
    """Render source speech data on a final video without calling an ASR.

    Accept a SpeechTranscript or its to_dict() result, with times already local
    to the video. Select a template or supply a complete typed subtitle_config.
    Return collision-safe SRT, ASS, and video paths after successful rendering.
    Only task='transcribe' is supported. Missing alignment uses native coarse
    timing and explicitly reports any suppressed word effects through progress.
    """
    document = SpeechTranscript.from_dict(
        transcript.to_dict() if isinstance(transcript, SpeechTranscript) else transcript
    )

    def report(message: str) -> None:
        if message.startswith("Warning:"):
            message = message.split("; inspect retained", 1)[0] + "."
        if progress is not None:
            progress(message)
        elif message.startswith("Warning:"):
            warnings.warn(message, UserWarning, stacklevel=3)

    if subtitle_config is not None and (
        template is not None or template_dir is not None
    ):
        raise ValidationError("Use a template or subtitle_config, not both")
    from .config import validate_subtitle_config
    from .custom_templates import resolve_subtitle_template
    from .font_catalog import bundled_font_directory
    from .layout import resolve_subtitle_config, resolve_wrapping_metrics
    from .models import TranscriptDocument
    from .subtitler import (
        embed_subtitles,
        probe_video_geometry,
        validate_ffmpeg_support,
    )
    from .transcriber import _build_subtitle_segments, write_transcription_artifacts
    from .utils import (
        create_work_dir,
        find_unique_stem,
        publish_files,
        with_language_suffix,
    )
    from .wrapping import transform_display_text

    selected = resolve_subtitle_template(template, template_dir)
    config = validate_subtitle_config(subtitle_config or selected.template.config)
    source = Path(video_path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise ValidationError(f"Video file not found at '{video_path}'")
    destination = Path(output_dir).expanduser().resolve(strict=False)
    if destination.exists() and not destination.is_dir():
        raise ValidationError(f"Output path '{output_dir}' is a file")
    validate_ffmpeg_support()
    geometry = probe_video_geometry(source)
    native = TranscriptDocument(
        source_path=source,
        language=document.language,
        task=document.task,
        model_name=document.model_name,
        full_text=document.full_text,
        segments=tuple(
            _build_subtitle_segments(document.segments, language=document.language)
        ),
        asr_backend=document.asr_backend,
    )
    with bundled_font_directory(config.style.typography.font) as fonts:
        resolved = resolve_subtitle_config(config, geometry, bundled_fonts_dir=fonts)
        metrics = resolve_wrapping_metrics(
            resolved,
            geometry,
            language=document.language,
            sample_text=[
                transform_display_text(
                    segment["text"], resolved.style.typography.text_case
                )
                for segment in native.segments
            ],
            verify_font_coverage=True,
            bundled_fonts_dir=fonts,
        )
        work_dir = create_work_dir(destination)
        try:
            _, srt, ass = write_transcription_artifacts(
                native,
                work_dir,
                config,
                geometry=geometry,
                resolved_subtitle_config=resolved,
                wrapping_metrics=metrics,
                template_requested=template,
                template_resolved=selected.template.name,
                template_source=selected.source,
                template_base=selected.base,
                progress=report,
            )
            video = work_dir / f"video{source.suffix}"
            embed_subtitles(
                source,
                ass,
                work_dir,
                document.language,
                output_path=video,
                geometry=geometry,
                fonts_dir=metrics.text_measurer.info.renderer_fonts_dir,
                progress=progress,
            )
            stem = with_language_suffix(source.stem, document.language)
            while True:
                chosen = find_unique_stem(
                    destination, stem, (".srt", ".ass", source.suffix)
                )
                artifacts = GeneratedSubtitleArtifacts(
                    destination / f"{chosen}.srt",
                    destination / f"{chosen}.ass",
                    destination / f"{chosen}{source.suffix}",
                )
                try:
                    publish_files(
                        {
                            Path(srt): artifacts.srt_path,
                            Path(ass): artifacts.ass_path,
                            video: artifacts.video_path,
                        }
                    )
                except FileExistsError:
                    continue
                return artifacts
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
