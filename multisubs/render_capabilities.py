"""Content-aware subtitle rendering capability decisions.

libass remains authoritative for shaping complete logical lines.  The
positioned word renderer, however, places logical fragments from measured
prefix widths and therefore cannot safely claim bidirectional or contextual
shaping support.  This module keeps that distinction explicit and shared by
production and preview preparation.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class RendererCapability:
    """The safe rendering strategy for one cue's requested word effects."""

    renderer_strategy: str
    word_effects_supported: bool
    fallback_reason: str | None
    shaping_features: tuple[str, ...]


_COMPLEX_SCRIPT_RANGES = (
    (0x0590, 0x05FF, "hebrew"),
    (0x0600, 0x06FF, "arabic"),
    (0x0700, 0x074F, "syriac"),
    (0x0750, 0x077F, "arabic"),
    (0x0780, 0x07BF, "thaana"),
    (0x07C0, 0x07FF, "nko"),
    (0x0800, 0x083F, "samaritan"),
    (0x0840, 0x085F, "mandaic"),
    (0x0870, 0x089F, "arabic"),
    (0x08A0, 0x08FF, "arabic"),
    (0x0900, 0x097F, "devanagari"),
    (0x0980, 0x09FF, "bengali"),
    (0x0A00, 0x0A7F, "gurmukhi"),
    (0x0A80, 0x0AFF, "gujarati"),
    (0x0B00, 0x0B7F, "oriya"),
    (0x0B80, 0x0BFF, "tamil"),
    (0x0C00, 0x0C7F, "telugu"),
    (0x0C80, 0x0CFF, "kannada"),
    (0x0D00, 0x0D7F, "malayalam"),
    (0x0D80, 0x0DFF, "sinhala"),
    (0xFB50, 0xFDFF, "arabic-presentation"),
    (0xFE70, 0xFEFF, "arabic-presentation"),
)
_JOINING_CONTROLS = frozenset({"\u200c", "\u200d"})
_BIDIRECTIONAL_CLASSES = frozenset(
    {"R", "AL", "AN", "RLE", "RLO", "RLI", "LRE", "LRO", "LRI", "FSI", "PDI", "PDF"}
)


def assess_renderer_capability(
    text: str,
    *,
    word_effects_requested: bool,
) -> RendererCapability:
    """Select a rendering path from the actual display text and request.

    Complete logical lines are safe to hand to libass.  Per-word positioned
    fragments are enabled only when this renderer can preserve visual order
    and contextual shaping without synthesizing a visual-run algorithm.
    """
    features = _shaping_features(text)
    if not word_effects_requested:
        return RendererCapability("full-line", True, None, features)
    if features:
        return RendererCapability(
            "full-line",
            False,
            "unsupported-word-shaping",
            features,
        )
    return RendererCapability("positioned-fragments", True, None, ())


def _shaping_features(text: str) -> tuple[str, ...]:
    features: set[str] = set()
    for character in text:
        if character in _JOINING_CONTROLS:
            features.add("joining-control")
        if unicodedata.bidirectional(character) in _BIDIRECTIONAL_CLASSES:
            features.add("bidirectional")
        codepoint = ord(character)
        for start, end, name in _COMPLEX_SCRIPT_RANGES:
            if start <= codepoint <= end:
                features.add(name)
                break
    return tuple(sorted(features))
