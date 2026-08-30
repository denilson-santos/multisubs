"""ASS subtitle serialization isolated from transcription and rendering."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from .config import validate_subtitle_config
from .errors import ArtifactError, ValidationError
from .layout import (
    WrappingMetrics,
    resolve_cue_placement,
    resolve_native_layout_region,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
)
from .models import (
    AssDrawingEvent,
    CuePlacement,
    KaraokeCue,
    KaraokeMode,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleDisplayFragment,
    SubtitlePlacementMode,
    SubtitlePosition,
    SubtitleVisualLine,
    VideoGeometry,
)
from .utils import atomic_write_text
from .wrapping import build_visual_lines

ASS_STYLE_FIELDS = (
    "font",
    "font_size",
    "primary_color",
    "secondary_color",
    "outline_color",
    "back_color",
    "bold",
    "italic",
    "underline",
    "strikeout",
    "scale_x",
    "scale_y",
    "spacing",
    "angle",
    "border_style",
    "outline_weight",
    "shadow_weight",
    "alignment",
    "margin_l",
    "margin_r",
    "margin_v",
)

_ASS_ALIGNMENT_BY_POSITION = {
    SubtitlePosition.BOTTOM_LEFT: 1,
    SubtitlePosition.BOTTOM_CENTER: 2,
    SubtitlePosition.BOTTOM_RIGHT: 3,
    SubtitlePosition.MIDDLE_LEFT: 4,
    SubtitlePosition.CENTER: 5,
    SubtitlePosition.MIDDLE_RIGHT: 6,
    SubtitlePosition.TOP_LEFT: 7,
    SubtitlePosition.TOP_CENTER: 8,
    SubtitlePosition.TOP_RIGHT: 9,
}


@dataclass(frozen=True)
class _PositionedLine:
    """One visual line and its resolved ASS anchor position."""

    line: SubtitleVisualLine
    anchor: SubtitlePosition
    position_x: int
    position_y: int
    block_bounds: tuple[int, int, int, int]


def write_ass(
    path: Path,
    segments: Sequence[Mapping[str, Any]],
    subtitle_config: SubtitleConfig | None,
    geometry: VideoGeometry,
    *,
    placements: Sequence[CuePlacement | None] | None = None,
    guide_events: Sequence[AssDrawingEvent] | None = None,
    preserve_line_breaks: bool = False,
    wrapping_metrics: WrappingMetrics | None = None,
) -> None:
    """Write safe ASS dialogue on the probed, autorotated video canvas.

    ``placements`` is an internal per-cue contract for explicit placement.
    Native style placement emits no event-level position override. When
    ``preserve_line_breaks`` is enabled, the generated dialogue keeps only the
    caller's intentional line breaks instead of being wrapped again by libass.
    """
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ArtifactError("ASS canvas dimensions must be positive")
    config = resolve_subtitle_config(
        validate_subtitle_config(subtitle_config),
        geometry,
        text_measurer=(
            wrapping_metrics.text_measurer if wrapping_metrics is not None else None
        ),
    )
    explicit_line_height = _uses_explicit_line_height(config)
    metrics = wrapping_metrics
    if explicit_line_height and metrics is None:
        metrics = resolve_wrapping_metrics(config, geometry)
    style = _compile_style(config, geometry)
    default_placement = resolve_cue_placement(config, geometry)
    if placements is not None and len(placements) != len(segments):
        raise ArtifactError("ASS cue placements must match the segment count")
    positioned_lines: list[tuple[_PositionedLine, ...]] = []
    backdrop_bounds: list[tuple[int, int, int, int] | None] = []
    for segment in segments:
        if not explicit_line_height:
            backdrop_bounds.append(None)
            positioned_lines.append(())
            continue
        if metrics is None:
            raise ArtifactError("Explicit line height requires wrapping metrics")
        karaoke_cue = segment.get("_karaoke_cue")
        fragments = (
            karaoke_cue.fragments
            if isinstance(karaoke_cue, KaraokeCue)
            else segment.get("display_fragments")
        )
        visual_lines = build_visual_lines(
            str(segment.get("text", "")),
            fragments
            if isinstance(fragments, Sequence)
            and not isinstance(fragments, (str, bytes))
            and all(isinstance(item, SubtitleDisplayFragment) for item in fragments)
            else None,
            metrics,
        )
        placement = (
            placements[len(positioned_lines)]
            if placements is not None
            else default_placement
        )
        if explicit_line_height and len(visual_lines) > 1:
            line_layout = _position_visual_lines(
                visual_lines,
                config,
                geometry,
                metrics,
                placement,
            )
            backdrop_bounds.append(line_layout[0].block_bounds if line_layout else None)
            positioned_lines.append(line_layout)
        else:
            backdrop_bounds.append(None)
            positioned_lines.append(())
    needs_shared_backdrop = any(positioned_lines) and (
        config.appearance.backdrop is SubtitleBackdrop.BOX
    )
    positioned_style_name = "Default"
    positioned_style: dict[str, str | int] | None = None
    if needs_shared_backdrop:
        # BorderStyle 4 would draw one box per generated line. Keep Default
        # unchanged for single-line cues and neutralize only the generated
        # per-line text style; the vector event owns their complete box.
        positioned_style_name = "Positioned"
        positioned_style = dict(style)
        positioned_style["border_style"] = 1
        positioned_style["outline_weight"] = 0
    style_lines = [_serialize_style_line("Default", style)]
    if positioned_style is not None:
        style_lines.append(
            _serialize_style_line(positioned_style_name, positioned_style)
        )
    lines = [
        "[Script Info]",
        "Title: multisubs generated subtitles",
        "ScriptType: v4.00+",
        f"PlayResX: {geometry.render_width}",
        f"PlayResY: {geometry.render_height}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        *style_lines,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    for index, segment in enumerate(segments):
        placement = placements[index] if placements is not None else default_placement
        # Older libass releases normalize positive values in the style Bold
        # field to boolean bold. Event-level \b accepts the exact OpenType rank
        # across those releases, so keep the base style neutral and apply the
        # validated semantic weight through the trusted override path.
        generated_override = rf"{{\b{config.appearance.font_weight.rank}}}"
        if preserve_line_breaks:
            generated_override += r"{\q2}"
        cue_start = quantize_ass_centiseconds(segment["start"])
        cue_end = quantize_ass_centiseconds(segment["end"])
        karaoke_cue = segment.get("_karaoke_cue")
        visual_line_events = positioned_lines[index]
        if visual_line_events:
            if metrics is None:
                raise ArtifactError(
                    "Positioned subtitle lines require wrapping metrics"
                )
            current_backdrop_bounds = backdrop_bounds[index]
            if needs_shared_backdrop and current_backdrop_bounds is not None:
                _append_shared_backdrop_event(
                    lines,
                    cue_start,
                    cue_end,
                    current_backdrop_bounds,
                    config.appearance.backdrop_color,
                    metrics.shadow_size,
                    style_name=positioned_style_name,
                )
            line_overrides = [
                generated_override
                + serialize_ass_placement(
                    CuePlacement(
                        anchor=item.anchor,
                        position_x=item.position_x,
                        position_y=item.position_y,
                    )
                )
                for item in visual_line_events
            ]
            if config.effects.mode is KaraokeMode.ACTIVE_WORD and isinstance(
                karaoke_cue, KaraokeCue
            ):
                for line_override, item in zip(
                    line_overrides, visual_line_events, strict=True
                ):
                    for (
                        event_start,
                        event_end,
                        event_text,
                    ) in serialize_active_word_line_events(
                        karaoke_cue,
                        item.line.fragments,
                        config,
                        cue_start,
                        cue_end,
                    ):
                        _append_dialogue_line(
                            lines,
                            event_start,
                            event_end,
                            line_override,
                            event_text,
                            layer=1,
                            style_name=positioned_style_name,
                        )
                continue
            if config.effects.mode is KaraokeMode.PROGRESSIVE and isinstance(
                karaoke_cue, KaraokeCue
            ):
                for line_override, item in zip(
                    line_overrides, visual_line_events, strict=True
                ):
                    for (
                        event_start,
                        event_end,
                        event_text,
                    ) in serialize_progressive_line_events(
                        karaoke_cue,
                        item.line.fragments,
                        config,
                        cue_start,
                        cue_end,
                    ):
                        _append_dialogue_line(
                            lines,
                            event_start,
                            event_end,
                            line_override,
                            event_text,
                            layer=1,
                            style_name=positioned_style_name,
                        )
                continue
            for line_override, item in zip(
                line_overrides, visual_line_events, strict=True
            ):
                _append_dialogue_line(
                    lines,
                    cue_start,
                    cue_end,
                    line_override,
                    escape_ass_text(item.line.text),
                    layer=1,
                    style_name=positioned_style_name,
                )
            continue
        generated_override += (
            serialize_ass_placement(placement) if placement is not None else ""
        )
        if config.effects.mode is KaraokeMode.ACTIVE_WORD and isinstance(
            karaoke_cue, KaraokeCue
        ):
            for event_start, event_end, event_text in serialize_active_word_events(
                karaoke_cue,
                config,
                cue_start,
                cue_end,
            ):
                _append_dialogue_line(
                    lines,
                    event_start,
                    event_end,
                    generated_override,
                    event_text,
                )
            continue
        karaoke_text = (
            serialize_karaoke_cue(
                karaoke_cue,
                config,
            )
            if config.effects.mode is KaraokeMode.PROGRESSIVE
            else None
        )
        dialogue_text = (
            karaoke_text
            if karaoke_text is not None
            else escape_ass_text(str(segment["text"]))
        )
        _append_dialogue_line(
            lines,
            cue_start,
            cue_end,
            generated_override,
            dialogue_text,
        )
    for event in guide_events or ():
        _append_guide_event(lines, event)
    atomic_write_text(path, "\n".join(lines) + "\n")


def _append_dialogue_line(
    lines: list[str],
    start_centiseconds: int,
    end_centiseconds: int,
    generated_override: str,
    dialogue_text: str,
    *,
    layer: int = 0,
    style_name: str = "Default",
) -> None:
    if end_centiseconds < start_centiseconds:
        raise ArtifactError("ASS dialogue end must not precede its start")
    lines.append(
        f"Dialogue: {layer},"
        f"{format_ass_centiseconds(start_centiseconds)},"
        f"{format_ass_centiseconds(end_centiseconds)},"
        f"{style_name},,0,0,0,,{generated_override}{dialogue_text}"
    )


def _serialize_style_line(
    name: str,
    style: Mapping[str, str | int],
) -> str:
    """Serialize one trusted internal ASS style in canonical field order."""
    return (
        f"Style: {name},"
        + ",".join(str(style[field]) for field in ASS_STYLE_FIELDS)
        + ",1"
    )


def _uses_explicit_line_height(config: SubtitleConfig) -> bool:
    requested = config.appearance.line_height_requested
    if requested is None:
        requested = config.appearance.line_height
    return not (isinstance(requested, str) and requested.casefold() == "auto")


def _position_visual_lines(
    visual_lines: Sequence[SubtitleVisualLine],
    config: SubtitleConfig,
    geometry: VideoGeometry,
    metrics: WrappingMetrics,
    placement: CuePlacement | None,
) -> tuple[_PositionedLine, ...]:
    """Position visual lines around one stable native or explicit anchor."""
    layout = config.layout
    if placement is not None:
        anchor = placement.anchor
        anchor_x, anchor_y = placement.position_x, placement.position_y
    else:
        region = resolve_native_layout_region(geometry, layout)
        anchor = layout.position
        anchor_x, anchor_y = _native_anchor_point(anchor, region)

    content_width = max((line.width for line in visual_lines), default=0.0)
    padding = metrics.backdrop_size
    shadow = metrics.shadow_size
    block_width = _round_playres(content_width + 2 * padding + shadow)
    block_height = _round_playres(
        metrics.natural_line_height
        + (len(visual_lines) - 1) * metrics.resolved_line_height
        + 2 * padding
        + shadow
    )
    if block_width > metrics.max_width:
        raise ValidationError(
            "Measured subtitle lines exceed the configured max-width envelope"
        )
    if block_height > metrics.max_height:
        raise ValidationError(
            "Measured subtitle lines exceed the configured max-height envelope"
        )
    block_left, block_top, block_right, block_bottom = _anchor_bounds(
        anchor_x,
        anchor_y,
        block_width,
        block_height,
        anchor,
    )
    bounds = (block_left, block_top, block_right, block_bottom)
    content_top = block_top + padding
    result: list[_PositionedLine] = []
    for line in visual_lines:
        if anchor.value.startswith("top-"):
            line_y = _round_playres(
                content_top + line.index * metrics.resolved_line_height
            )
        elif anchor.value.startswith("bottom-"):
            line_y = _round_playres(
                content_top
                + line.index * metrics.resolved_line_height
                + metrics.natural_line_height
            )
        else:
            line_y = _round_playres(
                content_top
                + line.index * metrics.resolved_line_height
                + metrics.natural_line_height / 2
            )
        result.append(
            _PositionedLine(
                line=line,
                anchor=anchor,
                position_x=anchor_x,
                position_y=line_y,
                block_bounds=bounds,
            )
        )
    return tuple(result)


def _native_anchor_point(
    position: SubtitlePosition,
    region: Any,
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


def _round_playres(value: float) -> int:
    return int(math.floor(float(value) + 0.5))


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


def _append_shared_backdrop_event(
    lines: list[str],
    start_centiseconds: int,
    end_centiseconds: int,
    bounds: tuple[int, int, int, int],
    color: str,
    shadow_size: int,
    *,
    style_name: str,
) -> None:
    """Append one lower-layer vector backdrop for a positioned visual block."""
    left, top, right, bottom = bounds
    ass_color = rgba_to_ass_color(color)
    alpha = ass_color[2:4]
    bgr = ass_color[4:10]
    path = (
        f"m {left} {top} l {right} {top} l {right} {bottom} "
        f"l {left} {bottom} l {left} {top}"
    )
    text = (
        f"{{\\an7\\pos(0,0)\\p1\\1c&H{bgr}&\\1a&H{alpha}&"
        f"\\3a&HFF&\\4a&HFF&\\bord0\\shad{shadow_size}}}{path}{{\\p0}}"
    )
    lines.append(
        "Dialogue: 0,"
        f"{format_ass_centiseconds(start_centiseconds)},"
        f"{format_ass_centiseconds(end_centiseconds)},"
        f"{style_name},,0,0,0,,{text}"
    )


def _append_guide_event(lines: list[str], event: AssDrawingEvent) -> None:
    """Append one generated diagnostic event without treating it as user text."""
    if not isinstance(event, AssDrawingEvent):
        raise ArtifactError("ASS guide events must use the typed drawing contract")
    if (
        isinstance(event.start, bool)
        or not isinstance(event.start, Real)
        or isinstance(event.end, bool)
        or not isinstance(event.end, Real)
        or not math.isfinite(float(event.start))
        or not math.isfinite(float(event.end))
        or event.start < 0
        or event.end < event.start
        or not isinstance(event.text, str)
        or not event.text
        or "\n" in event.text
        or "\r" in event.text
    ):
        raise ArtifactError("ASS guide events must contain valid timestamps and text")
    lines.append(
        "Dialogue: 0,"
        f"{format_ass_time(event.start)},{format_ass_time(event.end)},"
        f"Default,,0,0,0,,{event.text}"
    )


def _compile_style(
    config: SubtitleConfig,
    geometry: VideoGeometry | None = None,
) -> dict[str, str | int]:
    """Compile semantic layout into the private numeric ASS style fields."""
    appearance = config.appearance
    layout = config.layout
    backdrop_size = _resolved_style_int(appearance.backdrop_size, "backdrop-size")
    margin_top = _resolved_style_int(layout.margin_top, "margin-top")
    margin_bottom = _resolved_style_int(layout.margin_bottom, "margin-bottom")
    explicit = layout.placement_mode is SubtitlePlacementMode.EXPLICIT
    margin_v = (
        0
        if explicit
        else margin_top
        if layout.position.value.startswith("top-")
        else margin_bottom
        if layout.position.value.startswith("bottom-")
        else 0
    )
    backdrop_color = rgba_to_ass_color(appearance.backdrop_color)
    if explicit:
        margin_l = 0
        margin_r = 0
    else:
        margin_l = _resolved_style_int(layout.margin_left, "margin-left")
        margin_r = _resolved_style_int(layout.margin_right, "margin-right")
    return {
        "font": appearance.font,
        "font_size": _resolved_style_int(appearance.font_size, "font-size"),
        "primary_color": rgba_to_ass_color(appearance.text_color),
        # SecondaryColour is mandatory in a V4+ Style. It remains the neutral
        # inactive color for ordinary cues; karaoke events override both colors.
        "secondary_color": rgba_to_ass_color(appearance.text_color),
        "outline_color": backdrop_color,
        "back_color": backdrop_color,
        # Exact weight is emitted as a trusted event-level \b override because
        # older libass style parsers coerce every positive value to bold.
        "bold": 0,
        "italic": -1 if appearance.italic else 0,
        "underline": 0,
        "strikeout": 0,
        "scale_x": 100,
        "scale_y": 100,
        "spacing": _resolved_style_int(appearance.letter_spacing, "letter-spacing"),
        "angle": 0,
        # libass BorderStyle 4 creates one box for the whole cue, matching the
        # backdrop used by multisubs before the semantic CLI cutover.
        "border_style": 4 if appearance.backdrop is SubtitleBackdrop.BOX else 1,
        "outline_weight": (
            0 if appearance.backdrop is SubtitleBackdrop.NONE else backdrop_size
        ),
        "shadow_weight": _resolved_style_int(appearance.shadow_size, "shadow-size"),
        "alignment": _ass_alignment_for_position(
            layout.anchor if explicit and layout.anchor is not None else layout.position
        ),
        "margin_l": margin_l,
        "margin_r": margin_r,
        "margin_v": margin_v,
    }


def rgba_to_ass_color(value: str) -> str:
    """Convert #RRGGBB[AA] into ASS &HAABBGGRR notation."""
    if (
        not isinstance(value, str)
        or len(value) not in {7, 9}
        or not value.startswith("#")
    ):
        raise ArtifactError("ASS colors require #RRGGBB or #RRGGBBAA notation")
    try:
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
        conventional_alpha = int(value[7:9], 16) if len(value) == 9 else 255
    except ValueError as exc:
        raise ArtifactError("ASS colors require hexadecimal digits") from exc
    ass_alpha = 255 - conventional_alpha
    return f"&H{ass_alpha:02X}{blue:02X}{green:02X}{red:02X}"


def _resolved_style_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactError(
            f"{field} must be resolved against video geometry before ASS compilation"
        )
    return value


def serialize_ass_placement(placement: CuePlacement) -> str:
    """Serialize one generated ASS anchor override without transcript text."""
    if not isinstance(placement, CuePlacement):
        raise ArtifactError("ASS cue placement must use the typed placement contract")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (placement.position_x, placement.position_y)
    ):
        raise ArtifactError(
            "ASS cue placement coordinates must be non-negative integers"
        )
    alignment = _ass_alignment_for_position(placement.anchor)
    return f"{{\\an{alignment}\\pos({placement.position_x},{placement.position_y})}}"


def _ass_alignment_for_position(position: SubtitlePosition) -> int:
    """Return the private ASS alignment code for one semantic position."""
    try:
        return _ASS_ALIGNMENT_BY_POSITION[position]
    except KeyError as exc:
        raise ArtifactError(f"Unsupported subtitle position: {position}") from exc


def format_ass_time(seconds: object) -> str:
    """Format one finite non-negative time using ASS centiseconds."""
    return format_ass_centiseconds(quantize_ass_centiseconds(seconds))


def format_ass_centiseconds(total_centiseconds: object) -> str:
    """Format one already quantized non-negative ASS timestamp."""
    if (
        isinstance(total_centiseconds, bool)
        or not isinstance(total_centiseconds, int)
        or total_centiseconds < 0
    ):
        raise ArtifactError("ASS centiseconds must be a non-negative integer")
    hours, remainder = divmod(total_centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def quantize_ass_centiseconds(seconds: object) -> int:
    """Quantize one timestamp using the rounding policy shared by ASS output."""
    value = _finite_time(seconds)
    if value is None:
        raise ArtifactError("ASS timestamp must be a finite, non-negative number")
    return round(value * 100)


def allocate_karaoke_durations(
    cue_start: object,
    cue_end: object,
    words: Sequence[Mapping[str, Any]],
) -> tuple[int, ...]:
    """Allocate exact non-negative ASS centiseconds between word starts."""
    start_centiseconds, end_centiseconds, starts, _ = _quantized_karaoke_boundaries(
        cue_start, cue_end, words
    )
    boundaries = (*starts[1:], end_centiseconds)
    durations = tuple(
        next_boundary - current
        for current, next_boundary in zip(starts, boundaries, strict=True)
    )
    if any(duration < 0 for duration in durations):
        raise ArtifactError("Karaoke durations must be non-negative")
    if sum(durations) != end_centiseconds - start_centiseconds:
        raise ArtifactError("Karaoke durations must conserve cue duration")
    return durations


def allocate_active_word_intervals(
    cue_start: object,
    cue_end: object,
    words: Sequence[Mapping[str, Any]],
) -> tuple[tuple[int, int], ...]:
    """Return non-overlapping absolute centisecond intervals for active words."""
    _, end_centiseconds, starts, ends = _quantized_karaoke_boundaries(
        cue_start, cue_end, words
    )
    next_starts = (*starts[1:], end_centiseconds)
    return tuple(
        (start, min(end, next_start))
        for start, end, next_start in zip(starts, ends, next_starts, strict=True)
    )


def _quantized_karaoke_boundaries(
    cue_start: object,
    cue_end: object,
    words: Sequence[Mapping[str, Any]],
) -> tuple[int, int, tuple[int, ...], tuple[int, ...]]:
    start_centiseconds = quantize_ass_centiseconds(cue_start)
    end_centiseconds = quantize_ass_centiseconds(cue_end)
    if end_centiseconds < start_centiseconds or not words:
        raise ArtifactError("Karaoke cue timestamps are invalid")

    starts: list[int] = []
    ends: list[int] = []
    previous_start: float | None = None
    for word in words:
        if not isinstance(word, Mapping):
            raise ArtifactError("Karaoke words must use mapping records")
        start = _finite_time(word.get("start"))
        end = _finite_time(word.get("end"))
        if start is None or end is None or end < start:
            raise ArtifactError("Karaoke words must have valid timestamps")
        if previous_start is not None and start < previous_start:
            raise ArtifactError("Karaoke word starts must be chronological")
        previous_start = start
        starts.append(quantize_ass_centiseconds(start))
        ends.append(quantize_ass_centiseconds(end))

    if starts[0] != start_centiseconds:
        raise ArtifactError(
            "Karaoke cue must start at the first displayed word timestamp"
        )
    if any(start > end_centiseconds for start in starts) or any(
        end > end_centiseconds for end in ends
    ):
        raise ArtifactError("Karaoke word timestamps must fit inside the cue")
    return start_centiseconds, end_centiseconds, tuple(starts), tuple(ends)


def serialize_karaoke_cue(
    cue: object,
    config: SubtitleConfig,
) -> str | None:
    """Compile one prepared karaoke cue without escaping generated overrides."""
    if (
        not isinstance(cue, KaraokeCue)
        or config.effects.mode is not KaraokeMode.PROGRESSIVE
    ):
        return None
    highlight_color = config.effects.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    _validate_karaoke_cue(cue)
    return _serialize_karaoke_fragments(cue.fragments, cue.durations, config)


def _serialize_karaoke_fragments(
    fragments: Sequence[SubtitleDisplayFragment],
    durations: Sequence[int],
    config: SubtitleConfig,
) -> str:
    """Serialize one visual line while retaining cue-global word durations."""
    highlight_color = config.effects.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    result = (
        "{"
        + rgba_to_ass_color_override(highlight_color, 1)
        + rgba_to_ass_color_override(config.appearance.text_color, 2)
        + "}"
    )
    for fragment in fragments:
        if fragment.word_index is not None:
            if fragment.word_index < 0 or fragment.word_index >= len(durations):
                raise ArtifactError("Karaoke fragment word indexes are invalid")
            result += f"{{\\k{durations[fragment.word_index]}}}"
        result += escape_ass_text(fragment.text)
    return result


def serialize_active_word_events(
    cue: KaraokeCue,
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
) -> tuple[tuple[int, int, str], ...]:
    """Split one cue into stable full-text intervals with one active word."""
    if config.effects.mode is not KaraokeMode.ACTIVE_WORD:
        raise ArtifactError("Active-word events require active-word karaoke mode")
    _validate_karaoke_cue(cue)
    if cue_end < cue_start:
        raise ArtifactError("Karaoke cue timestamps are invalid")
    if len(cue.active_intervals) != len(cue.durations):
        raise ArtifactError("Active-word intervals must match karaoke word count")

    plain_text = escape_ass_text("".join(fragment.text for fragment in cue.fragments))
    events: list[tuple[int, int, str]] = []
    cursor = cue_start
    for word_index, interval in enumerate(cue.active_intervals):
        if (
            not isinstance(interval, tuple)
            or len(interval) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in interval
            )
        ):
            raise ArtifactError("Active-word intervals must use integer boundaries")
        start, end = interval
        if start < cursor or end < start or end > cue_end:
            raise ArtifactError("Active-word intervals must be ordered inside the cue")
        if cursor < start:
            events.append((cursor, start, plain_text))
        if start < end:
            events.append(
                (start, end, _serialize_active_word_text(cue, config, word_index))
            )
        cursor = end
    if cursor < cue_end:
        events.append((cursor, cue_end, plain_text))
    if not events:
        events.append((cue_start, cue_end, plain_text))
    return tuple(events)


def serialize_progressive_line_events(
    cue: KaraokeCue,
    fragments: Sequence[SubtitleDisplayFragment],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
) -> tuple[tuple[int, int, str], ...]:
    """Serialize one visual line with cue-relative progressive colors.

    A standalone ASS event starts its karaoke clock at the event start.  A
    per-line event therefore cannot use only the line's local ``\\k`` tags:
    words on later visual lines would highlight at cue start.  Explicit
    line-height rendering uses stable intervals instead, changing each line's
    color state at the original cue-global word boundaries.
    """
    if config.effects.mode is not KaraokeMode.PROGRESSIVE:
        raise ArtifactError("Progressive line events require progressive karaoke mode")
    _validate_karaoke_cue(cue)
    if cue_end < cue_start:
        raise ArtifactError("Karaoke line timestamps are invalid")
    duration = cue_end - cue_start
    if sum(cue.durations) != duration:
        raise ArtifactError("Karaoke durations must conserve cue duration")

    boundaries = [cue_start]
    for word_duration in cue.durations:
        boundaries.append(boundaries[-1] + word_duration)

    events: list[tuple[int, int, str]] = []
    for activated_count, (start, end) in enumerate(
        zip(boundaries[:-1], boundaries[1:], strict=True)
    ):
        if end <= start:
            continue
        events.append(
            (
                start,
                end,
                _serialize_progressive_state(
                    fragments,
                    config,
                    activated_count,
                    duration=end - start,
                ),
            )
        )
    if not events:
        events.append(
            (
                cue_start,
                cue_end,
                _serialize_progressive_state(
                    fragments,
                    config,
                    len(cue.durations),
                ),
            )
        )
    return tuple(events)


def _serialize_progressive_state(
    fragments: Sequence[SubtitleDisplayFragment],
    config: SubtitleConfig,
    activated_count: int,
    *,
    duration: int | None = None,
) -> str:
    """Compile one progressive interval for a visual line.

    The active word, when present on this line, retains a ``\\k`` tag for the
    interval's original duration.  Earlier words are statically highlighted;
    later words remain in the normal color.  This keeps the word sweep while
    ensuring a line event starts at the cue-global word boundary.
    """
    highlight_color = config.effects.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    if activated_count < 0:
        raise ArtifactError("Progressive activation count must be non-negative")
    normal_override = (
        "{" + rgba_to_ass_color_override(config.appearance.text_color, 1) + "}"
    )
    highlight_override = "{" + rgba_to_ass_color_override(highlight_color, 1) + "}"
    progressive_setup = (
        "{"
        + rgba_to_ass_color_override(highlight_color, 1)
        + rgba_to_ass_color_override(config.appearance.text_color, 2)
        + "}"
    )
    result = normal_override
    for fragment in fragments:
        if not isinstance(fragment, SubtitleDisplayFragment):
            raise ArtifactError("Karaoke fragments must use the typed display contract")
        if fragment.word_index is not None:
            if fragment.word_index < 0:
                raise ArtifactError("Karaoke fragment word indexes are invalid")
            if fragment.word_index < activated_count:
                result += highlight_override
            elif (
                duration is not None
                and fragment.word_index == activated_count
                and duration > 0
            ):
                result += progressive_setup + f"{{\\k{duration}}}"
            else:
                result += normal_override
        result += escape_ass_text(fragment.text)
    return result


def serialize_active_word_line_events(
    cue: KaraokeCue,
    fragments: Sequence[SubtitleDisplayFragment],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
) -> tuple[tuple[int, int, str], ...]:
    """Serialize active-word intervals for one visual line of a cue."""
    if config.effects.mode is not KaraokeMode.ACTIVE_WORD:
        raise ArtifactError("Active-word events require active-word karaoke mode")
    _validate_karaoke_cue(cue)
    if cue_end < cue_start or len(cue.active_intervals) != len(cue.durations):
        raise ArtifactError("Karaoke line timestamps are invalid")
    plain_text = escape_ass_text("".join(fragment.text for fragment in fragments))
    events: list[tuple[int, int, str]] = []
    cursor = cue_start
    for word_index, interval in enumerate(cue.active_intervals):
        if (
            not isinstance(interval, tuple)
            or len(interval) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in interval
            )
        ):
            raise ArtifactError("Active-word intervals must use integer boundaries")
        start, end = interval
        if start < cursor or end < start or end > cue_end:
            raise ArtifactError("Active-word intervals must be ordered inside the cue")
        if cursor < start:
            events.append((cursor, start, plain_text))
        if start < end:
            events.append(
                (
                    start,
                    end,
                    _serialize_active_word_fragments(
                        fragments,
                        config,
                        word_index,
                    ),
                )
            )
        cursor = end
    if cursor < cue_end:
        events.append((cursor, cue_end, plain_text))
    if not events:
        events.append((cue_start, cue_end, plain_text))
    return tuple(events)


def _serialize_active_word_text(
    cue: KaraokeCue,
    config: SubtitleConfig,
    active_word_index: int,
) -> str:
    return _serialize_active_word_fragments(cue.fragments, config, active_word_index)


def _serialize_active_word_fragments(
    fragments: Sequence[SubtitleDisplayFragment],
    config: SubtitleConfig,
    active_word_index: int,
) -> str:
    """Apply one active-word color to a fragment subset."""
    highlight_color = config.effects.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    normal_override = (
        "{" + rgba_to_ass_color_override(config.appearance.text_color, 1) + "}"
    )
    highlight_override = "{" + rgba_to_ass_color_override(highlight_color, 1) + "}"
    result = normal_override
    for fragment in fragments:
        if fragment.word_index == active_word_index:
            result += (
                highlight_override + escape_ass_text(fragment.text) + normal_override
            )
        else:
            result += escape_ass_text(fragment.text)
    return result


def _validate_karaoke_cue(cue: KaraokeCue) -> None:
    durations = cue.durations
    if not durations or any(
        isinstance(duration, bool) or not isinstance(duration, int) or duration < 0
        for duration in durations
    ):
        raise ArtifactError("Karaoke durations must be non-negative integers")
    timed_indexes: list[int] = []
    for fragment in cue.fragments:
        if not isinstance(fragment, SubtitleDisplayFragment):
            raise ArtifactError("Karaoke fragments must use the typed display contract")
        if not isinstance(fragment.text, str):
            raise ArtifactError("Karaoke fragment text must be a string")
        if fragment.word_index is not None:
            if (
                isinstance(fragment.word_index, bool)
                or not isinstance(fragment.word_index, int)
                or fragment.word_index < 0
                or fragment.word_index >= len(durations)
            ):
                raise ArtifactError("Karaoke fragment word indexes are invalid")
            timed_indexes.append(fragment.word_index)
    if timed_indexes != list(range(len(durations))):
        raise ArtifactError("Karaoke fragments must map each duration exactly once")


def rgba_to_ass_color_override(value: str, channel: int) -> str:
    """Compile one semantic RGBA color into ASS color and alpha overrides."""
    if channel not in {1, 2, 3, 4}:
        raise ArtifactError("ASS color override channel must be between 1 and 4")
    ass_color = rgba_to_ass_color(value)
    alpha = ass_color[2:4]
    blue_green_red = ass_color[4:10]
    return f"\\{channel}c&H{blue_green_red}&\\{channel}a&H{alpha}&"


def escape_ass_text(text: str) -> str:
    """Escape transcription-derived dialogue text without accepting overrides."""
    escaped = text.replace("\r\n", "\n").replace("\r", "\n")
    escaped = escaped.replace("\\", "\\\\")
    escaped = escaped.replace("{", "\\{").replace("}", "\\}")
    return escaped.replace("\n", "\\N")


def _finite_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        return None
    return result
