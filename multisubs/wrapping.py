"""Font-aware subtitle text wrapping shared by transcription and preview."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import cache
from typing import Any

from .layout import WrappingMetrics, estimate_text_width
from .models import SubtitleDisplayFragment, SubtitleVisualLine

PAUSE_BREAK_THRESHOLD = 0.45


def normalise_display_text(text: str) -> str:
    """Normalize physical line endings and whitespace for display text."""
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


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
    """Return the first lexical segment that fits the resolved visual budget.

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


def words_to_text(words: Sequence[Mapping[str, Any]]) -> str:
    """Join word-like records without inserting spaces into CJK text."""
    return join_text_parts(str(word["word"]).strip() for word in words)


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
        token = str(word.get("word", "")).strip()
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
    """Join word-like parts using language-neutral separator heuristics."""
    result = ""
    for raw_part in parts:
        part = str(raw_part).strip()
        if not part:
            continue
        if result and _needs_text_separator(result[-1], part[0]):
            result += " "
        result += part
    return result.strip()


def is_cjk_or_emoji(character: str) -> bool:
    """Return whether a character normally joins without a space."""
    codepoint = ord(character)
    return (
        _is_wide_character(character)
        or 0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
    )


def grapheme_clusters(text: str) -> list[str]:
    """Group combining marks and zero-width joiner sequences."""
    clusters: list[str] = []
    current = ""
    for character in text:
        category = _category(character)
        if current and (
            category in {"Mn", "Me", "Cf"}
            or character in {"\ufe0e", "\ufe0f"}
            or current.endswith("\u200d")
        ):
            current += character
            continue
        if current:
            clusters.append(current)
        current = character
    if current:
        clusters.append(current)
    return clusters


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
    candidates = [
        index
        for index in range(1, len(words))
        if line_count(words_to_text(words[:index]), words[:index], metrics)
        <= metrics.line_capacity
    ]
    if not candidates:
        return 1

    def key(index: int) -> tuple[int, int, float, int]:
        prefix = words[:index]
        width = estimate_text_width(words_to_text(prefix), metrics)
        return _layout_break_key(
            index=index,
            unit_count=len(words),
            priority=boundary_priority(words, index),
            width=width,
            metrics=metrics,
        )

    return max(candidates, key=key)


def _find_best_text_layout_break(
    units: Sequence[str],
    join: Callable[[Sequence[str]], str],
    metrics: WrappingMetrics,
) -> int:
    """Choose the first preview-cue boundary with normal layout priorities."""
    candidates = [
        index
        for index in range(1, len(units))
        if line_count(join(units[:index]), None, metrics) <= metrics.line_capacity
    ]
    if not candidates:
        return 1

    def key(index: int) -> tuple[int, int, float, int]:
        prefix = join(units[:index])
        return _layout_break_key(
            index=index,
            unit_count=len(units),
            priority=_display_boundary_priority(units, None, index),
            width=estimate_text_width(prefix, metrics),
            metrics=metrics,
        )

    return max(candidates, key=key)


def _layout_break_key(
    *,
    index: int,
    unit_count: int,
    priority: int,
    width: float,
    metrics: WrappingMetrics,
) -> tuple[int, int, float, int]:
    """Rank a cue boundary consistently for aligned and preview text."""
    orphan_penalty = int(index == 1 or unit_count - index == 1)
    return (
        priority,
        -orphan_penalty,
        -abs(metrics.width_budget - width),
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
        return "".join(parts) if compact else join_text_parts(parts)

    if estimate_text_width(join(units), metrics) <= metrics.width_budget:
        return [normalised], True
    if metrics.line_capacity <= 1:
        return [normalised], False
    return _partition_text_units(units, join, metrics, source_words=source_words)


def _text_units(
    text: str,
    words: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[str], bool, list[Mapping[str, Any]] | None]:
    if words:
        source_words = [word for word in words if str(word.get("word", "")).strip()]
        return (
            [str(word.get("word", "")).strip() for word in source_words],
            False,
            source_words,
        )
    if any(character.isspace() for character in text):
        return text.split(), False, None
    clusters = grapheme_clusters(text)
    if len(clusters) > 1 and any(is_cjk_or_emoji(cluster[0]) for cluster in clusters):
        return clusters, True, None
    return [text], True, None


def _partition_text_units(
    units: Sequence[str],
    join: Callable[[Sequence[str]], str],
    metrics: WrappingMetrics,
    *,
    source_words: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[str], bool]:
    unit_count = len(units)
    maximum_lines = min(metrics.line_capacity, unit_count)

    @cache
    def line(start: int, end: int) -> tuple[str, float]:
        value = join(units[start:end])
        return value, estimate_text_width(value, metrics)

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
            return _partition_lines(best, line), True

    candidates = partitions(0, maximum_lines, True)
    if not candidates:
        return [join(units)], False
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
    return _partition_lines(best, line), False


def _line_fits(width: float, *, unit_count: int, budget: int) -> bool:
    return width <= budget or unit_count == 1


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


def _partition_score(
    endings: Sequence[int],
    line: Callable[[int, int], tuple[str, float]],
    unit_count: int,
    width_budget: int,
    units: Sequence[str],
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


def _display_boundary_priority(
    units: Sequence[str],
    source_words: Sequence[Mapping[str, Any]] | None,
    index: int,
) -> int:
    if source_words is not None and len(source_words) == len(units):
        return boundary_priority(source_words, index)
    previous = units[index - 1]
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
    if is_cjk_or_emoji(previous) and is_cjk_or_emoji(next_character):
        return False
    return True


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
