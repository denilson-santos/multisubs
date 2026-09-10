from pathlib import Path

from multisubs.text_segmentation import (
    LinguisticSegmenter,
    build_source_text_map,
    display_text_for_records,
    grapheme_boundaries,
    grapheme_clusters,
    linguistic_units,
    normalize_line_endings,
    simulated_effect_units,
    source_text_for_records,
    word_units,
)


def _character_records(text: str, *, step: float = 0.1):
    return [
        {"word": character, "start": index * step, "end": (index + 1) * step}
        for index, character in enumerate(text)
    ]


def test_line_endings_keep_bidirectional_source_offsets():
    normalized, raw_to_normalized, normalized_to_raw = normalize_line_endings(
        "A\r\nB\rC"
    )

    assert normalized == "A\nB\nC"
    assert raw_to_normalized == (0, 1, 1, 2, 3, 4)
    assert normalized_to_raw == (0, 1, 3, 4, 5)


def test_simulated_cjk_effect_units_model_character_alignment():
    assert simulated_effect_units("装置は") == ("装", "置", "は")
    assert simulated_effect_units("你好世界") == ("你", "好", "世", "界")


def test_repeated_alignment_records_use_monotonic_source_offsets():
    records = [
        {"word": "na", "start": 0.0, "end": 0.2, "score": 0.8},
        {"word": "na", "start": 0.3, "end": 0.5, "score": 0.9},
    ]
    source_map = build_source_text_map("na na", records)

    aligned = [span for span in source_map.spans if span.kind == "alignment"]
    assert [(span.start, span.end) for span in aligned] == [(0, 2), (3, 5)]
    assert [span.source_record_identity for span in aligned] == [(0, 0), (0, 1)]
    assert source_map.complete is True
    assert source_map.timing_complete is True
    assert source_text_for_records(source_map) == "na na"
    assert records[0] == {
        "word": "na",
        "start": 0.0,
        "end": 0.2,
        "score": 0.8,
    }


def test_source_map_retains_nbsp_and_unmatched_source_ranges():
    source_map = build_source_text_map(
        "a\u00a0b!",
        [
            {"word": "a", "start": 0.0, "end": 0.2},
            {"word": "b", "start": 0.3, "end": 0.5},
        ],
    )

    assert source_map.normalized_text == "a\u00a0b!"
    assert source_text_for_records(source_map) == "a\u00a0b!"
    assert display_text_for_records(source_map) == "a\u00a0b!"
    assert source_map.complete is False
    assert "unmatched-source-text" in source_map.fallback_reasons
    unmatched = [span for span in source_map.spans if span.kind == "unmatched-source"]
    assert [span.text for span in unmatched] == ["!"]


def test_source_map_marks_missing_record_time_without_dropping_text():
    source_map = build_source_text_map(
        "안녕하세요 세계",
        [
            {"word": "안녕하세요", "start": 0.0, "end": 0.4},
            {"word": "세계"},
        ],
    )

    assert source_map.complete is True
    assert source_map.timing_complete is False
    assert source_text_for_records(source_map) == "안녕하세요 세계"
    assert "missing-or-invalid-alignment-time" in source_map.fallback_reasons
    assert "incomplete-alignment-timing" in source_map.fallback_reasons


def test_empty_source_uses_explicit_record_compatibility_fallback():
    records = [
        {"word": "字幕", "start": 0.0, "end": 0.4},
        {"word": "AI", "start": 0.4, "end": 0.8},
    ]

    source_map = build_source_text_map(
        "",
        records,
        fallback_text="字幕AI",
    )

    assert source_map.source_provided is False
    assert source_map.complete is True
    assert source_text_for_records(source_map) == "字幕AI"


def test_source_map_preserves_logical_order_and_normalization_form():
    cases = (
        ("مرحبا بالعالم", ("مرحبا", "بالعالم")),
        ("שלום עולם", ("שלום", "עולם")),
        ("Café", ("Café",)),
        ("Cafe\u0301", ("Cafe\u0301",)),
        ("!", ("!",)),
    )

    for text, tokens in cases:
        records = [
            {"word": token, "start": index * 0.2, "end": index * 0.2 + 0.1}
            for index, token in enumerate(tokens)
        ]
        source_map = build_source_text_map(text, records)

        assert source_map.complete is True
        assert source_map.timing_complete is True
        assert source_text_for_records(source_map) == text


def test_source_map_retains_mismatch_and_nonchronological_timing_as_diagnostics():
    source_map = build_source_text_map(
        "hello world",
        [
            {"word": "hello", "start": 0.4, "end": 0.6},
            {"word": "there", "start": 0.1, "end": 0.3},
        ],
    )

    assert source_map.normalized_text == "hello world"
    assert source_map.complete is False
    assert source_map.timing_complete is False
    assert "non-chronological-alignment" in source_map.fallback_reasons
    assert "unmatched-alignment-record" in source_map.fallback_reasons
    assert any(span.kind == "unmatched-record" for span in source_map.spans)


def test_display_mapping_applies_expanding_case_without_retokenizing():
    source_map = build_source_text_map(
        "Straße x",
        [
            {"word": "Straße", "start": 0.0, "end": 0.4},
            {"word": "x", "start": 0.5, "end": 1.0},
        ],
    )

    units = source_map.mapped_record_indexes
    assert display_text_for_records(source_map, units, transform=str.upper) == (
        "STRASSE X"
    )
    assert source_text_for_records(source_map, units) == "Straße x"


def test_unicode_adapter_keeps_extended_graphemes_and_word_units():
    assert grapheme_clusters("🇧🇷👍🏽👩\u200d💻कि한") == [
        "🇧🇷",
        "👍🏽",
        "👩\u200d💻",
        "कि",
        "한",
    ]
    assert grapheme_boundaries("😀a") == (0, 1, 2)
    assert word_units("안녕하세요 세계") == ("안녕하세요", "세계")
    assert word_units("字幕AI") == ("字", "幕", "AI")


def test_japanese_groups_join_inflectional_tails_and_punctuation():
    text = "今日は寒くなかった。"
    records = _character_records(text)
    source_map = build_source_text_map(text, records)

    with LinguisticSegmenter() as segmenter:
        groups = segmenter.group_source_map(source_map, records, language="ja")

    assert "".join(group.source_text for group in groups) == text
    assert any(group.source_text == "寒くなかった。" for group in groups)
    assert groups[-1].boundary_class == "sentence"
    assert groups[-1].strategy == "sudachi-b"
    assert "SudachiDict-small/20260723" in groups[-1].backend_version


def test_japanese_groups_join_prefix_number_and_counter():
    text = "字幕AI第1回"
    records = _character_records(text)
    source_map = build_source_text_map(text, records)

    with LinguisticSegmenter() as segmenter:
        groups = segmenter.group_source_map(source_map, records, language="ja")

    assert "".join(group.source_text for group in groups) == text
    assert any(group.source_text == "第1回" for group in groups)


def test_chinese_groups_use_hmm_and_remove_invocation_cache():
    text = "我們今天學習中文。"
    records = _character_records(text)
    source_map = build_source_text_map(text, records)
    segmenter = LinguisticSegmenter()

    groups = segmenter.group_source_map(source_map, records, language="zh")
    assert segmenter._jieba_cache is not None
    cache_path = Path(segmenter._jieba_cache.name)
    assert cache_path.is_dir()
    segmenter.close()

    assert "".join(group.source_text for group in groups) == text
    assert any(group.source_text == "學習" for group in groups)
    assert groups[-1].source_text == "中文。"
    assert not cache_path.exists()


def test_preview_lexical_units_reuse_dictionary_grouping():
    assert "デフォルト" in linguistic_units("デフォルト設定を使用する。")
    assert "學習" in linguistic_units("我們今天學習中文。", language="zh")
    assert linguistic_units("字幕", language="en") == ("字", "幕")


def test_lexical_group_splits_at_a_significant_source_pause():
    text = "なかった"
    records = _character_records(text)
    records[2]["start"] = 1.0
    records[2]["end"] = 1.1
    records[3]["start"] = 1.1
    records[3]["end"] = 1.2
    source_map = build_source_text_map(text, records)

    with LinguisticSegmenter() as segmenter:
        groups = segmenter.group_source_map(source_map, records, language="ja")

    assert [group.source_text for group in groups] == ["なか", "った"]
    assert groups[0].boundary_class == "pause"
    assert groups[0].end_time == 0.2
    assert groups[1].start_time == 1.0


def test_alignment_records_never_split_one_grapheme_group():
    text = "कि"
    records = [
        {"word": "क", "start": 0.0, "end": 0.1},
        {"word": "ि", "start": 1.0, "end": 1.1},
    ]
    source_map = build_source_text_map(text, records)

    with LinguisticSegmenter() as segmenter:
        groups = segmenter.group_source_map(source_map, records, language="hi")

    assert len(groups) == 1
    assert groups[0].source_text == text
    assert groups[0].record_indexes == (0, 1)
