"""Transcription-free subtitle preview preparation and guide generation."""

from __future__ import annotations

import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .ass import (
    _render_strategy_for_segments,
    escape_ass_text,
    rgba_to_ass_color,
    write_ass,
)
from .errors import ValidationError
from .layout import (
    NativeLayoutRegion,
    WrappingMetrics,
    resolve_cue_placement,
    resolve_native_layout_region,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
)
from .models import (
    AssDrawingEvent,
    KaraokeCue,
    PreviewRequest,
    RelativeLength,
    SubtitleConfig,
    SubtitlePlacementMode,
    SubtitlePosition,
    VideoGeometry,
)
from .text_segmentation import word_units
from .wrapping import (
    build_display_fragments,
    ends_clause,
    ends_sentence,
    fit_first_text_segment,
    grapheme_clusters,
    normalise_display_text,
    transform_display_text,
)

DEFAULT_PREVIEW_TEXT = (
    "Example subtitle preview text that demonstrates a readable two-line "
    "caption on your selected video layout before final rendering"
)
MAX_PREVIEW_TIMESTAMP_SECONDS = 86_400.0
DEFAULT_PREVIEW_DURATION_MS = 4_000
MIN_PREVIEW_DURATION_MS = 1_000
MAX_PREVIEW_DURATION_MS = 15_000
_TIMESTAMP_PATTERN = re.compile(
    r"^(?P<hours>\d{2,}):(?P<minutes>[0-5]\d):"
    r"(?P<seconds>[0-5]\d)\.(?P<milliseconds>\d{1,3})$"
)
_DURATION_PATTERN = re.compile(
    r"^(?P<number>(?:0|[1-9]\d{0,4})(?:\.\d{1,3})?)(?P<unit>ms|s)$"
)
_GUIDE_COLOR = rgba_to_ass_color("#00D8FF")
_GUIDE_OUTLINE = rgba_to_ass_color("#001018")
_GUIDE_FONT_SIZE = 40


def parse_preview_timestamp(raw_value: str) -> float:
    """Parse a preview timestamp in ``HH:MM:SS.mmm`` notation."""
    if not isinstance(raw_value, str):
        raise ValidationError("preview-at must use HH:MM:SS.mmm notation")
    match = _TIMESTAMP_PATTERN.fullmatch(raw_value.strip())
    if match is None:
        raise ValidationError(
            "preview-at must use HH:MM:SS.mmm notation, for example 00:00:10.500"
        )
    milliseconds = match.group("milliseconds")
    value = (
        int(match.group("hours")) * 3_600
        + int(match.group("minutes")) * 60
        + int(match.group("seconds"))
        + int(milliseconds.ljust(3, "0")) / 1_000
    )
    if value > MAX_PREVIEW_TIMESTAMP_SECONDS:
        raise ValidationError(
            f"preview-at must not exceed {MAX_PREVIEW_TIMESTAMP_SECONDS:g} seconds"
        )
    return value


def parse_preview_duration(raw_value: object) -> int:
    """Parse an animation-preview duration into whole milliseconds."""
    if not isinstance(raw_value, str):
        raise ValidationError("preview-duration must end in ms or s")
    match = _DURATION_PATTERN.fullmatch(raw_value.strip().casefold())
    if match is None:
        raise ValidationError(
            "preview-duration must use ms or s (for example 4000ms or 4s)"
        )
    try:
        number = Decimal(match.group("number"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("preview-duration must be finite") from exc
    milliseconds = number * (1000 if match.group("unit") == "s" else 1)
    if not milliseconds.is_finite() or milliseconds != milliseconds.to_integral_value():
        raise ValidationError("preview-duration must resolve to whole milliseconds")
    result = int(milliseconds)
    if result < MIN_PREVIEW_DURATION_MS or result > MAX_PREVIEW_DURATION_MS:
        raise ValidationError("preview-duration must be from 1s through 15s")
    return result


def resolve_preview_timestamp(
    requested: float | None,
    geometry: VideoGeometry,
) -> float:
    """Resolve the requested frame time, defaulting to the video midpoint."""
    if requested is None:
        timestamp = (
            geometry.duration_seconds / 2
            if geometry.duration_seconds is not None
            else 0.0
        )
    else:
        timestamp = requested
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise ValidationError("preview-at must be a finite, non-negative timestamp")
    timestamp = float(timestamp)
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValidationError("preview-at must be a finite, non-negative timestamp")
    if timestamp > MAX_PREVIEW_TIMESTAMP_SECONDS:
        raise ValidationError(
            f"preview-at must not exceed {MAX_PREVIEW_TIMESTAMP_SECONDS:g} seconds"
        )
    duration = geometry.duration_seconds
    if duration is not None and timestamp > duration:
        raise ValidationError(
            f"preview-at ({timestamp:.3f}s) is later than the video duration "
            f"({duration:.3f}s)"
        )
    return timestamp


def normalise_preview_text(text: str) -> str:
    """Normalize and validate untrusted preview text before ASS serialization."""
    if not isinstance(text, str):
        raise ValidationError("preview-text must be text")
    normalised = normalise_display_text(text)
    if not normalised:
        raise ValidationError("preview-text must contain at least one character")
    return normalised


def build_simulated_karaoke_cue(
    display_text: str,
    cue_start: int,
    cue_end: int,
) -> KaraokeCue:
    """Build deterministic word intervals for one preview-only cue.

    Timings are ASS centiseconds. ``durations`` include the reserved pause after
    each non-final unit so the production progressive serializer still conserves
    the complete cue duration, while ``active_intervals`` retain the exact
    positive interval during which each unit is active.
    """
    if not isinstance(display_text, str) or not display_text:
        raise ValidationError("preview text must contain at least one character")
    if (
        isinstance(cue_start, bool)
        or not isinstance(cue_start, int)
        or isinstance(cue_end, bool)
        or not isinstance(cue_end, int)
        or cue_start < 0
        or cue_end <= cue_start
    ):
        raise ValidationError("preview cue timestamps must be ordered centiseconds")

    units = _preview_timing_units(display_text)
    if not units:
        raise ValidationError("preview text must contain at least one timing unit")
    duration = cue_end - cue_start
    if duration < len(units):
        raise ValidationError(
            f"preview text needs at least {len(units)} centiseconds for its "
            f"{len(units)} timing units; increase --preview-duration or shorten "
            "--preview-text"
        )

    weights = tuple(_preview_unit_weight(unit) for unit in units)
    gaps = tuple(
        _preview_gap_centiseconds(unit) if index < len(units) - 1 else 0
        for index, unit in enumerate(units)
    )
    gap_total = sum(gaps)
    maximum_gap_total = duration * 20 // 100
    if gap_total > maximum_gap_total:
        gaps = _scale_integer_values(gaps, maximum_gap_total)
        gap_total = sum(gaps)

    word_duration_total = duration - gap_total
    word_durations = _allocate_weighted_centiseconds(word_duration_total, weights)
    durations = tuple(
        word_duration + gap
        for word_duration, gap in zip(word_durations, gaps, strict=True)
    )
    fragments = build_display_fragments(
        display_text,
        [{"word": unit} for unit in units],
    )
    if fragments is None:
        raise ValidationError(
            "preview text could not be reconstructed into deterministic timing units"
        )

    active_intervals: list[tuple[int, int]] = []
    cursor = cue_start
    for word_duration, gap in zip(word_durations, gaps, strict=True):
        end = cursor + word_duration
        active_intervals.append((cursor, end))
        cursor = end + gap
    if cursor != cue_end or any(start >= end for start, end in active_intervals):
        raise ValidationError("preview timing could not conserve the cue duration")
    return KaraokeCue(
        fragments=fragments,
        durations=durations,
        active_intervals=tuple(active_intervals),
    )


def _preview_timing_units(display_text: str) -> tuple[str, ...]:
    units = word_units(display_text)
    return units or (display_text,)


def _is_punctuation_cluster(cluster: str) -> bool:
    return bool(cluster) and unicodedata.category(cluster[0]).startswith("P")


def _preview_unit_weight(unit: str) -> int:
    non_punctuation = sum(
        not unicodedata.category(cluster[0]).startswith("P")
        for cluster in grapheme_clusters(unit)
    )
    return max(1, non_punctuation)


def _preview_gap_centiseconds(unit: str) -> int:
    if ends_sentence(unit):
        return 15
    if ends_clause(unit):
        return 8
    return 4


def _scale_integer_values(values: tuple[int, ...], target: int) -> tuple[int, ...]:
    total = sum(values)
    if total <= 0 or target >= total:
        return values
    if target <= 0:
        return (0,) * len(values)
    floors = [value * target // total for value in values]
    remainders = [
        value * target - floor * total
        for value, floor in zip(values, floors, strict=True)
    ]
    for index in sorted(
        range(len(values)),
        key=lambda item: (-remainders[item], item),
    )[: target - sum(floors)]:
        floors[index] += 1
    return tuple(floors)


def _allocate_weighted_centiseconds(
    total: int,
    weights: tuple[int, ...],
) -> tuple[int, ...]:
    if total < len(weights):
        raise ValidationError(
            "preview duration is too short for the selected text; increase "
            "--preview-duration or shorten --preview-text"
        )
    minimum = [1] * len(weights)
    remaining = total - len(weights)
    weight_total = sum(weights)
    floors = [remaining * weight // weight_total for weight in weights]
    remainders = [
        remaining * weight - floor * weight_total
        for weight, floor in zip(weights, floors, strict=True)
    ]
    for index in sorted(
        range(len(weights)),
        key=lambda item: (-remainders[item], item),
    )[: remaining - sum(floors)]:
        floors[index] += 1
    return tuple(base + extra for base, extra in zip(minimum, floors, strict=True))


def build_preview_ass(
    path: Path,
    request: PreviewRequest,
    geometry: VideoGeometry,
    timestamp: float,
    *,
    resolved_config: SubtitleConfig | None = None,
    wrapping_metrics: WrappingMetrics | None = None,
) -> tuple[SubtitleConfig, str]:
    """Resolve preview layout, wrap its sample cue, and write a temporary ASS."""
    timestamp = resolve_preview_timestamp(timestamp, geometry)
    resolved_config = resolved_config or resolve_subtitle_config(
        request.subtitle_config, geometry
    )
    metrics = wrapping_metrics or resolve_wrapping_metrics(resolved_config, geometry)
    display_text = _prepare_preview_display_text(request, resolved_config, metrics)
    end = max(1.0, timestamp + 1.0)
    guide_events = (
        build_preview_guide_events(
            resolved_config,
            geometry,
            metrics,
            timestamp,
            display_text=display_text,
            requested_config=request.subtitle_config,
        )
        if request.guides
        else ()
    )
    segment: dict[str, object] = {
        "start": 0.0,
        "end": end,
        "text": display_text,
    }
    if (
        resolved_config.animation.word.text.enabled
        or resolved_config.style.word_backdrop.kind.value != "none"
    ):
        preview_cue = _build_preview_word_cue(display_text)
        if preview_cue is not None:
            segment["_karaoke_preview_cue"] = preview_cue
    write_ass(
        path,
        [segment],
        request.subtitle_config,
        geometry,
        guide_events=guide_events,
        preserve_line_breaks=True,
        wrapping_metrics=metrics,
        suppress_animation=True,
    )
    return resolved_config, display_text


def build_animation_preview_ass(
    path: Path,
    request: PreviewRequest,
    geometry: VideoGeometry,
    timestamp: float,
    *,
    resolved_config: SubtitleConfig | None = None,
    wrapping_metrics: WrappingMetrics | None = None,
) -> tuple[SubtitleConfig, str]:
    """Write one zero-based animated preview cue over a frozen-frame timeline."""
    timestamp = resolve_preview_timestamp(timestamp, geometry)
    resolved_config = resolved_config or resolve_subtitle_config(
        request.subtitle_config, geometry
    )
    metrics = wrapping_metrics or resolve_wrapping_metrics(resolved_config, geometry)
    display_text = _prepare_preview_display_text(request, resolved_config, metrics)
    duration_ms = _validate_preview_duration_ms(request.preview_duration_ms)
    cue_start = 50
    cue_end = cue_start + _milliseconds_to_centiseconds(duration_ms)
    karaoke_cue = build_simulated_karaoke_cue(display_text, cue_start, cue_end)
    total_duration_seconds = (duration_ms + 1_000) / 1_000
    guide_events = (
        build_preview_guide_events(
            resolved_config,
            geometry,
            metrics,
            timestamp,
            display_text=display_text,
            requested_config=request.subtitle_config,
            guide_end=total_duration_seconds,
            simulation=True,
            karaoke_cue=karaoke_cue,
        )
        if request.guides
        else ()
    )
    segment: dict[str, object] = {
        "start": cue_start / 100,
        "end": cue_end / 100,
        "text": display_text,
    }
    if (
        resolved_config.animation.word.text.enabled
        or resolved_config.style.word_backdrop.kind.value != "none"
    ):
        segment["_karaoke_cue"] = karaoke_cue
    write_ass(
        path,
        [segment],
        request.subtitle_config,
        geometry,
        guide_events=guide_events,
        preserve_line_breaks=True,
        wrapping_metrics=metrics,
    )
    return resolved_config, display_text


def _prepare_preview_display_text(
    request: PreviewRequest,
    resolved_config: SubtitleConfig,
    metrics: WrappingMetrics,
) -> str:
    transformed_text = transform_display_text(
        normalise_preview_text(request.preview_text),
        resolved_config.style.typography.text_case,
    )
    return fit_first_text_segment(transformed_text, metrics=metrics)


def _validate_preview_duration_ms(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("preview-duration must be a whole number of milliseconds")
    if value < MIN_PREVIEW_DURATION_MS or value > MAX_PREVIEW_DURATION_MS:
        raise ValidationError("preview-duration must be from 1s through 15s")
    return value


def _milliseconds_to_centiseconds(milliseconds: int) -> int:
    """Round CLI milliseconds to ASS centiseconds with half-up integer math."""
    return (milliseconds + 5) // 10


def _build_preview_word_cue(display_text: str) -> KaraokeCue | None:
    """Map sample words for a static, representative timed-emphasis snapshot."""
    words = [{"word": unit} for unit in word_units(display_text)]
    fragments = build_display_fragments(display_text, words)
    if fragments is None:
        return None
    return KaraokeCue(
        fragments=fragments,
        durations=(0,) * len(words),
        active_intervals=(),
    )


def build_preview_guide_events(
    config: SubtitleConfig,
    geometry: VideoGeometry,
    metrics: WrappingMetrics,
    timestamp: float,
    *,
    display_text: str,
    requested_config: SubtitleConfig | None = None,
    guide_end: float | None = None,
    simulation: bool = False,
    karaoke_cue: KaraokeCue | None = None,
) -> tuple[AssDrawingEvent, ...]:
    """Build generated ASS diagnostics for the resolved placement and envelope."""
    timestamp = resolve_preview_timestamp(timestamp, geometry)
    end = max(1.0, timestamp + 1.0) if guide_end is None else guide_end
    layout = config.layout
    if layout.placement_mode is SubtitlePlacementMode.NATIVE_STYLE:
        region = resolve_native_layout_region(geometry, layout)
        anchor = _native_anchor_point(layout.position, region)
        envelope = _anchor_bounds(
            anchor[0],
            anchor[1],
            int(metrics.max_width),
            int(metrics.max_height),
            layout.position,
        )
        active_margin = (
            layout.margin_top
            if layout.position.value.startswith("top-")
            else layout.margin_bottom
            if layout.position.value.startswith("bottom-")
            else 0
        )
        mode_detail = (
            f"native {layout.position.value}; region {region.width}x{region.height}px; "
            f"active vertical margin {active_margin}px"
        )
        events = [
            _rectangle_event(end, region.left, region.top, region.right, region.bottom),
            _rectangle_event(end, *envelope),
        ]
    else:
        placement = resolve_cue_placement(config, geometry)
        if placement is None:
            raise ValidationError("explicit preview guides require a cue placement")
        envelope = _anchor_bounds(
            placement.position_x,
            placement.position_y,
            int(metrics.max_width),
            int(metrics.max_height),
            placement.anchor,
        )
        mode_detail = (
            f"explicit {placement.anchor.value} at "
            f"({placement.position_x},{placement.position_y})"
        )
        events = [_rectangle_event(end, *envelope)]
        events.append(_crosshair_event(end, placement.position_x, placement.position_y))

    requested_spacing = (
        _format_preview_length(requested_config.style.typography.letter_spacing)
        if requested_config is not None
        else f"{int(metrics.letter_spacing)}px"
    )
    requested_line_height = (
        _format_preview_length(requested_config.style.typography.line_height)
        if requested_config is not None
        else f"{int(metrics.resolved_line_height)}px"
    )
    preview_segment: dict[str, object] = {"text": display_text}
    if karaoke_cue is not None:
        preview_segment["_karaoke_cue"] = karaoke_cue
    elif (
        config.animation.word.text.enabled
        or config.style.word_backdrop.kind.value != "none"
    ):
        preview_cue = _build_preview_word_cue(display_text)
        if preview_cue is not None:
            preview_segment["_karaoke_preview_cue"] = preview_cue
    render_strategy = _render_strategy_for_segments(
        config,
        [preview_segment],
        suppress_animation=not simulation,
    )
    simulation_detail = (
        r"\NTiming: simulated word times (not speech-synchronized)"
        if simulation
        else ""
    )
    label = (
        f"{{\\an7\\pos(12,12)\\fs{_GUIDE_FONT_SIZE}\\bord2\\shad0"
        f"\\1c{_GUIDE_COLOR}\\3c{_GUIDE_OUTLINE}}}"
        f"Preview guides\\N{escape_ass_text(mode_detail)}"
        f"\\NEnvelope: {int(metrics.max_width)}x{int(metrics.max_height)}px"
        f"\\NLetter spacing: {requested_spacing}"
        f" ({int(metrics.letter_spacing)}px resolved)"
        f"\\NLine height: {requested_line_height}"
        f" ({metrics.resolved_line_height:.1f}px resolved; "
        f"natural {metrics.natural_line_height:.1f}px)"
        f"\\NLine capacity: {metrics.line_capacity}"
        f"\\NOpacity: {config.style.opacity.original}"
        f"\\NText case: {config.style.typography.text_case.value}"
        f"{simulation_detail}"
        f"\\NRender strategy: {render_strategy}"
        f"\\NPlayRes: {geometry.render_width}x{geometry.render_height}"
    )
    events.append(AssDrawingEvent(0.0, end, label))
    return tuple(events)


def _format_preview_length(value: int | float | RelativeLength | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, RelativeLength):
        return value.original
    return f"{value}px"


def _native_anchor_point(
    position: SubtitlePosition, region: NativeLayoutRegion
) -> tuple[int, int]:
    if position.value.endswith("left"):
        x = region.left
    elif position.value.endswith("right"):
        x = region.right
    else:
        x = (region.left + region.right) // 2
    if position.value.startswith("top-"):
        y = region.top
    elif position.value.startswith("bottom-"):
        y = region.bottom
    else:
        y = (region.top + region.bottom) // 2
    return x, y


def _anchor_bounds(
    x: int,
    y: int,
    width: int,
    height: int,
    anchor: SubtitlePosition,
) -> tuple[int, int, int, int]:
    if anchor.value.endswith("left"):
        left, right = x, x + width
    elif anchor.value.endswith("right"):
        left, right = x - width, x
    else:
        left, right = x - width // 2, x + (width + 1) // 2
    if anchor.value.startswith("top-"):
        top, bottom = y, y + height
    elif anchor.value.startswith("bottom-"):
        top, bottom = y - height, y
    else:
        top, bottom = y - height // 2, y + (height + 1) // 2
    return left, top, right, bottom


def _rectangle_event(
    end: float, left: int, top: int, right: int, bottom: int
) -> AssDrawingEvent:
    path = (
        f"m {left} {top} l {right} {top} l {right} {bottom} "
        f"l {left} {bottom} l {left} {top}"
    )
    text = (
        f"{{\\p1\\1a&HFF&\\3c{_GUIDE_COLOR}\\3a&H40&"
        f"\\4a&HFF&\\bord2\\shad0}}{path}{{\\p0}}"
    )
    return AssDrawingEvent(0.0, end, text)


def _crosshair_event(end: float, x: int, y: int) -> AssDrawingEvent:
    size = 10
    path = f"m {x - size} {y} l {x + size} {y} m {x} {y - size} l {x} {y + size}"
    text = (
        f"{{\\p1\\1a&HFF&\\3c{_GUIDE_COLOR}\\3a&H40&"
        f"\\4a&HFF&\\bord2\\shad0}}{path}{{\\p0}}"
    )
    return AssDrawingEvent(0.0, end, text)
