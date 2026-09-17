"""Qwen3-ASR adapter using native Hugging Face Transformers checkpoints."""

from __future__ import annotations

import math
import wave
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
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
)
from .catalog import (
    QWEN_ALIGNMENT_LANGUAGES,
    qwen_language_code,
    qwen_language_name,
)

FORCED_ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B-hf"
MAX_ALIGNMENT_CHUNK_SECONDS = 300
MAX_NEW_TOKENS = 4096


@dataclass(frozen=True)
class _AudioChunk:
    path: Path
    start: float
    end: float


@dataclass(frozen=True)
class _TranscribedChunk:
    audio: _AudioChunk
    text: str
    language: str | None
    aligner_language: str | None


def _load_transformers() -> tuple[Any, Any, Any]:
    try:
        runtime = import_module("transformers")
    except ImportError as exc:
        raise DependencyError(
            "Hugging Face Transformers is required for --asr qwen; install "
            "multisubs[qwen]."
        ) from exc
    return (
        runtime.AutoProcessor,
        runtime.AutoModelForMultimodalLM,
        runtime.AutoModelForTokenClassification,
    )


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _finite_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric >= 0 else None


def _alignment_words(alignment: object, *, offset: float = 0.0) -> list[dict[str, Any]]:
    items = _field(alignment, "items", alignment)
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return []

    words: list[dict[str, Any]] = []
    for item in items:
        text = str(_field(item, "text", ""))
        start = _finite_time(_field(item, "start_time"))
        end = _finite_time(_field(item, "end_time"))
        if not text.strip() or start is None or end is None or end < start:
            continue
        words.append(
            {
                "word": text,
                "start": start + offset,
                "end": end + offset,
            }
        )
    return words


def _punctuation_gap(text: str) -> str | None:
    decoration = text.strip(" \t\r\n\v\f")
    if not decoration or any(character.isalnum() for character in decoration):
        return None
    return decoration


def _restore_alignment_punctuation(
    text: str, words: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Attach source punctuation omitted by the HF aligner to timed records."""
    restored = [dict(word) for word in words]
    matches: list[tuple[int, int]] = []
    cursor = 0
    for word in restored:
        raw_word = word.get("word")
        token = raw_word.strip(" \t\r\n\v\f") if isinstance(raw_word, str) else ""
        match_start = text.find(token, cursor) if token else -1
        if match_start < 0:
            return restored
        match_end = match_start + len(token)
        matches.append((match_start, match_end))
        cursor = match_end

    if not restored:
        return restored

    prefix = _punctuation_gap(text[: matches[0][0]])
    if prefix is not None:
        restored[0]["word"] = prefix + str(restored[0]["word"]).lstrip()

    for index in range(len(restored) - 1):
        gap = text[matches[index][1] : matches[index + 1][0]]
        punctuation = _punctuation_gap(gap)
        if punctuation is not None:
            restored[index]["word"] = (
                str(restored[index]["word"]).rstrip() + punctuation
            )

    suffix = _punctuation_gap(text[matches[-1][1] :])
    if suffix is not None:
        restored[-1]["word"] = str(restored[-1]["word"]).rstrip() + suffix
    return restored


def _model_options(torch: Any, device: str) -> dict[str, Any]:
    return {
        "dtype": torch.float16 if device == "cuda" else torch.float32,
        "device_map": "cuda:0" if device == "cuda" else "cpu",
    }


@contextmanager
def _wav_chunks(path: Path) -> Iterator[tuple[_AudioChunk, ...]]:
    """Yield bounded PCM WAV chunks while preserving exact source offsets."""
    with wave.open(str(path), "rb") as source:
        frame_rate = source.getframerate()
        total_frames = source.getnframes()
        frames_per_chunk = frame_rate * MAX_ALIGNMENT_CHUNK_SECONDS
        duration = total_frames / frame_rate if frame_rate else 0.0

        if total_frames <= frames_per_chunk:
            yield (_AudioChunk(path, 0.0, duration),)
            return

        params = source.getparams()
        with TemporaryDirectory(prefix="multisubs-qwen-") as directory:
            chunks: list[_AudioChunk] = []
            frame_offset = 0
            index = 0
            while frame_offset < total_frames:
                frame_count = min(frames_per_chunk, total_frames - frame_offset)
                frames = source.readframes(frame_count)
                chunk_path = Path(directory) / f"chunk-{index:04d}.wav"
                with wave.open(str(chunk_path), "wb") as target:
                    target.setparams(params)
                    target.writeframes(frames)
                chunks.append(
                    _AudioChunk(
                        chunk_path,
                        frame_offset / frame_rate,
                        (frame_offset + frame_count) / frame_rate,
                    )
                )
                frame_offset += frame_count
                index += 1
            yield tuple(chunks)


def _first_decoded(value: object, description: str) -> object:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise TranscriptionError(f"Qwen3-ASR returned invalid {description}.")
    return value[0]


def _transcribe_chunk(
    processor: Any,
    model: Any,
    torch: Any,
    chunk: _AudioChunk,
    requested_language: str | None,
) -> _TranscribedChunk:
    language_name = (
        qwen_language_name(requested_language)
        if requested_language is not None
        else None
    )
    inputs = processor.apply_transcription_request(
        audio=str(chunk.path),
        language=language_name,
    ).to(model.device, model.dtype)
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )
    generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]

    if requested_language is not None:
        decoded = processor.decode(generated_ids, return_format="transcription_only")
        decoded_text = _first_decoded(decoded, "transcription")
        if not isinstance(decoded_text, str):
            raise TranscriptionError("Qwen3-ASR returned invalid transcription text.")
        text = decoded_text.strip()
        return _TranscribedChunk(
            chunk,
            text,
            requested_language,
            qwen_language_name(requested_language),
        )

    decoded = processor.decode(generated_ids, return_format="parsed")
    parsed = _first_decoded(decoded, "parsed transcription")
    if not isinstance(parsed, Mapping):
        raise TranscriptionError("Qwen3-ASR returned an invalid parsed transcription.")
    transcription = parsed.get("transcription")
    if transcription is None:
        text = ""
    elif isinstance(transcription, str):
        text = transcription.strip()
    else:
        raise TranscriptionError("Qwen3-ASR returned invalid transcription text.")
    detected = parsed.get("language")
    if not isinstance(detected, str) or not detected.strip():
        if not text:
            return _TranscribedChunk(chunk, "", None, None)
        raise TranscriptionError(
            "Qwen3-ASR did not return a detected source language. Specify "
            "--lang CODE and retry."
        )
    language = qwen_language_code(detected)
    return _TranscribedChunk(
        chunk,
        text,
        language,
        detected,
    )


def _load_component(
    component: Any,
    model_name: str,
    options: Mapping[str, Any],
    *,
    description: str,
    progress: Any,
) -> Any:
    return load_model_with_retries(
        lambda: component.from_pretrained(model_name, **options),
        operation=description,
        progress=progress,
    )


def _align_chunk(
    processor: Any,
    model: Any,
    torch: Any,
    chunk: _TranscribedChunk,
) -> list[dict[str, Any]]:
    inputs, word_lists = processor.prepare_forced_aligner_inputs(
        audio=str(chunk.audio.path),
        transcript=chunk.text,
        language=chunk.aligner_language,
    )
    inputs = inputs.to(model.device, model.dtype)
    with torch.inference_mode():
        output = model(**inputs)
    decoded = processor.decode_forced_alignment(
        logits=output.logits,
        input_ids=inputs["input_ids"],
        word_lists=word_lists,
        timestamp_token_id=model.config.timestamp_token_id,
    )
    alignment = _first_decoded(decoded, "forced-alignment timestamps")
    return _alignment_words(alignment, offset=chunk.audio.start)


def _segment_record(
    chunk: _TranscribedChunk, words: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if words:
        return {
            "start": words[0]["start"],
            "end": words[-1]["end"],
            "text": chunk.text,
            "words": list(words),
        }
    return {
        "start": chunk.audio.start,
        "end": chunk.audio.end,
        "text": chunk.text,
    }


def _full_text(chunks: Sequence[_TranscribedChunk]) -> str:
    text = ""
    for chunk in chunks:
        if not chunk.text:
            continue
        separator = "" if not text or chunk.language in {"zh", "yue", "ja"} else " "
        text += separator + chunk.text
    return text.strip()


class QwenAdapter:
    """Transcribe and align with native Hugging Face Qwen3-ASR models."""

    backend = ASRBackend.QWEN

    def transcribe(self, request: ASRRequest) -> ASRResult:
        torch = load_torch()
        processor_type, model_type, aligner_type = _load_transformers()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_options = _model_options(torch, device)

        report(
            request.progress,
            f"Loading Qwen3-ASR model '{request.model_name}' on {device}...",
        )
        try:
            processor = _load_component(
                processor_type,
                request.model_name,
                {},
                description=f"Loading processor for '{request.model_name}'",
                progress=request.progress,
            )
            model = _load_component(
                model_type,
                request.model_name,
                model_options,
                description=f"Loading Qwen3-ASR model '{request.model_name}'",
                progress=request.progress,
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Could not load Qwen3-ASR model '{request.model_name}' on "
                f"{device}: {exc}"
            ) from exc

        report(request.progress, "Preparing 16 kHz mono audio for Qwen3-ASR...")
        try:
            with temporary_wav(request.input_path) as audio_path:
                with _wav_chunks(audio_path) as audio_chunks:
                    transcribed: list[_TranscribedChunk] = []
                    for index, audio_chunk in enumerate(audio_chunks, start=1):
                        suffix = (
                            f" ({index}/{len(audio_chunks)})"
                            if len(audio_chunks) > 1
                            else ""
                        )
                        report(
                            request.progress,
                            f"Transcribing audio with Qwen3-ASR{suffix}...",
                        )
                        transcribed.append(
                            _transcribe_chunk(
                                processor,
                                model,
                                torch,
                                audio_chunk,
                                request.language,
                            )
                        )

                    alignable = [
                        chunk
                        for chunk in transcribed
                        if chunk.text
                        and chunk.language in QWEN_ALIGNMENT_LANGUAGES
                        and chunk.aligner_language is not None
                    ]
                    aligner_processor = None
                    aligner = None
                    if alignable:
                        report(
                            request.progress,
                            f"Loading Qwen3 forced aligner '{FORCED_ALIGNER_MODEL}' "
                            f"on {device}...",
                        )
                        aligner_processor = _load_component(
                            processor_type,
                            FORCED_ALIGNER_MODEL,
                            {},
                            description=(
                                f"Loading processor for '{FORCED_ALIGNER_MODEL}'"
                            ),
                            progress=request.progress,
                        )
                        aligner = _load_component(
                            aligner_type,
                            FORCED_ALIGNER_MODEL,
                            model_options,
                            description=(
                                f"Loading Qwen3 forced aligner '{FORCED_ALIGNER_MODEL}'"
                            ),
                            progress=request.progress,
                        )

                    segments: list[Mapping[str, Any]] = []
                    for chunk in transcribed:
                        if not chunk.text:
                            continue
                        words: list[dict[str, Any]] = []
                        if (
                            chunk.language in QWEN_ALIGNMENT_LANGUAGES
                            and chunk.aligner_language is not None
                        ):
                            assert aligner_processor is not None and aligner is not None
                            report(
                                request.progress,
                                f"Aligning Qwen3-ASR transcript as "
                                f"{chunk.aligner_language}...",
                            )
                            words = _align_chunk(
                                aligner_processor,
                                aligner,
                                torch,
                                chunk,
                            )
                            words = _restore_alignment_punctuation(chunk.text, words)
                        segments.append(_segment_record(chunk, words))
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Could not transcribe '{request.input_path}' with Qwen3-ASR: {exc}"
            ) from exc

        if request.language is not None:
            language = request.language
        else:
            languages = [
                chunk.language
                for chunk in transcribed
                if chunk.text and chunk.language is not None
            ]
            if languages:
                language = Counter(languages).most_common(1)[0][0]
            else:
                raise TranscriptionError(
                    "Qwen3-ASR did not return a detected source language. Specify "
                    "--lang CODE and retry."
                )
        if language is None:
            raise TranscriptionError(
                "Qwen3-ASR did not return a detected source language. Specify "
                "--lang CODE and retry."
            )
        return ASRResult(language, _full_text(transcribed), tuple(segments))
