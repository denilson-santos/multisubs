"""Static CLI and ASS styling configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType

from .errors import ValidationError
from .models import (
    LayoutPreset,
    RelativeLength,
    SubtitleAppearance,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleLayout,
    SubtitleLayoutPreset,
    SubtitlePlacementMode,
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

POSITION_CHOICES = tuple(position.value for position in SubtitlePosition)
DEFAULT_POSITION = SubtitlePosition.BOTTOM_CENTER
LAYOUT_PRESET_CHOICES = tuple(preset.value for preset in SubtitleLayoutPreset)
BACKDROP_CHOICES = tuple(backdrop.value for backdrop in SubtitleBackdrop)

_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
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
    "max_width",
    "max_height",
    "position_x",
    "position_y",
}
_LAYOUT_OVERRIDE_FIELDS = frozenset(
    {
        "position",
        "margin_left",
        "margin_right",
        "margin_top",
        "margin_bottom",
        "max_width",
        "max_height",
    }
)

DEFAULT_FONT = "Roboto"
DEFAULT_FONT_SIZE = "4%"
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_BOLD = False
DEFAULT_ITALIC = False
DEFAULT_BACKDROP = SubtitleBackdrop.BOX
DEFAULT_BACKDROP_COLOR = "#00000099"
DEFAULT_BACKDROP_SIZE = "0px"
DEFAULT_SHADOW_SIZE = "4%"


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
            description="wide video with balanced lower native margins",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("6%"),
                margin_right=_preset_length("6%"),
                margin_top=_preset_length("0%"),
                margin_bottom=_preset_length("6%"),
                max_width=_preset_length("100%"),
                max_height=_preset_length("10.5%"),
            ),
        ),
        SubtitleLayoutPreset.PORTRAIT: LayoutPreset(
            name=SubtitleLayoutPreset.PORTRAIT,
            description="tall video with expanded lower native margins",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("8%"),
                margin_right=_preset_length("8%"),
                margin_top=_preset_length("0%"),
                margin_bottom=_preset_length("8%"),
                max_width=_preset_length("100%"),
                max_height=_preset_length("6%"),
            ),
        ),
        SubtitleLayoutPreset.SQUARE: LayoutPreset(
            name=SubtitleLayoutPreset.SQUARE,
            description="square video with compact lower native margins",
            layout=SubtitleLayout(
                position=SubtitlePosition.BOTTOM_CENTER,
                margin_left=_preset_length("7%"),
                margin_right=_preset_length("7%"),
                margin_top=_preset_length("0%"),
                margin_bottom=_preset_length("7%"),
                max_width=_preset_length("100%"),
                max_height=_preset_length("10.6%"),
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
                max_width=_preset_length("100%"),
                max_height=_preset_length("6.6%"),
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
                max_width=_preset_length("100%"),
                max_height=_preset_length("10.7%"),
            ),
        ),
        SubtitleLayoutPreset.CENTERED: LayoutPreset(
            name=SubtitleLayoutPreset.CENTERED,
            description="centered subtitle with balanced horizontal margins",
            layout=SubtitleLayout(
                position=SubtitlePosition.CENTER,
                margin_left=_preset_length("8%"),
                margin_right=_preset_length("8%"),
                margin_top=_preset_length("8%"),
                margin_bottom=_preset_length("8%"),
                max_width=_preset_length("100%"),
                max_height=_preset_length("10%"),
            ),
        ),
    }
)


def validate_subtitle_config(
    value: SubtitleConfig | None,
    *,
    appearance_values: Mapping[str, object] | None = None,
    position: SubtitlePosition | str | None = None,
    layout_preset: SubtitleLayoutPreset | str | None = None,
    relative_values: Mapping[str, RelativeLength | str] | None = None,
    position_x: RelativeLength | str | None = None,
    position_y: RelativeLength | str | None = None,
    anchor: SubtitlePosition | str | None = None,
) -> SubtitleConfig:
    """Return a complete, validated semantic subtitle configuration."""
    resolved_position = parse_position(position) if position is not None else None
    resolved_preset = (
        parse_layout_preset(layout_preset) if layout_preset is not None else None
    )
    resolved_anchor = parse_position(anchor) if anchor is not None else None
    if isinstance(value, SubtitleConfig):
        if (
            appearance_values
            or relative_values
            or position_x is not None
            or position_y is not None
        ):
            raise ValidationError(
                "values cannot override an existing subtitle configuration"
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
        if resolved_anchor is not None and resolved_anchor != value.layout.anchor:
            raise ValidationError(
                "anchor cannot override the anchor already stored in the subtitle "
                "configuration"
            )
        _validate_typed_subtitle_config(value)
        return value
    if value is not None:
        raise ValidationError(
            "raw ASS style mappings are no longer supported; use SubtitleConfig"
        )

    appearance_overrides = dict(appearance_values or {})
    known_appearance_fields = {
        "font",
        "text_color",
        "bold",
        "italic",
        "backdrop",
        "backdrop_color",
        "fonts_dir",
    }
    unknown_appearance_fields = set(appearance_overrides).difference(
        known_appearance_fields
    )
    if unknown_appearance_fields:
        names = ", ".join(sorted(unknown_appearance_fields))
        raise ValidationError(f"Unknown appearance value(s): {names}")

    parsed_relative_values = _validate_relative_values(relative_values)
    for field, raw_value in (
        ("position_x", position_x),
        ("position_y", position_y),
    ):
        if raw_value is None:
            continue
        if field in parsed_relative_values:
            raise ValidationError(
                f"{field.replace('_', '-')} was provided more than once"
            )
        if isinstance(raw_value, str):
            raw_value = parse_relative_length(raw_value)
        _validate_relative_length(raw_value, field)
        parsed_relative_values[field] = raw_value

    has_position_x = "position_x" in parsed_relative_values
    has_position_y = "position_y" in parsed_relative_values
    has_custom_coordinates = has_position_x or has_position_y
    if has_position_x != has_position_y:
        raise ValidationError("position-x and position-y must be supplied together")
    if has_custom_coordinates and resolved_position is not None:
        raise ValidationError(
            "position cannot be combined with custom position-x and position-y"
        )
    if resolved_anchor is not None and not has_custom_coordinates:
        raise ValidationError("anchor requires both position-x and position-y")
    if has_custom_coordinates and resolved_anchor is None:
        raise ValidationError("custom coordinates require an explicit anchor")
    if has_custom_coordinates and "max_width" not in parsed_relative_values:
        raise ValidationError("custom coordinates require an explicit max-width")
    if has_custom_coordinates and "max_height" not in parsed_relative_values:
        raise ValidationError("custom coordinates require an explicit max-height")
    layout_overrides = set()
    if resolved_position is not None:
        layout_overrides.add("position")
    layout_overrides.update(
        field for field in parsed_relative_values if field in _LAYOUT_OVERRIDE_FIELDS
    )
    config = SubtitleConfig(
        appearance=SubtitleAppearance(
            font=_validate_font(appearance_overrides.get("font", DEFAULT_FONT)),
            font_size=parsed_relative_values.get(
                "font_size", parse_relative_length(DEFAULT_FONT_SIZE)
            ),
            text_color=_validate_color(
                appearance_overrides.get("text_color", DEFAULT_TEXT_COLOR),
                "text-color",
            ),
            bold=_validate_boolean(
                appearance_overrides.get("bold", DEFAULT_BOLD), "bold"
            ),
            italic=_validate_boolean(
                appearance_overrides.get("italic", DEFAULT_ITALIC), "italic"
            ),
            backdrop=_validate_backdrop(
                appearance_overrides.get("backdrop", DEFAULT_BACKDROP)
            ),
            backdrop_color=_validate_color(
                appearance_overrides.get("backdrop_color", DEFAULT_BACKDROP_COLOR),
                "backdrop-color",
            ),
            backdrop_size=parsed_relative_values.get(
                "outline_weight", parse_relative_length(DEFAULT_BACKDROP_SIZE)
            ),
            shadow_size=parsed_relative_values.get(
                "shadow_weight", parse_relative_length(DEFAULT_SHADOW_SIZE)
            ),
            fonts_dir=_coerce_fonts_dir(appearance_overrides.get("fonts_dir")),
        ),
        layout=SubtitleLayout(
            position=resolved_position or DEFAULT_POSITION,
            margin_left=parsed_relative_values.get("margin_left", 0),
            margin_right=parsed_relative_values.get("margin_right", 0),
            margin_top=parsed_relative_values.get("margin_top", 0),
            margin_bottom=parsed_relative_values.get("margin_bottom", 0),
            placement_mode=(
                SubtitlePlacementMode.EXPLICIT
                if has_custom_coordinates
                else SubtitlePlacementMode.NATIVE_STYLE
            ),
            position_x=parsed_relative_values.get("position_x"),
            position_y=parsed_relative_values.get("position_y"),
            anchor=resolved_anchor if has_custom_coordinates else None,
            max_width=parsed_relative_values.get("max_width"),
            max_height=parsed_relative_values.get("max_height"),
        ),
        layout_preset=resolved_preset or SubtitleLayoutPreset.AUTO,
        layout_overrides=frozenset(layout_overrides),
    )
    _validate_typed_subtitle_config(config)
    return config


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
        raise ValidationError(f"{field.replace('_', '-')} must use % or px units")
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
    if not isinstance(config.layout.placement_mode, SubtitlePlacementMode):
        raise ValidationError("layout placement mode must be native-style or explicit")
    if config.layout.anchor is not None and not isinstance(
        config.layout.anchor, SubtitlePosition
    ):
        raise ValidationError("layout anchor must use a supported position value")
    has_position_x = config.layout.position_x is not None
    has_position_y = config.layout.position_y is not None
    if has_position_x != has_position_y:
        raise ValidationError("position-x and position-y must be supplied together")
    if config.layout.anchor is not None and not has_position_x:
        raise ValidationError("anchor requires both position-x and position-y")
    if has_position_x and config.layout.anchor is None:
        raise ValidationError("custom coordinates require an anchor")
    is_explicit = config.layout.placement_mode is SubtitlePlacementMode.EXPLICIT
    if is_explicit != has_position_x:
        raise ValidationError(
            "explicit placement requires position-x, position-y, and anchor"
        )
    if is_explicit and config.layout.max_width is None:
        raise ValidationError("explicit placement requires max-width")
    if is_explicit and config.layout.max_height is None:
        raise ValidationError("explicit placement requires max-height")
    try:
        preset = parse_layout_preset(config.layout_preset)
    except ValidationError:
        raise
    if not isinstance(config.layout_overrides, frozenset):
        raise ValidationError("layout overrides must be an immutable set")
    if not all(isinstance(field, str) for field in config.layout_overrides):
        raise ValidationError("layout overrides must contain field names")
    unknown_overrides = set(config.layout_overrides).difference(_LAYOUT_OVERRIDE_FIELDS)
    if unknown_overrides:
        names = ", ".join(sorted(unknown_overrides))
        raise ValidationError(f"Unknown layout override(s): {names}")
    if preset is not config.layout_preset:
        raise ValidationError("layout preset must use a supported preset value")
    _validate_font(config.appearance.font)
    _validate_color(config.appearance.text_color, "text-color")
    _validate_boolean(config.appearance.bold, "bold")
    _validate_boolean(config.appearance.italic, "italic")
    _validate_backdrop(config.appearance.backdrop)
    _validate_color(config.appearance.backdrop_color, "backdrop-color")
    _coerce_fonts_dir(config.appearance.fonts_dir)
    relative_fields = {
        "font_size": config.appearance.font_size,
        "outline_weight": config.appearance.backdrop_size,
        "shadow_weight": config.appearance.shadow_size,
        "margin_left": config.layout.margin_left,
        "margin_right": config.layout.margin_right,
        "margin_top": config.layout.margin_top,
        "margin_bottom": config.layout.margin_bottom,
        "max_width": config.layout.max_width,
        "max_height": config.layout.max_height,
    }
    for field, value in relative_fields.items():
        if value is None and field in {"max_width", "max_height"}:
            continue
        if isinstance(value, RelativeLength):
            _validate_relative_length(value, field)
        elif isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(
                f"{field.replace('_', '-')} must be an integer or relative length"
            )
        elif value < 0 or (
            field in {"font_size", "max_width", "max_height"} and value == 0
        ):
            comparator = (
                "greater than zero"
                if field in {"font_size", "max_width", "max_height"}
                else "non-negative"
            )
            raise ValidationError(f"{field.replace('_', '-')} must be {comparator}")

    for field, value in {
        "position_x": config.layout.position_x,
        "position_y": config.layout.position_y,
    }.items():
        if value is None:
            continue
        if isinstance(value, RelativeLength):
            _validate_relative_length(value, field)
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValidationError(
                f"{field.replace('_', '-')} must be a non-negative integer or "
                "relative length"
            )


def _validate_font(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("font must not be empty")
    if any(character in value for character in (",", "\r", "\n")):
        raise ValidationError("font cannot contain commas or line breaks")
    return value


def _validate_color(value: object, field: str) -> str:
    if not isinstance(value, str) or not _COLOR_PATTERN.fullmatch(value):
        raise ValidationError(
            f"{field} must use #RRGGBB or #RRGGBBAA hexadecimal notation"
        )
    return value.upper()


def _validate_boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be enabled or disabled")
    return value


def _validate_backdrop(value: object) -> SubtitleBackdrop:
    if isinstance(value, SubtitleBackdrop):
        return value
    if isinstance(value, str):
        try:
            return SubtitleBackdrop(value)
        except ValueError:
            pass
    raise ValidationError("backdrop must be one of: " + ", ".join(BACKDROP_CHOICES))


def _coerce_fonts_dir(value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, (str, Path)):
        raise ValidationError("fonts-dir must be a directory path")
    path = Path(value).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_dir():
        raise ValidationError(f"Fonts directory not found at '{value}'")
    return path
