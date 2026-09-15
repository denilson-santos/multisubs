"""Local ASR adapter selection without importing optional model runtimes."""

from __future__ import annotations

from .base import ASRAdapter, ASRBackend, ASRRequest, ASRResult
from .catalog import (
    ALL_LANGUAGE_CODES,
    ASR_CHOICES,
    ASR_SPECS,
    normalise_language_code,
    parse_backend,
    resolve_model,
    validate_request,
)

__all__ = (
    "ASRAdapter",
    "ASRBackend",
    "ASRRequest",
    "ASRResult",
    "ASR_CHOICES",
    "ASR_SPECS",
    "ALL_LANGUAGE_CODES",
    "create_adapter",
    "normalise_language_code",
    "parse_backend",
    "resolve_model",
    "validate_request",
)


def create_adapter(backend: ASRBackend) -> ASRAdapter:
    """Instantiate one lightweight adapter for the selected runtime."""
    if backend is ASRBackend.WHISPERX:
        from .whisperx import WhisperXAdapter

        return WhisperXAdapter()
    if backend is ASRBackend.FASTER_WHISPER:
        from .faster_whisper import FasterWhisperAdapter

        return FasterWhisperAdapter()
    if backend is ASRBackend.PARAKEET:
        from .parakeet import ParakeetAdapter

        return ParakeetAdapter()
    from .qwen import QwenAdapter

    return QwenAdapter()
