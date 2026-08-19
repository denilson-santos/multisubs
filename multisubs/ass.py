"""ASS subtitle serialization isolated from transcription and rendering."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

from .config import (
    subtitle_config_to_style_options,
    validate_subtitle_config,
)
from .errors import ArtifactError
from .layout import (
    resolve_cue_placement,
    resolve_safe_rectangle,
    resolve_subtitle_config,
)
from .models import CuePlacement, SubtitleConfig, SubtitlePosition, VideoGeometry
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
    subtitle_config: SubtitleConfig | Mapping[str, str | int] | None,
    geometry: VideoGeometry,
    *,
    placements: Sequence[CuePlacement | None] | None = None,
) -> None:
    """Write safe ASS dialogue on the probed, autorotated video canvas.

    ``placements`` is an internal per-cue contract. When omitted, a custom
    coordinate configuration produces one resolved placement for every cue;
    named positions continue to use the compiled style alignment.
    """
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ArtifactError("ASS canvas dimensions must be positive")
    config = resolve_subtitle_config(
        validate_subtitle_config(subtitle_config), geometry
    )
    resolve_safe_rectangle(geometry, config.layout)
    style = _compile_style(config)
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
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_time(segment['start'])},{format_ass_time(segment['end'])},"
            f"Default,,0,0,0,,{generated_override}"
            f"{escape_ass_text(str(segment['text']))}"
        )
    atomic_write_text(path, "\n".join(lines) + "\n")


def _compile_style(config: SubtitleConfig) -> dict[str, str | int]:
    """Compile semantic layout into the private numeric ASS style fields."""
    style = subtitle_config_to_style_options(config)
    style["alignment"] = _ass_alignment_for_position(
        config.layout.anchor or config.layout.position
    )
    return style


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
