from multisubs.text_segmentation import (
    build_source_text_map,
    display_text_for_records,
    grapheme_boundaries,
    grapheme_clusters,
    normalize_line_endings,
    source_text_for_records,
    word_units,
)


def test_line_endings_keep_bidirectional_source_offsets():
    normalized, raw_to_normalized, normalized_to_raw = normalize_line_endings(
        "A\r\nB\rC"
    )

    assert normalized == "A\nB\nC"
    assert raw_to_normalized == (0, 1, 1, 2, 3, 4)
    assert normalized_to_raw == (0, 1, 3, 4, 5)


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
