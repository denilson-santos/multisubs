"""Static CLI and ASS styling configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from numbers import Real
from pathlib import Path
from types import MappingProxyType

from .errors import ValidationError
from .models import (
    CueAnimationType,
    FontWeight,
    FontWeightInputForm,
    RelativeLength,
    SubtitleAnimation,
    SubtitleAnimationPhase,
    SubtitleBackdrop,
    SubtitleBackdropStyle,
    SubtitleConfig,
    SubtitleCueAnimation,
    SubtitleElementAnimation,
    SubtitleLayout,
    SubtitleOpacity,
    SubtitlePlacementMode,
    SubtitlePosition,
    SubtitleShadow,
    SubtitleStyle,
    SubtitleTypography,
    SubtitleWordAnimation,
    SubtitleWordBackdropStyle,
    SubtitleWordElementAnimation,
    TextCase,
    WordAnimationMode,
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
BACKDROP_CHOICES = tuple(backdrop.value for backdrop in SubtitleBackdrop)
CUE_ENTRANCE_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.FADE,
        CueAnimationType.SLIDE_UP,
        CueAnimationType.SLIDE_DOWN,
        CueAnimationType.SLIDE_LEFT,
        CueAnimationType.SLIDE_RIGHT,
        CueAnimationType.POP,
        CueAnimationType.ZOOM,
    }
)
CUE_EMPHASIS_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.PULSE,
        CueAnimationType.BOUNCE,
        CueAnimationType.FLOAT,
        CueAnimationType.SHAKE,
        CueAnimationType.FLASH,
        CueAnimationType.BREATHE,
    }
)
CUE_EXIT_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.FADE,
        CueAnimationType.SLIDE_UP,
        CueAnimationType.SLIDE_DOWN,
        CueAnimationType.SLIDE_LEFT,
        CueAnimationType.SLIDE_RIGHT,
        CueAnimationType.ZOOM,
    }
)
WORD_ENTRANCE_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.FADE,
        CueAnimationType.SLIDE_UP,
        CueAnimationType.SLIDE_DOWN,
        CueAnimationType.POP,
        CueAnimationType.ZOOM,
    }
)
WORD_TEXT_EMPHASIS_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.HIGHLIGHT,
        CueAnimationType.PULSE,
        CueAnimationType.BOUNCE,
        CueAnimationType.FLOAT,
        CueAnimationType.BREATHE,
    }
)
WORD_BACKDROP_EMPHASIS_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.PULSE,
        CueAnimationType.BOUNCE,
        CueAnimationType.FLOAT,
        CueAnimationType.BREATHE,
    }
)
# Kept as the union for callers that display a generic word-emphasis list.
WORD_EMPHASIS_ANIMATION_CHOICES = WORD_TEXT_EMPHASIS_ANIMATION_CHOICES
WORD_EXIT_ANIMATION_CHOICES = tuple(
    animation.value
    for animation in CueAnimationType
    if animation
    in {
        CueAnimationType.NONE,
        CueAnimationType.FADE,
        CueAnimationType.SLIDE_UP,
        CueAnimationType.SLIDE_DOWN,
        CueAnimationType.ZOOM,
    }
)
WORD_ANIMATION_MODE_CHOICES = tuple(mode.value for mode in WordAnimationMode)
FONT_WEIGHT_NAMES = tuple(weight.canonical_name for weight in FontWeight)
FONT_WEIGHT_RANKS = tuple(weight.rank for weight in FontWeight)
TEXT_CASE_CHOICES = tuple(text_case.value for text_case in TextCase)

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
_DURATION_PATTERN = re.compile(
    r"^(?P<number>(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,3})?)(?P<unit>ms|s)$"
)
_RELATIVE_FIELDS = {
    "font_size",
    "letter_spacing",
    "line_height",
    "outline_weight",
    "word_backdrop_size",
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
DEFAULT_FONT = "Roboto"
DEFAULT_FONT_SIZE = "4%"
DEFAULT_LETTER_SPACING = "0px"
DEFAULT_LINE_HEIGHT = "auto"
DEFAULT_OPACITY = "100%"
DEFAULT_TEXT_CASE = TextCase.ORIGINAL
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_FONT_WEIGHT = FontWeight.REGULAR
DEFAULT_ITALIC = False
DEFAULT_BACKDROP = SubtitleBackdrop.BOX
DEFAULT_BACKDROP_COLOR = "#00000099"
DEFAULT_BACKDROP_SIZE = "25%"
DEFAULT_WORD_BACKDROP = SubtitleBackdrop.NONE
DEFAULT_WORD_BACKDROP_COLOR = "#111827E6"
DEFAULT_WORD_BACKDROP_SIZE = "25%"
DEFAULT_SHADOW_SIZE = "0px"
DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR = "#FFD54F"
DEFAULT_WORD_ANIMATION_MODE = WordAnimationMode.ACTIVE_WORD
DEFAULT_MARGIN_LEFT = "18%"
DEFAULT_MARGIN_RIGHT = "18%"
DEFAULT_MARGIN_TOP = "0%"
DEFAULT_MARGIN_BOTTOM = "3%"
DEFAULT_MAX_WIDTH = "100%"
DEFAULT_MAX_HEIGHT = "12%"

_ENTRANCE_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.FADE: 160,
        CueAnimationType.SLIDE_UP: 220,
        CueAnimationType.SLIDE_DOWN: 220,
        CueAnimationType.SLIDE_LEFT: 220,
        CueAnimationType.SLIDE_RIGHT: 220,
        CueAnimationType.POP: 220,
        CueAnimationType.ZOOM: 220,
    }
)
_CUE_EMPHASIS_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.PULSE: 600,
        CueAnimationType.BOUNCE: 600,
        CueAnimationType.FLOAT: 900,
        CueAnimationType.SHAKE: 400,
        CueAnimationType.FLASH: 500,
        CueAnimationType.BREATHE: 1200,
    }
)
_EXIT_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.FADE: 120,
        CueAnimationType.SLIDE_UP: 180,
        CueAnimationType.SLIDE_DOWN: 180,
        CueAnimationType.SLIDE_LEFT: 180,
        CueAnimationType.SLIDE_RIGHT: 180,
        CueAnimationType.ZOOM: 160,
    }
)
_WORD_ENTRANCE_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.FADE: 100,
        CueAnimationType.SLIDE_UP: 140,
        CueAnimationType.SLIDE_DOWN: 140,
        CueAnimationType.POP: 160,
        CueAnimationType.ZOOM: 140,
    }
)
_WORD_TEXT_EMPHASIS_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.HIGHLIGHT: 0,
        CueAnimationType.PULSE: 240,
        CueAnimationType.BOUNCE: 240,
        CueAnimationType.FLOAT: 600,
        CueAnimationType.BREATHE: 600,
    }
)
_WORD_BACKDROP_EMPHASIS_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.PULSE: 240,
        CueAnimationType.BOUNCE: 240,
        CueAnimationType.FLOAT: 600,
        CueAnimationType.BREATHE: 600,
    }
)
_WORD_EXIT_ANIMATION_DURATIONS_MS = MappingProxyType(
    {
        CueAnimationType.NONE: 0,
        CueAnimationType.FADE: 100,
        CueAnimationType.SLIDE_UP: 120,
        CueAnimationType.SLIDE_DOWN: 120,
        CueAnimationType.ZOOM: 100,
    }
)


@dataclass(frozen=True)
class _AnimationTrackSpec:
    default: SubtitleElementAnimation
    entrance_choices: tuple[str, ...]
    emphasis_choices: tuple[str, ...]
    exit_choices: tuple[str, ...]
    entrance_durations: Mapping[CueAnimationType, int]
    emphasis_durations: Mapping[CueAnimationType, int]
    exit_durations: Mapping[CueAnimationType, int]


@dataclass(frozen=True)
class _ResolvedLayoutOptions:
    """Parsed layout inputs shared by semantic configuration construction."""

    lengths: dict[str, RelativeLength]
    line_height: float | int | RelativeLength | str
    position: SubtitlePosition
    anchor: SubtitlePosition | None
    has_custom_coordinates: bool


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


def parse_animation_duration(raw_value: object) -> int:
    """Parse a unit-bearing animation duration into whole milliseconds."""
    if not isinstance(raw_value, str):
        raise ValidationError("animation duration must end in ms or s")
    match = _DURATION_PATTERN.fullmatch(raw_value.strip().casefold())
    if match is None:
        raise ValidationError(
            "animation duration must use ms or s (for example 150ms or 0.15s)"
        )
    try:
        number = Decimal(match.group("number"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("animation duration must be finite") from exc
    milliseconds = number * (1000 if match.group("unit") == "s" else 1)
    if not milliseconds.is_finite() or milliseconds != milliseconds.to_integral_value():
        raise ValidationError("animation duration must resolve to whole milliseconds")
    result = int(milliseconds)
    if result < 10 or result > 5000:
        raise ValidationError("animation duration must be from 10ms through 5000ms")
    return result


def parse_text_case(raw_value: object) -> TextCase:
    """Parse one canonical, case-insensitive display casing mode."""
    if isinstance(raw_value, TextCase):
        return raw_value
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValidationError("text-case must be original, uppercase, or lowercase")
    try:
        return TextCase(raw_value.strip().casefold())
    except ValueError as exc:
        raise ValidationError(
            "text-case must be original, uppercase, or lowercase"
        ) from exc


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


def validate_subtitle_config(
    value: SubtitleConfig | None,
    *,
    defaults: SubtitleConfig | None = None,
    appearance_values: Mapping[str, object] | None = None,
    position: SubtitlePosition | str | None = None,
    relative_values: Mapping[str, RelativeLength | str] | None = None,
    animation_values: Mapping[str, object] | None = None,
    position_x: RelativeLength | str | None = None,
    position_y: RelativeLength | str | None = None,
    anchor: SubtitlePosition | str | None = None,
) -> SubtitleConfig:
    """Return a complete, validated semantic subtitle configuration."""
    resolved_position = parse_position(position) if position is not None else None
    resolved_anchor = parse_position(anchor) if anchor is not None else None
    if isinstance(value, SubtitleConfig):
        return _validate_existing_subtitle_config(
            value,
            defaults=defaults,
            appearance_values=appearance_values,
            relative_values=relative_values,
            animation_values=animation_values,
            position_x=position_x,
            position_y=position_y,
            position=resolved_position,
            anchor=resolved_anchor,
        )
    if value is not None:
        raise ValidationError(
            "raw ASS style mappings are no longer supported; use SubtitleConfig"
        )
    if defaults is not None:
        if not isinstance(defaults, SubtitleConfig):
            raise ValidationError("subtitle defaults must use SubtitleConfig")
        _validate_typed_subtitle_config(defaults)

    default_style = defaults.style if defaults is not None else None
    default_typography = default_style.typography if default_style is not None else None
    default_layout = defaults.layout if defaults is not None else None
    default_cue_animation = (
        defaults.animation.cue if defaults is not None else SubtitleCueAnimation()
    )
    default_word_animation = (
        defaults.animation.word if defaults is not None else SubtitleWordAnimation()
    )

    appearance_overrides = dict(appearance_values or {})
    animation_overrides = dict(animation_values or {})
    known_appearance_fields = {
        "font",
        "text_color",
        "font_weight",
        "bold",
        "italic",
        "backdrop",
        "backdrop_color",
        "word_backdrop",
        "word_backdrop_color",
        "opacity",
        "text_case",
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

    font_weight, font_weight_input, font_weight_input_form = _resolve_font_weight(
        appearance_overrides, default_typography
    )

    opacity = _validate_opacity(
        appearance_overrides.get(
            "opacity",
            default_style.opacity if default_style is not None else DEFAULT_OPACITY,
        )
    )

    animation, highlight_color = _resolve_animation_config(
        default_cue_animation,
        default_word_animation,
        animation_overrides,
        default_typography,
    )

    layout_options = _resolve_layout_options(
        relative_values,
        position_x=position_x,
        position_y=position_y,
        position=resolved_position,
        anchor=resolved_anchor,
        default_typography=default_typography,
        default_layout=default_layout,
    )
    style = _build_subtitle_style(
        appearance_overrides,
        default_style,
        layout_options.lengths,
        font_weight=font_weight,
        font_weight_input=font_weight_input,
        font_weight_input_form=font_weight_input_form,
        line_height=layout_options.line_height,
        highlight_color=highlight_color,
        opacity=opacity,
    )
    config = SubtitleConfig(
        style=style,
        layout=_build_subtitle_layout(default_layout, layout_options),
        animation=animation,
    )
    _validate_typed_subtitle_config(config)
    return config


def apply_subtitle_feature_disables(
    config: SubtitleConfig,
    *,
    disable_cue_animations: bool = False,
    disable_word_animations: bool = False,
) -> SubtitleConfig:
    """Remove all animation-dependent presentation features by scope.

    Cue suppression clears its text/backdrop tracks while preserving the static
    cue backdrop. Word suppression additionally clears timed word decoration and
    highlight color, because those fields depend on aligned-word animation
    support.
    """
    validated = validate_subtitle_config(config)
    if not any(
        (
            disable_cue_animations,
            disable_word_animations,
        )
    ):
        return validated

    cue = validated.animation.cue
    word = validated.animation.word
    style = validated.style
    typography = style.typography

    if disable_cue_animations:
        cue = replace(
            cue,
            text=SubtitleElementAnimation(),
            backdrop=SubtitleElementAnimation(),
        )

    if disable_word_animations:
        word = replace(
            word,
            text=replace(
                word.text,
                entrance=SubtitleAnimationPhase(),
                emphasis=SubtitleAnimationPhase(),
                exit=SubtitleAnimationPhase(),
            ),
            backdrop=replace(
                word.backdrop,
                entrance=SubtitleAnimationPhase(),
                emphasis=SubtitleAnimationPhase(),
                exit=SubtitleAnimationPhase(),
            ),
        )
        typography = replace(typography, highlight_color=None)
        style = replace(
            style,
            word_backdrop=replace(
                style.word_backdrop,
                kind=SubtitleBackdrop.NONE,
            ),
        )

    updated = replace(
        validated,
        style=replace(style, typography=typography),
        animation=replace(validated.animation, cue=cue, word=word),
    )
    return validate_subtitle_config(updated)


def _resolve_layout_options(
    values: Mapping[str, RelativeLength | str] | None,
    *,
    position_x: RelativeLength | str | None,
    position_y: RelativeLength | str | None,
    position: SubtitlePosition | None,
    anchor: SubtitlePosition | None,
    default_typography: SubtitleTypography | None,
    default_layout: SubtitleLayout | None,
) -> _ResolvedLayoutOptions:
    """Parse relative layout overrides and validate placement combinations."""
    parsed_values = _validate_relative_values(values)
    for field, raw_value in (("position_x", position_x), ("position_y", position_y)):
        if raw_value is None:
            continue
        if field in parsed_values:
            raise ValidationError(
                f"{field.replace('_', '-')} was provided more than once"
            )
        if isinstance(raw_value, str):
            raw_value = parse_relative_length(raw_value)
        _validate_relative_length(raw_value, field)
        parsed_values[field] = raw_value

    has_position_x = "position_x" in parsed_values
    has_position_y = "position_y" in parsed_values
    has_custom_coordinates = has_position_x or has_position_y
    if has_position_x != has_position_y:
        raise ValidationError("position-x and position-y must be supplied together")
    if has_custom_coordinates and position is not None:
        raise ValidationError(
            "position cannot be combined with custom position-x and position-y"
        )
    if anchor is not None and not has_custom_coordinates:
        raise ValidationError("anchor requires both position-x and position-y")
    if has_custom_coordinates and anchor is None:
        raise ValidationError("custom coordinates require an explicit anchor")
    if has_custom_coordinates and "max_width" not in parsed_values:
        raise ValidationError("custom coordinates require an explicit max-width")
    if has_custom_coordinates and "max_height" not in parsed_values:
        raise ValidationError("custom coordinates require an explicit max-height")

    resolved_position = position or (
        default_layout.position if default_layout is not None else DEFAULT_POSITION
    )
    _validate_layout_option_effects(
        parsed_values,
        position=resolved_position,
        has_custom_coordinates=has_custom_coordinates,
    )
    return _ResolvedLayoutOptions(
        lengths={
            key: value
            for key, value in parsed_values.items()
            if isinstance(value, RelativeLength)
        },
        line_height=parsed_values.get(
            "line_height",
            default_typography.line_height
            if default_typography is not None
            else DEFAULT_LINE_HEIGHT,
        ),
        position=resolved_position,
        anchor=anchor,
        has_custom_coordinates=has_custom_coordinates,
    )


def _build_subtitle_style(
    appearance: Mapping[str, object],
    defaults: SubtitleStyle | None,
    lengths: Mapping[str, RelativeLength],
    *,
    font_weight: FontWeight,
    font_weight_input: str,
    font_weight_input_form: FontWeightInputForm,
    line_height: float | int | RelativeLength | str,
    highlight_color: str | None,
    opacity: SubtitleOpacity,
) -> SubtitleStyle:
    """Build and validate semantic appearance fields from explicit inputs."""
    typography_default = defaults.typography if defaults is not None else None
    backdrop_default = defaults.backdrop if defaults is not None else None
    word_backdrop_default = defaults.word_backdrop if defaults is not None else None
    shadow_default = defaults.shadow if defaults is not None else None
    return SubtitleStyle(
        typography=SubtitleTypography(
            font=_validate_font(
                appearance.get(
                    "font",
                    typography_default.font
                    if typography_default is not None
                    else DEFAULT_FONT,
                )
            ),
            font_size=lengths.get(
                "font_size",
                typography_default.font_size
                if typography_default is not None
                else parse_relative_length(DEFAULT_FONT_SIZE),
            ),
            letter_spacing=lengths.get(
                "letter_spacing",
                typography_default.letter_spacing
                if typography_default is not None
                else parse_relative_length(DEFAULT_LETTER_SPACING),
            ),
            color=_validate_color(
                appearance.get(
                    "text_color",
                    typography_default.color
                    if typography_default is not None
                    else DEFAULT_TEXT_COLOR,
                ),
                "text-color",
            ),
            font_weight=font_weight,
            italic=_validate_boolean(
                appearance.get(
                    "italic",
                    typography_default.italic
                    if typography_default is not None
                    else DEFAULT_ITALIC,
                ),
                "italic",
            ),
            fonts_dir=_coerce_fonts_dir(
                appearance.get(
                    "fonts_dir",
                    typography_default.fonts_dir
                    if typography_default is not None
                    else None,
                )
            ),
            font_weight_input=font_weight_input,
            font_weight_input_form=font_weight_input_form,
            line_height=line_height,
            text_case=parse_text_case(
                appearance.get(
                    "text_case",
                    typography_default.text_case
                    if typography_default is not None
                    else DEFAULT_TEXT_CASE,
                )
            ),
            highlight_color=highlight_color,
        ),
        backdrop=SubtitleBackdropStyle(
            kind=_validate_backdrop(
                appearance.get(
                    "backdrop",
                    backdrop_default.kind
                    if backdrop_default is not None
                    else DEFAULT_BACKDROP,
                )
            ),
            color=_validate_color(
                appearance.get(
                    "backdrop_color",
                    backdrop_default.color
                    if backdrop_default is not None
                    else DEFAULT_BACKDROP_COLOR,
                ),
                "backdrop-color",
            ),
            size=lengths.get(
                "outline_weight",
                backdrop_default.size
                if backdrop_default is not None
                else parse_relative_length(DEFAULT_BACKDROP_SIZE),
            ),
        ),
        word_backdrop=SubtitleWordBackdropStyle(
            kind=_validate_backdrop(
                appearance.get(
                    "word_backdrop",
                    word_backdrop_default.kind
                    if word_backdrop_default is not None
                    else DEFAULT_WORD_BACKDROP,
                )
            ),
            color=_validate_color(
                appearance.get(
                    "word_backdrop_color",
                    word_backdrop_default.color
                    if word_backdrop_default is not None
                    else DEFAULT_WORD_BACKDROP_COLOR,
                ),
                "word-backdrop-color",
            ),
            size=lengths.get(
                "word_backdrop_size",
                word_backdrop_default.size
                if word_backdrop_default is not None
                else parse_relative_length(DEFAULT_WORD_BACKDROP_SIZE),
            ),
        ),
        shadow=SubtitleShadow(
            size=lengths.get(
                "shadow_weight",
                shadow_default.size
                if shadow_default is not None
                else parse_relative_length(DEFAULT_SHADOW_SIZE),
            )
        ),
        opacity=opacity,
    )


def _build_subtitle_layout(
    defaults: SubtitleLayout | None,
    options: _ResolvedLayoutOptions,
) -> SubtitleLayout:
    """Build the complete semantic layout from one validated option set."""
    lengths = options.lengths
    return SubtitleLayout(
        position=options.position,
        margin_left=lengths.get(
            "margin_left",
            defaults.margin_left
            if defaults is not None
            else parse_relative_length(DEFAULT_MARGIN_LEFT),
        ),
        margin_right=lengths.get(
            "margin_right",
            defaults.margin_right
            if defaults is not None
            else parse_relative_length(DEFAULT_MARGIN_RIGHT),
        ),
        margin_top=lengths.get(
            "margin_top",
            defaults.margin_top
            if defaults is not None
            else parse_relative_length(DEFAULT_MARGIN_TOP),
        ),
        margin_bottom=lengths.get(
            "margin_bottom",
            defaults.margin_bottom
            if defaults is not None
            else parse_relative_length(DEFAULT_MARGIN_BOTTOM),
        ),
        placement_mode=(
            SubtitlePlacementMode.EXPLICIT
            if options.has_custom_coordinates
            else SubtitlePlacementMode.NATIVE_STYLE
        ),
        position_x=lengths.get("position_x"),
        position_y=lengths.get("position_y"),
        anchor=options.anchor if options.has_custom_coordinates else None,
        max_width=lengths.get(
            "max_width",
            defaults.max_width
            if defaults is not None
            else parse_relative_length(DEFAULT_MAX_WIDTH),
        ),
        max_height=lengths.get(
            "max_height",
            defaults.max_height
            if defaults is not None
            else parse_relative_length(DEFAULT_MAX_HEIGHT),
        ),
    )


def _resolve_font_weight(
    appearance: Mapping[str, object],
    default: SubtitleTypography | None,
) -> tuple[FontWeight, str, FontWeightInputForm]:
    """Resolve a canonical weight and its public-input diagnostics."""
    if "font_weight" in appearance:
        return _parse_font_weight_request(appearance["font_weight"])
    if "bold" in appearance:
        bold = _validate_boolean(appearance["bold"], "bold")
        weight = FontWeight.BOLD if bold else FontWeight.REGULAR
        return weight, weight.canonical_name, FontWeightInputForm.BOLD_SHORTHAND
    if default is not None:
        return (
            default.font_weight,
            default.font_weight_input,
            default.font_weight_input_form,
        )
    return (
        DEFAULT_FONT_WEIGHT,
        DEFAULT_FONT_WEIGHT.canonical_name,
        FontWeightInputForm.DEFAULT,
    )


def _resolve_animation_config(
    default_cue: SubtitleCueAnimation,
    default_word: SubtitleWordAnimation,
    overrides: Mapping[str, object],
    default_typography: SubtitleTypography | None,
) -> tuple[SubtitleAnimation, str | None]:
    """Resolve four independent animation tracks and their highlight color."""
    track_specs = _animation_track_specs(default_cue, default_word)
    known_fields = {"word_text_mode", "word_backdrop_mode", "word_text_highlight_color"}
    for prefix in track_specs:
        for phase in ("entrance", "emphasis", "exit"):
            known_fields.update((f"{prefix}_{phase}", f"{prefix}_{phase}_duration"))
    unknown_fields = set(overrides).difference(known_fields)
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ValidationError(f"Unknown animation value(s): {names}")

    tracks = {
        prefix: _resolve_animation_track(
            prefix,
            spec.default,
            overrides,
            entrance_choices=spec.entrance_choices,
            emphasis_choices=spec.emphasis_choices,
            exit_choices=spec.exit_choices,
            entrance_durations=spec.entrance_durations,
            emphasis_durations=spec.emphasis_durations,
            exit_durations=spec.exit_durations,
        )
        for prefix, spec in track_specs.items()
    }
    word_text_mode = _validate_word_animation_mode(
        overrides.get("word_text_mode", default_word.text.mode)
    )
    word_backdrop_mode = _validate_word_animation_mode(
        overrides.get("word_backdrop_mode", default_word.backdrop.mode)
    )
    explicit_highlight_color = overrides.get("word_text_highlight_color")
    word_text_highlighted = (
        tracks["word_text"].emphasis.type is CueAnimationType.HIGHLIGHT
    )
    if not word_text_highlighted and explicit_highlight_color is not None:
        raise ValidationError(
            "animation-word-text-highlight-color requires "
            "--animation-word-text-emphasis highlight"
        )
    default_highlight_color = (
        default_typography.highlight_color if default_typography is not None else None
    )
    raw_highlight_color = (
        explicit_highlight_color
        if explicit_highlight_color is not None
        else default_highlight_color or DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR
    )
    highlight_color = (
        _validate_color(raw_highlight_color, "animation-word-text-highlight-color")
        if word_text_highlighted
        else None
    )
    return (
        SubtitleAnimation(
            cue=SubtitleCueAnimation(
                text=tracks["cue_text"],
                backdrop=tracks["cue_backdrop"],
            ),
            word=SubtitleWordAnimation(
                text=SubtitleWordElementAnimation(
                    entrance=tracks["word_text"].entrance,
                    emphasis=tracks["word_text"].emphasis,
                    exit=tracks["word_text"].exit,
                    mode=word_text_mode,
                ),
                backdrop=SubtitleWordElementAnimation(
                    entrance=tracks["word_backdrop"].entrance,
                    emphasis=tracks["word_backdrop"].emphasis,
                    exit=tracks["word_backdrop"].exit,
                    mode=word_backdrop_mode,
                ),
            ),
        ),
        highlight_color,
    )


def _animation_track_specs(
    default_cue: SubtitleCueAnimation,
    default_word: SubtitleWordAnimation,
) -> dict[str, _AnimationTrackSpec]:
    """Describe valid phase choices and default durations for each track."""
    cue_spec = (
        CUE_ENTRANCE_ANIMATION_CHOICES,
        CUE_EMPHASIS_ANIMATION_CHOICES,
        CUE_EXIT_ANIMATION_CHOICES,
        _ENTRANCE_ANIMATION_DURATIONS_MS,
        _CUE_EMPHASIS_ANIMATION_DURATIONS_MS,
        _EXIT_ANIMATION_DURATIONS_MS,
    )
    word_entrance = WORD_ENTRANCE_ANIMATION_CHOICES
    word_exit = WORD_EXIT_ANIMATION_CHOICES
    return {
        "cue_text": _AnimationTrackSpec(default_cue.text, *cue_spec),
        "cue_backdrop": _AnimationTrackSpec(default_cue.backdrop, *cue_spec),
        "word_text": _AnimationTrackSpec(
            default_word.text,
            word_entrance,
            WORD_TEXT_EMPHASIS_ANIMATION_CHOICES,
            word_exit,
            _WORD_ENTRANCE_ANIMATION_DURATIONS_MS,
            _WORD_TEXT_EMPHASIS_ANIMATION_DURATIONS_MS,
            _WORD_EXIT_ANIMATION_DURATIONS_MS,
        ),
        "word_backdrop": _AnimationTrackSpec(
            default_word.backdrop,
            word_entrance,
            WORD_BACKDROP_EMPHASIS_ANIMATION_CHOICES,
            word_exit,
            _WORD_ENTRANCE_ANIMATION_DURATIONS_MS,
            _WORD_BACKDROP_EMPHASIS_ANIMATION_DURATIONS_MS,
            _WORD_EXIT_ANIMATION_DURATIONS_MS,
        ),
    }


def _validate_existing_subtitle_config(
    value: SubtitleConfig,
    *,
    defaults: SubtitleConfig | None,
    appearance_values: Mapping[str, object] | None,
    relative_values: Mapping[str, RelativeLength | str] | None,
    animation_values: Mapping[str, object] | None,
    position_x: RelativeLength | str | None,
    position_y: RelativeLength | str | None,
    position: SubtitlePosition | None,
    anchor: SubtitlePosition | None,
) -> SubtitleConfig:
    """Revalidate typed configs and reject attempts to layer extra overrides."""
    if (
        defaults is not None
        or appearance_values
        or relative_values
        or animation_values
        or position_x is not None
        or position_y is not None
    ):
        raise ValidationError(
            "values cannot override an existing subtitle configuration"
        )
    if position is not None and position != value.layout.position:
        raise ValidationError(
            "position cannot override the position already stored in the "
            "subtitle configuration"
        )
    if anchor is not None and anchor != value.layout.anchor:
        raise ValidationError(
            "anchor cannot override the anchor already stored in the subtitle "
            "configuration"
        )

    _validate_typed_subtitle_config(value)
    if not value.animation.word.uses_timed_highlight:
        return value
    highlight_color = _validate_color(
        value.style.typography.highlight_color
        or DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR,
        "animation-word-text-highlight-color",
    )
    if highlight_color == value.style.typography.highlight_color:
        return value
    return replace(
        value,
        style=replace(
            value.style,
            typography=replace(
                value.style.typography,
                highlight_color=highlight_color,
            ),
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


def _validate_layout_option_effects(
    values: Mapping[str, object],
    *,
    position: SubtitlePosition,
    has_custom_coordinates: bool,
) -> None:
    """Reject explicit layout values that the selected placement cannot use."""
    margin_fields = tuple(
        field
        for field in (
            "margin_left",
            "margin_right",
            "margin_top",
            "margin_bottom",
        )
        if field in values
    )
    if has_custom_coordinates:
        if margin_fields:
            options = _format_cli_options(margin_fields)
            raise ValidationError(
                f"{options} cannot be combined with custom coordinates because "
                "explicit placement ignores margins"
            )
        return

    position_name = position.value
    if position_name.startswith("top-"):
        inactive_fields = ("margin_bottom",)
        active_option = "--margin-top"
        position_group = "top"
    elif position_name.startswith("bottom-"):
        inactive_fields = ("margin_top",)
        active_option = "--margin-bottom"
        position_group = "bottom"
    else:
        inactive_fields = ("margin_top", "margin_bottom")
        active_option = None
        position_group = "middle"

    provided_inactive_fields = tuple(
        field for field in inactive_fields if field in values
    )
    if not provided_inactive_fields:
        return

    options = _format_cli_options(provided_inactive_fields)
    verb = "has" if len(provided_inactive_fields) == 1 else "have"
    if active_option is None:
        raise ValidationError(
            f"{options} {verb} no effect with --position {position_name}; use custom "
            f"coordinates to offset {position_group} positions"
        )
    raise ValidationError(
        f"{options} {verb} no effect with --position {position_name}; use "
        f"{active_option} for {position_group} positions"
    )


def _format_cli_options(fields: tuple[str, ...]) -> str:
    options = tuple(f"--{field.replace('_', '-')}" for field in fields)
    if len(options) == 1:
        return options[0]
    if len(options) == 2:
        return " and ".join(options)
    return ", ".join(options[:-1]) + f", and {options[-1]}"


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
    _validate_typed_layout(config.layout)
    _validate_typed_style(config.style, config.animation)
    _validate_typed_dimensions(config)


def _validate_typed_layout(layout: SubtitleLayout) -> None:
    """Validate the mode, anchor, and coordinate relationships."""
    if not isinstance(layout.position, SubtitlePosition):
        raise ValidationError("layout position must use a supported position value")
    if not isinstance(layout.placement_mode, SubtitlePlacementMode):
        raise ValidationError("layout placement mode must be native-style or explicit")
    if layout.anchor is not None and not isinstance(layout.anchor, SubtitlePosition):
        raise ValidationError("layout anchor must use a supported position value")
    has_position_x = layout.position_x is not None
    has_position_y = layout.position_y is not None
    if has_position_x != has_position_y:
        raise ValidationError("position-x and position-y must be supplied together")
    if layout.anchor is not None and not has_position_x:
        raise ValidationError("anchor requires both position-x and position-y")
    if has_position_x and layout.anchor is None:
        raise ValidationError("custom coordinates require an anchor")
    is_explicit = layout.placement_mode is SubtitlePlacementMode.EXPLICIT
    if is_explicit != has_position_x:
        raise ValidationError(
            "explicit placement requires position-x, position-y, and anchor"
        )
    if is_explicit and layout.max_width is None:
        raise ValidationError("explicit placement requires max-width")
    if is_explicit and layout.max_height is None:
        raise ValidationError("explicit placement requires max-height")


def _validate_typed_style(
    style: SubtitleStyle,
    animation: SubtitleAnimation,
) -> None:
    """Validate appearance primitives and their semantic animation links."""
    typography = style.typography
    backdrop = style.backdrop
    word_backdrop = style.word_backdrop
    _validate_font(typography.font)
    _validate_color(typography.color, "text-color")
    if not isinstance(typography.font_weight, FontWeight):
        raise ValidationError("font-weight must use the typed FontWeight contract")
    if (
        not isinstance(typography.font_weight_input, str)
        or not typography.font_weight_input.strip()
    ):
        raise ValidationError("font-weight input must not be empty")
    if not isinstance(typography.font_weight_input_form, FontWeightInputForm):
        raise ValidationError(
            "font-weight input form must use the typed FontWeightInputForm contract"
        )
    input_form = typography.font_weight_input_form
    if input_form is FontWeightInputForm.BOLD_SHORTHAND:
        expected_input = typography.font_weight.canonical_name
        if (
            typography.font_weight not in {FontWeight.REGULAR, FontWeight.BOLD}
            or typography.font_weight_input != expected_input
        ):
            raise ValidationError("bold shorthand must resolve to regular or bold")
    elif input_form is FontWeightInputForm.DEFAULT:
        if (
            typography.font_weight is not DEFAULT_FONT_WEIGHT
            or typography.font_weight_input != DEFAULT_FONT_WEIGHT.canonical_name
        ):
            raise ValidationError("default font-weight metadata is inconsistent")
    else:
        parsed_weight, _, parsed_form = _parse_font_weight_request(
            typography.font_weight_input
        )
        if parsed_weight is not typography.font_weight or parsed_form is not input_form:
            raise ValidationError("font-weight metadata is inconsistent")
    _validate_boolean(typography.italic, "italic")
    _validate_backdrop(backdrop.kind)
    _validate_color(backdrop.color, "backdrop-color")
    if not isinstance(word_backdrop, SubtitleWordBackdropStyle):
        raise ValidationError(
            "word backdrop must use the typed SubtitleWordBackdropStyle contract"
        )
    _validate_backdrop(word_backdrop.kind)
    _validate_color(word_backdrop.color, "word-backdrop-color")
    _validate_opacity(style.opacity)
    if not isinstance(typography.text_case, TextCase):
        raise ValidationError("text-case must use the typed TextCase contract")
    _coerce_fonts_dir(typography.fonts_dir)
    _validate_line_height_value(typography.line_height, "line-height")
    if typography.line_height_requested is not None:
        _validate_line_height_value(
            typography.line_height_requested, "line-height-requested"
        )
    _validate_animation(animation, typography)


def _validate_typed_dimensions(config: SubtitleConfig) -> None:
    """Validate integer and relative-unit values across style and layout."""
    typography = config.style.typography
    backdrop = config.style.backdrop
    shadow = config.style.shadow
    word_backdrop = config.style.word_backdrop
    relative_fields = {
        "font_size": typography.font_size,
        "letter_spacing": typography.letter_spacing,
        "outline_weight": backdrop.size,
        "word_backdrop_size": word_backdrop.size,
        "shadow_weight": shadow.size,
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


def _validate_animation(
    value: object, typography: SubtitleTypography
) -> SubtitleAnimation:
    if not isinstance(value, SubtitleAnimation):
        raise ValidationError(
            "subtitle animation must use the typed animation contract"
        )
    if not isinstance(value.cue, SubtitleCueAnimation):
        raise ValidationError("cue animation must use the typed cue contract")
    if not isinstance(value.word, SubtitleWordAnimation):
        raise ValidationError("word animation must use the typed word contract")
    tracks = (
        (
            "cue text",
            value.cue.text,
            _ENTRANCE_ANIMATION_DURATIONS_MS,
            _CUE_EMPHASIS_ANIMATION_DURATIONS_MS,
            _EXIT_ANIMATION_DURATIONS_MS,
        ),
        (
            "cue backdrop",
            value.cue.backdrop,
            _ENTRANCE_ANIMATION_DURATIONS_MS,
            _CUE_EMPHASIS_ANIMATION_DURATIONS_MS,
            _EXIT_ANIMATION_DURATIONS_MS,
        ),
        (
            "word text",
            value.word.text,
            _WORD_ENTRANCE_ANIMATION_DURATIONS_MS,
            _WORD_TEXT_EMPHASIS_ANIMATION_DURATIONS_MS,
            _WORD_EXIT_ANIMATION_DURATIONS_MS,
        ),
        (
            "word backdrop",
            value.word.backdrop,
            _WORD_ENTRANCE_ANIMATION_DURATIONS_MS,
            _WORD_BACKDROP_EMPHASIS_ANIMATION_DURATIONS_MS,
            _WORD_EXIT_ANIMATION_DURATIONS_MS,
        ),
    )
    for scope, track, entrance_durations, emphasis_durations, exit_durations in tracks:
        if not isinstance(track, SubtitleElementAnimation):
            raise ValidationError(
                f"{scope} animation must use the typed element contract"
            )
        for phase_name, phase, durations in (
            ("entrance", track.entrance, entrance_durations),
            ("emphasis", track.emphasis, emphasis_durations),
            ("exit", track.exit, exit_durations),
        ):
            _validate_animation_phase(
                phase, durations=durations, scope=scope, phase=phase_name
            )
    for scope, track in (
        ("word text", value.word.text),
        ("word backdrop", value.word.backdrop),
    ):
        if not isinstance(track, SubtitleWordElementAnimation):
            raise ValidationError(
                f"{scope} animation must use the typed word element contract"
            )
        if not isinstance(track.mode, WordAnimationMode):
            raise ValidationError(
                f"{scope} mode must use the typed WordAnimationMode contract"
            )
    if value.word.text.emphasis.type is CueAnimationType.HIGHLIGHT:
        _validate_color(
            typography.highlight_color or DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR,
            "animation-word-text-highlight-color",
        )
    elif typography.highlight_color is not None:
        raise ValidationError(
            "animation-word-text-highlight-color requires word text highlight emphasis"
        )
    return value


def _resolve_animation_track(
    prefix: str,
    default: SubtitleElementAnimation,
    overrides: Mapping[str, object],
    *,
    entrance_choices: tuple[str, ...],
    emphasis_choices: tuple[str, ...],
    exit_choices: tuple[str, ...],
    entrance_durations: Mapping[CueAnimationType, int],
    emphasis_durations: Mapping[CueAnimationType, int],
    exit_durations: Mapping[CueAnimationType, int],
) -> SubtitleElementAnimation:
    phases: dict[str, SubtitleAnimationPhase] = {}
    for phase_name, choices, durations in (
        ("entrance", entrance_choices, entrance_durations),
        ("emphasis", emphasis_choices, emphasis_durations),
        ("exit", exit_choices, exit_durations),
    ):
        type_key = f"{prefix}_{phase_name}"
        duration_key = f"{type_key}_duration"
        default_phase = getattr(default, phase_name)
        requested_type = overrides.get(type_key, default_phase)
        if (
            isinstance(requested_type, str)
            and requested_type == default_phase.type.value
        ):
            requested_type = default_phase
        selected = _parse_animation_phase(
            requested_type,
            durations=durations,
            choices=choices,
            scope=prefix.replace("_", "-"),
            phase=phase_name,
        )
        explicit_duration = overrides.get(duration_key)
        if explicit_duration is not None:
            if selected.type in {CueAnimationType.NONE, CueAnimationType.HIGHLIGHT}:
                raise ValidationError(
                    f"animation-{prefix.replace('_', '-')}-{phase_name}-duration "
                    f"cannot be used with {selected.type.value}"
                )
            selected = replace(
                selected, duration_ms=parse_animation_duration(explicit_duration)
            )
        phases[phase_name] = selected
    return SubtitleElementAnimation(**phases)


def _parse_animation_phase(
    value: object,
    *,
    durations: Mapping[CueAnimationType, int],
    choices: tuple[str, ...],
    scope: str,
    phase: str,
) -> SubtitleAnimationPhase:
    if isinstance(value, SubtitleAnimationPhase):
        _validate_animation_phase(
            value,
            durations=durations,
            scope=scope,
            phase=phase,
        )
        return value
    if isinstance(value, CueAnimationType):
        animation_type = value
    elif isinstance(value, str):
        try:
            animation_type = CueAnimationType(value)
        except ValueError:
            animation_type = None
    else:
        animation_type = None
    if animation_type is None or animation_type not in durations:
        raise ValidationError(
            f"animation-{scope}-{phase} must be one of: " + ", ".join(choices)
        )
    return SubtitleAnimationPhase(
        type=animation_type,
        duration_ms=durations[animation_type],
    )


def _validate_animation_phase(
    value: object,
    *,
    durations: Mapping[CueAnimationType, int],
    scope: str,
    phase: str,
) -> SubtitleAnimationPhase:
    if not isinstance(value, SubtitleAnimationPhase):
        raise ValidationError(
            f"{scope} {phase} must use the typed animation phase contract"
        )
    if not isinstance(value.type, CueAnimationType) or value.type not in durations:
        raise ValidationError(f"{scope} {phase} animation type is invalid")
    if (
        isinstance(value.duration_ms, bool)
        or not isinstance(value.duration_ms, int)
        or value.duration_ms < 0
        or value.duration_ms > 5000
    ):
        raise ValidationError(
            f"{scope} {phase} animation duration must be from 0 through 5000 ms"
        )
    durationless_types = {CueAnimationType.NONE, CueAnimationType.HIGHLIGHT}
    if value.type in durationless_types and value.duration_ms != 0:
        raise ValidationError(
            f"{scope} {phase} animation {value.type.value} must have 0 ms duration"
        )
    if value.type not in durationless_types and value.duration_ms == 0:
        raise ValidationError(f"{scope} {phase} animation requires a positive duration")
    return value


def _validate_word_animation_mode(value: object) -> WordAnimationMode:
    if isinstance(value, WordAnimationMode):
        return value
    if isinstance(value, str):
        try:
            return WordAnimationMode(value)
        except ValueError:
            pass
    raise ValidationError(
        "word animation mode must be one of: " + ", ".join(WORD_ANIMATION_MODE_CHOICES)
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
