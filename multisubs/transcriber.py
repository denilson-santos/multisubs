"""WhisperX transcription, cue construction, and artifact coordination."""

from __future__ import annotations

import json
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from numbers import Real
from pathlib import Path
from typing import Any, cast

from .animation import normalize_cue_animation, normalize_word_animation
from .ass import (
    _render_strategy_for_segments,
    allocate_active_word_intervals,
    allocate_karaoke_durations,
    quantize_ass_centiseconds,
    resolve_subtitle_palettes,
    write_ass,
)
from .config import (
    MODELS as _MODELS,
)
from .config import SUPPORTED_LANGUAGES, validate_subtitle_config
from .errors import ArtifactError, DependencyError, TranscriptionError, ValidationError
from .layout import (
    WrappingMetrics,
    resolve_cue_placement,
    resolve_native_layout_region,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
)
from .models import (
    KaraokeCue,
    RelativeLength,
    SubtitleAnimationPhase,
    SubtitleConfig,
    SubtitleDisplayFragment,
    SubtitleDisplayGroup,
    SubtitleElementAnimation,
    SubtitlePlacementMode,
    SubtitlePosition,
    SubtitleSourceMap,
    SubtitleWordElementAnimation,
    TextCase,
    TranscriptDocument,
    TranscriptionPaths,
    VideoGeometry,
)
from .text_measurement import TextMeasurer
from .text_segmentation import (
    LinguisticSegmenter,
    build_source_text_map,
    display_units_for_records,
    source_text_for_records,
)
from .utils import atomic_write_text, find_unique_stem
from .wrapping import (
    PAUSE_BREAK_THRESHOLD as _WRAPPING_PAUSE_BREAK_THRESHOLD,
)
from .wrapping import (
    boundary_priority as _wrapping_boundary_priority,
)
from .wrapping import (
    build_display_fragments as _wrapping_build_display_fragments,
)
from .wrapping import (
    ends_clause as _wrapping_ends_clause,
)
from .wrapping import (
    ends_sentence as _wrapping_ends_sentence,
)
from .wrapping import (
    grapheme_clusters as _wrapping_grapheme_clusters,
)
from .wrapping import (
    has_significant_pause as _wrapping_has_significant_pause,
)
from .wrapping import (
    is_cjk_or_emoji as _wrapping_is_cjk_or_emoji,
)
from .wrapping import (
    join_text_parts as _wrapping_join_text_parts,
)
from .wrapping import (
    line_count as _wrapping_line_count,
)
from .wrapping import (
    normalise_display_text as _wrapping_normalise_display_text,
)
from .wrapping import (
    render_display_units as _wrapping_render_display_units,
)
from .wrapping import (
    split_display_units_for_layout as _wrapping_split_display_units_for_layout,
)
from .wrapping import (
    split_words_for_layout as _wrapping_split_words_for_layout,
)
from .wrapping import transform_display_text as _wrapping_transform_display_text
from .wrapping import (
    words_to_text as _wrapping_words_to_text,
)
from .wrapping import (
    wrap_subtitle_text as _wrapping_wrap_subtitle_text,
)

MAX_CUE_DURATION = 6.0
PAUSE_BREAK_THRESHOLD = 0.45
MODEL_LOAD_ATTEMPTS = 3
MODEL_RETRY_BASE_DELAY_SECONDS = 1.0

_RETRYABLE_MODEL_ERROR_MARKERS = (
    "connection",
    "connection reset",
    "remote end closed",
    "remote protocol",
    "server disconnected",
    "server error",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "too many requests",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
)

ProgressReporter = Callable[[str], None] | None
_SKIP_JSON_VALUE = object()


@dataclass(frozen=True)
class _MappedWord:
    """A linguistic group carrying source-record identity through cue splitting."""

    records: tuple[dict[str, Any], ...]
    source_map: SubtitleSourceMap
    display_group: SubtitleDisplayGroup
    token: str
    start: float
    end: float

    @property
    def record(self) -> dict[str, Any]:
        """Return the final record for legacy boundary helpers."""
        return self.records[-1]

    @property
    def record_indexes(self) -> tuple[int, ...]:
        return self.display_group.record_indexes


MODELS = _MODELS


def generate_transcriptions(
    input_path: str | Path,
    output_dir: str | Path,
    style_options: SubtitleConfig | None = None,
    lang: str | None = None,
    task: str = "transcribe",
    model_name: str = "turbo",
    *,
    position: SubtitlePosition | str | None = None,
    position_x: RelativeLength | str | None = None,
    position_y: RelativeLength | str | None = None,
    anchor: SubtitlePosition | str | None = None,
    progress: ProgressReporter = None,
) -> tuple[str, str, str]:
    """Generate JSON, SRT, and ASS files for one local video.

    The established tuple return value is preserved for programmatic callers.
    Heavy runtime dependencies are loaded only after the input and output have
    been validated.
    """
    source_path = _normalise_input_path(input_path)
    subtitle_config = validate_subtitle_config(
        style_options,
        position=position,
        position_x=position_x,
        position_y=position_y,
        anchor=anchor,
    )
    _validate_effect_task(subtitle_config, task)
    destination_dir = _normalise_output_dir(output_dir)
    from .subtitler import probe_video_geometry

    geometry = probe_video_geometry(source_path)
    resolved_config = resolve_subtitle_config(subtitle_config, geometry)
    # Validate the visual budget before loading speech models.
    resolve_wrapping_metrics(resolved_config, geometry, language=lang)
    document = transcribe_video(
        source_path,
        lang=lang,
        task=task,
        model_name=model_name,
        progress=progress,
    )
    wrapping_metrics = resolve_wrapping_metrics(
        resolved_config,
        geometry,
        language="en" if task == "translate" else document.language,
        sample_text=[
            _transform_display_text(
                str(segment.get("text", "")),
                resolved_config.style.typography.text_case,
            )
            for segment in document.segments
        ],
        verify_font_coverage=True,
    )
    return write_transcription_artifacts(
        document,
        destination_dir,
        subtitle_config,
        geometry=geometry,
        resolved_subtitle_config=resolved_config,
        wrapping_metrics=wrapping_metrics,
        progress=progress,
    )


def transcribe_video(
    input_path: str | Path,
    lang: str | None = None,
    task: str = "transcribe",
    model_name: str = "turbo",
    *,
    progress: ProgressReporter = None,
) -> TranscriptDocument:
    """Transcribe and align one video without serializing output artifacts."""
    source_path = _normalise_input_path(input_path)
    if model_name.endswith(".en"):
        if lang not in (None, "en"):
            raise ValidationError(
                f'Model "{model_name}" is English-only; use --lang en or '
                "choose a multilingual model for another source language."
            )
        lang = "en"
    if lang is not None and lang not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"Source language '{lang}' has no supported default alignment model. "
            "Use --help to list supported language codes."
        )

    _report(progress, f"Generating transcripts for '{source_path.name}'...")
    torch, whisperx = _load_runtime_dependencies()
    device, compute_type = _select_compute_configuration(torch)

    _report(
        progress,
        f"Loading WhisperX model '{model_name}' on {device} ({compute_type})...",
    )
    try:
        model = _load_model_with_retries(
            lambda: _load_silero_whisperx_model(
                whisperx,
                model_name=model_name,
                device=device,
                compute_type=compute_type,
                language=lang or None,
                task=task,
            ),
            operation=f"Loading WhisperX model '{model_name}'",
            progress=progress,
        )
    except Exception as exc:  # WhisperX has no stable public error hierarchy.
        raise TranscriptionError(
            f"Could not load WhisperX model '{model_name}' on {device}: {exc}"
        ) from exc

    _report(progress, "Transcribing audio...")
    try:
        audio = whisperx.load_audio(str(source_path))
        result = model.transcribe(audio)
    except Exception as exc:  # Enrich the external boundary with source context.
        raise TranscriptionError(
            f"Could not transcribe '{source_path}': {exc}"
        ) from exc

    result_mapping = _require_mapping(result, "WhisperX transcription result")
    raw_segments = _require_sequence(
        result_mapping.get("segments"), "transcription segments"
    )
    source_language = _result_language(result_mapping, lang)
    if source_language not in SUPPORTED_LANGUAGES:
        raise TranscriptionError(
            f"Detected source language '{source_language}' has no supported default "
            "alignment model. Use --help to list supported languages; if detection "
            "was incorrect, specify the source language with --lang CODE."
        )
    if lang is None:
        _report(progress, f"Detected source language: {source_language}.")
    alignment_language = "en" if task == "translate" else source_language

    _report(progress, "Aligning words for subtitle timing...")
    try:
        align_model, align_metadata = _load_model_with_retries(
            lambda: whisperx.load_align_model(
                language_code=alignment_language,
                device=device,
            ),
            operation=f"Loading alignment model for '{alignment_language}'",
            progress=progress,
        )
        aligned_result = whisperx.align(
            raw_segments,
            align_model,
            align_metadata,
            audio,
            device,
            return_char_alignments=False,
        )
    except Exception as exc:  # WhisperX alignment errors are dependency-specific.
        raise TranscriptionError(
            f"Could not align transcript words for '{source_path}': {exc}"
        ) from exc

    aligned_mapping = _require_mapping(aligned_result, "WhisperX alignment result")
    aligned_segments = _require_sequence(
        aligned_mapping.get("segments"), "aligned segments"
    )
    segments = _build_subtitle_segments(
        aligned_segments,
        language="en" if task == "translate" else source_language,
    )
    _validate_subtitle_segments(segments)

    full_text = _result_full_text(result_mapping, segments)
    return TranscriptDocument(
        source_path=source_path,
        language=source_language,
        task=task,
        model_name=model_name,
        full_text=full_text,
        segments=tuple(segments),
    )


def write_transcription_artifacts(
    document: TranscriptDocument,
    output_dir: str | Path,
    subtitle_config: SubtitleConfig | None = None,
    *,
    geometry: VideoGeometry | None = None,
    resolved_subtitle_config: SubtitleConfig | None = None,
    wrapping_metrics: WrappingMetrics | None = None,
    template_requested: str | None = None,
    template_resolved: str = "default",
    template_source: str = "builtin",
    template_base: str | None = None,
    verify_font_coverage: bool = False,
    progress: ProgressReporter = None,
) -> tuple[str, str, str]:
    """Serialize one semantic transcript as JSON, SRT, and ASS artifacts."""
    config = validate_subtitle_config(subtitle_config)
    _validate_effect_task(config, document.task)
    destination_dir = _normalise_output_dir(output_dir)
    if geometry is None:
        from .subtitler import probe_video_geometry

        geometry = probe_video_geometry(document.source_path)
    resolved_config = resolve_subtitle_config(
        resolved_subtitle_config or config,
        geometry,
    )
    _validate_subtitle_segments(document.segments)
    display_segments, resolved_wrapping_metrics = layout_subtitle_cues(
        document.segments,
        resolved_config,
        geometry,
        language="en" if document.task == "translate" else document.language,
        wrapping_metrics=wrapping_metrics,
        verify_font_coverage=verify_font_coverage,
    )
    display_segments, fallback_cues = prepare_karaoke_cues(
        display_segments,
        resolved_config,
    )
    if _requires_word_timing(resolved_config) and fallback_cues:
        _report(
            progress,
            f"Warning: {fallback_cues} subtitle cue(s) could not be mapped "
            "to complete word timings and were rendered without word animation; "
            "no timestamps were invented.",
        )
    measurement_diagnostic = resolved_wrapping_metrics.text_measurer.diagnostic
    if measurement_diagnostic is not None:
        _report(progress, measurement_diagnostic)
    paths = _choose_transcription_paths(
        destination_dir,
        document.source_path.stem,
        document.language,
    )

    _write_json(
        paths.json_path,
        full_text=document.full_text,
        segments=display_segments,
        file_name=document.source_path.stem,
        lang=document.language,
        input_path=document.source_path,
        task=document.task,
        model_name=document.model_name,
        subtitle_config=config,
        resolved_subtitle_config=resolved_config,
        geometry=geometry,
        wrapping_metrics=resolved_wrapping_metrics,
        karaoke_fallback_cues=fallback_cues,
        template_requested=template_requested,
        template_resolved=template_resolved,
        template_source=template_source,
        template_base=template_base,
    )
    _report(progress, "Completed JSON transcript.")

    _write_srt(paths.srt_path, display_segments)
    _report(progress, "Completed SRT transcript.")

    write_ass(
        paths.ass_path,
        display_segments,
        resolved_config,
        geometry,
        wrapping_metrics=resolved_wrapping_metrics,
    )
    _report(progress, "Completed ASS transcript.")
    return paths.as_tuple()


def _normalise_input_path(input_path: str | Path) -> Path:
    source_path = Path(input_path).expanduser().resolve(strict=False)
    if not source_path.exists() or not source_path.is_file():
        raise ValidationError(f"Video file not found at '{input_path}'")
    return source_path


def _normalise_output_dir(output_dir: str | Path) -> Path:
    destination_dir = Path(output_dir).expanduser().resolve(strict=False)
    if destination_dir.exists() and not destination_dir.is_dir():
        raise ValidationError(
            f"Output path '{output_dir}' is a file; provide a directory instead"
        )
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArtifactError(
            f"Could not create output directory '{destination_dir}': {exc}"
        ) from exc
    return destination_dir


def _validate_effect_task(config: SubtitleConfig, task: str) -> None:
    if _requires_word_timing(config) and task == "translate":
        raise ValidationError(
            "Word animations cannot be generated for translation because "
            "source-language word timings do not map losslessly to translated text"
        )


def _load_runtime_dependencies() -> tuple[Any, Any]:
    try:
        import torch
    except ImportError as exc:
        raise DependencyError("PyTorch is required to transcribe video") from exc

    try:
        import whisperx
    except ImportError as exc:
        raise DependencyError("WhisperX is required to transcribe video") from exc
    return torch, whisperx


def _load_silero_whisperx_model(
    whisperx: Any,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    language: str | None,
    task: str,
) -> Any:
    """Load WhisperX's Silero pipeline without an unused Pyannote ONNX probe.

    WhisperX 3.8 imports Pyannote's optional speaker-embedding module while
    importing its ASR implementation. That module imports ONNX Runtime even
    though this application explicitly selects the TorchScript Silero VAD.
    On hosts without a complete DRM sysfs tree, ONNX Runtime emits a harmless
    GPU-discovery warning during that unused import. Temporarily blocking only
    that optional import avoids the warning without changing PyTorch/CUDA
    selection or the Silero VAD implementation.
    """
    with _block_optional_onnxruntime_import():
        return whisperx.load_model(
            model_name,
            device,
            compute_type=compute_type,
            language=language,
            task=task,
            vad_method="silero",
        )


@contextmanager
def _block_optional_onnxruntime_import():
    """Prevent an unused optional ONNX Runtime import during Silero setup."""
    module_name = "onnxruntime"
    if module_name in sys.modules:
        yield
        return

    # An import entry set to None makes importlib raise ModuleNotFoundError,
    # which Pyannote already handles as its optional ONNX dependency path.
    sys.modules[module_name] = cast(Any, None)
    try:
        yield
    finally:
        sys.modules.pop(module_name, None)


def _load_model_with_retries(
    loader: Callable[[], Any],
    *,
    operation: str,
    progress: ProgressReporter,
    attempts: int = MODEL_LOAD_ATTEMPTS,
    base_delay_seconds: float = MODEL_RETRY_BASE_DELAY_SECONDS,
) -> Any:
    """Retry transient model-download failures before giving up.

    WhisperX may load several assets through Hugging Face and Torch Hub. A
    connection can close after an asset has been partially cached, so a short
    exponential backoff often lets a subsequent attempt resume successfully.
    Deterministic failures are raised immediately and are never retried.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return loader()
        except Exception as exc:  # External model loaders have no shared error type.
            last_error = exc
            if attempt >= attempts or not _is_retryable_model_error(exc):
                raise

            delay = base_delay_seconds * (2 ** (attempt - 1))
            _report(
                progress,
                f"{operation} encountered a temporary connection error; "
                f"retrying ({attempt + 1}/{attempts}) in {delay:g}s...",
            )
            time.sleep(delay)

    # The loop either returns or raises, but retaining this guard keeps the
    # helper safe if its attempt count is changed to an invalid value later.
    if last_error is not None:
        raise last_error
    raise ValueError("Model load attempts must be greater than zero")


def _is_retryable_model_error(error: BaseException) -> bool:
    """Identify connection-like errors without retrying local configuration errors."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ConnectionError, TimeoutError)):
            return True

        exception_name = type(current).__name__.lower()
        if any(marker in exception_name for marker in ("connection", "timeout")):
            return True

        message = str(current).lower()
        if any(marker in message for marker in _RETRYABLE_MODEL_ERROR_MARKERS):
            return True

        current = current.__cause__ or current.__context__
    return False


def _select_compute_configuration(torch: Any) -> tuple[str, str]:
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception as exc:
        raise DependencyError(
            f"Could not determine the available compute device: {exc}"
        ) from exc
    return (device, "float16" if device == "cuda" else "int8")


def _require_mapping(value: object, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TranscriptionError(f"WhisperX returned an invalid {description}")
    return value


def _require_sequence(value: object, description: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TranscriptionError(f"WhisperX returned invalid {description}")
    return value


def _result_language(result: Mapping[str, Any], requested_language: str | None) -> str:
    if requested_language is not None:
        return requested_language
    language = result.get("language")
    if isinstance(language, str) and language:
        return language
    raise TranscriptionError(
        "WhisperX did not return a detected source language. "
        "Specify the source language with --lang CODE and retry."
    )


def _result_full_text(
    result: Mapping[str, Any], segments: Sequence[Mapping[str, Any]]
) -> str:
    text = result.get("text")
    if isinstance(text, str) and text.strip():
        return _normalise_display_text(text)
    mapped_segments: list[str] = []
    seen_maps: set[int] = set()
    for segment in segments:
        source_maps = segment.get("_source_maps")
        if isinstance(source_maps, Sequence) and not isinstance(
            source_maps, (str, bytes)
        ):
            for source_map in source_maps:
                if not isinstance(source_map, SubtitleSourceMap):
                    continue
                map_identity = id(source_map)
                if map_identity not in seen_maps:
                    mapped_segments.append(source_map.normalized_text)
                    seen_maps.add(map_identity)
            continue
        source_map = segment.get("_source_map")
        if isinstance(source_map, SubtitleSourceMap):
            map_identity = id(source_map)
            if map_identity not in seen_maps:
                mapped_segments.append(source_map.normalized_text)
                seen_maps.add(map_identity)
            continue
        segment_text = segment.get("text", "")
        if isinstance(segment_text, str):
            mapped_segments.append(segment_text)
    if mapped_segments:
        return _normalise_display_text("".join(mapped_segments))
    return _normalise_display_text(
        " ".join(
            str(segment.get("text", ""))
            for segment in segments
            if isinstance(segment.get("text", ""), str)
        )
    )


def _choose_transcription_paths(
    output_dir: Path,
    file_name: str,
    lang: str,
) -> TranscriptionPaths:
    stem = find_unique_stem(
        output_dir, f"{file_name}-{lang}", (".json", ".srt", ".ass")
    )
    return TranscriptionPaths(
        json_path=output_dir / f"{stem}.json",
        srt_path=output_dir / f"{stem}.srt",
        ass_path=output_dir / f"{stem}.ass",
    )


def _build_subtitle_segments(
    aligned_segments: Sequence[object],
    *,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Build semantic cues while retaining source text beside timed records."""
    cues: list[dict[str, Any]] = []
    pending_words: list[_MappedWord] = []

    with LinguisticSegmenter() as segmenter:
        for source_segment_index, raw_segment in enumerate(aligned_segments):
            segment = _require_mapping(raw_segment, "aligned segment")
            raw_records = _alignment_records(segment)
            source_text = segment.get("text")
            fallback_text = (
                _words_to_text(raw_records)
                if not isinstance(source_text, str) or (not source_text and raw_records)
                else None
            )
            source_map = build_source_text_map(
                source_text,
                raw_records,
                fallback_text=fallback_text,
                source_segment_index=source_segment_index,
            )
            if source_map.timing_complete:
                display_groups = segmenter.group_source_map(
                    source_map, raw_records, language=language
                )
                mapped_words = [
                    _MappedWord(
                        records=tuple(
                            raw_records[index] for index in group.record_indexes
                        ),
                        source_map=source_map,
                        display_group=group,
                        token=group.source_text,
                        start=group.start_time,
                        end=group.end_time,
                    )
                    for group in display_groups
                ]
                _validate_word_order(pending_words, mapped_words)
                pending_words.extend(mapped_words)
                continue

            if pending_words:
                cues.extend(_build_cues_from_words(pending_words))
                pending_words = []

            start, end = _segment_times(segment)
            _append_cue(
                cues,
                source_map.normalized_text,
                start,
                end,
                raw_records,
                source_map=source_map,
                source_record_indexes=source_map.mapped_record_indexes,
                mapping_reason=";".join(source_map.fallback_reasons) or None,
            )

    if pending_words:
        cues.extend(_build_cues_from_words(pending_words))

    for index, cue in enumerate(cues):
        cue["id"] = index
    return cues


def _alignment_records(segment: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-safe copies of every aligned record, including untimed ones."""
    raw_words = segment.get("words", [])
    if not isinstance(raw_words, Sequence) or isinstance(raw_words, (str, bytes)):
        return []
    return [
        _json_safe_mapping(raw_word)
        for raw_word in raw_words
        if isinstance(raw_word, Mapping)
    ]


def _timed_words(segment: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_words = segment.get("words", [])
    if not isinstance(raw_words, Sequence) or isinstance(raw_words, (str, bytes)):
        return []

    words: list[dict[str, Any]] = []
    for raw_word in raw_words:
        if not isinstance(raw_word, Mapping):
            continue
        text = raw_word.get("word")
        start = _finite_time(raw_word.get("start"))
        end = _finite_time(raw_word.get("end"))
        if (
            not isinstance(text, str)
            or not text.strip()
            or start is None
            or end is None
        ):
            continue
        if end < start:
            continue

        word = _json_safe_mapping(raw_word)
        word["word"] = text
        word["start"] = start
        word["end"] = end
        words.append(word)
    return words


def _validate_word_order(
    previous_words: Sequence[Mapping[str, Any] | _MappedWord],
    next_words: Sequence[Mapping[str, Any] | _MappedWord],
) -> None:
    words = [*previous_words, *next_words]
    previous_start: float | None = None
    for word in words:
        start = _word_start(word)
        end = _word_end(word)
        if end < start:
            raise TranscriptionError("WhisperX returned invalid word timestamps")
        if previous_start is not None and start < previous_start:
            raise TranscriptionError(
                "WhisperX returned non-chronological word timestamps"
            )
        previous_start = start


def _segment_times(segment: Mapping[str, Any]) -> tuple[float, float]:
    start = _finite_time(segment.get("start"))
    end = _finite_time(segment.get("end"))
    if start is None or end is None or end < start:
        raise TranscriptionError("WhisperX returned invalid segment timestamps")
    return start, end


def _finite_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        return None
    return result


def _build_cues_from_words(
    words: Sequence[dict[str, Any] | _MappedWord],
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    current_words: list[dict[str, Any] | _MappedWord] = []

    for word in words:
        if current_words and _words_have_significant_pause(current_words[-1], word):
            _append_words_cue(cues, current_words)
            current_words = []

        current_words.append(word)
        while current_words and _cue_exceeds_limits(current_words):
            if len(current_words) == 1:
                _append_words_cue(cues, current_words)
                current_words = []
                break

            break_at = _find_best_cue_break(current_words)
            if break_at <= 0 or break_at >= len(current_words):
                break_at = len(current_words) - 1
            _append_words_cue(cues, current_words[:break_at])
            current_words = current_words[break_at:]

        if current_words and _ends_sentence(_word_text(current_words[-1])):
            _append_words_cue(cues, current_words)
            current_words = []

    if current_words:
        _append_words_cue(cues, current_words)
    return cues


def _append_words_cue(
    cues: list[dict[str, Any]],
    words: Sequence[dict[str, Any] | _MappedWord],
) -> None:
    if not words:
        return
    mapped_words = [word for word in words if isinstance(word, _MappedWord)]
    source_map = (
        mapped_words[0].source_map
        if mapped_words
        and len(mapped_words) == len(words)
        and all(word.source_map is mapped_words[0].source_map for word in mapped_words)
        else None
    )
    source_record_indexes = (
        tuple(index for word in mapped_words for index in word.record_indexes)
        if source_map
        else None
    )
    source_maps: tuple[SubtitleSourceMap, ...] | None = None
    if mapped_words:
        source_maps = tuple(dict.fromkeys(word.source_map for word in mapped_words))
    _append_cue(
        cues,
        _source_text_for_words(words),
        _word_start(words[0]),
        _word_end(words[-1]),
        [record for word in words for record in _word_records(word)],
        source_map=source_map,
        source_record_indexes=source_record_indexes,
        source_maps=source_maps,
        display_groups=_cue_local_display_groups(
            mapped_words,
            preserve_record_indexes=source_map is not None,
        ),
    )


def _cue_exceeds_limits(
    words: Sequence[Mapping[str, Any] | _MappedWord],
) -> bool:
    return _words_duration(words) > MAX_CUE_DURATION


def _words_duration(words: Sequence[Mapping[str, Any] | _MappedWord]) -> float:
    return _word_end(words[-1]) - _word_start(words[0])


def _find_best_cue_break(
    words: Sequence[Mapping[str, Any] | _MappedWord],
) -> int:
    """Select the best valid word boundary before a cue exceeds its limits."""
    candidates = [
        index
        for index in range(1, len(words))
        if not _cue_exceeds_limits(words[:index])
    ]
    if not candidates:
        return 1

    def key(index: int) -> tuple[int, float]:
        prefix = words[:index]
        duration_distance = abs(MAX_CUE_DURATION - _words_duration(prefix))
        return (
            _cue_boundary_priority(words, index),
            -duration_distance,
        )

    return max(candidates, key=key)


def _append_cue(
    cues: list[dict[str, Any]],
    text: object,
    start: float,
    end: float,
    words: Sequence[Mapping[str, Any]],
    *,
    source_map: SubtitleSourceMap | None = None,
    source_record_indexes: Sequence[int] | None = None,
    mapping_reason: str | None = None,
    source_maps: Sequence[SubtitleSourceMap] | None = None,
    display_groups: Sequence[SubtitleDisplayGroup] | None = None,
) -> None:
    if not isinstance(text, str):
        return
    normalised_text = _normalise_display_text(text)
    if not normalised_text:
        return
    if end < start or start < 0:
        raise TranscriptionError("Subtitle cue has invalid timestamps")
    cue: dict[str, Any] = {
        "id": len(cues),
        "start": start,
        "end": end,
        "text": normalised_text,
        "words": [dict(word) for word in words],
    }
    if source_map is not None:
        cue["_source_map"] = source_map
        cue["_source_record_indexes"] = tuple(source_record_indexes or ())
    if source_maps:
        cue["_source_maps"] = tuple(source_maps)
    if display_groups:
        cue["_display_groups"] = tuple(display_groups)
    if mapping_reason:
        cue["_alignment_fallback_reason"] = mapping_reason
        cue["_segmentation"] = {
            "strategy": "static-fallback",
            "backend_version": None,
            "alignment_granularity": "source-record",
            "group_count": 0,
            "emergency_subdivisions": 0,
            "fallback_reason": mapping_reason.split(";"),
            "fallback_count": 1,
        }
    cues.append(cue)


def _word_record(word: Mapping[str, Any] | _MappedWord) -> Mapping[str, Any]:
    return word.record if isinstance(word, _MappedWord) else word


def _word_records(
    word: Mapping[str, Any] | _MappedWord,
) -> tuple[Mapping[str, Any], ...]:
    return word.records if isinstance(word, _MappedWord) else (word,)


def _cue_local_display_groups(
    words: Sequence[_MappedWord],
    *,
    preserve_record_indexes: bool,
) -> tuple[SubtitleDisplayGroup, ...]:
    groups: list[SubtitleDisplayGroup] = []
    record_offset = 0
    for identity, word in enumerate(words):
        record_indexes = (
            word.record_indexes
            if preserve_record_indexes
            else tuple(range(record_offset, record_offset + len(word.record_indexes)))
        )
        groups.append(
            replace(
                word.display_group,
                identity=identity,
                record_indexes=record_indexes,
            )
        )
        record_offset += len(record_indexes)
    return tuple(groups)


def _word_start(word: Mapping[str, Any] | _MappedWord) -> float:
    value = (
        word.start if isinstance(word, _MappedWord) else _finite_time(word.get("start"))
    )
    if value is None:
        raise TranscriptionError("WhisperX returned invalid word timestamps")
    return value


def _word_end(word: Mapping[str, Any] | _MappedWord) -> float:
    value = word.end if isinstance(word, _MappedWord) else _finite_time(word.get("end"))
    if value is None:
        raise TranscriptionError("WhisperX returned invalid word timestamps")
    return value


def _word_text(word: Mapping[str, Any] | _MappedWord) -> str:
    if isinstance(word, _MappedWord):
        return word.token
    return str(word.get("word", ""))


def _source_text_for_words(
    words: Sequence[Mapping[str, Any] | _MappedWord],
) -> str:
    if not words or not all(isinstance(word, _MappedWord) for word in words):
        return _words_to_text([_word_record(word) for word in words])
    mapped_words = cast(Sequence[_MappedWord], words)
    return "".join(word.token for word in mapped_words)


def _words_have_significant_pause(
    previous: Mapping[str, Any] | _MappedWord,
    next_word: Mapping[str, Any] | _MappedWord,
) -> bool:
    return _word_start(next_word) - _word_end(previous) >= PAUSE_BREAK_THRESHOLD


def _cue_boundary_priority(
    words: Sequence[Mapping[str, Any] | _MappedWord], index: int
) -> int:
    previous = words[index - 1]
    if isinstance(previous, _MappedWord):
        if previous.display_group.boundary_class == "sentence":
            return 3
        if previous.display_group.boundary_class == "clause":
            return 2
    if _words_have_significant_pause(previous, words[index]):
        return 1
    return _boundary_priority([_word_record(word) for word in words], index)


def _require_span_time(value: float | None) -> float:
    if value is None:
        raise TranscriptionError("WhisperX returned invalid word timestamps")
    return value


def layout_subtitle_cues(
    segments: Sequence[Mapping[str, Any]],
    resolved_config: SubtitleConfig,
    geometry: VideoGeometry,
    *,
    language: str | None = None,
    text_measurer: TextMeasurer | None = None,
    wrapping_metrics: WrappingMetrics | None = None,
    verify_font_coverage: bool = False,
) -> tuple[list[dict[str, Any]], WrappingMetrics]:
    """Create display cues from semantic cues using resolved layout metrics."""
    if wrapping_metrics is not None and text_measurer is not None:
        raise ValidationError(
            "wrapping metrics and text measurer cannot be supplied together"
        )
    metrics = wrapping_metrics or resolve_wrapping_metrics(
        resolved_config,
        geometry,
        language=language,
        text_measurer=text_measurer,
        sample_text=(
            [
                _transform_display_text(
                    str(segment.get("semantic_text", segment.get("text", ""))),
                    resolved_config.style.typography.text_case,
                )
                for segment in segments
            ]
            if verify_font_coverage
            else None
        ),
        verify_font_coverage=verify_font_coverage,
    )
    text_case = resolved_config.style.typography.text_case
    display_cues: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(segments):
        source_text = segment.get("text")
        if not isinstance(source_text, str):
            source_text = segment.get("semantic_text")
        raw_words = segment.get("words", [])
        words = (
            [dict(word) for word in raw_words if isinstance(word, Mapping)]
            if isinstance(raw_words, Sequence)
            and not isinstance(raw_words, (str, bytes))
            else []
        )
        existing_map = segment.get("_source_map")
        source_map = (
            existing_map
            if isinstance(existing_map, SubtitleSourceMap)
            else build_source_text_map(
                source_text,
                words,
                fallback_text=_words_to_text(words)
                if not isinstance(source_text, str) or (not source_text and words)
                else None,
                source_segment_index=segment_index,
            )
        )
        existing_indexes = segment.get("_source_record_indexes")
        record_indexes = (
            tuple(index for index in existing_indexes if isinstance(index, int))
            if isinstance(existing_indexes, Sequence)
            and not isinstance(existing_indexes, (str, bytes))
            else source_map.mapped_record_indexes
        )
        words_by_record = {
            record_index: word
            for record_index, word in zip(record_indexes, words, strict=False)
        }
        raw_display_groups = segment.get("_display_groups")
        display_groups = (
            tuple(
                group
                for group in raw_display_groups
                if isinstance(group, SubtitleDisplayGroup)
            )
            if isinstance(raw_display_groups, Sequence)
            and not isinstance(raw_display_groups, (str, bytes))
            else ()
        )
        if source_map.timing_complete and words and record_indexes:
            units = display_units_for_records(
                source_map,
                record_indexes,
                transform=lambda value: _transform_display_text(value, text_case),
            )
            if len(units) == len(record_indexes) and all(
                index in words_by_record for index in record_indexes
            ):
                groups = _wrapping_split_display_units_for_layout(
                    units,
                    metrics,
                    boundary_words=[words_by_record[index] for index in record_indexes],
                    display_groups=display_groups,
                )
                for group in groups:
                    group_indexes = tuple(unit.record_index for unit in group)
                    source_group = source_text_for_records(
                        source_map,
                        group_indexes,
                    )
                    cue_display_groups = _display_groups_for_records(
                        display_groups,
                        group_indexes,
                        source_map,
                        words_by_record,
                    )
                    # Linguistic groups choose preferred cue/line boundaries,
                    # but every original alignment record remains an effect
                    # unit. A group can occupy multiple visual lines; mapping
                    # its records to one group index would then repeat an
                    # effect index and trigger static fallback in ASS.
                    record_to_effect_unit = {
                        record_index: offset
                        for offset, record_index in enumerate(group_indexes)
                    }
                    display_text, fragments, line_breaks = (
                        _wrapping_render_display_units(
                            group,
                            metrics,
                            word_indexes=record_to_effect_unit,
                            display_groups=cue_display_groups,
                        )
                    )
                    group_words = [words_by_record[index] for index in group_indexes]
                    _append_display_cue(
                        display_cues,
                        source_group,
                        display_text,
                        _word_start(group_words[0]),
                        _word_end(group_words[-1]),
                        group_words,
                        [],
                        metrics,
                        display_fragments=fragments,
                        generated_line_breaks=line_breaks,
                        source_map=source_map,
                        source_record_indexes=group_indexes,
                        display_groups=cue_display_groups,
                    )
                continue

        semantic_text = source_map.normalized_text
        if not semantic_text and isinstance(source_text, str):
            semantic_text = source_text
        if not semantic_text:
            continue
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TranscriptionError("Subtitle cue has invalid timestamps") from exc
        _append_display_cue(
            display_cues,
            semantic_text,
            _transform_display_text(_normalise_display_text(semantic_text), text_case),
            start,
            end,
            words,
            [],
            metrics,
            mapping_reason=";".join(source_map.fallback_reasons) or None,
            source_map=source_map,
            source_record_indexes=record_indexes,
            display_groups=display_groups,
        )

    for index, cue in enumerate(display_cues):
        cue["id"] = index
    return display_cues, metrics


def _append_display_cue(
    cues: list[dict[str, Any]],
    semantic_text: str,
    unwrapped_display_text: str,
    start: float,
    end: float,
    words: Sequence[Mapping[str, Any]],
    display_words: Sequence[Mapping[str, Any]],
    metrics: WrappingMetrics,
    *,
    display_fragments: tuple[SubtitleDisplayFragment, ...] | None = None,
    generated_line_breaks: Sequence[str] = (),
    mapping_reason: str | None = None,
    source_map: SubtitleSourceMap | None = None,
    source_record_indexes: Sequence[int] | None = None,
    display_groups: Sequence[SubtitleDisplayGroup] = (),
) -> None:
    if end < start or start < 0:
        raise TranscriptionError("Subtitle cue has invalid timestamps")
    rendered_display_text = (
        unwrapped_display_text
        if display_fragments is not None
        else _wrap_subtitle_text(
            unwrapped_display_text,
            display_words or None,
            metrics=metrics,
        )
    )
    if display_fragments is None and display_words:
        display_fragments = _wrapping_build_display_fragments(
            rendered_display_text,
            display_words,
        )
    cue: dict[str, Any] = {
        "id": len(cues),
        "start": start,
        "end": end,
        "text": rendered_display_text,
        "semantic_text": semantic_text,
        "display_text": rendered_display_text,
        "words": [dict(word) for word in words],
        "display_fragments": display_fragments,
    }
    if generated_line_breaks:
        cue["_generated_line_breaks"] = tuple(generated_line_breaks)
    if mapping_reason:
        cue["_alignment_fallback_reason"] = mapping_reason
        cue["_segmentation"] = {
            "strategy": "static-fallback",
            "backend_version": None,
            "alignment_granularity": "source-record",
            "group_count": 0,
            "emergency_subdivisions": 0,
            "fallback_reason": mapping_reason.split(";"),
            "fallback_count": 1,
        }
    if source_map is not None:
        cue["_source_map"] = source_map
        cue["_source_record_indexes"] = tuple(source_record_indexes or ())
    if display_groups:
        cue["_display_groups"] = tuple(display_groups)
        cue["_segmentation"] = _segmentation_metadata(display_groups)
    cues.append(cue)


def _display_groups_for_records(
    display_groups: Sequence[SubtitleDisplayGroup],
    record_indexes: Sequence[int],
    source_map: SubtitleSourceMap,
    words_by_record: Mapping[int, Mapping[str, Any]],
) -> tuple[SubtitleDisplayGroup, ...]:
    selected = set(record_indexes)
    units_by_record = {
        unit.record_index: unit
        for unit in display_units_for_records(source_map, record_indexes)
    }
    result: list[SubtitleDisplayGroup] = []
    for display_group in display_groups:
        retained = tuple(
            index for index in display_group.record_indexes if index in selected
        )
        if not retained:
            continue
        first_unit = units_by_record[retained[0]]
        last_unit = units_by_record[retained[-1]]
        emergency = retained != display_group.record_indexes
        result.append(
            replace(
                display_group,
                identity=len(result),
                record_indexes=retained,
                source_start=first_unit.source_start,
                source_end=last_unit.source_end,
                source_text=source_text_for_records(source_map, retained),
                start_time=_word_start(words_by_record[retained[0]]),
                end_time=_word_end(words_by_record[retained[-1]]),
                boundary_class=(
                    "emergency" if emergency else display_group.boundary_class
                ),
                emergency_subdivision=(
                    emergency or display_group.emergency_subdivision
                ),
            )
        )
    return tuple(result)


def _segmentation_metadata(
    display_groups: Sequence[SubtitleDisplayGroup],
) -> dict[str, Any]:
    strategies = tuple(dict.fromkeys(group.strategy for group in display_groups))
    versions = tuple(
        dict.fromkeys(
            group.backend_version
            for group in display_groups
            if group.backend_version != "none"
        )
    )
    return {
        "strategy": "+".join(strategies),
        "backend_version": "+".join(versions) if versions else None,
        "alignment_granularity": "+".join(
            dict.fromkeys(group.alignment_granularity for group in display_groups)
        ),
        "group_count": len(display_groups),
        "emergency_subdivisions": sum(
            group.emergency_subdivision for group in display_groups
        ),
        "fallback_reason": None,
        "fallback_count": 0,
    }


def _transform_display_words(
    words: Sequence[Mapping[str, Any]], text_case: TextCase
) -> list[dict[str, Any]]:
    """Transform word text while retaining timing fields and source order."""
    transformed: list[dict[str, Any]] = []
    for word in words:
        display_word = dict(word)
        display_word["word"] = _transform_display_text(
            str(word.get("word", "")), text_case
        )
        transformed.append(display_word)
    return transformed


def prepare_karaoke_cues(
    segments: Sequence[Mapping[str, Any]],
    resolved_config: SubtitleConfig,
) -> tuple[list[dict[str, Any]], int]:
    """Prepare one immutable aligned-word timing contract per eligible cue."""
    prepared: list[dict[str, Any]] = []
    fallback_cues = 0
    for segment in segments:
        prepared_segment = dict(segment)
        prepared_segment.pop("_karaoke_cue", None)
        prepared_segment.pop("_word_effect", None)
        if _requires_word_timing(resolved_config):
            karaoke_cue, fallback_reason = _build_karaoke_cue(
                segment, resolved_config.style.typography.text_case
            )
            if karaoke_cue is None:
                fallback_cues += 1
                prepared_segment["_word_effect"] = {
                    "strategy": "static-fallback",
                    "status": "fallback",
                    "units": "alignment-records",
                    "unit_count": _segment_record_count(segment),
                    "fallback_reason": fallback_reason or "invalid-effect-contract",
                    "fallback_count": 1,
                }
            else:
                prepared_segment["_karaoke_cue"] = karaoke_cue
                prepared_segment["_word_effect"] = {
                    "strategy": "alignment-records",
                    "status": "active",
                    "units": "alignment-records",
                    "unit_count": len(karaoke_cue.durations),
                    "fallback_reason": None,
                    "fallback_count": 0,
                }
        prepared.append(prepared_segment)
    return prepared, fallback_cues


def _prepare_karaoke_cue(
    segment: Mapping[str, Any], text_case: TextCase = TextCase.ORIGINAL
) -> KaraokeCue | None:
    """Prepare record-timed effects while retaining the legacy return type."""
    karaoke_cue, _ = _build_karaoke_cue(segment, text_case)
    return karaoke_cue


def _build_karaoke_cue(
    segment: Mapping[str, Any], text_case: TextCase = TextCase.ORIGINAL
) -> tuple[KaraokeCue | None, str | None]:
    if segment.get("_alignment_fallback_reason"):
        return None, "incomplete-alignment-mapping"
    raw_words = segment.get("words")
    if not isinstance(raw_words, Sequence) or isinstance(raw_words, (str, bytes)):
        return None, "missing-alignment-records"
    words = [word for word in raw_words if isinstance(word, Mapping)]
    if not words:
        return None, "missing-alignment-records"
    if len(words) != len(raw_words):
        return None, "invalid-alignment-record"
    if any(
        not isinstance(word.get("word"), str) or not word["word"].strip()
        for word in words
    ):
        return None, "invalid-alignment-record"
    if any(_word_has_invalid_timing(word) for word in words):
        return None, "invalid-alignment-timing"

    raw_fragments = segment.get("display_fragments")
    if (
        isinstance(raw_fragments, Sequence)
        and not isinstance(raw_fragments, (str, bytes))
        and all(
            isinstance(fragment, SubtitleDisplayFragment) for fragment in raw_fragments
        )
    ):
        fragments = tuple(raw_fragments)
    else:
        fragments = _wrapping_build_display_fragments(
            str(segment.get("text", "")),
            _transform_display_words(words, text_case),
        )
    if fragments is None:
        return None, "record-fragment-mapping"
    timed_indexes = [
        fragment.word_index for fragment in fragments if fragment.word_index is not None
    ]
    if timed_indexes != list(range(len(words))):
        return None, "record-fragment-mapping"
    try:
        durations = allocate_karaoke_durations(
            segment.get("start"),
            segment.get("end"),
            words,
        )
        active_intervals = allocate_active_word_intervals(
            segment.get("start"),
            segment.get("end"),
            words,
        )
    except ArtifactError:
        return None, "invalid-effect-intervals"
    return (
        KaraokeCue(
            fragments=fragments,
            durations=durations,
            active_intervals=active_intervals,
        ),
        None,
    )


def _segment_record_count(segment: Mapping[str, Any]) -> int:
    raw_words = segment.get("words")
    if not isinstance(raw_words, Sequence) or isinstance(raw_words, (str, bytes)):
        return 0
    return sum(isinstance(word, Mapping) for word in raw_words)


def _word_has_invalid_timing(word: Mapping[str, Any]) -> bool:
    start = _finite_time(word.get("start"))
    end = _finite_time(word.get("end"))
    return start is None or end is None or end < start


def _validate_subtitle_segments(segments: Sequence[Mapping[str, Any]]) -> None:
    previous_start: float | None = None
    for segment in segments:
        start = _finite_time(segment.get("start"))
        end = _finite_time(segment.get("end"))
        if start is None or end is None or end < start:
            raise TranscriptionError(
                "Subtitle cues must have valid, ordered timestamps"
            )
        if previous_start is not None and start < previous_start:
            raise TranscriptionError("Subtitle cues must be in chronological order")
        previous_start = start


def _write_json(
    path: Path,
    *,
    full_text: str,
    segments: Sequence[Mapping[str, Any]],
    file_name: str,
    lang: str,
    input_path: Path,
    task: str,
    model_name: str,
    subtitle_config: SubtitleConfig,
    resolved_subtitle_config: SubtitleConfig,
    geometry: VideoGeometry,
    wrapping_metrics: WrappingMetrics | None = None,
    karaoke_fallback_cues: int = 0,
    template_requested: str | None = None,
    template_resolved: str = "default",
    template_source: str = "builtin",
    template_base: str | None = None,
) -> None:
    requested_layout = subtitle_config.layout
    resolved_layout = resolved_subtitle_config.layout
    placement = resolve_cue_placement(resolved_subtitle_config, geometry)
    wrapping_metrics = wrapping_metrics or resolve_wrapping_metrics(
        resolved_subtitle_config, geometry
    )
    explicit = resolved_layout.placement_mode is SubtitlePlacementMode.EXPLICIT
    native_region = (
        None if explicit else resolve_native_layout_region(geometry, resolved_layout)
    )
    base_palette, effective_palette = resolve_subtitle_palettes(
        resolved_subtitle_config
    )
    json_data = {
        "schema_version": 3,
        "metadata": {
            "file_name": file_name,
            "original_path": str(input_path),
            "language": lang,
            "task": task,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model": model_name,
            "duration": segments[-1]["end"] if segments else 0.0,
            "num_segments": len(segments),
            "rendering": {
                "video_stream_index": geometry.stream_index,
                "coded_width": geometry.coded_width,
                "coded_height": geometry.coded_height,
                "render_width": geometry.render_width,
                "render_height": geometry.render_height,
                "rotation_degrees": geometry.rotation_degrees,
                "sample_aspect_ratio": _format_fraction(geometry.sample_aspect_ratio),
                "display_aspect_ratio": _format_fraction(geometry.display_aspect_ratio),
                "container_duration": geometry.duration_seconds,
                "template": {
                    "requested": template_requested,
                    "resolved": template_resolved,
                },
                "placement_mode": resolved_layout.placement_mode.value,
                "requested_position": (
                    None if explicit else requested_layout.position.value
                ),
                "resolved_position": (
                    None if explicit else resolved_layout.position.value
                ),
                "render_strategy": _line_height_render_strategy(
                    resolved_subtitle_config,
                    segments,
                ),
                "margins": {
                    "applied": not explicit,
                    "left": resolved_layout.margin_left,
                    "right": resolved_layout.margin_right,
                    "top": resolved_layout.margin_top,
                    "bottom": resolved_layout.margin_bottom,
                },
                "requested": {
                    "backdrop_type": subtitle_config.style.backdrop.kind.value,
                    "word_backdrop_type": (
                        subtitle_config.style.word_backdrop.kind.value
                    ),
                    "font_size": _format_requested_length(
                        subtitle_config.style.typography.font_size
                    ),
                    "letter_spacing": _format_requested_length(
                        subtitle_config.style.typography.letter_spacing
                    ),
                    "line_height": _format_requested_length(
                        subtitle_config.style.typography.line_height_requested
                        if subtitle_config.style.typography.line_height_requested
                        is not None
                        else subtitle_config.style.typography.line_height
                    ),
                    "backdrop_size": _format_requested_length(
                        subtitle_config.style.backdrop.size
                    ),
                    "word_backdrop_size": _format_requested_length(
                        subtitle_config.style.word_backdrop.size
                    ),
                    "shadow_size": _format_requested_length(
                        subtitle_config.style.shadow.size
                    ),
                    "margins": {
                        "left": _format_requested_length(requested_layout.margin_left),
                        "right": _format_requested_length(
                            requested_layout.margin_right
                        ),
                        "top": _format_requested_length(requested_layout.margin_top),
                        "bottom": _format_requested_length(
                            requested_layout.margin_bottom
                        ),
                    },
                    "max_width": _format_requested_length(requested_layout.max_width),
                    "max_height": _format_requested_length(requested_layout.max_height),
                },
                "resolved": {
                    "backdrop_type": (
                        resolved_subtitle_config.style.backdrop.kind.value
                    ),
                    "word_backdrop_type": (
                        resolved_subtitle_config.style.word_backdrop.kind.value
                    ),
                    "font_size": resolved_subtitle_config.style.typography.font_size,
                    "letter_spacing": (
                        resolved_subtitle_config.style.typography.letter_spacing
                    ),
                    "line_height": (
                        resolved_subtitle_config.style.typography.line_height
                    ),
                    "backdrop_size": resolved_subtitle_config.style.backdrop.size,
                    "word_backdrop_size": (
                        resolved_subtitle_config.style.word_backdrop.size
                    ),
                    "shadow_size": resolved_subtitle_config.style.shadow.size,
                    "margins": {
                        "left": resolved_layout.margin_left,
                        "right": resolved_layout.margin_right,
                        "top": resolved_layout.margin_top,
                        "bottom": resolved_layout.margin_bottom,
                    },
                    "max_width": resolved_layout.max_width,
                    "max_height": resolved_layout.max_height,
                    "line_capacity": wrapping_metrics.line_capacity,
                },
                "wrapping": {
                    "available_width": wrapping_metrics.available_width,
                    "available_height": wrapping_metrics.available_height,
                    "max_width": wrapping_metrics.max_width,
                    "max_height": wrapping_metrics.max_height,
                    "width_budget": wrapping_metrics.width_budget,
                    "line_height": wrapping_metrics.line_height,
                    "natural_line_height": wrapping_metrics.natural_line_height,
                    "resolved_line_height": wrapping_metrics.resolved_line_height,
                    "ascent": wrapping_metrics.text_measurer.ascent,
                    "descent": wrapping_metrics.text_measurer.descent,
                    "vertical_decoration": wrapping_metrics.vertical_decoration,
                    "line_capacity": wrapping_metrics.line_capacity,
                    "font_size": wrapping_metrics.font_size,
                    "letter_spacing": wrapping_metrics.letter_spacing,
                    "backdrop_size": wrapping_metrics.backdrop_size,
                    "shadow_size": wrapping_metrics.shadow_size,
                },
                "percentage_bases": {
                    "font_size": "render-height",
                    "letter_spacing": "resolved-font-size",
                    "line_height": "natural-line-height",
                    "max_width": (
                        "render-width"
                        if explicit
                        else "native-width-after-horizontal-margins"
                    ),
                    "max_height": (
                        "render-height"
                        if explicit
                        or resolved_layout.position.value
                        in {"middle-left", "center", "middle-right"}
                        else "native-height-after-active-margin"
                    ),
                    "position_x": "render-width" if explicit else None,
                    "position_y": "render-height" if explicit else None,
                },
                "text_measurement": wrapping_metrics.text_measurer.info.as_json(),
                "text_case": {
                    "requested": subtitle_config.style.typography.text_case.value,
                    "resolved": (
                        resolved_subtitle_config.style.typography.text_case.value
                    ),
                },
                "opacity": {
                    "requested": subtitle_config.style.opacity.original,
                    "percentage": _decimal_json_number(
                        resolved_subtitle_config.style.opacity.percentage
                    ),
                    "normalized": _decimal_json_number(
                        resolved_subtitle_config.style.opacity.normalized
                    ),
                    "base_colors": {
                        "text": base_palette.text_color,
                        "backdrop": base_palette.backdrop_color,
                        "word_backdrop": base_palette.word_backdrop_color,
                        "shadow": base_palette.backdrop_color,
                        "word_highlight": base_palette.highlight_color,
                    },
                    "effective_colors": {
                        "text": effective_palette.text_color,
                        "backdrop": effective_palette.backdrop_color,
                        "word_backdrop": effective_palette.word_backdrop_color,
                        "shadow": effective_palette.backdrop_color,
                        "word_highlight": effective_palette.highlight_color,
                    },
                },
                "animation": _serialize_animation_metadata(
                    resolved_subtitle_config,
                    segments,
                    karaoke_fallback_cues=karaoke_fallback_cues,
                ),
            },
        },
        "transcription": {
            "text": full_text,
            "segments": [_serializable_segment(segment) for segment in segments],
        },
    }
    rendering = json_data["metadata"]["rendering"]
    mapping_metadata = _serialize_alignment_mapping_metadata(segments)
    if mapping_metadata is not None:
        rendering["text_mapping"] = mapping_metadata
    effect_metadata = _serialize_word_effect_metadata(segments)
    if effect_metadata is not None:
        rendering["word_effects"] = effect_metadata
    if template_source != "builtin":
        rendering["template"].update(
            {
                "source": template_source,
                "schema_version": 1,
                "base": template_base,
            }
        )
    if native_region is not None:
        rendering["native_region"] = {
            "left": native_region.left,
            "top": native_region.top,
            "right": native_region.right,
            "bottom": native_region.bottom,
            "width": native_region.width,
            "height": native_region.height,
        }
    if explicit and placement is not None:
        rendering["requested_coordinates"] = {
            "x": _format_requested_length(requested_layout.position_x),
            "y": _format_requested_length(requested_layout.position_y),
            "anchor": requested_layout.anchor.value
            if requested_layout.anchor is not None
            else None,
            "coordinate_space": "playres",
        }
        rendering["resolved_coordinates"] = {
            "x": placement.position_x,
            "y": placement.position_y,
            "anchor": placement.anchor.value,
            "coordinate_space": "playres",
        }
    try:
        content = json.dumps(json_data, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ArtifactError(
            f"Could not serialize JSON transcript '{path}': {exc}"
        ) from exc
    atomic_write_text(path, f"{content}\n")


def _serialize_animation_metadata(
    config: SubtitleConfig,
    segments: Sequence[Mapping[str, Any]],
    *,
    karaoke_fallback_cues: int,
) -> dict[str, object]:
    cue = config.animation.cue

    def phase_data(phase: SubtitleAnimationPhase) -> dict[str, object]:
        data: dict[str, object] = {"type": phase.type.value}
        if phase.duration_ms:
            data["duration_ms"] = phase.duration_ms
        return data

    word = config.animation.word

    def track_data(
        track: SubtitleElementAnimation | SubtitleWordElementAnimation,
        *,
        include_mode: bool = False,
        active: bool,
    ) -> dict[str, object]:
        data: dict[str, object] = {
            "active": active,
            "entrance": phase_data(track.entrance),
            "emphasis": phase_data(track.emphasis),
            "exit": phase_data(track.exit),
        }
        if include_mode:
            if not isinstance(track, SubtitleWordElementAnimation):
                raise ArtifactError("Only word animation tracks have a mode")
            data["mode"] = track.mode.value
        return data

    shortened_cues = {}
    for element, track in (("text", cue.text), ("backdrop", cue.backdrop)):
        shortened_cues[element] = sum(
            normalize_cue_animation(
                quantize_ass_centiseconds(segment["start"]),
                quantize_ass_centiseconds(segment["end"]),
                track,
            ).shortened
            for segment in segments
        )
    shortened_words = {"text": 0, "backdrop": 0}
    for segment in segments:
        prepared = segment.get("_karaoke_cue")
        if not isinstance(prepared, KaraokeCue):
            continue
        for start, end in prepared.active_intervals:
            shortened_words["text"] += normalize_word_animation(
                start, end, word.text
            ).shortened
            shortened_words["backdrop"] += normalize_word_animation(
                start, end, word.backdrop
            ).shortened
    return {
        "cue": {
            "text": track_data(cue.text, active=True),
            "backdrop": track_data(
                cue.backdrop,
                active=config.style.backdrop.kind.value != "none",
            ),
            "shortened_cues": shortened_cues,
        },
        "word": {
            "text": track_data(word.text, include_mode=True, active=word.text.enabled),
            "backdrop": track_data(
                word.backdrop,
                include_mode=True,
                active=config.style.word_backdrop.kind.value != "none",
            ),
            "normal_color": config.style.typography.color,
            "highlight_color": config.style.typography.highlight_color,
            "shortened_words": shortened_words,
            "fallback_cues": karaoke_fallback_cues,
        },
    }


def _requires_word_timing(config: SubtitleConfig) -> bool:
    """Return whether effective rendering needs aligned word timestamps."""
    return (
        config.animation.word.text.enabled
        or config.style.word_backdrop.kind.value != "none"
    )


def _format_fraction(value: Fraction) -> str:
    return f"{value.numerator}:{value.denominator}"


def _decimal_json_number(value: Decimal) -> int | float:
    """Return a readable JSON number while retaining integral percentages."""
    return int(value) if value == value.to_integral_value() else float(value)


def _format_requested_length(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, RelativeLength):
        return value.original
    return f"{value}px"


def _line_height_render_strategy(
    config: SubtitleConfig,
    segments: Sequence[Mapping[str, Any]],
) -> str:
    return _render_strategy_for_segments(config, segments)


def _serializable_segment(segment: Mapping[str, Any]) -> dict[str, Any]:
    """Expose original and display text without internal rendering helpers."""
    serializable = {
        key: value
        for key, value in segment.items()
        if key
        not in {
            "text",
            "semantic_text",
            "display_text",
            "display_fragments",
            "_karaoke_cue",
            "_source_map",
            "_source_maps",
            "_source_record_indexes",
            "_generated_line_breaks",
            "_alignment_fallback_reason",
            "_display_groups",
            "_segmentation",
            "_word_effect",
        }
    }
    serializable["text"] = segment.get("semantic_text", segment.get("text", ""))
    serializable["display_text"] = segment.get("display_text", segment.get("text", ""))
    segmentation = segment.get("_segmentation")
    if isinstance(segmentation, Mapping):
        serializable["segmentation"] = _json_safe_mapping(segmentation)
    word_effect = segment.get("_word_effect")
    if isinstance(word_effect, Mapping):
        serializable["word_effect"] = _json_safe_mapping(word_effect)
    reason = segment.get("_alignment_fallback_reason")
    source_map = segment.get("_source_map")
    if isinstance(reason, str) and reason:
        mapping: dict[str, Any] = {
            "status": "fallback",
            "reason": reason.split(";"),
        }
        if isinstance(source_map, SubtitleSourceMap):
            mapping.update(
                {
                    "source_records": source_map.record_count,
                    "mapped_records": len(source_map.mapped_record_indexes),
                    "timed_records": len(source_map.timed_record_indexes),
                }
            )
        serializable["alignment_mapping"] = mapping
    return serializable


def _serialize_alignment_mapping_metadata(
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Aggregate mapping fallbacks without exposing transcript content."""
    fallback_segments = [
        segment
        for segment in segments
        if isinstance(segment.get("_alignment_fallback_reason"), str)
        and segment.get("_alignment_fallback_reason")
    ]
    if not fallback_segments:
        return None
    reasons: dict[str, int] = {}
    mapped_records = 0
    timed_records = 0
    source_records = 0
    for segment in fallback_segments:
        raw_reason = str(segment["_alignment_fallback_reason"])
        for reason in raw_reason.split(";"):
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
        source_map = segment.get("_source_map")
        if isinstance(source_map, SubtitleSourceMap):
            source_records += source_map.record_count
            mapped_records += len(source_map.mapped_record_indexes)
            timed_records += len(source_map.timed_record_indexes)
    return {
        "fallback_cues": len(fallback_segments),
        "source_records": source_records,
        "mapped_records": mapped_records,
        "timed_records": timed_records,
        "reasons": reasons,
    }


def _serialize_word_effect_metadata(
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Aggregate per-cue record-timed effect diagnostics."""
    diagnostics = [
        diagnostic
        for segment in segments
        if isinstance(diagnostic := segment.get("_word_effect"), Mapping)
    ]
    if not diagnostics:
        return None
    reasons: dict[str, int] = {}
    fallback_cues = 0
    for diagnostic in diagnostics:
        if diagnostic.get("status") != "fallback":
            continue
        fallback_cues += 1
        reason = diagnostic.get("fallback_reason")
        if isinstance(reason, str) and reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "units": "alignment-records",
        "cues": len(diagnostics),
        "fallback_cues": fallback_cues,
        "reasons": reasons,
    }


def _write_srt(path: Path, segments: Sequence[Mapping[str, Any]]) -> None:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                (
                    str(index),
                    f"{_format_srt_time(segment['start'])} --> "
                    f"{_format_srt_time(segment['end'])}",
                    str(segment["text"]).strip(),
                )
            )
        )
    atomic_write_text(path, "\n\n".join(blocks) + ("\n\n" if blocks else ""))


def _format_srt_time(seconds: object) -> str:
    value = _finite_time(seconds)
    if value is None:
        raise ArtifactError("SRT timestamp must be a finite, non-negative number")
    total_millis = round(value * 1000)
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def _json_safe_mapping(value: Mapping[object, object]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        safe_item = _json_safe_value(item)
        if safe_item is not _SKIP_JSON_VALUE:
            result[key] = safe_item
    return result


def _json_safe_value(value: object) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Real):
        number = float(value)
        return number if math.isfinite(number) else _SKIP_JSON_VALUE
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        safe_values = []
        for item in value:
            safe_item = _json_safe_value(item)
            if safe_item is not _SKIP_JSON_VALUE:
                safe_values.append(safe_item)
        return safe_values
    return _SKIP_JSON_VALUE


def _report(progress: ProgressReporter, message: str) -> None:
    if progress is not None:
        progress(message)


# Keep the established private helper names available to the semantic cue code and
# existing callers while sharing the exact wrapping implementation with previews.
PAUSE_BREAK_THRESHOLD = _WRAPPING_PAUSE_BREAK_THRESHOLD
_boundary_priority = _wrapping_boundary_priority
_ends_clause = _wrapping_ends_clause
_ends_sentence = _wrapping_ends_sentence
_grapheme_clusters = _wrapping_grapheme_clusters
_has_significant_pause = _wrapping_has_significant_pause
_is_cjk_or_emoji = _wrapping_is_cjk_or_emoji
_join_text_parts = _wrapping_join_text_parts
_line_count = _wrapping_line_count
_normalise_display_text = _wrapping_normalise_display_text
_split_words_for_layout = _wrapping_split_words_for_layout
_transform_display_text = _wrapping_transform_display_text
_wrap_subtitle_text = _wrapping_wrap_subtitle_text
_words_to_text = _wrapping_words_to_text
