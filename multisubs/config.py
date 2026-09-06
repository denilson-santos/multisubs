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
DEFAULT_BACKDROP_SIZE = "0px"
DEFAULT_WORD_BACKDROP = SubtitleBackdrop.NONE
DEFAULT_WORD_BACKDROP_COLOR = "#111827E6"
DEFAULT_WORD_BACKDROP_SIZE = "20px"
DEFAULT_SHADOW_SIZE = "4%"
DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR = "#FFD54F"
DEFAULT_WORD_ANIMATION_MODE = WordAnimationMode.ACTIVE_WORD
DEFAULT_MARGIN_LEFT = "18%"
DEFAULT_MARGIN_RIGHT = "18%"
DEFAULT_MARGIN_TOP = "0%"
DEFAULT_MARGIN_BOTTOM = "3%"
DEFAULT_MAX_WIDTH = "100%"
DEFAULT_MAX_HEIGHT = "10%"

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
        if resolved_position is not None and resolved_position != value.layout.position:
            raise ValidationError(
                "position cannot override the position already stored in the "
                "subtitle configuration"
            )
        if resolved_anchor is not None and resolved_anchor != value.layout.anchor:
            raise ValidationError(
                "anchor cannot override the anchor already stored in the subtitle "
                "configuration"
            )
        _validate_typed_subtitle_config(value)
        if value.animation.word.uses_timed_highlight:
            highlight_color = _validate_color(
                value.style.typography.highlight_color
                or DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR,
                "animation-word-text-highlight-color",
            )
            if highlight_color != value.style.typography.highlight_color:
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
        return value
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
    default_backdrop = default_style.backdrop if default_style is not None else None
    default_word_backdrop = (
        default_style.word_backdrop if default_style is not None else None
    )
    default_shadow = default_style.shadow if default_style is not None else None
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
        font_weight = (
            default_typography.font_weight
            if default_typography is not None
            else DEFAULT_FONT_WEIGHT
        )
        font_weight_input = (
            default_typography.font_weight_input
            if default_typography is not None
            else DEFAULT_FONT_WEIGHT.canonical_name
        )
        font_weight_input_form = (
            default_typography.font_weight_input_form
            if default_typography is not None
            else FontWeightInputForm.DEFAULT
        )

    opacity = _validate_opacity(
        appearance_overrides.get(
            "opacity",
            default_style.opacity if default_style is not None else DEFAULT_OPACITY,
        )
    )

    track_specs = {
        "cue_text": (
            default_cue_animation.text,
            CUE_ENTRANCE_ANIMATION_CHOICES,
            CUE_EMPHASIS_ANIMATION_CHOICES,
            CUE_EXIT_ANIMATION_CHOICES,
            _ENTRANCE_ANIMATION_DURATIONS_MS,
            _CUE_EMPHASIS_ANIMATION_DURATIONS_MS,
            _EXIT_ANIMATION_DURATIONS_MS,
        ),
        "cue_backdrop": (
            default_cue_animation.backdrop,
            CUE_ENTRANCE_ANIMATION_CHOICES,
            CUE_EMPHASIS_ANIMATION_CHOICES,
            CUE_EXIT_ANIMATION_CHOICES,
            _ENTRANCE_ANIMATION_DURATIONS_MS,
            _CUE_EMPHASIS_ANIMATION_DURATIONS_MS,
            _EXIT_ANIMATION_DURATIONS_MS,
        ),
        "word_text": (
            default_word_animation.text,
            WORD_ENTRANCE_ANIMATION_CHOICES,
            WORD_TEXT_EMPHASIS_ANIMATION_CHOICES,
            WORD_EXIT_ANIMATION_CHOICES,
            _WORD_ENTRANCE_ANIMATION_DURATIONS_MS,
            _WORD_TEXT_EMPHASIS_ANIMATION_DURATIONS_MS,
            _WORD_EXIT_ANIMATION_DURATIONS_MS,
        ),
        "word_backdrop": (
            default_word_animation.backdrop,
            WORD_ENTRANCE_ANIMATION_CHOICES,
            WORD_BACKDROP_EMPHASIS_ANIMATION_CHOICES,
            WORD_EXIT_ANIMATION_CHOICES,
            _WORD_ENTRANCE_ANIMATION_DURATIONS_MS,
            _WORD_BACKDROP_EMPHASIS_ANIMATION_DURATIONS_MS,
            _WORD_EXIT_ANIMATION_DURATIONS_MS,
        ),
    }
    known_animation_fields = {
        "word_text_mode",
        "word_backdrop_mode",
        "word_text_highlight_color",
    }
    for prefix in track_specs:
        for phase_name in ("entrance", "emphasis", "exit"):
            known_animation_fields.add(f"{prefix}_{phase_name}")
            known_animation_fields.add(f"{prefix}_{phase_name}_duration")
    unknown_animation_fields = set(animation_overrides).difference(
        known_animation_fields
    )
    if unknown_animation_fields:
        names = ", ".join(sorted(unknown_animation_fields))
        raise ValidationError(f"Unknown animation value(s): {names}")
    resolved_tracks = {
        prefix: _resolve_animation_track(
            prefix,
            default_track,
            animation_overrides,
            entrance_choices=entrance_choices,
            emphasis_choices=emphasis_choices,
            exit_choices=exit_choices,
            entrance_durations=entrance_durations,
            emphasis_durations=emphasis_durations,
            exit_durations=exit_durations,
        )
        for prefix, (
            default_track,
            entrance_choices,
            emphasis_choices,
            exit_choices,
            entrance_durations,
            emphasis_durations,
            exit_durations,
        ) in track_specs.items()
    }
    word_text_mode = _validate_word_animation_mode(
        animation_overrides.get("word_text_mode", default_word_animation.text.mode)
    )
    word_backdrop_mode = _validate_word_animation_mode(
        animation_overrides.get(
            "word_backdrop_mode", default_word_animation.backdrop.mode
        )
    )
    explicit_highlight_color = animation_overrides.get("word_text_highlight_color")
    word_text_highlighted = (
        resolved_tracks["word_text"].emphasis.type is CueAnimationType.HIGHLIGHT
    )
    if not word_text_highlighted and explicit_highlight_color is not None:
        raise ValidationError(
            "animation-word-text-highlight-color requires "
            "--animation-word-text-emphasis highlight"
        )
    raw_highlight_color = (
        explicit_highlight_color
        if explicit_highlight_color is not None
        else (
            default_typography.highlight_color
            if default_typography is not None
            else None
        )
        or DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR
    )
    highlight_color = (
        _validate_color(
            raw_highlight_color,
            "animation-word-text-highlight-color",
        )
        if word_text_highlighted
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
    parsed_line_height = parsed_relative_values.get(
        "line_height",
        default_typography.line_height
        if default_typography is not None
        else DEFAULT_LINE_HEIGHT,
    )

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
    _validate_layout_option_effects(
        parsed_relative_values,
        position=(
            resolved_position
            or (
                default_layout.position
                if default_layout is not None
                else DEFAULT_POSITION
            )
        ),
        has_custom_coordinates=has_custom_coordinates,
    )
    config = SubtitleConfig(
        style=SubtitleStyle(
            typography=SubtitleTypography(
                font=_validate_font(
                    appearance_overrides.get(
                        "font",
                        default_typography.font
                        if default_typography is not None
                        else DEFAULT_FONT,
                    )
                ),
                font_size=parsed_length_values.get(
                    "font_size",
                    default_typography.font_size
                    if default_typography is not None
                    else parse_relative_length(DEFAULT_FONT_SIZE),
                ),
                letter_spacing=parsed_length_values.get(
                    "letter_spacing",
                    default_typography.letter_spacing
                    if default_typography is not None
                    else parse_relative_length(DEFAULT_LETTER_SPACING),
                ),
                color=_validate_color(
                    appearance_overrides.get(
                        "text_color",
                        default_typography.color
                        if default_typography is not None
                        else DEFAULT_TEXT_COLOR,
                    ),
                    "text-color",
                ),
                font_weight=font_weight,
                italic=_validate_boolean(
                    appearance_overrides.get(
                        "italic",
                        default_typography.italic
                        if default_typography is not None
                        else DEFAULT_ITALIC,
                    ),
                    "italic",
                ),
                fonts_dir=_coerce_fonts_dir(
                    appearance_overrides.get(
                        "fonts_dir",
                        default_typography.fonts_dir
                        if default_typography is not None
                        else None,
                    )
                ),
                font_weight_input=font_weight_input,
                font_weight_input_form=font_weight_input_form,
                line_height=parsed_line_height,
                text_case=parse_text_case(
                    appearance_overrides.get(
                        "text_case",
                        default_typography.text_case
                        if default_typography is not None
                        else DEFAULT_TEXT_CASE,
                    )
                ),
                highlight_color=highlight_color,
            ),
            backdrop=SubtitleBackdropStyle(
                kind=_validate_backdrop(
                    appearance_overrides.get(
                        "backdrop",
                        default_backdrop.kind
                        if default_backdrop is not None
                        else DEFAULT_BACKDROP,
                    )
                ),
                color=_validate_color(
                    appearance_overrides.get(
                        "backdrop_color",
                        default_backdrop.color
                        if default_backdrop is not None
                        else DEFAULT_BACKDROP_COLOR,
                    ),
                    "backdrop-color",
                ),
                size=parsed_length_values.get(
                    "outline_weight",
                    default_backdrop.size
                    if default_backdrop is not None
                    else parse_relative_length(DEFAULT_BACKDROP_SIZE),
                ),
            ),
            word_backdrop=SubtitleWordBackdropStyle(
                kind=_validate_backdrop(
                    appearance_overrides.get(
                        "word_backdrop",
                        default_word_backdrop.kind
                        if default_word_backdrop is not None
                        else DEFAULT_WORD_BACKDROP,
                    )
                ),
                color=_validate_color(
                    appearance_overrides.get(
                        "word_backdrop_color",
                        default_word_backdrop.color
                        if default_word_backdrop is not None
                        else DEFAULT_WORD_BACKDROP_COLOR,
                    ),
                    "word-backdrop-color",
                ),
                size=parsed_length_values.get(
                    "word_backdrop_size",
                    default_word_backdrop.size
                    if default_word_backdrop is not None
                    else parse_relative_length(DEFAULT_WORD_BACKDROP_SIZE),
                ),
            ),
            shadow=SubtitleShadow(
                size=parsed_length_values.get(
                    "shadow_weight",
                    default_shadow.size
                    if default_shadow is not None
                    else parse_relative_length(DEFAULT_SHADOW_SIZE),
                )
            ),
            opacity=opacity,
        ),
        layout=SubtitleLayout(
            position=(
                resolved_position
                or (
                    default_layout.position
                    if default_layout is not None
                    else DEFAULT_POSITION
                )
            ),
            margin_left=parsed_length_values.get(
                "margin_left",
                default_layout.margin_left
                if default_layout is not None
                else parse_relative_length(DEFAULT_MARGIN_LEFT),
            ),
            margin_right=parsed_length_values.get(
                "margin_right",
                default_layout.margin_right
                if default_layout is not None
                else parse_relative_length(DEFAULT_MARGIN_RIGHT),
            ),
            margin_top=parsed_length_values.get(
                "margin_top",
                default_layout.margin_top
                if default_layout is not None
                else parse_relative_length(DEFAULT_MARGIN_TOP),
            ),
            margin_bottom=parsed_length_values.get(
                "margin_bottom",
                default_layout.margin_bottom
                if default_layout is not None
                else parse_relative_length(DEFAULT_MARGIN_BOTTOM),
            ),
            placement_mode=(
                SubtitlePlacementMode.EXPLICIT
                if has_custom_coordinates
                else SubtitlePlacementMode.NATIVE_STYLE
            ),
            position_x=parsed_length_values.get("position_x"),
            position_y=parsed_length_values.get("position_y"),
            anchor=resolved_anchor if has_custom_coordinates else None,
            max_width=parsed_length_values.get(
                "max_width",
                default_layout.max_width
                if default_layout is not None
                else parse_relative_length(DEFAULT_MAX_WIDTH),
            ),
            max_height=parsed_length_values.get(
                "max_height",
                default_layout.max_height
                if default_layout is not None
                else parse_relative_length(DEFAULT_MAX_HEIGHT),
            ),
        ),
        animation=SubtitleAnimation(
            cue=SubtitleCueAnimation(
                text=resolved_tracks["cue_text"],
                backdrop=resolved_tracks["cue_backdrop"],
            ),
            word=SubtitleWordAnimation(
                text=SubtitleWordElementAnimation(
                    entrance=resolved_tracks["word_text"].entrance,
                    emphasis=resolved_tracks["word_text"].emphasis,
                    exit=resolved_tracks["word_text"].exit,
                    mode=word_text_mode,
                ),
                backdrop=SubtitleWordElementAnimation(
                    entrance=resolved_tracks["word_backdrop"].entrance,
                    emphasis=resolved_tracks["word_backdrop"].emphasis,
                    exit=resolved_tracks["word_backdrop"].exit,
                    mode=word_backdrop_mode,
                ),
            ),
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
    typography = config.style.typography
    backdrop = config.style.backdrop
    word_backdrop = config.style.word_backdrop
    shadow = config.style.shadow
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
    _validate_opacity(config.style.opacity)
    if not isinstance(typography.text_case, TextCase):
        raise ValidationError("text-case must use the typed TextCase contract")
    _coerce_fonts_dir(typography.fonts_dir)
    _validate_line_height_value(typography.line_height, "line-height")
    if typography.line_height_requested is not None:
        _validate_line_height_value(
            typography.line_height_requested, "line-height-requested"
        )
    _validate_animation(config.animation, typography)
    relative_fields = {
        "font_size": typography.font_size,
        "letter_spacing": typography.letter_spacing,
        "outline_weight": backdrop.size,
        "word_backdrop_size": config.style.word_backdrop.size,
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
