"""Semantic subtitle layout validation against the resolved video canvas."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from .errors import ValidationError
from .models import (
    RelativeLength,
    SubtitleConfig,
    SubtitleLayout,
    SubtitleLayoutPreset,
    VideoGeometry,
)

_MAX_FONT_SIZE_PIXELS = 512
_LANDSCAPE_ASPECT_THRESHOLD = Fraction(11, 10)
_PORTRAIT_ASPECT_THRESHOLD = Fraction(9, 10)


def resolve_relative_length(
    value: int | RelativeLength,
    basis: int,
    *,
    field: str,
    maximum: int | None = None,
) -> int:
    """Resolve one pixel or percentage length against an integer axis."""
    if basis <= 0:
        raise ValidationError("Relative length resolution requires a positive basis")
    if isinstance(value, RelativeLength):
        if not isinstance(value.value, Decimal) or not value.value.is_finite():
            raise ValidationError(f"{field} must be a finite decimal number")
        if value.value < 0:
            raise ValidationError(f"{field} cannot be negative")
        if value.unit == "%":
            decimal_value = Decimal(basis) * value.value / Decimal(100)
        elif value.unit == "px":
            decimal_value = value.value
        else:
            raise ValidationError(f"{field} must use % or px units")
    elif isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer or a relative length")
    else:
        decimal_value = Decimal(value)

    try:
        resolved = int(
            decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    except (ArithmeticError, ValueError) as exc:
        raise ValidationError(f"{field} could not be resolved safely") from exc
    if resolved < 0:
        raise ValidationError(f"{field} cannot be negative")
    if maximum is not None and resolved > maximum:
        raise ValidationError(
            f"{field} resolves to {resolved}px, exceeding the maximum of {maximum}px"
        )
    return resolved


def resolve_subtitle_config(
    config: SubtitleConfig,
    geometry: VideoGeometry,
) -> SubtitleConfig:
    """Resolve all geometry-dependent subtitle lengths exactly once."""
    from .config import (
        DEFAULT_POSITION,
        DEFAULT_STYLE,
        get_layout_preset,
        validate_subtitle_config,
    )

    validated = validate_subtitle_config(config)
    short_edge = min(geometry.render_width, geometry.render_height)
    font_size = resolve_relative_length(
        validated.appearance.font_size,
        short_edge,
        field="font-size",
        maximum=min(_MAX_FONT_SIZE_PIXELS, short_edge),
    )
    if font_size <= 0:
        raise ValidationError("font-size must resolve to a value greater than zero")

    outline_weight = resolve_relative_length(
        validated.appearance.outline_weight,
        font_size,
        field="backdrop-size",
        maximum=font_size,
    )
    shadow_weight = resolve_relative_length(
        validated.appearance.shadow_weight,
        font_size,
        field="shadow-size",
        maximum=font_size,
    )
    resolved_preset = (
        classify_layout_preset(geometry)
        if validated.layout_preset is SubtitleLayoutPreset.AUTO
        else validated.layout_preset
    )
    preset_layout = get_layout_preset(resolved_preset).layout
    layout_overrides = _effective_layout_overrides(
        validated,
        default_position=DEFAULT_POSITION,
        default_margins=(
            DEFAULT_STYLE["margin_l"],
            DEFAULT_STYLE["margin_r"],
            DEFAULT_STYLE["margin_v"],
            DEFAULT_STYLE["margin_v"],
        ),
    )
    layout = validated.layout
    merged_layout = SubtitleLayout(
        position=(
            layout.position
            if "position" in layout_overrides
            else preset_layout.position
        ),
        margin_left=(
            layout.margin_left
            if "margin_left" in layout_overrides
            else preset_layout.margin_left
        ),
        margin_right=(
            layout.margin_right
            if "margin_right" in layout_overrides
            else preset_layout.margin_right
        ),
        margin_top=(
            layout.margin_top
            if "margin_top" in layout_overrides
            else preset_layout.margin_top
        ),
        margin_bottom=(
            layout.margin_bottom
            if "margin_bottom" in layout_overrides
            else preset_layout.margin_bottom
        ),
    )
    resolved_layout = SubtitleLayout(
        position=merged_layout.position,
        margin_left=resolve_relative_length(
            merged_layout.margin_left,
            geometry.render_width,
            field="margin-left",
            maximum=geometry.render_width,
        ),
        margin_right=resolve_relative_length(
            merged_layout.margin_right,
            geometry.render_width,
            field="margin-right",
            maximum=geometry.render_width,
        ),
        margin_top=resolve_relative_length(
            merged_layout.margin_top,
            geometry.render_height,
            field="margin-top",
            maximum=geometry.render_height,
        ),
        margin_bottom=resolve_relative_length(
            merged_layout.margin_bottom,
            geometry.render_height,
            field="margin-bottom",
            maximum=geometry.render_height,
        ),
    )
    resolved_appearance = replace(
        validated.appearance,
        font_size=font_size,
        outline_weight=outline_weight,
        shadow_weight=shadow_weight,
    )
    resolved = SubtitleConfig(
        appearance=resolved_appearance,
        layout=resolved_layout,
        layout_preset=resolved_preset,
        layout_overrides=layout_overrides,
    )
    resolve_safe_rectangle(geometry, resolved.layout)
    return resolved


def classify_layout_preset(geometry: VideoGeometry) -> SubtitleLayoutPreset:
    """Select a concrete preset from the autorotated render aspect ratio."""
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ValidationError("Video geometry must have positive render dimensions")
    aspect_ratio = Fraction(geometry.render_width, geometry.render_height)
    if aspect_ratio > _LANDSCAPE_ASPECT_THRESHOLD:
        return SubtitleLayoutPreset.LANDSCAPE
    if aspect_ratio < _PORTRAIT_ASPECT_THRESHOLD:
        return SubtitleLayoutPreset.PORTRAIT
    return SubtitleLayoutPreset.SQUARE


def _effective_layout_overrides(
    config: SubtitleConfig,
    *,
    default_position: object,
    default_margins: tuple[object, object, object, object],
) -> frozenset[str]:
    """Return explicit fields, inferring legacy typed replacements when needed."""
    overrides = set(config.layout_overrides)
    if overrides or config.layout_preset is not SubtitleLayoutPreset.AUTO:
        return frozenset(overrides)

    layout = config.layout
    if layout.position != default_position:
        overrides.add("position")
    for field, default_value in zip(
        (
            "margin_left",
            "margin_right",
            "margin_top",
            "margin_bottom",
        ),
        default_margins,
        strict=True,
    ):
        if getattr(layout, field) != default_value:
            overrides.add(field)
    return frozenset(overrides)


@dataclass(frozen=True)
class SafeRectangle:
    """Subtitle-safe canvas bounds expressed in PlayRes pixels."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """Return the usable horizontal span."""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Return the usable vertical span."""
        return self.bottom - self.top


def resolve_safe_rectangle(
    geometry: VideoGeometry,
    layout: SubtitleLayout,
) -> SafeRectangle:
    """Resolve and validate the layout safe rectangle for one video canvas."""
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ValidationError("Video geometry must have positive render dimensions")

    margin_left = _resolved_layout_int(layout.margin_left, "margin-left")
    margin_right = _resolved_layout_int(layout.margin_right, "margin-right")
    margin_top = _resolved_layout_int(layout.margin_top, "margin-top")
    margin_bottom = _resolved_layout_int(layout.margin_bottom, "margin-bottom")
    margins = (margin_left, margin_right, margin_top, margin_bottom)
    if any(margin < 0 for margin in margins):
        raise ValidationError("Subtitle margins must be non-negative")

    rectangle = SafeRectangle(
        left=margin_left,
        top=margin_top,
        right=geometry.render_width - margin_right,
        bottom=geometry.render_height - margin_bottom,
    )
    if rectangle.width <= 0:
        raise ValidationError(
            "Subtitle left and right margins leave no usable safe rectangle"
        )
    if rectangle.height <= 0:
        raise ValidationError(
            "Subtitle top and bottom margins leave no usable safe rectangle"
        )
    return rectangle


def _resolved_layout_int(value: int | RelativeLength, field: str) -> int:
    if isinstance(value, RelativeLength):
        raise ValidationError(
            f"{field} must be resolved against video geometry before safe-area use"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer")
    return value
