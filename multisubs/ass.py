"""ASS subtitle serialization isolated from transcription and rendering."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

from .config import validate_subtitle_config
from .errors import ArtifactError
from .layout import (
    resolve_cue_placement,
    resolve_subtitle_config,
)
from .models import (
    AssDrawingEvent,
    CuePlacement,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitlePlacementMode,
    SubtitlePosition,
    VideoGeometry,
)
from .utils import atomic_write_text

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


def write_ass(
    path: Path,
    segments: Sequence[Mapping[str, Any]],
    subtitle_config: SubtitleConfig | None,
    geometry: VideoGeometry,
    *,
    placements: Sequence[CuePlacement | None] | None = None,
    guide_events: Sequence[AssDrawingEvent] | None = None,
    preserve_line_breaks: bool = False,
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
        validate_subtitle_config(subtitle_config), geometry
    )
    style = _compile_style(config, geometry)
    default_placement = resolve_cue_placement(config, geometry)
    if placements is not None and len(placements) != len(segments):
        raise ArtifactError("ASS cue placements must match the segment count")
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
        "Style: Default,"
        + ",".join(str(style[field]) for field in ASS_STYLE_FIELDS)
        + ",1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    for index, segment in enumerate(segments):
        placement = placements[index] if placements is not None else default_placement
        generated_override = (
            serialize_ass_placement(placement) if placement is not None else ""
        )
        if preserve_line_breaks:
            generated_override += r"{\q2}"
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_time(segment['start'])},{format_ass_time(segment['end'])},"
            f"Default,,0,0,0,,{generated_override}"
            f"{escape_ass_text(str(segment['text']))}"
        )
    for event in guide_events or ():
        _append_guide_event(lines, event)
    atomic_write_text(path, "\n".join(lines) + "\n")


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
        # SecondaryColour is mandatory in a V4+ Style even though multisubs does
        # not currently emit karaoke tags. Matching PrimaryColour is the neutral
        # fallback and preserves the former default style.
        "secondary_color": rgba_to_ass_color(appearance.text_color),
        "outline_color": backdrop_color,
        "back_color": backdrop_color,
        "bold": -1 if appearance.bold else 0,
        "italic": -1 if appearance.italic else 0,
        "underline": 0,
        "strikeout": 0,
        "scale_x": 100,
        "scale_y": 100,
        "spacing": 0,
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
    value = _finite_time(seconds)
    if value is None:
        raise ArtifactError("ASS timestamp must be a finite, non-negative number")
    total_centiseconds = round(value * 100)
    hours, remainder = divmod(total_centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


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
