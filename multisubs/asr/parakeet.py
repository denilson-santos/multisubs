"""NVIDIA Parakeet adapter using NeMo word and segment timestamps."""

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


def _load_nemo_asr() -> Any:
    try:
        import nemo.collections.asr as nemo_asr
    except ImportError as exc:
        raise DependencyError(
            "NVIDIA NeMo ASR is required for --asr parakeet; install "
            "multisubs[parakeet]."
        ) from exc
    return nemo_asr


def _timestamp_mapping(hypothesis: object) -> Mapping[str, Any]:
    value = getattr(hypothesis, "timestamp", None)
    if not isinstance(value, Mapping):
        value = getattr(hypothesis, "timestep", None)
    return value if isinstance(value, Mapping) else {}


def _stamp_value(stamp: object, key: str, default: object = None) -> object:
    if isinstance(stamp, Mapping):
        return stamp.get(key, default)
    return getattr(stamp, key, default)


def _word_record(stamp: object) -> dict[str, Any]:
    return {
        "word": str(_stamp_value(stamp, "word", _stamp_value(stamp, "text", ""))),
        "start": _stamp_value(stamp, "start"),
        "end": _stamp_value(stamp, "end"),
    }


def _words_for_segment(
    words: Sequence[dict[str, Any]], start: object, end: object
) -> list[dict[str, Any]]:
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return []
    return [
        word
        for word in words
        if isinstance(word.get("start"), (int, float))
        and isinstance(word.get("end"), (int, float))
        and float(start) <= (float(word["start"]) + float(word["end"])) / 2 < float(end)
    ]


def _normalise_hypothesis(
    hypothesis: object, duration: float
) -> tuple[str, tuple[Mapping[str, Any], ...]]:
    text = str(
        getattr(hypothesis, "text", hypothesis if isinstance(hypothesis, str) else "")
    ).strip()
    timestamps = _timestamp_mapping(hypothesis)
    raw_words = timestamps.get("word", ())
    words = (
        [_word_record(word) for word in raw_words]
        if isinstance(raw_words, Sequence) and not isinstance(raw_words, (str, bytes))
        else []
    )
    raw_segments = timestamps.get("segment", ())
    segments: list[Mapping[str, Any]] = []
    if isinstance(raw_segments, Sequence) and not isinstance(
        raw_segments, (str, bytes)
    ):
        for stamp in raw_segments:
            start = _stamp_value(stamp, "start")
            end = _stamp_value(stamp, "end")
            segment_text = str(
                _stamp_value(stamp, "segment", _stamp_value(stamp, "text", ""))
            )
            record: dict[str, Any] = {
                "start": start,
                "end": end,
                "text": segment_text,
            }
            segment_words = _words_for_segment(words, start, end)
            if segment_words:
                record["words"] = segment_words
            segments.append(record)
    if not segments and text:
        end = words[-1]["end"] if words else duration
        record = {"start": 0.0, "end": end, "text": text}
        if words:
            record["words"] = words
        segments.append(record)
    return text, tuple(segments)


class ParakeetAdapter:
    """Transcribe 16 kHz mono audio with Parakeet through NVIDIA NeMo."""

    backend = ASRBackend.PARAKEET

    def transcribe(self, request: ASRRequest) -> ASRResult:
        torch = load_torch()
        nemo_asr = _load_nemo_asr()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        report(
            request.progress,
            f"Loading Parakeet model '{request.model_name}' on {device}...",
        )
        try:
            model = load_model_with_retries(
                lambda: nemo_asr.models.ASRModel.from_pretrained(
                    model_name=request.model_name
                ),
                operation=f"Loading Parakeet model '{request.model_name}'",
                progress=request.progress,
            )
            model = model.to(device)
            model.eval()
        except Exception as exc:
            raise TranscriptionError(
                f"Could not load Parakeet model '{request.model_name}' on "
                f"{device}: {exc}"
            ) from exc

        report(request.progress, "Preparing 16 kHz mono audio for Parakeet...")
        with temporary_wav(request.input_path) as audio_path:
            report(request.progress, "Transcribing audio with Parakeet...")
            try:
                output = model.transcribe(
                    [str(audio_path)], timestamps=True, verbose=request.verbose
                )
                hypothesis = output[0]
            except Exception as exc:
                raise TranscriptionError(
                    f"Could not transcribe '{request.input_path}' with Parakeet: {exc}"
                ) from exc
            text, segments = _normalise_hypothesis(hypothesis, wav_duration(audio_path))
        return ASRResult(request.language, text, segments)
