"""Qwen3-ASR adapter with optional official forced alignment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import DependencyError, TranscriptionError
from .base import (
    ASRBackend,
    ASRRequest,
    ASRResult,
    load_model_with_retries,
    load_torch,
    report,
    temporary_wav,
    wav_duration,
)
from .catalog import (
    QWEN_ALIGNMENT_LANGUAGES,
    qwen_language_code,
    qwen_language_name,
)

FORCED_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"


def _load_qwen_asr() -> Any:
    try:
        from qwen_asr import Qwen3ASRModel
    except ImportError as exc:
        raise DependencyError(
            "Qwen3-ASR is required for --asr qwen; install multisubs[qwen]."
        ) from exc
    return Qwen3ASRModel


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _alignment_words(alignment: object) -> list[dict[str, Any]]:
    items = _field(alignment, "items", ())
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return []
    return [
        {
            "word": str(_field(item, "text", "")),
            "start": _field(item, "start_time"),
            "end": _field(item, "end_time"),
        }
        for item in items
    ]


def _model_options(torch: Any, device: str) -> dict[str, Any]:
    return {
        "dtype": torch.float16 if device == "cuda" else torch.float32,
        "device_map": "cuda:0" if device == "cuda" else "cpu",
    }


class QwenAdapter:
    """Transcribe with Qwen3-ASR and align supported source languages."""

    backend = ASRBackend.QWEN

    def transcribe(self, request: ASRRequest) -> ASRResult:
        torch = load_torch()
        model_type = _load_qwen_asr()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_options = _model_options(torch, device)
        use_alignment = request.language in QWEN_ALIGNMENT_LANGUAGES
        if use_alignment:
            model_options.update(
                forced_aligner=FORCED_ALIGNER_MODEL,
                forced_aligner_kwargs=_model_options(torch, device),
            )
        report(
            request.progress,
            f"Loading Qwen3-ASR model '{request.model_name}' on {device}...",
        )
        try:
            model = load_model_with_retries(
                lambda: model_type.from_pretrained(
                    request.model_name,
                    **model_options,
                    max_inference_batch_size=1,
                ),
                operation=f"Loading Qwen3-ASR model '{request.model_name}'",
                progress=request.progress,
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Could not load Qwen3-ASR model '{request.model_name}' on "
                f"{device}: {exc}"
            ) from exc

        forced_language = (
            qwen_language_name(request.language)
            if request.language is not None
            else None
        )
        report(request.progress, "Preparing 16 kHz mono audio for Qwen3-ASR...")
        with temporary_wav(request.input_path) as audio_path:
            report(request.progress, "Transcribing audio with Qwen3-ASR...")
            try:
                output = model.transcribe(
                    audio=str(audio_path),
                    language=forced_language,
                    return_time_stamps=use_alignment,
                )
                result = output[0]
            except Exception as exc:
                raise TranscriptionError(
                    f"Could not transcribe '{request.input_path}' with Qwen3-ASR: {exc}"
                ) from exc

            text = str(_field(result, "text", "")).strip()
            detected = _field(result, "language")
            if request.language is not None:
                language = request.language
            elif isinstance(detected, str) and detected:
                language = qwen_language_code(detected)
            else:
                raise TranscriptionError(
                    "Qwen3-ASR did not return a detected source language. Specify "
                    "--lang CODE and retry."
                )

            words = _alignment_words(_field(result, "time_stamps")) if text else []

            segments: tuple[Mapping[str, Any], ...] = ()
            if text:
                end = words[-1]["end"] if words else wav_duration(audio_path)
                segment: dict[str, Any] = {
                    "start": words[0]["start"] if words else 0.0,
                    "end": end,
                    "text": text,
                }
                if words:
                    segment["words"] = words
                segments = (segment,)
        return ASRResult(language, text, segments)
