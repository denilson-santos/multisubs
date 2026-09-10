"""Font-aware subtitle text wrapping shared by transcription and preview."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from functools import cache
from typing import Any

from .layout import WrappingMetrics
from .models import (
    SubtitleDisplayFragment,
    SubtitleDisplayUnit,
    SubtitleVisualLine,
    TextCase,
)
from .text_segmentation import (
    grapheme_clusters as _unicode_grapheme_clusters,
)
from .text_segmentation import (
    line_break_boundaries,
)
from .text_segmentation import (
    normalise_display_text as _normalise_unicode_display_text,
)

PAUSE_BREAK_THRESHOLD = 0.45


def normalise_display_text(text: str) -> str:
    """Normalize physical line endings and whitespace for display text."""
    return _normalise_unicode_display_text(text)


def transform_display_text(text: str, text_case: TextCase) -> str:
    """Apply one typed, locale-independent case transform to plain text."""
    if text_case is TextCase.ORIGINAL:
        return text
    if text_case is TextCase.UPPERCASE:
        return text.upper()
    if text_case is TextCase.LOWERCASE:
        return text.lower()
    raise ValueError("text_case must use the typed TextCase contract")


def has_multiple_visual_lines(text: str) -> bool:
    """Return whether display text contains more than one visual line."""
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return len(normalised.split("\n")) > 1


def wrap_subtitle_text(
    text: str,
    words: Sequence[Mapping[str, Any]] | None = None,
    *,
    metrics: WrappingMetrics,
) -> str:
    """Wrap one subtitle using the resolved width and height budgets."""
    lines, _ = _layout_text_lines(text, words, metrics)
    return "\n".join(lines)


def fit_first_text_segment(text: str, *, metrics: WrappingMetrics) -> str:
    """Return the longest first lexical segment that fits the visual budget.

    Preview text has no timestamps, but it can still model the first timed cue
    that normal aligned transcription would create. The remaining text is left
    for a hypothetical later cue instead of overflowing the preview envelope.
    """
    normalised = normalise_display_text(text)
    if not normalised:
        return ""
    if line_count(normalised, None, metrics) <= metrics.line_capacity:
        return wrap_subtitle_text(normalised, metrics=metrics)

    units, compact, _ = _text_units(normalised, None)
    if len(units) < 2:
        return wrap_subtitle_text(normalised, metrics=metrics)

    def join(parts: Sequence[str]) -> str:
        return "".join(parts) if compact else join_text_parts(parts)

    break_at = _find_best_text_layout_break(units, join, metrics)
    return wrap_subtitle_text(join(units[:break_at]), metrics=metrics)


def line_count(
    text: str,
    words: Sequence[Mapping[str, Any]] | None,
    metrics: WrappingMetrics,
) -> int:
    """Return visual line count, or capacity plus one when it overflows."""
    lines, fits = _layout_text_lines(text, words, metrics)
    return len(lines) if fits else metrics.line_capacity + 1


def split_words_for_layout(
    words: Sequence[Mapping[str, Any]],
    metrics: WrappingMetrics,
) -> list[list[dict[str, Any]]]:
    """Split aligned words into timed groups that fit the line capacity."""
    remaining = [dict(word) for word in words]
    groups: list[list[dict[str, Any]]] = []
    while remaining:
        text = words_to_text(remaining)
        if line_count(text, remaining, metrics) <= metrics.line_capacity:
            groups.append(remaining)
            break
        if len(remaining) == 1:
            groups.append(remaining)
            break
        break_at = _find_best_layout_break(remaining, metrics)
        if break_at <= 0 or break_at >= len(remaining):
            break_at = 1
        groups.append(remaining[:break_at])
        remaining = remaining[break_at:]
    return groups


def split_display_units_for_layout(
    units: Sequence[SubtitleDisplayUnit],
    metrics: WrappingMetrics,
    *,
    boundary_words: Sequence[Mapping[str, Any]] | None = None,
) -> list[list[SubtitleDisplayUnit]]:
    """Split mapped display units into groups that fit the visual budget."""
    remaining = list(units)
    groups: list[list[SubtitleDisplayUnit]] = []
    offset = 0
    while remaining:
        _, fits = _layout_display_units(remaining, metrics)
        if fits or len(remaining) == 1:
            groups.append(remaining)
            break
        break_at = _find_best_display_unit_break(
            remaining,
            metrics,
            boundary_words=(
                boundary_words[offset:] if boundary_words is not None else None
            ),
        )
        if break_at <= 0 or break_at >= len(remaining):
            break_at = 1
        groups.append(remaining[:break_at])
        remaining = remaining[break_at:]
        offset += break_at
    return groups


def _layout_display_units(
    units: Sequence[SubtitleDisplayUnit],
    metrics: WrappingMetrics,
) -> tuple[list[list[SubtitleDisplayUnit]], bool]:
    if not units:
        return [], True
    text = _join_display_units(units)
    if _content_width(text, metrics) <= metrics.width_budget:
        return [list(units)], True
    if len(units) < 2 or metrics.line_capacity <= 1:
        return [list(units)], False
    allowed_breaks = {
        index for index, unit in enumerate(units) if index > 0 and unit.can_break_before
    }
    ranges, fits = _partition_text_unit_ranges(
        units,
        _join_display_units,
        metrics,
        source_words=None,
        allowed_breaks=allowed_breaks,
    )
    return (
        [list(units[start:end]) for start, end in ranges] if ranges else [list(units)],
        fits,
    )


def _find_best_display_unit_break(
    units: Sequence[SubtitleDisplayUnit],
    metrics: WrappingMetrics,
    *,
    boundary_words: Sequence[Mapping[str, Any]] | None,
) -> int:
    candidates: list[int] = []
    for index in range(1, len(units)):
        _, fits = _layout_display_units(units[:index], metrics)
        if not fits:
            break
        candidates.append(index)
    if not candidates:
        return 1

    def key(index: int) -> tuple[int, int, int]:
        priority = (
            boundary_priority(boundary_words, index)
            if boundary_words is not None and len(boundary_words) == len(units)
            else _display_boundary_priority(
                [unit.display_token for unit in units], None, index
            )
        )
        return _layout_break_key(
            index=index,
            unit_count=len(units),
            priority=priority,
        )

    return max(candidates, key=key)


def _join_display_units(units: Sequence[SubtitleDisplayUnit]) -> str:
    """Join mapped units without inventing or deleting internal separators."""
    return _trim_display_edges("".join(unit.display_text for unit in units))


def _render_unit_line(
    units: Sequence[SubtitleDisplayUnit],
    *,
    word_indexes: Mapping[int, int] | None,
    trim_leading: bool,
) -> tuple[str, tuple[SubtitleDisplayFragment, ...], str]:
    if not units:
        return "", (), ""
    fragments: list[SubtitleDisplayFragment] = []
    pieces: list[str] = []
    first_prefix = units[0].display_prefix
    # Keep the source separator for reverse-mapping diagnostics. Display line
    # breaks may normalize CRLF/CR to LF and physical newlines to spaces.
    replaced_separator = units[0].source_prefix
    if trim_leading:
        first_prefix = first_prefix.lstrip(" \t\r\n\v\f")
    if first_prefix:
        pieces.append(first_prefix)
        fragments.append(SubtitleDisplayFragment(first_prefix))
    for index, unit in enumerate(units):
        if index:
            if unit.display_prefix:
                pieces.append(unit.display_prefix)
                fragments.append(SubtitleDisplayFragment(unit.display_prefix))
        if unit.display_token:
            pieces.append(unit.display_token)
            word_index = (
                word_indexes.get(unit.record_index, unit.record_index)
                if word_indexes is not None
                else unit.record_index
            )
            fragments.append(SubtitleDisplayFragment(unit.display_token, word_index))
        if index == len(units) - 1 and unit.display_suffix:
            display_suffix = unit.display_suffix.strip(" \t\r\n\v\f")
            if display_suffix:
                pieces.append(display_suffix)
                fragments.append(SubtitleDisplayFragment(display_suffix))
    return _trim_display_edges("".join(pieces)), tuple(fragments), replaced_separator


def render_display_units(
    units: Sequence[SubtitleDisplayUnit],
    metrics: WrappingMetrics,
    *,
    word_indexes: Mapping[int, int] | None = None,
) -> tuple[str, tuple[SubtitleDisplayFragment, ...], tuple[str, ...]]:
    """Wrap mapped units while preserving fragment and line-break provenance."""
    lines, _ = _layout_display_units(units, metrics)
    rendered_lines: list[str] = []
    fragments: list[SubtitleDisplayFragment] = []
    line_breaks: list[str] = []
    for line_index, line in enumerate(lines):
        rendered_line, line_fragments, replaced_separator = _render_unit_line(
            line,
            word_indexes=word_indexes,
            trim_leading=True,
        )
        if line_index:
            line_breaks.append(replaced_separator)
        rendered_lines.append(rendered_line)
        fragments.extend(line_fragments)
        if line_index < len(lines) - 1:
            fragments.append(SubtitleDisplayFragment("\n"))
    return "\n".join(rendered_lines), tuple(fragments), tuple(line_breaks)


def words_to_text(
    words: Sequence[Mapping[str, Any]],
    *,
    source_text: str | None = None,
) -> str:
    """Join word-like records, using source text when the caller has it.

    The source-aware path is lossless. The no-source form is a compatibility
    adapter for direct Python callers and uses conservative script rules only
    when there is no authoritative separator to preserve.
    """
    if source_text is not None:
        return normalise_display_text(source_text)
    return join_text_parts(str(word.get("word", "")) for word in words)


def build_display_fragments(
    display_text: str,
    words: Sequence[Mapping[str, Any]],
) -> tuple[SubtitleDisplayFragment, ...] | None:
    """Map exact display text back to its ordered aligned-word fragments.

    The mapping scans the already rendered display string against the source
    word records. Separators, including intentional line breaks, remain
    untimed fragments so the effect compiler never has to tokenize or rewrite
    user-facing subtitle text.
    """
    if not isinstance(display_text, str) or not words:
        return None

    fragments: list[SubtitleDisplayFragment] = []
    cursor = 0
    for index, word in enumerate(words):
        if not isinstance(word, Mapping):
            return None
        token = _trim_display_edges(str(word.get("word", "")))
        if not token:
            return None
        token_start = display_text.find(token, cursor)
        if token_start < cursor:
            return None
        separator = display_text[cursor:token_start]
        if separator:
            fragments.append(SubtitleDisplayFragment(separator))
        fragments.append(SubtitleDisplayFragment(token, word_index=index))
        cursor = token_start + len(token)

    remainder = display_text[cursor:]
    if remainder:
        fragments.append(SubtitleDisplayFragment(remainder))
    if (
        not fragments
        or "".join(fragment.text for fragment in fragments) != display_text
    ):
        return None
    return tuple(fragments)


def build_visual_lines(
    display_text: str,
    fragments: Sequence[SubtitleDisplayFragment] | None,
    metrics: WrappingMetrics,
) -> tuple[SubtitleVisualLine, ...]:
    """Split display fragments into measured lines for explicit rendering.

    The wrapped text is already the source of truth for line boundaries. This
    helper only partitions those boundaries while retaining word indexes so
    karaoke compilers can reuse the exact aligned fragments on each line.
    """
    normalised = display_text.replace("\r\n", "\n").replace("\r", "\n")
    line_texts = normalised.split("\n")
    line_fragments: list[list[SubtitleDisplayFragment]] = [[] for _ in line_texts]
    if fragments is None:
        for index, line in enumerate(line_texts):
            if line:
                line_fragments[index].append(SubtitleDisplayFragment(line))
    else:
        line_index = 0
        for fragment in fragments:
            if not isinstance(fragment, SubtitleDisplayFragment):
                continue
            parts = fragment.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            for part_index, part in enumerate(parts):
                if part:
                    line_fragments[line_index].append(
                        SubtitleDisplayFragment(part, fragment.word_index)
                    )
                if part_index < len(parts) - 1 and line_index + 1 < len(line_texts):
                    line_index += 1

    return tuple(
        SubtitleVisualLine(
            text=line,
            fragments=tuple(line_fragments[index]),
            width=metrics.text_measurer.measure(line),
            index=index,
        )
        for index, line in enumerate(line_texts)
    )


def join_text_parts(parts: Sequence[str] | Any) -> str:
    """Join word-like parts for legacy callers without a source string.

    This compatibility path cannot recover omitted source separators. It only
    supplies a conservative default; production aligned text uses the source
    map and never reaches this heuristic.
    """
    result = ""
    for raw_part in parts:
        part = _trim_join_part(str(raw_part))
        if not part:
            continue
        if result and _needs_text_separator(result[-1], part[0]):
            result += " "
        result += part
    return _trim_join_part(result)


def is_cjk_or_emoji(character: str) -> bool:
    """Return whether a character normally joins without a space."""
    codepoint = ord(character)
    return (
        _is_wide_character(character)
        or 0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
    )


def grapheme_clusters(text: str) -> list[str]:
    """Return extended grapheme clusters from the selected Unicode adapter."""
    return _unicode_grapheme_clusters(text)


def ends_sentence(word: str) -> bool:
    """Return whether a word has a sentence-ending mark."""
    return word.rstrip().endswith((".", "!", "?", "…"))


def ends_clause(word: str) -> bool:
    """Return whether a word has a clause boundary mark."""
    return word.rstrip().endswith((",", ";", ":", "—", "–"))


def has_significant_pause(
    previous_word: Mapping[str, Any], next_word: Mapping[str, Any]
) -> bool:
    """Return whether adjacent aligned words have a readable pause."""
    previous_end = _finite_time(previous_word.get("end"))
    next_start = _finite_time(next_word.get("start"))
    return (
        previous_end is not None
        and next_start is not None
        and next_start - previous_end >= PAUSE_BREAK_THRESHOLD
    )


def boundary_priority(words: Sequence[Mapping[str, Any]], index: int) -> int:
    """Score a word boundary by sentence, clause, and pause semantics."""
    previous_word = words[index - 1]
    next_word = words[index]
    previous_text = str(previous_word.get("word", ""))
    if ends_sentence(previous_text):
        return 3
    if ends_clause(previous_text):
        return 2
    if has_significant_pause(previous_word, next_word):
        return 1
    return 0


def _find_best_layout_break(
    words: Sequence[Mapping[str, Any]],
    metrics: WrappingMetrics,
) -> int:
    candidates: list[int] = []
    for index in range(1, len(words)):
        _, fits = _layout_text_lines(
            words_to_text(words[:index]), words[:index], metrics
        )
        # For a multi-unit prefix, adding ordered text cannot make it fit again.
        if not fits:
            break
        candidates.append(index)
    if not candidates:
        return 1

    def key(index: int) -> tuple[int, int, int]:
        return _layout_break_key(
            index=index,
            unit_count=len(words),
            priority=boundary_priority(words, index),
        )

    return max(candidates, key=key)


def _find_best_text_layout_break(
    units: Sequence[str],
    join: Callable[[Sequence[str]], str],
    metrics: WrappingMetrics,
) -> int:
    """Choose the first preview-cue boundary with normal layout priorities."""
    candidates: list[int] = []
    for index in range(1, len(units)):
        _, fits = _layout_text_lines(join(units[:index]), None, metrics)
        # For a multi-unit prefix, adding ordered text cannot make it fit again.
        if not fits:
            break
        candidates.append(index)
    if not candidates:
        return 1

    def key(index: int) -> tuple[int, int, int]:
        return _layout_break_key(
            index=index,
            unit_count=len(units),
            priority=_display_boundary_priority(units, None, index),
        )

    return max(candidates, key=key)


def _layout_break_key(
    *,
    index: int,
    unit_count: int,
    priority: int,
) -> tuple[int, int, int]:
    """Rank boundaries by semantics, orphan avoidance, then retained text."""
    orphan_penalty = int(index == 1 or unit_count - index == 1)
    return (
        priority,
        -orphan_penalty,
        index,
    )


def _layout_text_lines(
    text: str,
    words: Sequence[Mapping[str, Any]] | None,
    metrics: WrappingMetrics,
) -> tuple[list[str], bool]:
    normalised = normalise_display_text(text)
    if not normalised:
        return [], True
    units, compact, source_words = _text_units(normalised, words)
    if len(units) < 2:
        return [normalised], True

    def join(parts: Sequence[str]) -> str:
        if compact:
            return _trim_display_edges("".join(parts))
        return join_text_parts(parts)

    if _content_width(join(units), metrics) <= metrics.width_budget:
        return [normalised], True
    if metrics.line_capacity <= 1:
        return [normalised], False
    allowed_breaks = None
    if compact and any(character.isspace() for character in normalised):
        allowed_breaks = _text_unit_breaks(normalised, units)
    return _partition_text_units(
        units,
        join,
        metrics,
        source_words=source_words,
        allowed_breaks=allowed_breaks,
    )


def _text_units(
    text: str,
    words: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[str], bool, list[Mapping[str, Any]] | None]:
    if words:
        source_words = [
            word for word in words if _trim_display_edges(str(word.get("word", "")))
        ]
        return (
            [_trim_display_edges(str(word.get("word", ""))) for word in source_words],
            False,
            source_words,
        )
    if any(character.isspace() for character in text):
        return _text_units_with_separators(text), True, None
    clusters = grapheme_clusters(text)
    cluster_ends: list[int] = []
    cursor = 0
    for cluster in clusters:
        cursor += len(cluster)
        cluster_ends.append(cursor)
    break_boundaries = set(line_break_boundaries(text))
    if (
        len(clusters) > 1
        and any(boundary in break_boundaries for boundary in cluster_ends[:-1])
        and sum(boundary in break_boundaries for boundary in cluster_ends[:-1])
        >= max(1, len(clusters) - 2)
    ):
        return clusters, True, None
    return [text], True, None


def _partition_text_units(
    units: Sequence[Any],
    join: Callable[[Sequence[Any]], str],
    metrics: WrappingMetrics,
    *,
    source_words: Sequence[Mapping[str, Any]] | None,
    allowed_breaks: Collection[int] | None = None,
) -> tuple[list[str], bool]:
    ranges, fits = _partition_text_unit_ranges(
        units,
        join,
        metrics,
        source_words=source_words,
        allowed_breaks=allowed_breaks,
    )
    if not ranges:
        return [join(units)], False
    return [join(units[start:end]) for start, end in ranges], fits


def _partition_text_unit_ranges(
    units: Sequence[Any],
    join: Callable[[Sequence[Any]], str],
    metrics: WrappingMetrics,
    *,
    source_words: Sequence[Mapping[str, Any]] | None,
    allowed_breaks: Collection[int] | None = None,
) -> tuple[list[tuple[int, int]], bool]:
    """Partition arbitrary units and return ranges for mapped renderers."""
    unit_count = len(units)
    maximum_lines = min(metrics.line_capacity, unit_count)
    allowed = (
        set(range(1, unit_count)) if allowed_breaks is None else set(allowed_breaks)
    )

    @cache
    def line(start: int, end: int) -> tuple[str, float]:
        value = join(units[start:end])
        return value, _content_width(value, metrics)

    @cache
    def partitions(
        start: int,
        lines_left: int,
        allow_overflow: bool,
    ) -> tuple[tuple[int, ...], ...]:
        if lines_left == 1:
            _, width = line(start, unit_count)
            if allow_overflow or _line_fits(
                width,
                unit_count=unit_count - start,
                budget=metrics.width_budget,
            ):
                return ((unit_count,),)
            return ()

        results: list[tuple[int, ...]] = []
        final_start = unit_count - lines_left + 1
        for end in range(start + 1, final_start + 1):
            if end < unit_count and end not in allowed:
                continue
            _, width = line(start, end)
            if not allow_overflow and not _line_fits(
                width,
                unit_count=end - start,
                budget=metrics.width_budget,
            ):
                continue
            for tail in partitions(end, lines_left - 1, allow_overflow):
                results.append((end, *tail))
        return tuple(results)

    for line_count_value in range(2, maximum_lines + 1):
        candidates = partitions(0, line_count_value, False)
        if candidates:
            best = min(
                candidates,
                key=lambda endings: _partition_score(
                    endings,
                    line,
                    unit_count,
                    metrics.width_budget,
                    units,
                    source_words,
                ),
            )
            return _ranges_from_endings(best), True

    candidates = partitions(0, maximum_lines, True)
    if not candidates:
        return [], False
    best = min(
        candidates,
        key=lambda endings: _partition_score(
            endings,
            line,
            unit_count,
            metrics.width_budget,
            units,
            source_words,
        ),
    )
    return _ranges_from_endings(best), False


def _line_fits(width: float, *, unit_count: int, budget: int) -> bool:
    return width <= budget or unit_count == 1


def _content_width(text: str, metrics: WrappingMetrics) -> float:
    """Measure text content against the budget after decoration allowance."""
    return metrics.text_measurer.measure(text)


def _partition_lines(
    endings: Sequence[int],
    line: Callable[[int, int], tuple[str, float]],
) -> list[str]:
    result: list[str] = []
    start = 0
    for end in endings:
        result.append(line(start, end)[0])
        start = end
    return result


def _ranges_from_endings(endings: Sequence[int]) -> list[tuple[int, int]]:
    starts = (0, *endings[:-1])
    return list(zip(starts, endings, strict=True))


def _partition_score(
    endings: Sequence[int],
    line: Callable[[int, int], tuple[str, float]],
    unit_count: int,
    width_budget: int,
    units: Sequence[Any],
    source_words: Sequence[Mapping[str, Any]] | None,
) -> tuple[int, float, float, int, float, float, tuple[int, ...]]:
    starts = (0, *endings[:-1])
    widths = [line(start, end)[1] for start, end in zip(starts, endings, strict=True)]
    counts = [end - start for start, end in zip(starts, endings, strict=True)]
    priorities = [
        _display_boundary_priority(units, source_words, end) for end in endings[:-1]
    ]
    overflows = [max(0.0, width - width_budget) for width in widths]
    orphan_count = (
        sum(count == 1 for count in counts) if unit_count > len(counts) else 0
    )
    widest = max(widths)
    shortest = min(widths)
    short_line_penalty = max(0.0, widest * 0.35 - shortest)
    raggedness = sum((widest - width) ** 2 for width in widths)
    semantic_penalty = sum(3 - priority for priority in priorities)
    return (
        semantic_penalty,
        max(overflows),
        sum(overflows),
        orphan_count,
        short_line_penalty,
        raggedness,
        tuple(endings),
    )


def _text_units_with_separators(text: str) -> list[str]:
    """Split text into tokens while keeping each following separator exact."""
    units: list[str] = []
    unit_start = 0
    cursor = 0
    while cursor < len(text):
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor == len(text):
            break
        while cursor < len(text) and not text[cursor].isspace():
            cursor += 1
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        units.append(text[unit_start:cursor])
        unit_start = cursor
    return units or [text]


def _text_unit_breaks(text: str, units: Sequence[str]) -> set[int]:
    """Return unit boundaries permitted by Unicode line breaking."""
    boundaries = set(line_break_boundaries(text))
    result: set[int] = set()
    offset = 0
    for index, unit in enumerate(units[:-1], start=1):
        offset += len(unit)
        if offset in boundaries:
            result.add(index)
    return result


def _display_boundary_priority(
    units: Sequence[Any],
    source_words: Sequence[Mapping[str, Any]] | None,
    index: int,
) -> int:
    if source_words is not None and len(source_words) == len(units):
        return boundary_priority(source_words, index)
    previous = units[index - 1]
    if isinstance(previous, SubtitleDisplayUnit):
        previous = previous.display_token
    previous = _trim_display_edges(str(previous))
    if ends_sentence(previous):
        return 3
    if ends_clause(previous):
        return 2
    return 0


def _needs_text_separator(previous: str, next_character: str) -> bool:
    if (
        next_character in ".,!?;:%)]}»、。，！？；：》」』】〉》"
        or previous in "([{«「『【〈《"
    ):
        return False
    if _is_cjk_join_character(previous) or _is_cjk_join_character(next_character):
        return False
    return True


def _trim_join_part(text: str) -> str:
    """Trim only physical/ordinary edge whitespace in the legacy adapter."""
    return text.strip(" \t\r\n")


def _trim_display_edges(text: str) -> str:
    """Trim ordinary display padding without treating NBSP as disposable."""
    return text.strip(" \t\r\n\v\f")


def _is_cjk_join_character(character: str) -> bool:
    """Identify ideographic/kana characters for no-source compatibility joins."""
    if not character:
        return False
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x3040 <= codepoint <= 0x30FF
        or 0x31F0 <= codepoint <= 0x31FF
    )


def _is_wide_character(character: str) -> bool:
    import unicodedata

    return unicodedata.east_asian_width(character) in {"W", "F"}


def _category(character: str) -> str:
    import unicodedata

    return unicodedata.category(character)


def _finite_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if result < 0 or result != result or result in {float("inf"), float("-inf")}:
        return None
    return result
