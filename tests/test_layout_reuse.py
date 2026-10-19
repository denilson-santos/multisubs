"""Reused display units preserve Unicode source offsets through subdivision."""

from fractions import Fraction

import pytest

from multisubs import transcriber
from multisubs.config import validate_subtitle_config
from multisubs.layout import resolve_subtitle_config
from multisubs.models import VideoGeometry
from multisubs.text_segmentation import grapheme_clusters


@pytest.mark.parametrize(
    ("language", "text", "case"),
    [
        (
            "pt",
            "a\u0301 criança descreve uma história longa com palavras repetidas " * 3,
            "uppercase",
        ),
        (
            "de",
            "die straße bleibt groß und die wörter bleiben lesbar " * 3,
            "uppercase",
        ),
        (
            "ja",
            "今日は寒くなかったけれど字幕のデフォルト設定を使用する" * 3,
            "original",
        ),
        ("zh", "我们今天学习中文并使用清晰的字幕显示每个词语" * 3, "original"),
        ("ar", "مرحبا بالعالم مع نص طويل يحافظ على الكلمات والمسافات " * 3, "original"),
    ],
)
def test_subdivisions_reuse_units_without_changing_source_mapping(
    language,
    text,
    case,
    monkeypatch,
):
    # Whole graphemes supply synthetic alignment, including combining marks.
    tokens = grapheme_clusters(text) if language in {"ja", "zh"} else text.split()
    if language not in {"ja", "zh"}:
        tokens = [
            token if index == 0 else " " + token for index, token in enumerate(tokens)
        ]
    text = "".join(tokens)
    words = [
        {"word": token, "start": index * 0.1, "end": index * 0.1 + 0.09}
        for index, token in enumerate(tokens)
    ]
    segments = transcriber._build_subtitle_segments(
        [{"text": text, "start": 0, "end": len(tokens) * 0.1, "words": words}],
        language=language,
    )
    geometry = VideoGeometry(
        0, 1080, 1920, 1080, 1920, 0, Fraction(1), Fraction(9, 16), 60
    )
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            appearance_values={"text_case": case},
            relative_values={
                "font_size": "40px",
                "max_width": "260px",
                "max_height": "65px",
            },
        ),
        geometry,
    )
    original_units = transcriber.display_units_for_records
    original_groups = transcriber._display_groups_for_records
    calls = []

    def count_units(*args, **kwargs):
        calls.append(args[0])
        return original_units(*args, **kwargs)

    monkeypatch.setattr(transcriber, "display_units_for_records", count_units)
    actual, _ = transcriber.layout_subtitle_cues(
        segments, config, geometry, language=language
    )
    assert len(actual) > len(segments)
    assert len(calls) == len(segments)

    def legacy_groups(groups, indexes, source, records, units):
        # Replay the former source-unit reconstruction at each subdivision.
        return original_groups(
            groups, indexes, source, records, original_units(source, indexes)
        )

    monkeypatch.setattr(transcriber, "_display_groups_for_records", legacy_groups)
    expected, _ = transcriber.layout_subtitle_cues(
        segments, config, geometry, language=language
    )
    assert actual == expected
