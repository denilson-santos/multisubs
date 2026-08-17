"""Static CLI and ASS styling configuration."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

from .errors import ValidationError
from .models import (
    LayoutPreset,
    RelativeLength,
    SubtitleAppearance,
    SubtitleConfig,
    SubtitleLayout,
    SubtitleLayoutPreset,
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
LAYOUT_PRESET_CHOICES = tuple(preset.value for preset in SubtitleLayoutPreset)

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
_RELATIVE_LENGTH_PATTERN = re.compile(
    r"^(?P<number>(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,3})?)"
    r"(?P<unit>%|px)$"
)
_RELATIVE_FIELDS = {
    "font_size",
    "outline_weight",
    "shadow_weight",
    "margin_left",
    "margin_right",
    "margin_top",
    "margin_bottom",
}
_LAYOUT_OVERRIDE_FIELDS = frozenset(
    {
        "position",
        "margin_left",
        "margin_right",
        "margin_top",
        "margin_bottom",
    }
)


def parse_relative_length(raw_value: str) -> RelativeLength:
    """Parse one finite, unit-bearing percentage or pixel length."""
    if not isinstance(raw_value, str):
        raise ValidationError("length must be a string ending in % or px")

    original = raw_value.strip()
    match = _RELATIVE_LENGTH_PATTERN.fullmatch(original)
    if match is None:
        raise ValidationError(
            "length must be a non-negative number with a % or px suffix "
            "(for example 8% or 72px)"
        )
    try:
        value = Decimal(match.group("number"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("length must be a finite decimal number") from exc
    if not value.is_finite():
        raise ValidationError("length must be a finite decimal number")
    return RelativeLength(value=value, unit=match.group("unit"), original=original)


def _preset_length(raw_value: str) -> RelativeLength:
    return parse_relative_length(raw_value)


LAYOUT_PRESETS: Mapping[SubtitleLayoutPreset, LayoutPreset] = MappingProxyType(
    {
        SubtitleLayoutPreset.LANDSCAPE: LayoutPreset(
            name=SubtitleLayoutPreset.LANDSCAPE,
            description="wide video with a balanced lower safe area",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("6%"),
                margin_right=_preset_length("6%"),
                margin_top=_preset_length("0%"),
                margin_bottom=_preset_length("6%"),
            ),
        ),
        SubtitleLayoutPreset.PORTRAIT: LayoutPreset(
            name=SubtitleLayoutPreset.PORTRAIT,
            description="tall video with an expanded lower safe area",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("8%"),
                margin_right=_preset_length("8%"),
                margin_top=_preset_length("0%"),
                margin_bottom=_preset_length("8%"),
            ),
        ),
        SubtitleLayoutPreset.SQUARE: LayoutPreset(
            name=SubtitleLayoutPreset.SQUARE,
            description="square video with a compact lower safe area",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("7%"),
                margin_right=_preset_length("7%"),
                margin_top=_preset_length("0%"),
                margin_bottom=_preset_length("7%"),
            ),
        ),
        SubtitleLayoutPreset.VERTICAL_SOCIAL: LayoutPreset(
            name=SubtitleLayoutPreset.VERTICAL_SOCIAL,
            description="generic vertical overlay-safe composition",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("8%"),
                margin_right=_preset_length("12%"),
                margin_top=_preset_length("8%"),
                margin_bottom=_preset_length("16%"),
            ),
        ),
        SubtitleLayoutPreset.UPPER_THIRD: LayoutPreset(
            name=SubtitleLayoutPreset.UPPER_THIRD,
            description="top-centered subtitle in the upper third",
            layout=SubtitleLayout(
                position=SubtitlePosition.TOP_CENTER,
                margin_left=_preset_length("6%"),
                margin_right=_preset_length("6%"),
                margin_top=_preset_length("8%"),
                margin_bottom=_preset_length("0%"),
            ),
        ),
        SubtitleLayoutPreset.CENTERED: LayoutPreset(
            name=SubtitleLayoutPreset.CENTERED,
            description="centered subtitle with a balanced safe area",
            layout=SubtitleLayout(
                position=SubtitlePosition.CENTER,
                margin_left=_preset_length("8%"),
                margin_right=_preset_length("8%"),
                margin_top=_preset_length("8%"),
                margin_bottom=_preset_length("8%"),
            ),
        ),
    }
)


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
    layout_preset: SubtitleLayoutPreset | str | None = None,
    relative_values: Mapping[str, RelativeLength | str] | None = None,
) -> SubtitleConfig:
    """Return typed subtitle configuration from typed or legacy style input."""
    resolved_position = parse_position(position) if position is not None else None
    resolved_preset = (
        parse_layout_preset(layout_preset) if layout_preset is not None else None
    )
    if isinstance(value, SubtitleConfig):
        if relative_values:
            raise ValidationError(
                "relative values cannot override an existing subtitle configuration"
            )
        if resolved_position is not None and resolved_position != value.layout.position:
            raise ValidationError(
                "position cannot override the position already stored in the "
                "subtitle configuration"
            )
        if resolved_preset is not None and resolved_preset != value.layout_preset:
            raise ValidationError(
                "layout preset cannot override the preset already stored in the "
                "subtitle configuration"
            )
        _validate_typed_subtitle_config(value)
        return value
    style = validate_style_options(value)
    parsed_relative_values = _validate_relative_values(relative_values)
    style_keys = set(value) if value else set()
    layout_overrides = set()
    if resolved_position is not None:
        layout_overrides.add("position")
    if "margin_l" in style_keys:
        layout_overrides.add("margin_left")
    if "margin_r" in style_keys:
        layout_overrides.add("margin_right")
    if "margin_v" in style_keys:
        layout_overrides.update({"margin_top", "margin_bottom"})
    layout_overrides.update(
        field for field in parsed_relative_values if field in _LAYOUT_OVERRIDE_FIELDS
    )
    return _subtitle_config_from_validated_style(
        style,
        position=resolved_position or DEFAULT_POSITION,
        layout_preset=resolved_preset or SubtitleLayoutPreset.AUTO,
        layout_overrides=frozenset(layout_overrides),
        relative_values=parsed_relative_values,
    )


def subtitle_config_to_style_options(
    config: SubtitleConfig,
) -> dict[str, str | int]:
    """Convert typed configuration into the temporary ASS style mapping."""
    appearance = config.appearance
    layout = config.layout
    font_size = _resolved_style_int(appearance.font_size, "font-size")
    outline_weight = _resolved_style_int(
        appearance.outline_weight, "backdrop-size"
    )
    shadow_weight = _resolved_style_int(appearance.shadow_weight, "shadow-size")
    margin_left = _resolved_style_int(layout.margin_left, "margin-left")
    margin_right = _resolved_style_int(layout.margin_right, "margin-right")
    margin_top = _resolved_style_int(layout.margin_top, "margin-top")
    margin_bottom = _resolved_style_int(layout.margin_bottom, "margin-bottom")
    margin_v = (
        margin_top
        if layout.position.value.startswith("top-")
        else margin_bottom
        if layout.position.value.startswith("bottom-")
        else min(margin_top, margin_bottom)
    )
    return validate_style_options(
        {
            "font": appearance.font,
            "font_size": font_size,
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
            "outline_weight": outline_weight,
            "shadow_weight": shadow_weight,
            "margin_l": margin_left,
            "margin_r": margin_right,
            "margin_v": margin_v,
        }
    )


def _subtitle_config_from_validated_style(
    style: Mapping[str, str | int],
    *,
    position: SubtitlePosition,
    layout_preset: SubtitleLayoutPreset = SubtitleLayoutPreset.AUTO,
    layout_overrides: frozenset[str] = frozenset(),
    relative_values: Mapping[str, RelativeLength] | None = None,
) -> SubtitleConfig:
    relative_values = relative_values or {}
    return SubtitleConfig(
        appearance=SubtitleAppearance(
            font=str(style["font"]),
            font_size=relative_values.get("font_size", int(style["font_size"])),
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
            outline_weight=relative_values.get(
                "outline_weight", int(style["outline_weight"])
            ),
            shadow_weight=relative_values.get(
                "shadow_weight", int(style["shadow_weight"])
            ),
        ),
        layout=SubtitleLayout(
            position=position,
            margin_left=relative_values.get("margin_left", int(style["margin_l"])),
            margin_right=relative_values.get(
                "margin_right", int(style["margin_r"])
            ),
            margin_top=relative_values.get("margin_top", int(style["margin_v"])),
            margin_bottom=relative_values.get(
                "margin_bottom", int(style["margin_v"])
            ),
        ),
        layout_preset=layout_preset,
        layout_overrides=layout_overrides,
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


def parse_layout_preset(
    value: SubtitleLayoutPreset | str,
) -> SubtitleLayoutPreset:
    """Parse one public layout preset name."""
    if isinstance(value, SubtitleLayoutPreset):
        return value
    if not isinstance(value, str):
        raise ValidationError(
            "layout must be one of: " + ", ".join(LAYOUT_PRESET_CHOICES)
        )
    try:
        return SubtitleLayoutPreset(value)
    except ValueError as exc:
        raise ValidationError(
            "layout must be one of: " + ", ".join(LAYOUT_PRESET_CHOICES)
        ) from exc


def get_layout_preset(value: SubtitleLayoutPreset | str) -> LayoutPreset:
    """Return an immutable concrete preset definition."""
    preset = parse_layout_preset(value)
    if preset is SubtitleLayoutPreset.AUTO:
        raise ValidationError("auto must be resolved against video geometry first")
    try:
        return LAYOUT_PRESETS[preset]
    except KeyError as exc:
        raise ValidationError(
            f"No layout preset is defined for '{preset.value}'"
        ) from exc


def _validate_relative_values(
    values: Mapping[str, RelativeLength | str] | None,
) -> dict[str, RelativeLength]:
    if not values:
        return {}
    unknown = set(values).difference(_RELATIVE_FIELDS)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValidationError(f"Unknown relative value(s): {names}")

    parsed: dict[str, RelativeLength] = {}
    for key, value in values.items():
        if isinstance(value, str):
            value = parse_relative_length(value)
        _validate_relative_length(value, key)
        parsed[key] = value
    return parsed


def _validate_relative_length(value: object, field: str) -> None:
    if not isinstance(value, RelativeLength):
        raise ValidationError(f"{field.replace('_', '-')} must be a relative length")
    if value.unit not in {"%", "px"}:
        raise ValidationError(
            f"{field.replace('_', '-')} must use % or px units"
        )
    if not isinstance(value.value, Decimal) or not value.value.is_finite():
        raise ValidationError(
            f"{field.replace('_', '-')} must be a finite decimal number"
        )
    if value.value < 0:
        raise ValidationError(f"{field.replace('_', '-')} cannot be negative")
    if not isinstance(value.original, str) or not value.original.strip():
        raise ValidationError(
            f"{field.replace('_', '-')} must retain its original value"
        )
    try:
        parsed = parse_relative_length(value.original)
    except ValidationError as exc:
        raise ValidationError(
            f"{field.replace('_', '-')} has an invalid original value"
        ) from exc
    if parsed.value != value.value or parsed.unit != value.unit:
        raise ValidationError(
            f"{field.replace('_', '-')} does not match its original value"
        )


def _validate_typed_subtitle_config(config: SubtitleConfig) -> None:
    if not isinstance(config.layout.position, SubtitlePosition):
        raise ValidationError("layout position must use a supported position value")
    try:
        preset = parse_layout_preset(config.layout_preset)
    except ValidationError:
        raise
    if not isinstance(config.layout_overrides, frozenset):
        raise ValidationError("layout overrides must be an immutable set")
    if not all(isinstance(field, str) for field in config.layout_overrides):
        raise ValidationError("layout overrides must contain field names")
    unknown_overrides = set(config.layout_overrides).difference(
        _LAYOUT_OVERRIDE_FIELDS
    )
    if unknown_overrides:
        names = ", ".join(sorted(unknown_overrides))
        raise ValidationError(f"Unknown layout override(s): {names}")
    if preset is not config.layout_preset:
        raise ValidationError("layout preset must use a supported preset value")
    style_values: dict[str, str | int] = {
        "font": config.appearance.font,
        "primary_color": config.appearance.primary_color,
        "secondary_color": config.appearance.secondary_color,
        "outline_color": config.appearance.outline_color,
        "back_color": config.appearance.back_color,
        "bold": config.appearance.bold,
        "italic": config.appearance.italic,
        "underline": config.appearance.underline,
        "strikeout": config.appearance.strikeout,
        "scale_x": config.appearance.scale_x,
        "scale_y": config.appearance.scale_y,
        "spacing": config.appearance.spacing,
        "angle": config.appearance.angle,
        "border_style": config.appearance.border_style,
    }
    relative_fields = {
        "font_size": config.appearance.font_size,
        "outline_weight": config.appearance.outline_weight,
        "shadow_weight": config.appearance.shadow_weight,
        "margin_left": config.layout.margin_left,
        "margin_right": config.layout.margin_right,
        "margin_top": config.layout.margin_top,
        "margin_bottom": config.layout.margin_bottom,
    }
    for field, value in relative_fields.items():
        if isinstance(value, RelativeLength):
            _validate_relative_length(value, field)
        else:
            style_key = {
                "font_size": "font_size",
                "outline_weight": "outline_weight",
                "shadow_weight": "shadow_weight",
                "margin_left": "margin_l",
                "margin_right": "margin_r",
                "margin_top": "margin_v",
                "margin_bottom": "margin_v",
            }[field]
            style_values[style_key] = value
    validate_style_options(style_values)


def _resolved_style_int(value: int | RelativeLength, field: str) -> int:
    if isinstance(value, RelativeLength):
        raise ValidationError(
            f"{field} must be resolved against video geometry before ASS compilation"
        )
    return value


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
