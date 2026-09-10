from dataclasses import replace
from fractions import Fraction

import pytest

from multisubs.config import validate_subtitle_config
from multisubs.layout import resolve_subtitle_config, resolve_wrapping_metrics
from multisubs.models import TextCase, VideoGeometry
from multisubs.text_measurement import (
    TextMeasurementInfo,
    TextMeasurer,
    build_unicode_text_measurer,
)
from multisubs.text_segmentation import build_source_text_map, display_units_for_records
from multisubs.wrapping import (
    build_display_fragments,
    build_visual_lines,
    fit_first_text_segment,
    has_multiple_visual_lines,
    render_display_units,
    split_words_for_layout,
    transform_display_text,
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
    assert isinstance(resolved.style.typography.font_size, int)
    assert isinstance(resolved.style.typography.letter_spacing, int)
    measurer = build_unicode_text_measurer(
        resolved.style.typography.font,
        resolved.style.typography.font_size,
        letter_spacing=resolved.style.typography.letter_spacing,
    )
    return resolve_wrapping_metrics(resolved, GEOMETRY, text_measurer=measurer)


def _box_metrics(*, max_height: str):
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Test",
        resolved_font="Test",
        resolved_style="Regular",
        font_source="test",
        shaping="basic",
        metric_size=43,
    )
    measurer = TextMeasurer(
        info,
        lambda text: len(text) * 10,
        line_height=43,
    )
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "box"},
        relative_values={
            "font_size": "43px",
            "outline_weight": "11px",
            "max_width": "152px",
            "max_height": max_height,
        },
    )
    resolved = resolve_subtitle_config(config, GEOMETRY, text_measurer=measurer)
    return resolve_wrapping_metrics(
        resolved,
        GEOMETRY,
        text_measurer=measurer,
    )


def test_shared_wrapping_accounts_for_letter_spacing():
    compact = _metrics()
    spaced = _metrics(letter_spacing="10px")
    text = "aa bb"

    assert wrap_subtitle_text(text, metrics=compact) == text
    assert wrap_subtitle_text(text, metrics=spaced) == "aa\nbb"


@pytest.mark.parametrize(
    ("text", "text_case", "expected"),
    [
        ("Olá, ação!", TextCase.UPPERCASE, "OLÁ, AÇÃO!"),
        ("Straße", TextCase.UPPERCASE, "STRASSE"),
        ("ΟΣ Σ", TextCase.LOWERCASE, "ος σ"),
        ("Cafe\u0301", TextCase.UPPERCASE, "CAFE\u0301"),
        ("字幕 😀 مرحبا", TextCase.UPPERCASE, "字幕 😀 مرحبا"),
        ("i ı İ I", TextCase.UPPERCASE, "I I İ I"),
        (r"unsafe {\an9}", TextCase.UPPERCASE, r"UNSAFE {\AN9}"),
        ("Already Mixed", TextCase.ORIGINAL, "Already Mixed"),
    ],
)
def test_display_text_case_uses_unicode_default_casing(text, text_case, expected):
    assert transform_display_text(text, text_case) == expected


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


def test_wrapping_counts_backdrop_decoration_once_at_width_boundary():
    metrics = _box_metrics(max_height="190px")

    assert metrics.width_budget == 130
    assert wrap_subtitle_text("one two three", metrics=metrics) == "one two three"


def test_preview_first_segment_uses_available_lines_before_cutting_prefix():
    text = "one two three four five six seven eight nine ten eleven twelve"

    three_line = fit_first_text_segment(
        text,
        metrics=_box_metrics(max_height="190px"),
    )
    four_line = fit_first_text_segment(
        text,
        metrics=_box_metrics(max_height="195px"),
    )

    assert three_line == "one two three\nfour five six\nseven eight"
    assert four_line == "one two three\nfour five six\nseven eight\nnine ten"
    assert three_line.count("\n") == 2
    assert four_line.count("\n") == 3


def test_timed_word_break_uses_available_visual_lines():
    metrics = _box_metrics(max_height="190px")
    words = [
        {"word": f"w{index}", "start": index, "end": index + 0.1} for index in range(13)
    ]

    groups = split_words_for_layout(words, metrics)

    assert [[word["word"] for word in group] for group in groups] == [
        [f"w{index}" for index in range(11)],
        ["w11", "w12"],
    ]


def test_timed_word_break_keeps_sentence_priority_over_longer_prefixes():
    metrics = _box_metrics(max_height="190px")
    words = [
        {"word": word, "start": index, "end": index + 0.1}
        for index, word in enumerate(
            ["one", "two.", *[f"word{index}" for index in range(11)]]
        )
    ]

    groups = split_words_for_layout(words, metrics)

    assert [word["word"] for word in groups[0]] == ["one", "two."]


def test_visual_lines_preserve_word_fragments_and_measure_each_line():
    metrics = _metrics(max_height="100px")
    text = "aa\nbb"
    fragments = build_display_fragments(
        text,
        [
            {"word": "aa", "start": 0.0, "end": 0.2},
            {"word": "bb", "start": 0.2, "end": 0.4},
        ],
    )

    lines = build_visual_lines(text, fragments, metrics)

    assert [line.text for line in lines] == ["aa", "bb"]
    assert [line.index for line in lines] == [0, 1]
    assert [[fragment.word_index for fragment in line.fragments] for line in lines] == [
        [0],
        [1],
    ]


def test_mapped_display_wrapping_retains_source_separator_provenance():
    source_map = build_source_text_map(
        "one two ",
        [
            {"word": "one", "start": 0.0, "end": 0.2},
            {"word": "two", "start": 0.2, "end": 0.4},
        ],
    )
    metrics = replace(
        _metrics(),
        text_measurer=TextMeasurer(
            TextMeasurementInfo(
                mode="font-metrics",
                requested_font="Test",
                resolved_font="Test",
                resolved_style="Regular",
                font_source="test",
                shaping="basic",
                metric_size=20,
            ),
            lambda text: len(text) * 10.0,
            line_height=20.0,
        ),
    )
    units = display_units_for_records(source_map)

    display, fragments, line_breaks = render_display_units(units, metrics)

    assert display == "one\ntwo"
    assert line_breaks == (" ",)
    assert "".join(fragment.text for fragment in fragments) == display


def test_text_only_wrapping_keeps_nonbreaking_separators():
    metrics = replace(
        _metrics(),
        text_measurer=TextMeasurer(
            TextMeasurementInfo(
                mode="font-metrics",
                requested_font="Test",
                resolved_font="Test",
                resolved_style="Regular",
                font_source="test",
                shaping="basic",
                metric_size=20,
            ),
            lambda text: len(text) * 30.0,
            line_height=20.0,
        ),
    )

    assert wrap_subtitle_text("a\u00a0b", metrics=metrics) == "a\u00a0b"


def test_multiple_visual_lines_normalizes_line_endings():
    assert not has_multiple_visual_lines("one visual line")
    assert has_multiple_visual_lines("first\r\nsecond")
    assert has_multiple_visual_lines("first\rsecond")
