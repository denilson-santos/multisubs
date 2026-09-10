"""Unicode boundaries and lossless source/alignment mapping.

This module deliberately has no WhisperX, PyTorch, font, or FFmpeg imports. It
owns only bounded text normalization, Unicode boundary data, and the mapping
between source text and alignment records.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping, Sequence
from contextlib import redirect_stderr
from importlib.metadata import version
from numbers import Real
from tempfile import TemporaryDirectory
from typing import Any, cast

from uniseg.graphemecluster import (
    grapheme_cluster_boundaries as _grapheme_cluster_boundaries,
)
from uniseg.graphemecluster import grapheme_clusters as _grapheme_clusters
from uniseg.linebreak import line_break_boundaries as _line_break_boundaries
from uniseg.sentencebreak import sentence_boundaries as _sentence_boundaries
from uniseg.wordbreak import word_boundaries as _word_boundaries
from uniseg.wordbreak import words as _unicode_words

from .models import (
    SubtitleDisplayGroup,
    SubtitleDisplayUnit,
    SubtitleSourceMap,
    SubtitleSourceSpan,
)

PAUSE_BREAK_THRESHOLD = 0.45
_SENTENCE_MARKS = frozenset(".!?…。！？؟।॥")
_CLAUSE_MARKS = frozenset(",;:—–、，؛،：")
_CLOSING_MARKS = frozenset("”’\"'»」』】〉》）)]}")
_OPENING_MARKS = frozenset("“‘\"'«「『【〈《（([{")


def normalize_line_endings(
    text: str,
) -> tuple[str, tuple[int | None, ...], tuple[int, ...]]:
    """Normalize CRLF/CR to LF and return bidirectional code-point offsets."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    normalized: list[str] = []
    raw_to_normalized: list[int | None] = [None] * len(text)
    normalized_to_raw: list[int] = []
    raw_index = 0
    while raw_index < len(text):
        if text.startswith("\r\n", raw_index):
            normalized_index = len(normalized)
            normalized.append("\n")
            normalized_to_raw.append(raw_index)
            raw_to_normalized[raw_index] = normalized_index
            raw_to_normalized[raw_index + 1] = normalized_index
            raw_index += 2
            continue
        if text[raw_index] == "\r":
            normalized_index = len(normalized)
            normalized.append("\n")
            normalized_to_raw.append(raw_index)
            raw_to_normalized[raw_index] = normalized_index
            raw_index += 1
            continue
        character = text[raw_index]
        normalized_index = len(normalized)
        normalized.append(character)
        normalized_to_raw.append(raw_index)
        raw_to_normalized[raw_index] = normalized_index
        raw_index += 1
    return (
        "".join(normalized),
        tuple(raw_to_normalized),
        tuple(normalized_to_raw),
    )


def normalise_display_text(text: str) -> str:
    """Normalize physical line endings without collapsing meaningful spacing."""
    normalized, _, _ = normalize_line_endings(text)
    return _trim_display_edges(normalized.replace("\n", " "))


def grapheme_clusters(text: str) -> list[str]:
    """Return Unicode extended grapheme clusters from the pinned UAX data."""
    return list(_grapheme_clusters(text))


def grapheme_boundaries(text: str) -> tuple[int, ...]:
    """Return Python code-point offsets at grapheme boundaries."""
    return tuple(_grapheme_cluster_boundaries(text))


def line_break_boundaries(text: str) -> tuple[int, ...]:
    """Return Python code-point offsets where UAX #14 permits a line break."""
    return tuple(_line_break_boundaries(text))


def word_boundaries(text: str) -> tuple[int, ...]:
    """Return Python code-point offsets from Unicode word breaking."""
    return tuple(_word_boundaries(text))


def word_units(text: str) -> tuple[str, ...]:
    """Return non-whitespace Unicode word units with trailing punctuation."""
    units: list[str] = []
    separated = False
    for unit in _unicode_words(text):
        if not unit:
            continue
        if unit.isspace():
            separated = True
            continue
        has_alphanumeric = any(character.isalnum() for character in unit)
        previous_has_alphanumeric = bool(units) and any(
            character.isalnum() for character in units[-1]
        )
        if separated:
            units.append(unit)
        elif has_alphanumeric and previous_has_alphanumeric:
            units.append(unit)
        elif units:
            units[-1] += unit
        else:
            units.append(unit)
        separated = False
    return tuple(units)


def sentence_boundaries(text: str) -> tuple[int, ...]:
    """Return Python code-point offsets from Unicode sentence breaking."""
    return tuple(_sentence_boundaries(text))


def linguistic_units(
    text: str,
    *,
    language: str | None = None,
) -> tuple[str, ...]:
    """Return offline lexical preview units through the production adapter."""
    effective_language = _segmentation_language(text, language)
    if effective_language is None:
        return word_units(text)
    with LinguisticSegmenter() as segmenter:
        boundaries, _, _ = segmenter._lexical_boundaries(text, effective_language)
    ordered = sorted({0, len(text), *boundaries})
    return tuple(
        piece
        for start, end in zip(ordered[:-1], ordered[1:], strict=True)
        if (piece := text[start:end].strip(" \t\r\n\v\f"))
    )


def simulated_effect_units(
    text: str,
    *,
    language: str | None = None,
) -> tuple[str, ...]:
    """Return deterministic preview effect units without real alignments.

    Production effects follow validated WhisperX records. A preview has no such
    records, so CJK chunks use grapheme-like units to model the common
    character-aligned case while whitespace-delimited Latin and other-script
    chunks remain intact. Separators stay untimed and are reconstructed by the
    preview fragment mapper.
    """
    effective_language = _segmentation_language(text, language)
    units = word_units(text)
    if effective_language not in {"ja", "zh"}:
        return units
    result: list[str] = []
    for unit in units:
        if any(_is_cjk_script_character(character) for character in unit):
            result.extend(grapheme_clusters(unit))
        else:
            result.append(unit)
    return tuple(result)


def _is_cjk_script_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x2E80 <= codepoint <= 0x9FFF
        or 0xAC00 <= codepoint <= 0xD7AF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x3040 <= codepoint <= 0x30FF
    )


class LinguisticSegmenter:
    """Invocation-scoped, offline Japanese/Chinese lexical segmenter."""

    def __init__(self) -> None:
        self._japanese: Any | None = None
        self._chinese: Any | None = None
        self._jieba_cache: TemporaryDirectory[str] | None = None

    def close(self) -> None:
        """Remove the invocation-local jieba cache, if it was initialized."""
        if self._jieba_cache is not None:
            self._jieba_cache.cleanup()
            self._jieba_cache = None
        self._japanese = None
        self._chinese = None

    def __enter__(self) -> LinguisticSegmenter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def group_source_map(
        self,
        source_map: SubtitleSourceMap,
        records: Sequence[Mapping[str, Any]],
        *,
        language: str | None,
    ) -> tuple[SubtitleDisplayGroup, ...]:
        """Derive timed display groups without changing source records."""
        spans = _alignment_spans(source_map)
        if (
            not source_map.timing_complete
            or not spans
            or source_map.record_count != len(records)
        ):
            return ()
        effective_language = _segmentation_language(
            source_map.normalized_text, language
        )
        if effective_language is None:
            safe_boundaries = set(grapheme_boundaries(source_map.normalized_text))
            boundaries = {span.end for span in spans if span.end in safe_boundaries}
            strategy, backend_version = "alignment-records", "none"
        else:
            boundaries, strategy, backend_version = self._lexical_boundaries(
                source_map.normalized_text, effective_language
            )
        return _groups_from_boundaries(
            source_map,
            boundaries,
            strategy=strategy,
            backend_version=backend_version,
        )

    def _lexical_boundaries(
        self, text: str, language: str | None
    ) -> tuple[set[int], str, str]:
        if language == "ja":
            return self._japanese_boundaries(text)
        if language == "zh":
            return self._chinese_boundaries(text)
        return {len(text)}, "alignment-records", "none"

    def _japanese_boundaries(self, text: str) -> tuple[set[int], str, str]:
        from sudachipy import dictionary, tokenizer

        japanese = self._japanese
        if japanese is None:
            japanese = dictionary.Dictionary(dict="small").create()
            self._japanese = japanese
        tokens = japanese.tokenize(text, tokenizer.Tokenizer.SplitMode.B)
        boundaries = {0, len(text), *(token.end() for token in tokens)}
        for token in tokens:
            part = token.part_of_speech()
            if part and (
                part[0] == "助動詞"
                or (part[0] in {"動詞", "形容詞"} and part[1] == "非自立可能")
                or (part[0] == "名詞" and part[2] == "助数詞可能")
            ):
                boundaries.discard(token.begin())
            if part and part[0] == "接頭辞":
                boundaries.discard(token.end())
        _tailor_punctuation_boundaries(text, boundaries)
        boundaries.intersection_update(grapheme_boundaries(text))
        return (
            boundaries,
            "sudachi-b",
            f"SudachiPy/{version('SudachiPy')};"
            f"SudachiDict-small/{version('SudachiDict-small')}",
        )

    def _chinese_boundaries(self, text: str) -> tuple[set[int], str, str]:
        import jieba

        chinese = self._chinese
        if chinese is None:
            self._jieba_cache = TemporaryDirectory(prefix="multisubs-jieba-")
            chinese = jieba.Tokenizer()
            # jieba initializes this dynamic attribute to None, then accepts a
            # temporary-directory path before initialize() builds its cache.
            cast(Any, chinese).tmp_dir = self._jieba_cache.name
            try:
                with redirect_stderr(io.StringIO()):
                    chinese.initialize()
            except Exception:
                self.close()
                raise
            self._chinese = chinese
        tokens = tuple(chinese.tokenize(text, HMM=True))
        boundaries = {0, len(text), *(end for _, _, end in tokens)}
        _tailor_punctuation_boundaries(text, boundaries)
        boundaries.intersection_update(grapheme_boundaries(text))
        return boundaries, "jieba-hmm", f"jieba/{version('jieba')}"


def _segmentation_language(text: str, language: str | None) -> str | None:
    canonical = (language or "").lower().split("-", 1)[0]
    if language is not None:
        return canonical if canonical in {"ja", "zh"} else None
    if any("\u3040" <= character <= "\u30ff" for character in text):
        return "ja"
    if any("\u3400" <= character <= "\u9fff" for character in text):
        return "zh"
    return None


def _tailor_punctuation_boundaries(text: str, boundaries: set[int]) -> None:
    """Attach closing marks left and opening marks right, including quote runs."""
    for index, character in enumerate(text):
        if character in _SENTENCE_MARKS | _CLAUSE_MARKS | _CLOSING_MARKS:
            boundaries.discard(index)
        if character in _OPENING_MARKS:
            boundaries.discard(index + 1)


def _groups_from_boundaries(
    source_map: SubtitleSourceMap,
    lexical_boundaries: set[int],
    *,
    strategy: str,
    backend_version: str,
) -> tuple[SubtitleDisplayGroup, ...]:
    spans = _alignment_spans(source_map)
    source_pieces = _source_pieces_by_record(source_map)
    alignment_granularity = _alignment_granularity(spans)
    safe_pause_boundaries = set(grapheme_boundaries(source_map.normalized_text))
    groups: list[SubtitleDisplayGroup] = []
    pending: list[SubtitleSourceSpan] = []
    for span in spans:
        if (
            pending
            and pending[-1].end in safe_pause_boundaries
            and _spans_have_significant_pause(pending[-1], span)
        ):
            groups.append(
                _display_group(
                    pending,
                    len(groups),
                    "pause",
                    strategy,
                    backend_version,
                    source_pieces,
                    alignment_granularity,
                )
            )
            pending = []
        pending.append(span)
        assert span.end is not None
        if span.end in lexical_boundaries:
            boundary_class = _boundary_class(
                _source_text_for_group(source_pieces, pending)
            )
            groups.append(
                _display_group(
                    pending,
                    len(groups),
                    boundary_class,
                    strategy,
                    backend_version,
                    source_pieces,
                    alignment_granularity,
                )
            )
            pending = []
    if pending:
        groups.append(
            _display_group(
                pending,
                len(groups),
                _boundary_class(_source_text_for_group(source_pieces, pending)),
                strategy,
                backend_version,
                source_pieces,
                alignment_granularity,
            )
        )
    return tuple(groups)


def _display_group(
    spans: Sequence[SubtitleSourceSpan],
    identity: int,
    boundary_class: str,
    strategy: str,
    backend_version: str,
    source_pieces: Mapping[int, str],
    alignment_granularity: str,
) -> SubtitleDisplayGroup:
    indexes = tuple(
        span.record_index for span in spans if span.record_index is not None
    )
    first, last = spans[0], spans[-1]
    assert first.start is not None and last.end is not None
    assert first.start_time is not None and last.end_time is not None
    return SubtitleDisplayGroup(
        identity=identity,
        source_segment_index=first.source_segment_index,
        record_indexes=indexes,
        source_start=first.start,
        source_end=last.end,
        source_text=_source_text_for_group(source_pieces, spans),
        start_time=first.start_time,
        end_time=last.end_time,
        boundary_class=boundary_class,
        strategy=strategy,
        backend_version=backend_version,
        alignment_granularity=alignment_granularity,
    )


def _spans_have_significant_pause(
    previous: SubtitleSourceSpan, next_span: SubtitleSourceSpan
) -> bool:
    return (
        previous.end_time is not None
        and next_span.start_time is not None
        and next_span.start_time - previous.end_time >= PAUSE_BREAK_THRESHOLD
    )


def _source_text_for_group(
    source_pieces: Mapping[int, str],
    spans: Sequence[SubtitleSourceSpan],
) -> str:
    return "".join(
        source_pieces.get(span.record_index, "")
        for span in spans
        if span.record_index is not None
    )


def _alignment_granularity(spans: Sequence[SubtitleSourceSpan]) -> str:
    character_flags = [len(grapheme_clusters(span.text)) == 1 for span in spans]
    if all(character_flags):
        return "character"
    if any(character_flags):
        return "mixed"
    return "word"


def _boundary_class(text: str) -> str:
    stripped = text.rstrip()
    while stripped and stripped[-1] in _CLOSING_MARKS:
        stripped = stripped[:-1].rstrip()
    if stripped and stripped[-1] in _SENTENCE_MARKS:
        return "sentence"
    if stripped and stripped[-1] in _CLAUSE_MARKS:
        return "clause"
    return "lexical"


def build_source_text_map(
    source_text: object,
    records: Sequence[object],
    *,
    fallback_text: str | None = None,
    source_segment_index: int = 0,
) -> SubtitleSourceMap:
    """Map aligned record text monotonically onto one source segment.

    Matching is intentionally cursor-based. Repeated tokens therefore resolve
    to their next occurrence instead of an unconstrained global match. Every
    unmatched source range and every unusable record remains represented in the
    returned map so callers can choose a coarse, untimed fallback.
    """
    # An empty segment text accompanied by an explicit fallback is the
    # compatibility form used by direct callers with records but no source
    # string. Keep an explicitly empty transcript authoritative when no
    # fallback was requested so callers can distinguish it from missing text.
    if isinstance(source_text, str) and not (
        source_text == "" and isinstance(fallback_text, str)
    ):
        source_provided = True
        raw_text = source_text
    else:
        source_provided = False
        raw_text = fallback_text if isinstance(fallback_text, str) else ""
    normalized_text, raw_to_normalized, normalized_to_raw = normalize_line_endings(
        raw_text
    )

    spans: list[SubtitleSourceSpan] = []
    mapped_record_indexes: list[int] = []
    timed_record_indexes: list[int] = []
    meaningful_record_indexes: list[int] = []
    reasons: list[str] = []
    cursor = 0
    previous_start: float | None = None

    for record_index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            spans.append(
                SubtitleSourceSpan(
                    source_segment_index,
                    record_index,
                    None,
                    None,
                    "",
                    "unmatched-record",
                    matched=False,
                    granularity="alignment-record",
                )
            )
            reasons.append("unmatched-alignment-record")
            continue

        raw_word = raw_record.get("word")
        token = raw_word.strip(" \t\r\n\v\f") if isinstance(raw_word, str) else ""
        token, _, _ = normalize_line_endings(token)
        if token:
            meaningful_record_indexes.append(record_index)
        match_start = normalized_text.find(token, cursor) if token else -1
        start_time = _finite_time(raw_record.get("start"))
        end_time = _finite_time(raw_record.get("end"))
        timed = (
            start_time is not None and end_time is not None and end_time >= start_time
        )
        if not timed:
            reasons.append("missing-or-invalid-alignment-time")
        elif previous_start is not None:
            assert start_time is not None
            if start_time < previous_start:
                reasons.append("non-chronological-alignment")
        if timed:
            assert start_time is not None
            previous_start = start_time

        if not token or match_start < 0:
            spans.append(
                SubtitleSourceSpan(
                    source_segment_index,
                    record_index,
                    None,
                    None,
                    token,
                    "unmatched-record",
                    start_time if timed else None,
                    end_time if timed else None,
                    matched=False,
                    granularity="alignment-record",
                )
            )
            reasons.append("unmatched-alignment-record")
            continue

        if match_start > cursor:
            spans.append(
                _gap_span(
                    normalized_text[cursor:match_start],
                    cursor,
                    match_start,
                    source_segment_index,
                )
            )
        match_end = match_start + len(token)
        matched_text = normalized_text[match_start:match_end]
        spans.append(
            SubtitleSourceSpan(
                source_segment_index,
                record_index,
                match_start,
                match_end,
                matched_text,
                "alignment",
                start_time if timed else None,
                end_time if timed else None,
            )
        )
        mapped_record_indexes.append(record_index)
        if timed:
            timed_record_indexes.append(record_index)
        cursor = match_end

    if cursor < len(normalized_text):
        spans.append(
            _gap_span(
                normalized_text[cursor:],
                cursor,
                len(normalized_text),
                source_segment_index,
            )
        )

    if not meaningful_record_indexes:
        reasons.append("missing-alignment")
    if len(mapped_record_indexes) != len(meaningful_record_indexes):
        reasons.append("unmatched-alignment-record")
    if any(span.kind == "unmatched-source" for span in spans):
        reasons.append("unmatched-source-text")

    unique_reasons = tuple(dict.fromkeys(reasons))
    complete = not unique_reasons or set(unique_reasons) <= {
        "missing-or-invalid-alignment-time",
        "non-chronological-alignment",
    }
    # A source map is text-complete only when every meaningful source character
    # belongs to a matched record or an intentional separator. Invalid timing
    # does not erase the text, but it does make timing-dependent effects unsafe.
    complete = complete and not any(
        span.kind in {"unmatched-source", "unmatched-record"} and bool(span.text)
        for span in spans
    )
    timing_complete = (
        complete
        and bool(mapped_record_indexes)
        and len(timed_record_indexes) == len(mapped_record_indexes)
        and "non-chronological-alignment" not in unique_reasons
    )
    if not timing_complete and complete and mapped_record_indexes:
        # Keep the reason additive and stable even when the invalid-time reason
        # was already collected for several records.
        if "incomplete-alignment-timing" not in unique_reasons:
            unique_reasons = (*unique_reasons, "incomplete-alignment-timing")

    return SubtitleSourceMap(
        raw_text=raw_text,
        normalized_text=normalized_text,
        spans=tuple(spans),
        raw_to_normalized=raw_to_normalized,
        normalized_to_raw=normalized_to_raw,
        source_provided=source_provided,
        complete=complete,
        timing_complete=timing_complete,
        fallback_reasons=unique_reasons,
        record_count=len(records),
        mapped_record_indexes=tuple(mapped_record_indexes),
        timed_record_indexes=tuple(timed_record_indexes),
    )


def source_text_for_records(
    source_map: SubtitleSourceMap,
    record_indexes: Sequence[int] | None = None,
) -> str:
    """Reconstruct source text for selected records without adding separators."""
    indexes = (
        source_map.mapped_record_indexes
        if record_indexes is None
        else tuple(record_indexes)
    )
    source_pieces = _source_pieces_by_record(source_map)
    pieces = [source_pieces[index] for index in indexes if index in source_pieces]
    return _trim_display_edges("".join(pieces))


def display_text_for_records(
    source_map: SubtitleSourceMap,
    record_indexes: Sequence[int] | None = None,
    *,
    transform: Callable[[str], str] | None = None,
) -> str:
    """Reconstruct transformed display text while retaining source identity."""
    units = display_units_for_records(source_map, record_indexes, transform=transform)
    return _trim_display_edges("".join(unit.display_text for unit in units))


def source_piece_for_record(source_map: SubtitleSourceMap, record_index: int) -> str:
    """Return the source piece assigned to one record, including its gap."""
    span = _record_span(source_map, record_index)
    if span is None or span.start is None or span.end is None:
        return ""
    previous_end = _previous_record_end(source_map, span)
    suffix = _trailing_source(source_map, span)
    return source_map.normalized_text[previous_end : span.end] + suffix


def display_units_for_records(
    source_map: SubtitleSourceMap,
    record_indexes: Sequence[int] | None = None,
    *,
    transform: Callable[[str], str] | None = None,
) -> tuple[SubtitleDisplayUnit, ...]:
    """Create transformed units with exact source separators and offsets."""
    transform = transform or (lambda value: value)
    requested = (
        source_map.mapped_record_indexes
        if record_indexes is None
        else tuple(record_indexes)
    )
    selected = set(requested)
    units: list[SubtitleDisplayUnit] = []
    line_breaks = set(line_break_boundaries(source_map.normalized_text))
    alignment_spans = _alignment_spans(source_map)
    previous_end = 0
    for span_index, span in enumerate(alignment_spans):
        assert span.start is not None and span.end is not None
        if span.record_index not in selected:
            previous_end = span.end
            continue
        assert span.record_index is not None
        source_prefix = source_map.normalized_text[previous_end : span.start]
        source_suffix = (
            source_map.normalized_text[span.end :]
            if span_index == len(alignment_spans) - 1
            else ""
        )
        units.append(
            SubtitleDisplayUnit(
                source_segment_index=span.source_segment_index,
                record_index=span.record_index,
                source_start=span.start,
                source_end=span.end,
                source_prefix=source_prefix,
                source_token=span.text,
                source_suffix=source_suffix,
                display_prefix=_display_separator(source_prefix),
                display_token=transform(span.text),
                display_suffix=_display_separator(source_suffix),
                can_break_before=span.start in line_breaks and span.start > 0,
            )
        )
        previous_end = span.end
    return tuple(units)


def _alignment_spans(source_map: SubtitleSourceMap) -> tuple[SubtitleSourceSpan, ...]:
    return tuple(
        span
        for span in source_map.spans
        if span.kind == "alignment"
        and span.record_index is not None
        and span.start is not None
        and span.end is not None
    )


def _record_span(
    source_map: SubtitleSourceMap, record_index: int
) -> SubtitleSourceSpan | None:
    return next(
        (
            span
            for span in _alignment_spans(source_map)
            if span.record_index == record_index
        ),
        None,
    )


def _source_pieces_by_record(source_map: SubtitleSourceMap) -> dict[int, str]:
    spans = _alignment_spans(source_map)
    result: dict[int, str] = {}
    previous_end = 0
    for span_index, span in enumerate(spans):
        assert span.record_index is not None
        assert span.end is not None
        suffix = (
            source_map.normalized_text[span.end :]
            if span_index == len(spans) - 1
            else ""
        )
        result[span.record_index] = (
            source_map.normalized_text[previous_end : span.end] + suffix
        )
        previous_end = span.end
    return result


def _previous_record_end(
    source_map: SubtitleSourceMap, span: SubtitleSourceSpan
) -> int:
    assert span.start is not None
    previous = [
        item
        for item in _alignment_spans(source_map)
        if item.end is not None and item.end <= span.start
    ]
    if not previous:
        return 0
    assert previous[-1].end is not None
    return previous[-1].end


def _trailing_source(source_map: SubtitleSourceMap, span: SubtitleSourceSpan) -> str:
    alignment_spans = _alignment_spans(source_map)
    if not alignment_spans or alignment_spans[-1] != span:
        return ""
    assert span.end is not None
    return source_map.normalized_text[span.end :]


def _gap_span(
    text: str,
    start: int,
    end: int,
    source_segment_index: int,
) -> SubtitleSourceSpan:
    is_separator = bool(text) and all(character.isspace() for character in text)
    return SubtitleSourceSpan(
        source_segment_index,
        None,
        start,
        end,
        text,
        "separator" if is_separator else "unmatched-source",
        matched=is_separator,
        granularity="separator" if is_separator else "source-text",
    )


def _display_separator(text: str) -> str:
    return text.replace("\n", " ")


def _trim_display_edges(text: str) -> str:
    """Trim ordinary display padding without treating NBSP as disposable."""
    return text.strip(" \t\r\n\v\f")


def _finite_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    return (
        number
        if number >= 0
        and number == number
        and number not in {float("inf"), float("-inf")}
        else None
    )
