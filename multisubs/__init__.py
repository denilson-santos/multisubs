"""Public multisubs package API."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "4.2.0"

__all__ = (
    "__version__",
    "embed_subtitles",
    "generate_transcriptions",
    "generate_subtitles_from_json",
    "GeneratedSubtitleArtifacts",
)

if TYPE_CHECKING:
    from .subtitler import embed_subtitles
    from .timed_cues import GeneratedSubtitleArtifacts, generate_subtitles_from_json
    from .transcriber import generate_transcriptions


def __getattr__(name: str):
    """Load optional runtime-heavy public APIs only when requested."""
    if name == "generate_transcriptions":
        from .transcriber import generate_transcriptions

        return generate_transcriptions
    if name in ("generate_subtitles_from_json", "GeneratedSubtitleArtifacts"):
        from . import timed_cues

        return getattr(timed_cues, name)
    if name == "embed_subtitles":
        from .subtitler import embed_subtitles

        return embed_subtitles
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
