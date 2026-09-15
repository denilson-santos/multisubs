"""Shared contracts and utilities for local ASR adapters."""

from __future__ import annotations

import time
import wave
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from ..errors import DependencyError, TranscriptionError

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


class ASRBackend(str, Enum):
    """Supported local speech-recognition implementations."""

    WHISPERX = "whisperx"
    FASTER_WHISPER = "faster-whisper"
    PARAKEET = "parakeet"
    QWEN = "qwen"


@dataclass(frozen=True)
class ASRRequest:
    """One validated request passed to a concrete ASR adapter."""

    input_path: Path
    language: str | None
    task: str
    model_name: str
    progress: ProgressReporter = None


@dataclass(frozen=True)
class ASRResult:
    """Backend-neutral transcription data consumed by subtitle construction."""

    language: str | None
    text: str
    segments: tuple[Mapping[str, Any], ...]


class ASRAdapter(Protocol):
    """Minimal boundary implemented by every speech-recognition backend."""

    backend: ASRBackend

    def transcribe(self, request: ASRRequest) -> ASRResult:
        """Transcribe one local media file into normalized timed segments."""
        ...


def report(progress: ProgressReporter, message: str) -> None:
    if progress is not None:
        progress(message)


def load_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise DependencyError("PyTorch is required to transcribe video") from exc
    return torch


def load_model_with_retries(
    loader: Callable[[], Any],
    *,
    operation: str,
    progress: ProgressReporter,
    attempts: int = MODEL_LOAD_ATTEMPTS,
    base_delay_seconds: float = MODEL_RETRY_BASE_DELAY_SECONDS,
) -> Any:
    """Retry transient model-download failures with short exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return loader()
        except Exception as exc:  # Model runtimes have no shared error hierarchy.
            last_error = exc
            if attempt >= attempts or not is_retryable_model_error(exc):
                raise

            delay = base_delay_seconds * (2 ** (attempt - 1))
            report(
                progress,
                f"{operation} encountered a temporary connection error; "
                f"retrying ({attempt + 1}/{attempts}) in {delay:g}s...",
            )
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise ValueError("Model load attempts must be greater than zero")


def is_retryable_model_error(error: BaseException) -> bool:
    """Identify connection-like errors without retrying configuration failures."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ConnectionError, TimeoutError)):
            return True
        if any(
            marker in type(current).__name__.lower()
            for marker in ("connection", "timeout")
        ):
            return True
        if any(
            marker in str(current).lower() for marker in _RETRYABLE_MODEL_ERROR_MARKERS
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


def select_compute_configuration(torch: Any) -> tuple[str, str]:
    """Select the established CUDA/float16 or CPU/int8 runtime pair."""
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception as exc:
        raise DependencyError(
            f"Could not determine the available compute device: {exc}"
        ) from exc
    return (device, "float16" if device == "cuda" else "int8")


def require_mapping(
    value: object, description: str, backend: ASRBackend
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TranscriptionError(f"{backend.value} returned an invalid {description}")
    return value


def require_sequence(value: object, description: str, backend: ASRBackend) -> list[Any]:
    if isinstance(value, (str, bytes)):
        raise TranscriptionError(f"{backend.value} returned invalid {description}")
    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TranscriptionError(
            f"{backend.value} returned invalid {description}"
        ) from exc


def full_text_from_segments(segments: tuple[Mapping[str, Any], ...]) -> str:
    return "".join(str(segment.get("text", "")) for segment in segments).strip()


@contextmanager
def temporary_wav(input_path: Path) -> Iterator[Path]:
    """Extract one private 16 kHz mono WAV for audio-only model runtimes."""
    with TemporaryDirectory(prefix="multisubs-asr-") as directory:
        audio_path = Path(directory) / "audio.wav"
        from ..subtitler import extract_audio_track

        extract_audio_track(input_path, audio_path)
        yield audio_path


def wav_duration(audio_path: Path) -> float:
    try:
        with wave.open(str(audio_path), "rb") as audio:
            frame_rate = audio.getframerate()
            if frame_rate <= 0:
                raise TranscriptionError(
                    "Extracted ASR audio has an invalid sample rate"
                )
            return audio.getnframes() / frame_rate
    except (OSError, wave.Error) as exc:
        raise TranscriptionError(
            f"Could not inspect extracted ASR audio '{audio_path}': {exc}"
        ) from exc
