"""WhisperX transcription, cue construction, and artifact coordination."""

from __future__ import annotations

import json
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
from numbers import Real
from pathlib import Path
from typing import Any, cast

from .ass import write_ass
from .config import (
    DEFAULT_STYLE as _DEFAULT_STYLE,
)
from .config import (
    MODELS as _MODELS,
)
from .config import validate_subtitle_config
from .errors import ArtifactError, DependencyError, TranscriptionError, ValidationError
from .layout import resolve_safe_rectangle, resolve_subtitle_config
from .models import (
    RelativeLength,
    SubtitleConfig,
    SubtitlePosition,
    TranscriptDocument,
    TranscriptionPaths,
    VideoGeometry,
)
from .utils import atomic_write_text, find_unique_stem

MAX_CHARS_PER_LINE = 42
MAX_CHARS_PER_CUE = MAX_CHARS_PER_LINE * 2
MAX_LINE_OVERFLOW = 6
MIN_CHARS_PER_LINE = 15
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

# Keep shared configuration constants available from the transcriber while
# their canonical definitions remain in config.py.
DEFAULT_STYLE = _DEFAULT_STYLE
MODELS = _MODELS


def generate_transcriptions(
    input_path: str | Path,
    output_dir: str | Path,
    style_options: SubtitleConfig | Mapping[str, str | int] | None = None,
    lang: str = "en",
    task: str = "transcribe",
    model_name: str = "turbo",
    *,
    position: SubtitlePosition | str | None = None,
    progress: ProgressReporter = None,
) -> tuple[str, str, str]:
    """Generate JSON, SRT, and ASS files for one local video.

    The established tuple return value is preserved for programmatic callers.
    Heavy runtime dependencies are loaded only after the input and output have
    been validated.
    """
    source_path = _normalise_input_path(input_path)
    destination_dir = _normalise_output_dir(output_dir)
    subtitle_config = validate_subtitle_config(style_options, position=position)
    from .subtitler import probe_video_geometry

    geometry = probe_video_geometry(source_path)
    resolved_config = resolve_subtitle_config(subtitle_config, geometry)
    document = transcribe_video(
        source_path,
        lang=lang,
        task=task,
        model_name=model_name,
        progress=progress,
    )
    return write_transcription_artifacts(
        document,
        destination_dir,
        subtitle_config,
        geometry=geometry,
        resolved_subtitle_config=resolved_config,
        progress=progress,
    )


def transcribe_video(
    input_path: str | Path,
    lang: str = "en",
    task: str = "transcribe",
    model_name: str = "turbo",
    *,
    progress: ProgressReporter = None,
) -> TranscriptDocument:
    """Transcribe and align one video without serializing output artifacts."""
    source_path = _normalise_input_path(input_path)

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
    detected_language = _result_language(result_mapping, lang)

    _report(progress, "Aligning words for subtitle timing...")
    try:
        align_model, align_metadata = _load_model_with_retries(
            lambda: whisperx.load_align_model(
                language_code=detected_language,
                device=device,
            ),
            operation=f"Loading alignment model for '{detected_language}'",
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
    segments = _build_subtitle_segments(aligned_segments)
    _validate_subtitle_segments(segments)

    full_text = _result_full_text(result_mapping, segments)
    return TranscriptDocument(
        source_path=source_path,
        language=lang,
        task=task,
        model_name=model_name,
        full_text=full_text,
        segments=tuple(segments),
    )


def write_transcription_artifacts(
    document: TranscriptDocument,
    output_dir: str | Path,
    subtitle_config: SubtitleConfig | Mapping[str, str | int] | None = None,
    *,
    geometry: VideoGeometry | None = None,
    resolved_subtitle_config: SubtitleConfig | None = None,
    progress: ProgressReporter = None,
) -> tuple[str, str, str]:
    """Serialize one semantic transcript as JSON, SRT, and ASS artifacts."""
    destination_dir = _normalise_output_dir(output_dir)
    config = validate_subtitle_config(subtitle_config)
    if geometry is None:
        from .subtitler import probe_video_geometry

        geometry = probe_video_geometry(document.source_path)
    resolved_config = resolve_subtitle_config(
        resolved_subtitle_config or config,
        geometry,
    )
    _validate_subtitle_segments(document.segments)
    paths = _choose_transcription_paths(
        destination_dir,
        document.source_path.stem,
        document.language,
    )

    _write_json(
        paths.json_path,
        full_text=document.full_text,
        segments=document.segments,
        file_name=document.source_path.stem,
        lang=document.language,
        input_path=document.source_path,
        task=document.task,
        model_name=document.model_name,
        subtitle_config=config,
        resolved_subtitle_config=resolved_config,
        geometry=geometry,
    )
    _report(progress, "Completed JSON transcript.")

    _write_srt(paths.srt_path, document.segments)
    _report(progress, "Completed SRT transcript.")

    write_ass(paths.ass_path, document.segments, resolved_config, geometry)
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


def _result_language(result: Mapping[str, Any], requested_language: str) -> str:
    language = result.get("language")
    return language if isinstance(language, str) and language else requested_language


def _result_full_text(
    result: Mapping[str, Any], segments: Sequence[Mapping[str, Any]]
) -> str:
    text = result.get("text")
    if isinstance(text, str) and text.strip():
        return _normalise_display_text(text)
    return " ".join(segment["text"].replace("\n", " ") for segment in segments).strip()


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
) -> list[dict[str, Any]]:
    """Build readable cues from WhisperX word timestamps and coarse fallbacks."""
    cues: list[dict[str, Any]] = []
    pending_words: list[dict[str, Any]] = []

    for raw_segment in aligned_segments:
        segment = _require_mapping(raw_segment, "aligned segment")
        words = _timed_words(segment)
        if words:
            _validate_word_order(pending_words, words)
            pending_words.extend(words)
            continue

        if pending_words:
            cues.extend(_build_cues_from_words(pending_words))
            pending_words = []

        start, end = _segment_times(segment)
        _append_cue(cues, segment.get("text", ""), start, end, [])

    if pending_words:
        cues.extend(_build_cues_from_words(pending_words))

    for index, cue in enumerate(cues):
        cue["id"] = index
    return cues


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
    previous_words: Sequence[Mapping[str, Any]],
    next_words: Sequence[Mapping[str, Any]],
) -> None:
    words = [*previous_words, *next_words]
    previous_start: float | None = None
    for word in words:
        start = _finite_time(word.get("start"))
        end = _finite_time(word.get("end"))
        if start is None or end is None or end < start:
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


def _build_cues_from_words(words: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    current_words: list[dict[str, Any]] = []

    for word in words:
        if current_words and _has_significant_pause(current_words[-1], word):
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

        if current_words and _ends_sentence(str(current_words[-1].get("word", ""))):
            _append_words_cue(cues, current_words)
            current_words = []

    if current_words:
        _append_words_cue(cues, current_words)
    return cues


def _append_words_cue(
    cues: list[dict[str, Any]], words: Sequence[dict[str, Any]]
) -> None:
    if not words:
        return
    _append_cue(
        cues,
        _words_to_text(words),
        float(words[0]["start"]),
        float(words[-1]["end"]),
        list(words),
    )


def _cue_exceeds_limits(words: Sequence[Mapping[str, Any]]) -> bool:
    return (
        len(_words_to_text(words)) > MAX_CHARS_PER_CUE
        or _words_duration(words) > MAX_CUE_DURATION
    )


def _words_duration(words: Sequence[Mapping[str, Any]]) -> float:
    return float(words[-1]["end"]) - float(words[0]["start"])


def _find_best_cue_break(words: Sequence[Mapping[str, Any]]) -> int:
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
        character_distance = abs(MAX_CHARS_PER_CUE - len(_words_to_text(prefix)))
        duration_distance = abs(MAX_CUE_DURATION - _words_duration(prefix))
        distance = (
            character_distance / MAX_CHARS_PER_CUE
            + duration_distance / MAX_CUE_DURATION
        )
        return (_boundary_priority(words, index), -distance)

    return max(candidates, key=key)


def _append_cue(
    cues: list[dict[str, Any]],
    text: object,
    start: float,
    end: float,
    words: Sequence[Mapping[str, Any]],
) -> None:
    if not isinstance(text, str):
        return
    normalised_text = _normalise_display_text(text)
    if not normalised_text:
        return
    if end < start or start < 0:
        raise TranscriptionError("Subtitle cue has invalid timestamps")
    cues.append(
        {
            "id": len(cues),
            "start": start,
            "end": end,
            "text": _wrap_subtitle_text(normalised_text, words),
            "words": [dict(word) for word in words],
        }
    )


def _words_to_text(words: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(str(word["word"]).strip() for word in words).strip()


def _ends_sentence(word: str) -> bool:
    return word.rstrip().endswith((".", "!", "?", "…"))


def _ends_clause(word: str) -> bool:
    return word.rstrip().endswith((",", ";", ":", "—", "–"))


def _has_significant_pause(
    previous_word: Mapping[str, Any], next_word: Mapping[str, Any]
) -> bool:
    previous_end = _finite_time(previous_word.get("end"))
    next_start = _finite_time(next_word.get("start"))
    return (
        previous_end is not None
        and next_start is not None
        and next_start - previous_end >= PAUSE_BREAK_THRESHOLD
    )


def _boundary_priority(words: Sequence[Mapping[str, Any]], index: int) -> int:
    previous_word = words[index - 1]
    next_word = words[index]
    previous_text = str(previous_word.get("word", ""))
    if _ends_sentence(previous_text):
        return 3
    if _ends_clause(previous_text):
        return 2
    if _has_significant_pause(previous_word, next_word):
        return 1
    return 0


def _normalise_display_text(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def _wrap_subtitle_text(
    text: str,
    words: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Wrap one cue to at most two visual lines at a semantic boundary."""
    if len(text) <= MAX_CHARS_PER_LINE:
        return text

    if words:
        line_words = [word for word in words if str(word.get("word", "")).strip()]
    else:
        line_words = [{"word": word} for word in text.split()]
    if len(line_words) < 2:
        return text

    def key(index: int) -> tuple[int, int, int, int, int, int]:
        left = _words_to_text(line_words[:index])
        right = _words_to_text(line_words[index:])
        left_overflow = max(0, len(left) - MAX_CHARS_PER_LINE)
        right_overflow = max(0, len(right) - MAX_CHARS_PER_LINE)
        hard_overflow = max(0, left_overflow - MAX_LINE_OVERFLOW) + max(
            0, right_overflow - MAX_LINE_OVERFLOW
        )
        shortest_line = min(len(left), len(right))
        short_line_penalty = max(0, MIN_CHARS_PER_LINE - shortest_line) ** 2
        return (
            hard_overflow,
            short_line_penalty,
            left_overflow + right_overflow,
            -len(left),
            -_boundary_priority(line_words, index),
            abs(len(left) - len(right)),
        )

    break_at = min(range(1, len(line_words)), key=key)
    return (
        f"{_words_to_text(line_words[:break_at])}\n"
        f"{_words_to_text(line_words[break_at:])}"
    )


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
) -> None:
    requested_layout = subtitle_config.layout
    resolved_layout = resolved_subtitle_config.layout
    safe_rectangle = resolve_safe_rectangle(geometry, resolved_layout)
    json_data = {
        "schema_version": 1,
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
                "requested_position": requested_layout.position.value,
                "resolved_position": resolved_layout.position.value,
                "margins": {
                    "left": resolved_layout.margin_left,
                    "right": resolved_layout.margin_right,
                    "top": resolved_layout.margin_top,
                    "bottom": resolved_layout.margin_bottom,
                },
                "requested": {
                    "font_size": _format_requested_length(
                        subtitle_config.appearance.font_size
                    ),
                    "backdrop_size": _format_requested_length(
                        subtitle_config.appearance.outline_weight
                    ),
                    "shadow_size": _format_requested_length(
                        subtitle_config.appearance.shadow_weight
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
                },
                "resolved": {
                    "font_size": resolved_subtitle_config.appearance.font_size,
                    "backdrop_size": resolved_subtitle_config.appearance.outline_weight,
                    "shadow_size": resolved_subtitle_config.appearance.shadow_weight,
                    "margins": {
                        "left": resolved_layout.margin_left,
                        "right": resolved_layout.margin_right,
                        "top": resolved_layout.margin_top,
                        "bottom": resolved_layout.margin_bottom,
                    },
                },
                "safe_rectangle": {
                    "left": safe_rectangle.left,
                    "top": safe_rectangle.top,
                    "right": safe_rectangle.right,
                    "bottom": safe_rectangle.bottom,
                    "width": safe_rectangle.width,
                    "height": safe_rectangle.height,
                },
            },
        },
        "transcription": {"text": full_text, "segments": list(segments)},
    }
    try:
        content = json.dumps(json_data, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ArtifactError(
            f"Could not serialize JSON transcript '{path}': {exc}"
        ) from exc
    atomic_write_text(path, f"{content}\n")


def _format_fraction(value: Fraction) -> str:
    return f"{value.numerator}:{value.denominator}"


def _format_requested_length(value: object) -> str:
    if isinstance(value, RelativeLength):
        return value.original
    return f"{value}px"


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
