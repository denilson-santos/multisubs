"""Faster-Whisper adapter with native segment and word timestamps."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ..errors import DependencyError, TranscriptionError
from .base import (
    ASRBackend,
    ASRRequest,
    ASRResult,
    load_model_with_retries,
    report,
)
from .catalog import validate_result_language

MAX_TRANSLATION_CHUNK_SECONDS = 6


def _load_faster_whisper() -> tuple[Any, Any]:
    try:
        runtime = import_module("faster_whisper")
        ctranslate2 = import_module("ctranslate2")
    except ImportError as exc:
        raise DependencyError(
            "Faster-Whisper is required for --asr faster-whisper; install "
            "multisubs[faster-whisper]."
        ) from exc
    return runtime.WhisperModel, ctranslate2


def _word_record(word: object) -> dict[str, Any]:
    return {
        "word": str(getattr(word, "word", "")),
        "start": getattr(word, "start", None),
        "end": getattr(word, "end", None),
        "score": getattr(word, "probability", None),
    }


def _segment_record(segment: object, *, include_words: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "start": getattr(segment, "start", None),
        "end": getattr(segment, "end", None),
        "text": str(getattr(segment, "text", "")),
    }
    words = getattr(segment, "words", None)
    if include_words and words is not None:
        record["words"] = [_word_record(word) for word in words]
    return record


class FasterWhisperAdapter:
    """Transcribe directly with CTranslate2-backed Faster-Whisper."""

    backend = ASRBackend.FASTER_WHISPER

    def transcribe(self, request: ASRRequest) -> ASRResult:
        model_type, ctranslate2 = _load_faster_whisper()
        try:
            device = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        except Exception as exc:
            raise DependencyError(
                f"Could not determine CTranslate2 compute availability: {exc}"
            ) from exc
        compute_type = "float16" if device == "cuda" else "int8"
        report(
            request.progress,
            f"Loading Faster-Whisper model '{request.model_name}' on {device} "
            f"({compute_type})...",
        )
        try:
            model = load_model_with_retries(
                lambda: model_type(
                    request.model_name,
                    device=device,
                    compute_type=compute_type,
                ),
                operation=f"Loading Faster-Whisper model '{request.model_name}'",
                progress=request.progress,
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Could not load Faster-Whisper model '{request.model_name}' on "
                f"{device}: {exc}"
            ) from exc

        report(request.progress, "Transcribing audio with Faster-Whisper...")
        try:
            options: dict[str, Any] = {
                "language": request.language,
                "task": request.task,
                "word_timestamps": request.task == "transcribe",
                "vad_filter": True,
            }
            if request.task == "translate":
                # Faster-Whisper calls WhisperX's translation chunk boundary
                # ``chunk_length``. Keep both translation paths at six seconds
                # before the layout-level font fallback is considered.
                options["chunk_length"] = MAX_TRANSLATION_CHUNK_SECONDS
            segment_stream, info = model.transcribe(str(request.input_path), **options)
            segments = tuple(
                _segment_record(
                    segment,
                    include_words=request.task == "transcribe",
                )
                for segment in segment_stream
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Could not transcribe '{request.input_path}' with "
                f"Faster-Whisper: {exc}"
            ) from exc

        language_value = request.language or getattr(info, "language", None)
        if not isinstance(language_value, str) or not language_value:
            raise TranscriptionError(
                "Faster-Whisper did not return a detected source language. "
                "Specify --lang CODE and retry."
            )
        language = validate_result_language(self.backend, language_value)
        text = "".join(str(segment.get("text", "")) for segment in segments).strip()
        return ASRResult(language, text, segments)
