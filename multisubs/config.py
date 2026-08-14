"""Static CLI and ASS styling configuration."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from .errors import ValidationError
from .models import SubtitleAppearance, SubtitleConfig, SubtitleLayout

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
    "font_size": 14,
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
    "alignment": 2,
    "margin_l": 40,
    "margin_r": 40,
    "margin_v": 15,
}

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
) -> SubtitleConfig:
    """Return typed subtitle configuration from typed or legacy style input."""
    if isinstance(value, SubtitleConfig):
        style = subtitle_config_to_style_options(value)
    else:
        style = validate_style_options(value)
    return _subtitle_config_from_validated_style(style)


def subtitle_config_to_style_options(
    config: SubtitleConfig,
) -> dict[str, str | int]:
    """Convert typed configuration into the established ASS style mapping."""
    appearance = config.appearance
    layout = config.layout
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
            "alignment": layout.alignment,
            "margin_l": layout.margin_l,
            "margin_r": layout.margin_r,
            "margin_v": layout.margin_v,
        }
    )


def _subtitle_config_from_validated_style(
    style: Mapping[str, str | int],
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
            alignment=int(style["alignment"]),
            margin_l=int(style["margin_l"]),
            margin_r=int(style["margin_r"]),
            margin_v=int(style["margin_v"]),
        ),
    )


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
    if key == "alignment" and value not in range(1, 10):
        raise ValidationError("style-alignment must be between 1 and 9")
    if key == "border_style" and value not in {1, 3, 4}:
        raise ValidationError("style-border-style must be one of 1, 3, or 4")
    return value
