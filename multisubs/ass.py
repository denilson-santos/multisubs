"""ASS subtitle serialization isolated from transcription and rendering."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

from .config import (
    ASS_STYLE_FIELDS,
    subtitle_config_to_style_options,
    validate_subtitle_config,
)
from .errors import ArtifactError
from .models import SubtitleConfig, VideoGeometry
from .utils import atomic_write_text

LEGACY_PLAY_RES_X = 384
LEGACY_PLAY_RES_Y = 288
_VERTICAL_STYLE_FIELDS = ("font_size", "outline_weight", "shadow_weight", "margin_v")
_HORIZONTAL_STYLE_FIELDS = ("spacing", "margin_l", "margin_r")


def write_ass(
    path: Path,
    segments: Sequence[Mapping[str, Any]],
    subtitle_config: SubtitleConfig | Mapping[str, str | int] | None,
    geometry: VideoGeometry,
) -> None:
    """Write safe ASS dialogue on the probed, autorotated video canvas."""
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ArtifactError("ASS canvas dimensions must be positive")
    config = validate_subtitle_config(subtitle_config)
    style = _resolve_style_for_geometry(
        subtitle_config_to_style_options(config), geometry
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
        "Style: Default,"
        + ",".join(str(style[field]) for field in ASS_STYLE_FIELDS)
        + ",1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    for segment in segments:
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_time(segment['start'])},{format_ass_time(segment['end'])},"
            f"Default,,0,0,0,,{escape_ass_text(str(segment['text']))}"
        )
    atomic_write_text(path, "\n".join(lines) + "\n")


def _resolve_style_for_geometry(
    style: Mapping[str, str | int], geometry: VideoGeometry
) -> dict[str, str | int]:
    """Scale legacy ASS units from libass's implicit 384x288 canvas.

    The temporary ``--style-*`` interface historically supplied raw ASS values
    without a PlayRes header. libass used a 384x288 design canvas in that case,
    so preserve the visual proportions while the explicit canvas follows the
    autorotated video frame.
    """
    resolved = dict(style)
    width_scale = geometry.render_width / LEGACY_PLAY_RES_X
    height_scale = geometry.render_height / LEGACY_PLAY_RES_Y
    for field in _VERTICAL_STYLE_FIELDS:
        resolved[field] = _scale_style_value(
            int(resolved[field]), height_scale, minimum=1 if field == "font_size" else 0
        )
    for field in _HORIZONTAL_STYLE_FIELDS:
        resolved[field] = _scale_style_value(int(resolved[field]), width_scale)
    return resolved


def _scale_style_value(value: int, scale: float, *, minimum: int = 0) -> int:
    return max(minimum, int(round(value * scale)))


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
