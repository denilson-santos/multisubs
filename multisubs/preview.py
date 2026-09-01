"""Transcription-free subtitle preview preparation and guide generation."""

from __future__ import annotations

import math
import re
from pathlib import Path

from .ass import escape_ass_text, rgba_to_ass_color, write_ass
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
    PreviewRequest,
    RelativeLength,
    SubtitleConfig,
    SubtitlePlacementMode,
    SubtitlePosition,
    VideoGeometry,
)
from .wrapping import (
    fit_first_text_segment,
    has_multiple_visual_lines,
    normalise_display_text,
    transform_display_text,
)

DEFAULT_PREVIEW_TEXT = (
    "Example subtitle preview text that demonstrates a readable two-line "
    "caption on your selected video layout before final rendering"
)
MAX_PREVIEW_TIMESTAMP_SECONDS = 86_400.0
_TIMESTAMP_PATTERN = re.compile(
    r"^(?P<hours>\d{2,}):(?P<minutes>[0-5]\d):"
    r"(?P<seconds>[0-5]\d)\.(?P<milliseconds>\d{1,3})$"
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


def build_preview_ass(
    path: Path,
    request: PreviewRequest,
    geometry: VideoGeometry,
    timestamp: float,
) -> tuple[SubtitleConfig, str]:
    """Resolve preview layout, wrap its sample cue, and write a temporary ASS."""
    timestamp = resolve_preview_timestamp(timestamp, geometry)
    resolved_config = resolve_subtitle_config(request.subtitle_config, geometry)
    metrics = resolve_wrapping_metrics(resolved_config, geometry)
    transformed_text = transform_display_text(
        normalise_preview_text(request.preview_text),
        resolved_config.appearance.text_case,
    )
    display_text = fit_first_text_segment(transformed_text, metrics=metrics)
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
    write_ass(
        path,
        [{"start": 0.0, "end": end, "text": display_text}],
        request.subtitle_config,
        geometry,
        guide_events=guide_events,
        preserve_line_breaks=True,
        wrapping_metrics=metrics,
    )
    return resolved_config, display_text


def build_preview_guide_events(
    config: SubtitleConfig,
    geometry: VideoGeometry,
    metrics: WrappingMetrics,
    timestamp: float,
    *,
    display_text: str,
    requested_config: SubtitleConfig | None = None,
) -> tuple[AssDrawingEvent, ...]:
    """Build generated ASS diagnostics for the resolved placement and envelope."""
    timestamp = resolve_preview_timestamp(timestamp, geometry)
    end = max(1.0, timestamp + 1.0)
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
        _format_preview_length(requested_config.appearance.letter_spacing)
        if requested_config is not None
        else f"{int(metrics.letter_spacing)}px"
    )
    requested_line_height = (
        _format_preview_length(requested_config.appearance.line_height)
        if requested_config is not None
        else f"{int(metrics.resolved_line_height)}px"
    )
    render_strategy = (
        "positioned-lines"
        if _line_height_is_explicit(config) and has_multiple_visual_lines(display_text)
        else "single-event"
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
        f"\\NOpacity: {config.appearance.opacity.original}"
        f"\\NText case: {config.appearance.text_case.value}"
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


def _line_height_is_explicit(config: SubtitleConfig) -> bool:
    value = (
        config.appearance.line_height_requested
        if config.appearance.line_height_requested is not None
        else config.appearance.line_height
    )
    return not (isinstance(value, str) and value.casefold() == "auto")


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
