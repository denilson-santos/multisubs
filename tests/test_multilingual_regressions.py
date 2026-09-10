"""Desired behavior regressions, owned by the numbered multilingual plans."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from multisubs.config import validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.text_measurement import build_text_measurer
from multisubs.transcriber import _build_subtitle_segments, prepare_karaoke_cues
from multisubs.wrapping import (
    ends_clause,
    ends_sentence,
    grapheme_clusters,
    words_to_text,
)

CASES = json.loads(
    (Path(__file__).parent / "fixtures/multilingual/cases.json").read_text()
)


def _cases(name):
    return [
        pytest.param(
            case,
            id=case["id"],
            marks=(
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason=f"Multilingual Plan {case['owner']}: {case['id']}",
                )
                if case["owner"] not in {None, 2, 3}
                else ()
            ),
        )
        for case in CASES[name]
    ]


@pytest.mark.parametrize("case", _cases("joins"))
def test_source_separators_survive_word_reconstruction(case):
    assert words_to_text([{"word": p} for p in case["parts"]]) == case["text"]


@pytest.mark.parametrize("case", _cases("clusters"))
def test_display_units_preserve_extended_graphemes(case):
    assert grapheme_clusters(case["text"]) == case["clusters"]


@pytest.mark.parametrize("mark", ["。", "！", "？", "؟", "।", "。」"])
def test_unicode_sentence_endings(mark):
    assert ends_sentence("text" + mark)


@pytest.mark.parametrize("mark", ["、", "،", "؛"])
def test_unicode_clause_endings(mark):
    assert ends_clause("text" + mark)


@pytest.mark.parametrize("text", ["Dr.", "e.g.", "3.14"])
def test_decimal_and_common_abbreviation_periods_are_not_sentence_endings(text):
    assert not ends_sentence(text)


def test_missing_japanese_glyphs_are_not_measured_as_exact_inter():
    config = validate_subtitle_config(
        None,
        appearance_values={"font": "Inter"},
        relative_values={"font_size": "89px", "letter_spacing": "0px"},
    )
    # Resolve only the scalar typography for this boundary-level regression.
    typography = replace(config.style.typography, font_size=89, letter_spacing=0)
    try:
        measurer = build_text_measurer(
            typography,
            language="ja",
            sample_text="字幕",
            verify_font_coverage=True,
        )
    except ValidationError as exc:
        pytest.skip(f"No local Japanese covering face is available: {exc}")
    measured = measurer.measure("字幕")
    missing = measurer.measure("\U0010ffff\U0010ffff")
    assert measurer.info.coverage == "verified"
    assert measurer.info.resolved_font != "Inter"
    assert measured != missing


def test_partially_aligned_segment_keeps_untimed_text():
    source = {
        "start": 0.0,
        "end": 1.0,
        "text": "字幕。",
        "words": [
            {"word": "字", "start": 0.0, "end": 0.4},
            {"word": "幕", "start": 0.4, "end": 1.0},
            {"word": "。"},
        ],
    }
    cues = _build_subtitle_segments([source])
    assert "".join(c["text"] for c in cues) == source["text"]


def test_duration_boundary_does_not_cut_a_fitting_japanese_lexical_group():
    # The second word spans the six-second boundary but fits by itself.
    words = [
        {"word": "はい", "start": 0.0, "end": 5.7},
        {"word": "使", "start": 5.7, "end": 5.9},
        {"word": "用", "start": 5.9, "end": 6.1},
    ]
    cues = _build_subtitle_segments(
        [{"start": 0.0, "end": 6.1, "text": "はい使用", "words": words}]
    )
    assert any("使用" in cue["text"] for cue in cues)


def test_zero_length_alignment_is_preserved_without_stretching():
    words = [
        {"word": "字", "start": 0.0, "end": 0.0},
        {"word": "幕", "start": 0.0, "end": 0.02},
    ]
    cues = _build_subtitle_segments(
        [{"start": 0.0, "end": 0.02, "text": "字幕", "words": words}]
    )
    assert [w for c in cues for w in c["words"]] == words


def test_missing_alignment_uses_static_word_effect_fallback():
    from multisubs.templates import get_subtitle_template

    cues, fallback_count = prepare_karaoke_cues(
        [{"start": 0.0, "end": 1.0, "text": "字幕。", "words": []}],
        get_subtitle_template("amber-word").config,
    )
    assert fallback_count == 1
    assert cues[0]["text"] == "字幕。"
    assert "_karaoke_cue" not in cues[0]
    assert cues[0]["_word_effect"]["fallback_reason"] == "missing-alignment-records"
