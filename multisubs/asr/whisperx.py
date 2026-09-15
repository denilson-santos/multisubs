"""WhisperX adapter preserving the established alignment behavior."""

from __future__ import annotations

from typing import Any

from ..errors import DependencyError, TranscriptionError
from .base import (
    ASRBackend,
    ASRRequest,
    ASRResult,
    full_text_from_segments,
    load_model_with_retries,
    load_torch,
    report,
    require_mapping,
    require_sequence,
    select_compute_configuration,
)
from .catalog import validate_result_language

MAX_TRANSLATION_CHUNK_SECONDS = 6


def _load_whisperx() -> Any:
    try:
        import whisperx
    except ImportError as exc:
        raise DependencyError(
            "WhisperX is required for --asr whisperx; install multisubs[whisperx]."
        ) from exc
    return whisperx


class WhisperXAdapter:
    """Transcribe with WhisperX and align source-language words."""

    backend = ASRBackend.WHISPERX

    def transcribe(self, request: ASRRequest) -> ASRResult:
        torch = load_torch()
        whisperx = _load_whisperx()
        device, compute_type = select_compute_configuration(torch)
        report(
            request.progress,
            f"Loading WhisperX model '{request.model_name}' on {device} "
            f"({compute_type})...",
        )
        try:
            model = load_model_with_retries(
                lambda: whisperx.load_model(
                    request.model_name,
                    device,
                    compute_type=compute_type,
                    language=request.language,
                    task=request.task,
                ),
                operation=f"Loading WhisperX model '{request.model_name}'",
                progress=request.progress,
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Could not load WhisperX model '{request.model_name}' on "
                f"{device}: {exc}"
            ) from exc

        report(request.progress, "Transcribing audio with WhisperX...")
        try:
            audio = whisperx.load_audio(str(request.input_path))
            options: dict[str, object] = {
                "language": request.language,
                "task": request.task,
            }
            if request.task == "translate":
                options["chunk_size"] = MAX_TRANSLATION_CHUNK_SECONDS
            raw_result = model.transcribe(audio, **options)
        except Exception as exc:
            raise TranscriptionError(
                f"Could not transcribe '{request.input_path}' with WhisperX: {exc}"
            ) from exc

        result = require_mapping(raw_result, "transcription result", self.backend)
        raw_segments = require_sequence(
            result.get("segments"), "transcription segments", self.backend
        )
        language_value = request.language or result.get("language")
        if not isinstance(language_value, str) or not language_value:
            raise TranscriptionError(
                "WhisperX did not return a detected source language. Specify "
                "--lang CODE and retry."
            )
        language = validate_result_language(self.backend, language_value)

        segments = raw_segments
        if request.task != "translate":
            report(request.progress, "Aligning words with WhisperX...")
            try:
                align_model, align_metadata = load_model_with_retries(
                    lambda: whisperx.load_align_model(
                        language_code=language,
                        device=device,
                    ),
                    operation=f"Loading WhisperX alignment model for '{language}'",
                    progress=request.progress,
                )
                aligned = whisperx.align(
                    raw_segments,
                    align_model,
                    align_metadata,
                    audio,
                    device,
                    return_char_alignments=False,
                )
            except Exception as exc:
                raise TranscriptionError(
                    f"Could not align transcript words for '{request.input_path}' "
                    f"with WhisperX: {exc}"
                ) from exc
            aligned_result = require_mapping(aligned, "alignment result", self.backend)
            segments = require_sequence(
                aligned_result.get("segments"), "aligned segments", self.backend
            )

        normalized_segments = tuple(
            require_mapping(segment, "segment", self.backend) for segment in segments
        )
        text = result.get("text")
        full_text = (
            text.strip()
            if isinstance(text, str) and text.strip()
            else full_text_from_segments(normalized_segments)
        )
        return ASRResult(language, full_text, normalized_segments)
