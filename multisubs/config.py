"""Static CLI and ASS styling configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from numbers import Real
from pathlib import Path
from types import MappingProxyType

from .errors import ValidationError
from .models import (
    FontWeight,
    FontWeightInputForm,
    KaraokeMode,
    LayoutPreset,
    RelativeLength,
    SubtitleAppearance,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleEffects,
    SubtitleLayout,
    SubtitleLayoutPreset,
    SubtitleOpacity,
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
KARAOKE_MODE_CHOICES = tuple(mode.value for mode in KaraokeMode)
FONT_WEIGHT_NAMES = tuple(weight.canonical_name for weight in FontWeight)
FONT_WEIGHT_RANKS = tuple(weight.rank for weight in FontWeight)

_FONT_WEIGHT_BY_NAME = MappingProxyType(
    {weight.canonical_name: weight for weight in FontWeight}
)
_FONT_WEIGHT_BY_RANK = MappingProxyType({weight.rank: weight for weight in FontWeight})
_FONT_WEIGHT_ALIASES = MappingProxyType(
    {
        "hairline": FontWeight.THIN,
        "ultra-light": FontWeight.EXTRA_LIGHT,
        "normal": FontWeight.REGULAR,
        "book": FontWeight.REGULAR,
        "demi-bold": FontWeight.SEMI_BOLD,
        "ultra-bold": FontWeight.EXTRA_BOLD,
        "heavy": FontWeight.BLACK,
    }
)
FONT_WEIGHT_ALIASES = tuple(_FONT_WEIGHT_ALIASES)

_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
_RELATIVE_LENGTH_PATTERN = re.compile(
    r"^(?P<number>(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,3})?)"
    r"(?P<unit>%|px)$"
)
_OPACITY_PATTERN = re.compile(r"^(?P<number>(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,3})?)%$")
_RELATIVE_FIELDS = {
    "font_size",
    "letter_spacing",
    "line_height",
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
DEFAULT_LETTER_SPACING = "0px"
DEFAULT_LINE_HEIGHT = "auto"
DEFAULT_OPACITY = "100%"
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_FONT_WEIGHT = FontWeight.REGULAR
DEFAULT_ITALIC = False
DEFAULT_BACKDROP = SubtitleBackdrop.BOX
DEFAULT_BACKDROP_COLOR = "#00000099"
DEFAULT_BACKDROP_SIZE = "0px"
DEFAULT_SHADOW_SIZE = "4%"
DEFAULT_KARAOKE_HIGHLIGHT_COLOR = "#FFD54F"
DEFAULT_KARAOKE_MODE = KaraokeMode.PROGRESSIVE


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


def parse_line_height(raw_value: object) -> str | RelativeLength:
    """Parse ``auto`` or one positive, unit-bearing line-height value."""
    if isinstance(raw_value, str) and raw_value.strip().casefold() == "auto":
        return "auto"
    if not isinstance(raw_value, str):
        raise ValidationError("line-height must be auto or a positive length")
    try:
        value = parse_relative_length(raw_value)
    except ValidationError as exc:
        raise ValidationError(f"line-height: {exc}") from exc
    if value.value <= 0:
        raise ValidationError("line-height must be greater than zero")
    return value


def parse_opacity(raw_value: object) -> SubtitleOpacity:
    """Parse one explicit percentage between zero and one hundred."""
    if not isinstance(raw_value, str):
        raise ValidationError("opacity must be a percentage from 0% through 100%")
    original = raw_value.strip()
    match = _OPACITY_PATTERN.fullmatch(original)
    if match is None:
        raise ValidationError("opacity must be a percentage from 0% through 100%")
    try:
        percentage = Decimal(match.group("number"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("opacity must be a finite percentage") from exc
    if not percentage.is_finite() or percentage < 0 or percentage > 100:
        raise ValidationError("opacity must be between 0% and 100%")
    return SubtitleOpacity(percentage=percentage, original=original)


def parse_font_weight(value: object) -> FontWeight:
    """Parse one canonical name, documented alias, or 100-step numeric rank."""
    weight, _, _ = _parse_font_weight_request(value)
    return weight


def _parse_font_weight_request(
    value: object,
) -> tuple[FontWeight, str, FontWeightInputForm]:
    if isinstance(value, FontWeight):
        return value, value.canonical_name, FontWeightInputForm.NAME
    if isinstance(value, bool):
        raise _font_weight_error()
    if isinstance(value, int):
        weight = _FONT_WEIGHT_BY_RANK.get(value)
        if weight is None:
            raise _font_weight_error()
        return weight, str(value), FontWeightInputForm.NUMERIC
    if not isinstance(value, str):
        raise _font_weight_error()

    requested = value.strip()
    if re.fullmatch(r"[1-9][0-9]{2}", requested):
        rank = int(requested)
        weight = _FONT_WEIGHT_BY_RANK.get(rank)
        if weight is None:
            raise _font_weight_error()
        return weight, requested, FontWeightInputForm.NUMERIC

    lowered = requested.casefold()
    if not re.fullmatch(r"[a-z]+(?:(?: +|_|-)[a-z]+)*", lowered):
        raise _font_weight_error()
    normalized = re.sub(r" +", "-", lowered).replace("_", "-")
    weight = _FONT_WEIGHT_BY_NAME.get(normalized)
    if weight is not None:
        return weight, requested, FontWeightInputForm.NAME
    weight = _FONT_WEIGHT_ALIASES.get(normalized)
    if weight is not None:
        return weight, requested, FontWeightInputForm.ALIAS
    raise _font_weight_error()


def _font_weight_error() -> ValidationError:
    names = ", ".join(FONT_WEIGHT_NAMES)
    ranks = ", ".join(str(rank) for rank in FONT_WEIGHT_RANKS)
    return ValidationError(
        f"font-weight must be a supported name ({names}) or numeric rank ({ranks})"
    )


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
    effects_values: Mapping[str, object] | None = None,
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
            or effects_values
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
        if value.effects.enabled:
            highlight_color = _validate_color(
                value.effects.highlight_color or DEFAULT_KARAOKE_HIGHLIGHT_COLOR,
                "karaoke-highlight-color",
            )
            if highlight_color != value.effects.highlight_color:
                return replace(
                    value,
                    effects=replace(
                        value.effects,
                        highlight_color=highlight_color,
                    ),
                )
        return value
    if value is not None:
        raise ValidationError(
            "raw ASS style mappings are no longer supported; use SubtitleConfig"
        )

    appearance_overrides = dict(appearance_values or {})
    effects_overrides = dict(effects_values or {})
    known_appearance_fields = {
        "font",
        "text_color",
        "font_weight",
        "bold",
        "italic",
        "backdrop",
        "backdrop_color",
        "opacity",
        "fonts_dir",
    }
    unknown_appearance_fields = set(appearance_overrides).difference(
        known_appearance_fields
    )
    if unknown_appearance_fields:
        names = ", ".join(sorted(unknown_appearance_fields))
        raise ValidationError(f"Unknown appearance value(s): {names}")
    if "font_weight" in appearance_overrides and "bold" in appearance_overrides:
        raise ValidationError("font-weight cannot be combined with --bold or --no-bold")

    if "font_weight" in appearance_overrides:
        font_weight, font_weight_input, font_weight_input_form = (
            _parse_font_weight_request(appearance_overrides["font_weight"])
        )
    elif "bold" in appearance_overrides:
        bold = _validate_boolean(appearance_overrides["bold"], "bold")
        font_weight = FontWeight.BOLD if bold else FontWeight.REGULAR
        font_weight_input = font_weight.canonical_name
        font_weight_input_form = FontWeightInputForm.BOLD_SHORTHAND
    else:
        font_weight = DEFAULT_FONT_WEIGHT
        font_weight_input = DEFAULT_FONT_WEIGHT.canonical_name
        font_weight_input_form = FontWeightInputForm.DEFAULT

    opacity = _validate_opacity(appearance_overrides.get("opacity", DEFAULT_OPACITY))

    if "karaoke_highlight_color" in effects_overrides:
        if "highlight_color" in effects_overrides:
            raise ValidationError("highlight-color was provided more than once")
        effects_overrides["highlight_color"] = effects_overrides.pop(
            "karaoke_highlight_color"
        )
    if "mode" in effects_overrides:
        if "karaoke_mode" in effects_overrides:
            raise ValidationError("karaoke-mode was provided more than once")
        effects_overrides["karaoke_mode"] = effects_overrides.pop("mode")
    unknown_effect_fields = set(effects_overrides).difference(
        {"karaoke", "karaoke_mode", "highlight_color"}
    )
    if unknown_effect_fields:
        names = ", ".join(sorted(unknown_effect_fields))
        raise ValidationError(f"Unknown effect value(s): {names}")
    karaoke = _validate_boolean(effects_overrides.get("karaoke", False), "karaoke")
    raw_karaoke_mode = effects_overrides.get("karaoke_mode")
    if not karaoke and raw_karaoke_mode is not None:
        raise ValidationError("karaoke-mode requires --karaoke")
    karaoke_mode = (
        _validate_karaoke_mode(
            DEFAULT_KARAOKE_MODE if raw_karaoke_mode is None else raw_karaoke_mode
        )
        if karaoke
        else None
    )
    raw_highlight_color = effects_overrides.get("highlight_color")
    if not karaoke and raw_highlight_color is not None:
        raise ValidationError("karaoke-highlight-color requires --karaoke")
    highlight_color = (
        _validate_color(
            DEFAULT_KARAOKE_HIGHLIGHT_COLOR
            if raw_highlight_color is None
            else raw_highlight_color,
            "karaoke-highlight-color",
        )
        if karaoke
        else None
    )

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

    parsed_length_values: dict[str, RelativeLength] = {
        key: value
        for key, value in parsed_relative_values.items()
        if isinstance(value, RelativeLength)
    }
    parsed_line_height = parsed_relative_values.get("line_height", DEFAULT_LINE_HEIGHT)

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
            font_size=parsed_length_values.get(
                "font_size", parse_relative_length(DEFAULT_FONT_SIZE)
            ),
            letter_spacing=parsed_length_values.get(
                "letter_spacing", parse_relative_length(DEFAULT_LETTER_SPACING)
            ),
            text_color=_validate_color(
                appearance_overrides.get("text_color", DEFAULT_TEXT_COLOR),
                "text-color",
            ),
            font_weight=font_weight,
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
            backdrop_size=parsed_length_values.get(
                "outline_weight", parse_relative_length(DEFAULT_BACKDROP_SIZE)
            ),
            shadow_size=parsed_length_values.get(
                "shadow_weight", parse_relative_length(DEFAULT_SHADOW_SIZE)
            ),
            fonts_dir=_coerce_fonts_dir(appearance_overrides.get("fonts_dir")),
            font_weight_input=font_weight_input,
            font_weight_input_form=font_weight_input_form,
            line_height=parsed_line_height,
            opacity=opacity,
        ),
        layout=SubtitleLayout(
            position=resolved_position or DEFAULT_POSITION,
            margin_left=parsed_length_values.get("margin_left", 0),
            margin_right=parsed_length_values.get("margin_right", 0),
            margin_top=parsed_length_values.get("margin_top", 0),
            margin_bottom=parsed_length_values.get("margin_bottom", 0),
            placement_mode=(
                SubtitlePlacementMode.EXPLICIT
                if has_custom_coordinates
                else SubtitlePlacementMode.NATIVE_STYLE
            ),
            position_x=parsed_length_values.get("position_x"),
            position_y=parsed_length_values.get("position_y"),
            anchor=resolved_anchor if has_custom_coordinates else None,
            max_width=parsed_length_values.get("max_width"),
            max_height=parsed_length_values.get("max_height"),
        ),
        layout_preset=resolved_preset or SubtitleLayoutPreset.AUTO,
        layout_overrides=frozenset(layout_overrides),
        effects=SubtitleEffects(
            karaoke_mode=karaoke_mode,
            highlight_color=highlight_color,
        ),
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
) -> dict[str, RelativeLength | str]:
    if not values:
        return {}
    unknown = set(values).difference(_RELATIVE_FIELDS)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValidationError(f"Unknown relative value(s): {names}")

    parsed: dict[str, RelativeLength | str] = {}
    for key, value in values.items():
        if key == "line_height" and isinstance(value, str):
            parsed[key] = parse_line_height(value)
            continue
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
    if not isinstance(config.appearance.font_weight, FontWeight):
        raise ValidationError("font-weight must use the typed FontWeight contract")
    if (
        not isinstance(config.appearance.font_weight_input, str)
        or not config.appearance.font_weight_input.strip()
    ):
        raise ValidationError("font-weight input must not be empty")
    if not isinstance(config.appearance.font_weight_input_form, FontWeightInputForm):
        raise ValidationError(
            "font-weight input form must use the typed FontWeightInputForm contract"
        )
    input_form = config.appearance.font_weight_input_form
    if input_form is FontWeightInputForm.BOLD_SHORTHAND:
        expected_input = config.appearance.font_weight.canonical_name
        if (
            config.appearance.font_weight not in {FontWeight.REGULAR, FontWeight.BOLD}
            or config.appearance.font_weight_input != expected_input
        ):
            raise ValidationError("bold shorthand must resolve to regular or bold")
    elif input_form is FontWeightInputForm.DEFAULT:
        if (
            config.appearance.font_weight is not DEFAULT_FONT_WEIGHT
            or config.appearance.font_weight_input != DEFAULT_FONT_WEIGHT.canonical_name
        ):
            raise ValidationError("default font-weight metadata is inconsistent")
    else:
        parsed_weight, _, parsed_form = _parse_font_weight_request(
            config.appearance.font_weight_input
        )
        if (
            parsed_weight is not config.appearance.font_weight
            or parsed_form is not input_form
        ):
            raise ValidationError("font-weight metadata is inconsistent")
    _validate_boolean(config.appearance.italic, "italic")
    _validate_backdrop(config.appearance.backdrop)
    _validate_color(config.appearance.backdrop_color, "backdrop-color")
    _validate_opacity(config.appearance.opacity)
    _coerce_fonts_dir(config.appearance.fonts_dir)
    _validate_line_height_value(config.appearance.line_height, "line-height")
    if config.appearance.line_height_requested is not None:
        _validate_line_height_value(
            config.appearance.line_height_requested, "line-height-requested"
        )
    _validate_effects(config.effects)
    relative_fields = {
        "font_size": config.appearance.font_size,
        "letter_spacing": config.appearance.letter_spacing,
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


def _validate_line_height_value(value: object, field: str) -> None:
    """Validate a requested or resolved line-height representation."""
    if isinstance(value, str):
        try:
            parsed = parse_line_height(value)
        except ValidationError as exc:
            raise ValidationError(f"{field}: {exc}") from exc
        if parsed == "auto":
            return
        _validate_line_height_value(parsed, field)
        return
    if isinstance(value, RelativeLength):
        _validate_relative_length(value, field)
        if value.value <= 0:
            raise ValidationError(f"{field} must be greater than zero")
        return
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValidationError(
            f"{field} must be auto, a positive number, or a relative length"
        )
    number = float(value)
    if number <= 0 or number != number or number in {float("inf"), float("-inf")}:
        raise ValidationError(f"{field} must be greater than zero")


def _validate_opacity(value: object) -> SubtitleOpacity:
    """Validate the typed opacity value and its retained public token."""
    if isinstance(value, str):
        return parse_opacity(value)
    if not isinstance(value, SubtitleOpacity):
        raise ValidationError("opacity must use the typed SubtitleOpacity contract")
    if not isinstance(value.percentage, Decimal) or not value.percentage.is_finite():
        raise ValidationError("opacity must contain a finite decimal percentage")
    if value.percentage < 0 or value.percentage > 100:
        raise ValidationError("opacity must be between 0% and 100%")
    parsed = parse_opacity(value.original)
    if parsed.percentage != value.percentage:
        raise ValidationError("opacity metadata is inconsistent")
    return value


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


def _validate_effects(value: object) -> SubtitleEffects:
    if not isinstance(value, SubtitleEffects):
        raise ValidationError("subtitle effects must use the typed effects contract")
    if value.karaoke_mode is None:
        if value.highlight_color is not None:
            raise ValidationError(
                "karaoke-highlight-color requires karaoke to be enabled"
            )
        return value
    if not isinstance(value.karaoke_mode, KaraokeMode):
        raise ValidationError("karaoke-mode must use the typed KaraokeMode contract")
    _validate_color(
        value.highlight_color
        if value.highlight_color is not None
        else DEFAULT_KARAOKE_HIGHLIGHT_COLOR,
        "karaoke-highlight-color",
    )
    return value


def _validate_karaoke_mode(value: object) -> KaraokeMode:
    if isinstance(value, KaraokeMode):
        return value
    if isinstance(value, str):
        try:
            return KaraokeMode(value)
        except ValueError:
            pass
    raise ValidationError(
        "karaoke-mode must be one of: " + ", ".join(KARAOKE_MODE_CHOICES)
    )


def _coerce_fonts_dir(value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, (str, Path)):
        raise ValidationError("fonts-dir must be a directory path")
    path = Path(value).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_dir():
        raise ValidationError(f"Fonts directory not found at '{value}'")
    return path
