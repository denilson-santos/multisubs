from fractions import Fraction

from multisubs.config import validate_subtitle_config
from multisubs.layout import resolve_subtitle_config, resolve_wrapping_metrics
from multisubs.models import VideoGeometry
from multisubs.text_measurement import build_unicode_text_measurer
from multisubs.wrapping import (
    fit_first_text_segment,
    split_words_for_layout,
    wrap_subtitle_text,
)

GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1920,
    render_height=1080,
    rotation_degrees=0,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(16, 9),
    duration_seconds=10.0,
)


def _metrics(*, letter_spacing: str = "0px", max_height: str = "100px"):
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "20px",
            "letter_spacing": letter_spacing,
            "max_width": "55px",
            "max_height": max_height,
            "shadow_weight": "0px",
        },
        appearance_values={"backdrop": "none"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    assert isinstance(resolved.appearance.font_size, int)
    assert isinstance(resolved.appearance.letter_spacing, int)
    measurer = build_unicode_text_measurer(
        resolved.appearance.font,
        resolved.appearance.font_size,
        letter_spacing=resolved.appearance.letter_spacing,
    )
    return resolve_wrapping_metrics(resolved, GEOMETRY, text_measurer=measurer)


def test_shared_wrapping_accounts_for_letter_spacing():
    compact = _metrics()
    spaced = _metrics(letter_spacing="10px")
    text = "aa bb"

    assert wrap_subtitle_text(text, metrics=compact) == text
    assert wrap_subtitle_text(text, metrics=spaced) == "aa\nbb"


def test_timed_word_splitting_uses_the_same_spacing_adjusted_budget():
    metrics = _metrics(letter_spacing="10px", max_height="24px")
    words = [
        {"word": "aa", "start": 0.0, "end": 0.4},
        {"word": "bb", "start": 0.5, "end": 0.9},
    ]

    groups = split_words_for_layout(words, metrics)

    assert [[word["word"] for word in group] for group in groups] == [
        ["aa"],
        ["bb"],
    ]


def test_preview_first_segment_uses_the_same_spacing_adjusted_budget():
    metrics = _metrics(letter_spacing="10px")

    assert fit_first_text_segment("aa bb", metrics=metrics) == "aa\nbb"
