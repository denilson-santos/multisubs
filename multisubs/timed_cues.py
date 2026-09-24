"""Strict public timed-cue input and ASR-free subtitle generation."""

from __future__ import annotations

import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ass import write_ass
from .config import validate_subtitle_config
from .errors import ValidationError
from .font_catalog import bundled_font_directory
from .layout import resolve_subtitle_config, resolve_wrapping_metrics
from .models import SubtitleConfig
from .subtitle_artifacts import write_srt
from .text_segmentation import (
    LinguisticSegmenter,
    build_source_text_map,
    display_units_for_records,
    grapheme_boundaries,
)
from .transcriber import prepare_karaoke_cues
from .utils import create_work_dir, find_unique_stem, publish_files
from .wrapping import render_display_units, transform_display_text

MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 16
MAX_CUES = 20_000
MAX_WORDS = 100_000
MAX_TEXT_CHARACTERS = 1_000_000
MAX_TIME_SECONDS = 86_400
_LANGUAGE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z", re.ASCII)


@dataclass(frozen=True)
class TimedWord:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TimedCue:
    start: float
    end: float
    text: str
    words: tuple[TimedWord, ...]


@dataclass(frozen=True)
class TimedCueDocument:
    language: str
    cues: tuple[TimedCue, ...]


@dataclass(frozen=True)
class GeneratedSubtitleArtifacts:
    srt_path: Path
    ass_path: Path
    video_path: Path


def load_timed_cues(path: str | Path) -> TimedCueDocument:
    """Read and validate the bounded, versioned public cue document."""
    source = Path(path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise ValidationError(f"Timed-cue JSON file not found at '{path}'")
    try:
        with source.open("rb") as stream:
            payload = stream.read(MAX_JSON_BYTES + 1)
    except OSError as exc:
        raise ValidationError(
            f"Could not read timed-cue JSON file '{path}': {exc}"
        ) from exc
    if len(payload) > MAX_JSON_BYTES:
        raise ValidationError("Timed-cue JSON exceeds the 16 MiB limit")
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as exc:
        raise ValidationError("Timed-cue file must contain valid UTF-8 JSON") from exc
    _check_depth(decoded)
    _keys(decoded, {"schema_version", "language", "cues"}, "document")
    if type(decoded["schema_version"]) is not int or decoded["schema_version"] != 1:
        raise ValidationError("Timed-cue schema_version must be the integer 1")
    language = decoded["language"]
    if (
        not isinstance(language, str)
        or len(language) > 35
        or not _LANGUAGE.fullmatch(language)
    ):
        raise ValidationError("Timed-cue language must be a valid language tag")
    raw_cues = decoded["cues"]
    if not isinstance(raw_cues, list) or not raw_cues or len(raw_cues) > MAX_CUES:
        raise ValidationError("Timed-cue cues must contain 1 to 20,000 entries")
    cues: list[TimedCue] = []
    total_words = 0
    total_characters = 0
    previous_start = -1.0
    for cue_index, raw_cue in enumerate(raw_cues):
        label = f"cue {cue_index}"
        _keys(raw_cue, {"start", "end", "text", "words"}, label)
        start = _time(raw_cue["start"], f"{label}.start")
        end = _time(raw_cue["end"], f"{label}.end")
        if end <= start or start < previous_start:
            raise ValidationError(f"{label} must have increasing, chronological times")
        if round(start * 100) >= round(end * 100):
            raise ValidationError(
                f"{label} is too short for the ASS centisecond timeline"
            )
        previous_start = start
        cue_text = _text(raw_cue["text"], f"{label}.text")
        total_characters += len(cue_text)
        _check_text_budget(total_characters)
        raw_words = raw_cue["words"]
        if not isinstance(raw_words, list) or not raw_words:
            raise ValidationError(f"{label}.words must be a nonempty array")
        total_words += len(raw_words)
        if total_words > MAX_WORDS:
            raise ValidationError("Timed-cue document exceeds 100,000 words")
        words: list[TimedWord] = []
        cursor = 0
        previous_end = start
        boundaries = set(grapheme_boundaries(cue_text))
        for word_index, raw_word in enumerate(raw_words):
            word_label = f"{label}.words[{word_index}]"
            _keys(raw_word, {"start", "end", "text"}, word_label)
            word_start = _time(raw_word["start"], f"{word_label}.start")
            word_end = _time(raw_word["end"], f"{word_label}.end")
            if word_start < previous_end or word_end <= word_start or word_end > end:
                raise ValidationError(f"{word_label} has invalid or overlapping times")
            previous_end = word_end
            word_text = _text(raw_word["text"], f"{word_label}.text")
            total_characters += len(word_text)
            _check_text_budget(total_characters)
            while cursor < len(cue_text) and cue_text[cursor].isspace():
                cursor += 1
            word_finish = cursor + len(word_text)
            if (
                not cue_text.startswith(word_text, cursor)
                or cursor not in boundaries
                or word_finish not in boundaries
            ):
                raise ValidationError(
                    f"{word_label}.text does not map exactly to cue text"
                )
            cursor = word_finish
            words.append(TimedWord(word_start, word_end, word_text))
        if cue_text[cursor:].strip():
            raise ValidationError(f"{label}.text has text outside its timed words")
        cues.append(TimedCue(start, end, cue_text, tuple(words)))
    return TimedCueDocument(language, tuple(cues))


def generate_subtitles_from_json(
    cues_json_path: str | Path,
    video_path: str | Path,
    output_dir: str | Path,
    *,
    subtitle_config: SubtitleConfig | None = None,
) -> GeneratedSubtitleArtifacts:
    """Generate SRT/ASS from known times, then burn that ASS into a video."""
    document = load_timed_cues(cues_json_path)
    source = Path(video_path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise ValidationError(f"Video file not found at '{video_path}'")
    destination = Path(output_dir).expanduser().resolve(strict=False)
    if destination.exists() and not destination.is_dir():
        raise ValidationError(f"Output path '{output_dir}' is a file")
    config = validate_subtitle_config(subtitle_config)
    from .subtitler import (
        embed_subtitles,
        probe_video_geometry,
        validate_ffmpeg_support,
    )

    validate_ffmpeg_support()
    geometry = probe_video_geometry(source)
    if geometry.duration_seconds is not None:
        for index, cue in enumerate(document.cues):
            if cue.end > geometry.duration_seconds:
                raise ValidationError(f"cue {index} ends after the video duration")
    with bundled_font_directory(config.style.typography.font) as bundled_fonts_dir:
        resolved = resolve_subtitle_config(
            config, geometry, bundled_fonts_dir=bundled_fonts_dir
        )
        metrics = resolve_wrapping_metrics(
            resolved,
            geometry,
            language=document.language.split("-", 1)[0].lower(),
            sample_text=[
                transform_display_text(cue.text, resolved.style.typography.text_case)
                for cue in document.cues
            ],
            verify_font_coverage=True,
            bundled_fonts_dir=bundled_fonts_dir,
        )
        display_cues = _layout_cues(document, resolved, metrics)
        display_cues, _ = prepare_karaoke_cues(display_cues, resolved)
        work_dir = create_work_dir(destination)
        try:
            private_srt = work_dir / "subtitles.srt"
            private_ass = work_dir / "subtitles.ass"
            private_video = work_dir / f"video{source.suffix}"
            write_srt(private_srt, display_cues)
            write_ass(
                private_ass, display_cues, resolved, geometry, wrapping_metrics=metrics
            )
            embed_subtitles(
                source,
                private_ass,
                work_dir,
                lang=None,
                output_path=private_video,
                geometry=geometry,
                fonts_dir=metrics.text_measurer.info.renderer_fonts_dir,
            )
            language_suffix = document.language.lower()
            stem = f"{source.stem}-{language_suffix}"
            suffixes = (".srt", ".ass", source.suffix)
            while True:
                chosen = find_unique_stem(destination, stem, suffixes)
                result = GeneratedSubtitleArtifacts(
                    destination / f"{chosen}.srt",
                    destination / f"{chosen}.ass",
                    destination / f"{chosen}{source.suffix}",
                )
                try:
                    publish_files(
                        {
                            private_srt: result.srt_path,
                            private_ass: result.ass_path,
                            private_video: result.video_path,
                        }
                    )
                except FileExistsError:
                    continue
                return result
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


def _layout_cues(
    document: TimedCueDocument, config: SubtitleConfig, metrics: Any
) -> list[dict[str, Any]]:
    display_cues: list[dict[str, Any]] = []
    with LinguisticSegmenter() as segmenter:
        for index, cue in enumerate(document.cues):
            words = [
                {"start": word.start, "end": word.end, "word": word.text}
                for word in cue.words
            ]
            source_map = build_source_text_map(
                cue.text, words, source_segment_index=index
            )
            if not source_map.complete or not source_map.timing_complete:
                raise ValidationError(f"cue {index} has an incomplete word mapping")
            indexes = tuple(range(len(words)))
            units = display_units_for_records(
                source_map,
                indexes,
                transform=lambda value: transform_display_text(
                    value, config.style.typography.text_case
                ),
            )
            groups = segmenter.group_source_map(
                source_map, words, language=document.language.split("-", 1)[0].lower()
            )
            try:
                display_text, fragments, line_breaks = render_display_units(
                    units,
                    metrics,
                    word_indexes={word_index: word_index for word_index in indexes},
                    display_groups=groups,
                    require_fit=True,
                )
            except ValidationError as exc:
                raise ValidationError(
                    f"cue {index} exceeds the subtitle layout envelope: {exc}"
                ) from exc
            display_cues.append(
                {
                    "id": index,
                    "start": cue.start,
                    "end": cue.end,
                    "text": display_text,
                    "semantic_text": cue.text,
                    "display_text": display_text,
                    "words": words,
                    "display_fragments": fragments,
                    "_generated_line_breaks": line_breaks,
                    "_source_map": source_map,
                    "_source_record_indexes": indexes,
                    "_display_groups": groups,
                }
            )
    return display_cues


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key '{key}'")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValidationError(f"JSON constant '{value}' is not permitted")


def _check_depth(value: Any) -> None:
    stack = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise ValidationError("Timed-cue JSON exceeds nesting limit 16")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def _keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    missing = expected - value.keys()
    unknown = value.keys() - expected
    if missing:
        raise ValidationError(f"{label} is missing '{sorted(missing)[0]}'")
    if unknown:
        raise ValidationError(f"{label} has unknown key '{sorted(unknown)[0]}'")


def _time(value: Any, label: str) -> float:
    if type(value) not in (int, float):
        raise ValidationError(f"{label} must be a finite number")
    if type(value) is int and not 0 <= value <= MAX_TIME_SECONDS:
        raise ValidationError(f"{label} must be between 0 and 86,400 seconds")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{label} must be a finite number")
    if not 0 <= result <= MAX_TIME_SECONDS:
        raise ValidationError(f"{label} must be between 0 and 86,400 seconds")
    return result


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be nonempty text")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValidationError(f"{label} contains an invalid Unicode surrogate")
    return value


def _check_text_budget(characters: int) -> None:
    if characters > MAX_TEXT_CHARACTERS:
        raise ValidationError("Timed-cue document exceeds 1,000,000 text characters")
