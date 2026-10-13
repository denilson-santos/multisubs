"""Public multisubs package API."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "5.0.1"

__all__ = (
    "__version__",
    "embed_subtitles",
    "generate_transcriptions",
    "transcribe_speech",
    "SpeechTranscript",
    "render_transcript",
    "GeneratedSubtitleArtifacts",
    "render_subtitle_file",
    "build_subtitle_config",
    "SubtitleConfig",
    "MultisubsError",
    "ValidationError",
    "TemplateError",
)

if TYPE_CHECKING:
    from .errors import MultisubsError, TemplateError, ValidationError
    from .models import GeneratedSubtitleArtifacts, SubtitleConfig
    from .speech import SpeechTranscript, render_transcript
    from .subtitle_config import build_subtitle_config
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
    if name in ("GeneratedSubtitleArtifacts", "SubtitleConfig"):
        from . import models

        return getattr(models, name)
    if name == "build_subtitle_config":
        from .subtitle_config import build_subtitle_config

        return build_subtitle_config
    if name in ("MultisubsError", "ValidationError", "TemplateError"):
        from . import errors

        return getattr(errors, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
