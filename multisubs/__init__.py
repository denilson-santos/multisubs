"""Public multisubs package API."""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "1.1.0"

__all__ = ("__version__", "embed_subtitles", "generate_transcriptions")

if TYPE_CHECKING:
    from .subtitler import embed_subtitles
    from .transcriber import generate_transcriptions


def __getattr__(name: str):
    """Load optional runtime-heavy public APIs only when requested."""
    if name == "generate_transcriptions":
        from .transcriber import generate_transcriptions

        return generate_transcriptions
    if name == "embed_subtitles":
        from .subtitler import embed_subtitles

        return embed_subtitles
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
