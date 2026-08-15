"""Static CLI and ASS styling configuration."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from .errors import ValidationError
from .models import (
    SubtitleAppearance,
    SubtitleConfig,
    SubtitleLayout,
    SubtitlePosition,
)

SUPPORTED_LANGUAGES = (
    "ar",
    "ca",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "eu",
    "fa",
    "fi",
    "fr",
    "gl",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "ka",
    "ko",
    "lv",
    "ml",
    "nl",
    "nn",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sv",
    "te",
    "tl",
    "tr",
    "uk",
    "ur",
    "vi",
    "zh",
)

MODELS = (
    "tiny.en",
    "tiny",
    "base.en",
    "base",
    "small.en",
    "small",
    "medium.en",
    "medium",
    "large",
    "turbo",
)

DEFAULT_STYLE: dict[str, str | int] = {
    "font": "Roboto",
    "font_size": 43,
    "primary_color": "&H00FFFFFF",
    "secondary_color": "&H00FFFFFF",
    "outline_color": "&H66000000",
    "back_color": "&H66000000",
    "bold": 0,
    "italic": 0,
    "underline": 0,
    "strikeout": 0,
    "scale_x": 100,
    "scale_y": 100,
    "spacing": 0,
    "angle": 0,
    "border_style": 4,
    "outline_weight": 0,
    "shadow_weight": 2,
    "margin_l": 0,
    "margin_r": 0,
    "margin_v": 35,
}

POSITION_CHOICES = tuple(position.value for position in SubtitlePosition)
DEFAULT_POSITION = SubtitlePosition.BOTTOM_CENTER

_COLOR_FIELDS = {
    "primary_color",
    "secondary_color",
    "outline_color",
    "back_color",
}
_BOOLEAN_FIELDS = {"bold", "italic", "underline", "strikeout"}
_POSITIVE_FIELDS = {"font_size", "scale_x", "scale_y"}
_NON_NEGATIVE_FIELDS = {
    "outline_weight",
    "shadow_weight",
    "margin_l",
    "margin_r",
    "margin_v",
}
_COLOR_PATTERN = re.compile(r"^&H(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


def parse_style_option(key: str, raw_value: str) -> str | int:
    """Parse and validate one CLI style value without depending on argparse."""
    if key not in DEFAULT_STYLE:
        raise ValueError(f"Unknown style option: {key}")

    value: str | int
    if isinstance(DEFAULT_STYLE[key], int):
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise ValueError(f"{key.replace('_', '-')} must be an integer") from exc
    else:
        value = raw_value

    return _validate_style_value(key, value)


def validate_style_options(
    style_options: Mapping[str, str | int] | None,
) -> dict[str, str | int]:
    """Return complete, ASS-safe styling with defaults applied."""
    style = DEFAULT_STYLE.copy()
    if not style_options:
        return style

    unknown = set(style_options).difference(DEFAULT_STYLE)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValidationError(f"Unknown style option(s): {names}")

    for key, value in style_options.items():
        style[key] = _validate_style_value(key, value)
    return style


def validate_subtitle_config(
    value: SubtitleConfig | Mapping[str, str | int] | None,
    *,
    position: SubtitlePosition | str | None = None,
) -> SubtitleConfig:
    """Return typed subtitle configuration from typed or legacy style input."""
    resolved_position = parse_position(position) if position is not None else None
    if isinstance(value, SubtitleConfig):
        if resolved_position is not None and resolved_position != value.layout.position:
            raise ValidationError(
                "position cannot override the position already stored in the "
                "subtitle configuration"
            )
        return value
    style = validate_style_options(value)
    return _subtitle_config_from_validated_style(
        style,
        position=resolved_position or DEFAULT_POSITION,
    )


def subtitle_config_to_style_options(
    config: SubtitleConfig,
) -> dict[str, str | int]:
    """Convert typed configuration into the temporary ASS style mapping."""
    appearance = config.appearance
    layout = config.layout
    margin_v = (
        layout.margin_top
        if layout.position.value.startswith("top-")
        else layout.margin_bottom
        if layout.position.value.startswith("bottom-")
        else min(layout.margin_top, layout.margin_bottom)
    )
    return validate_style_options(
        {
            "font": appearance.font,
            "font_size": appearance.font_size,
            "primary_color": appearance.primary_color,
            "secondary_color": appearance.secondary_color,
            "outline_color": appearance.outline_color,
            "back_color": appearance.back_color,
            "bold": appearance.bold,
            "italic": appearance.italic,
            "underline": appearance.underline,
            "strikeout": appearance.strikeout,
            "scale_x": appearance.scale_x,
            "scale_y": appearance.scale_y,
            "spacing": appearance.spacing,
            "angle": appearance.angle,
            "border_style": appearance.border_style,
            "outline_weight": appearance.outline_weight,
            "shadow_weight": appearance.shadow_weight,
            "margin_l": layout.margin_left,
            "margin_r": layout.margin_right,
            "margin_v": margin_v,
        }
    )


def _subtitle_config_from_validated_style(
    style: Mapping[str, str | int],
    *,
    position: SubtitlePosition,
) -> SubtitleConfig:
    return SubtitleConfig(
        appearance=SubtitleAppearance(
            font=str(style["font"]),
            font_size=int(style["font_size"]),
            primary_color=str(style["primary_color"]),
            secondary_color=str(style["secondary_color"]),
            outline_color=str(style["outline_color"]),
            back_color=str(style["back_color"]),
            bold=int(style["bold"]),
            italic=int(style["italic"]),
            underline=int(style["underline"]),
            strikeout=int(style["strikeout"]),
            scale_x=int(style["scale_x"]),
            scale_y=int(style["scale_y"]),
            spacing=int(style["spacing"]),
            angle=int(style["angle"]),
            border_style=int(style["border_style"]),
            outline_weight=int(style["outline_weight"]),
            shadow_weight=int(style["shadow_weight"]),
        ),
        layout=SubtitleLayout(
            position=position,
            margin_left=int(style["margin_l"]),
            margin_right=int(style["margin_r"]),
            margin_top=int(style["margin_v"]),
            margin_bottom=int(style["margin_v"]),
        ),
    )


def parse_position(value: SubtitlePosition | str) -> SubtitlePosition:
    """Parse one lowercase, hyphenated semantic subtitle position."""
    if isinstance(value, SubtitlePosition):
        return value
    if not isinstance(value, str):
        raise ValidationError("position must be one of: " + ", ".join(POSITION_CHOICES))
    try:
        return SubtitlePosition(value)
    except ValueError as exc:
        raise ValidationError(
            "position must be one of: " + ", ".join(POSITION_CHOICES)
        ) from exc


def _validate_style_value(key: str, value: str | int) -> str | int:
    if key == "font":
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("style-font must not be empty")
        if any(character in value for character in (",", "\r", "\n")):
            raise ValidationError(
                "style-font cannot contain commas or line breaks for ASS output"
            )
        return value

    if key in _COLOR_FIELDS:
        if not isinstance(value, str) or not _COLOR_PATTERN.fullmatch(value):
            raise ValidationError(
                f"style-{key.replace('_', '-')} must be an ASS hexadecimal color "
                "such as &H00FFFFFF"
            )
        return value

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"style-{key.replace('_', '-')} must be an integer")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValidationError(f"style-{key.replace('_', '-')} must be finite") from exc
    if not finite:
        raise ValidationError(f"style-{key.replace('_', '-')} must be finite")
    if key in _BOOLEAN_FIELDS and value not in {0, 1}:
        raise ValidationError(f"style-{key.replace('_', '-')} must be 0 or 1")
    if key in _POSITIVE_FIELDS and value <= 0:
        raise ValidationError(
            f"style-{key.replace('_', '-')} must be greater than zero"
        )
    if key in _NON_NEGATIVE_FIELDS and value < 0:
        raise ValidationError(f"style-{key.replace('_', '-')} cannot be negative")
    if key == "border_style" and value not in {1, 3, 4}:
        raise ValidationError("style-border-style must be one of 1, 3, or 4")
    return value
