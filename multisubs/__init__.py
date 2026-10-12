"""Public multisubs package API."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "4.4.1"

__all__ = (
    "__version__",
    "embed_subtitles",
    "generate_transcriptions",
    "transcribe_speech",
    "SpeechTranscript",
    "render_transcript",
    "GeneratedSubtitleArtifacts",
    "render_subtitle_file",
)

if TYPE_CHECKING:
    from .models import GeneratedSubtitleArtifacts
    from .speech import SpeechTranscript, render_transcript
    from .subtitler import embed_subtitles, render_subtitle_file
    from .transcriber import generate_transcriptions, transcribe_speech


def __getattr__(name: str):
    """Load optional runtime-heavy public APIs only when requested."""
    if name in ("generate_transcriptions", "transcribe_speech"):
        from . import transcriber

        return getattr(transcriber, name)
    if name in ("SpeechTranscript", "render_transcript"):
        from . import speech

        return getattr(speech, name)
    if name in ("embed_subtitles", "render_subtitle_file"):
        from . import subtitler

        return getattr(subtitler, name)
    if name == "GeneratedSubtitleArtifacts":
        from .models import GeneratedSubtitleArtifacts

        return GeneratedSubtitleArtifacts
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
