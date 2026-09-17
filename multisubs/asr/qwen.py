"""Qwen3-ASR adapter using native Hugging Face Transformers checkpoints."""

from __future__ import annotations

import math
import sys
import wave
from array import array
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
MAX_ALIGNMENT_CHUNK_SECONDS = 180
MAX_NEW_TOKENS = 4096
CHUNK_BOUNDARY_SEARCH_SECONDS = 5
CHUNK_ENERGY_WINDOW_MILLISECONDS = 100


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
    dtype = torch.float32
    if device == "cuda":
        dtype = torch.float16
        is_bf16_supported = getattr(torch.cuda, "is_bf16_supported", None)
        bfloat16 = getattr(torch, "bfloat16", None)
        try:
            if (
                callable(is_bf16_supported)
                and is_bf16_supported()
                and bfloat16 is not None
            ):
                dtype = bfloat16
        except Exception:
            pass
    return {
        "dtype": dtype,
        "device_map": "cuda:0" if device == "cuda" else "cpu",
    }


def _window_energy(
    frames: object,
    *,
    frame_start: int,
    frame_count: int,
    channels: int,
    sample_width: int,
) -> int:
    if sample_width != 2:
        raise TranscriptionError(
            "Qwen3-ASR chunking requires 16-bit PCM audio from FFmpeg."
        )
    if isinstance(frames, bytes):
        byte_start = frame_start * channels * sample_width
        byte_end = byte_start + frame_count * channels * sample_width
        window = frames[byte_start:byte_end]
    else:
        setpos = getattr(frames, "setpos", None)
        readframes = getattr(frames, "readframes", None)
        if not callable(setpos) or not callable(readframes):
            raise TranscriptionError("Qwen3-ASR received an invalid WAV reader.")
        setpos(frame_start)
        window = readframes(frame_count)
        if not isinstance(window, bytes):
            raise TranscriptionError("Qwen3-ASR received invalid WAV frames.")
    samples = array("h")
    samples.frombytes(window)
    if sys.byteorder != "little":
        samples.byteswap()
    return sum(abs(sample) for sample in samples)


def _low_energy_boundary(
    frames: object,
    *,
    start: int,
    target: int,
    total_frames: int,
    frame_rate: int,
    channels: int,
    sample_width: int,
) -> int:
    """Find a quiet boundary near a target frame without changing coverage."""
    search_frames = frame_rate * CHUNK_BOUNDARY_SEARCH_SECONDS
    window_frames = max(1, frame_rate * CHUNK_ENERGY_WINDOW_MILLISECONDS // 1000)
    left = max(start + 1, target - search_frames)
    # Keep the hard chunk ceiling even when the quietest nearby window is
    # just after the nominal target.
    right = min(total_frames, target)
    last_window_start = right - window_frames
    if last_window_start < left:
        return target

    step = max(1, window_frames // 4)
    best_boundary = target
    best_energy: int | None = None
    best_distance = total_frames
    for window_start in range(left, last_window_start + 1, step):
        energy = _window_energy(
            frames,
            frame_start=window_start,
            frame_count=window_frames,
            channels=channels,
            sample_width=sample_width,
        )
        boundary = window_start + window_frames
        distance = abs(boundary - target)
        if best_energy is None or (energy, distance) < (best_energy, best_distance):
            best_energy = energy
            best_distance = distance
            best_boundary = boundary

    if last_window_start > left and (last_window_start - left) % step:
        energy = _window_energy(
            frames,
            frame_start=last_window_start,
            frame_count=window_frames,
            channels=channels,
            sample_width=sample_width,
        )
        boundary = last_window_start + window_frames
        distance = abs(boundary - target)
        if best_energy is None or (energy, distance) < (best_energy, best_distance):
            best_boundary = boundary
    return max(start + 1, min(total_frames, best_boundary))


@contextmanager
def _wav_chunks(path: Path) -> Iterator[tuple[_AudioChunk, ...]]:
    """Yield quiet-boundary PCM WAV chunks preserving exact source offsets."""
    with wave.open(str(path), "rb") as source:
        frame_rate = source.getframerate()
        total_frames = source.getnframes()
        duration = total_frames / frame_rate if frame_rate else 0.0
        if frame_rate <= 0:
            raise TranscriptionError("Qwen3-ASR audio has an invalid sample rate.")

        max_frames = frame_rate * MAX_ALIGNMENT_CHUNK_SECONDS
        if total_frames <= max_frames:
            yield (_AudioChunk(path, 0.0, duration),)
            return

        params = source.getparams()
        boundaries = [0]
        start = 0
        while total_frames - start > max_frames:
            target = start + max_frames
            boundary = _low_energy_boundary(
                source,
                start=start,
                target=target,
                total_frames=total_frames,
                frame_rate=frame_rate,
                channels=params.nchannels,
                sample_width=params.sampwidth,
            )
            boundaries.append(boundary)
            start = boundary
        boundaries.append(total_frames)

        with TemporaryDirectory(prefix="multisubs-qwen-") as directory:
            chunks: list[_AudioChunk] = []
            for index, (start, end) in enumerate(
                zip(boundaries[:-1], boundaries[1:], strict=True)
            ):
                source.setpos(start)
                chunk_frames = source.readframes(end - start)
                chunk_path = Path(directory) / f"chunk-{index:04d}.wav"
                with wave.open(str(chunk_path), "wb") as target:
                    target.setparams(params)
                    target.writeframes(chunk_frames)
                chunks.append(
                    _AudioChunk(
                        chunk_path,
                        start / frame_rate,
                        end / frame_rate,
                    )
                )
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

                    # The autoregressive ASR model is no longer needed while
                    # the independent forced aligner is loaded.
                    model = None
                    if device == "cuda":
                        import gc

                        gc.collect()
                        torch.cuda.empty_cache()

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
