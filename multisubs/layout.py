"""Semantic subtitle layout validation against the resolved video canvas."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

from .errors import ValidationError
from .models import (
    RelativeLength,
    SubtitleConfig,
    SubtitleLayout,
    VideoGeometry,
)

_MAX_FONT_SIZE_PIXELS = 512


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
    from .config import validate_subtitle_config

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
    layout = validated.layout
    resolved_layout = SubtitleLayout(
        position=layout.position,
        margin_left=resolve_relative_length(
            layout.margin_left,
            geometry.render_width,
            field="margin-left",
            maximum=geometry.render_width,
        ),
        margin_right=resolve_relative_length(
            layout.margin_right,
            geometry.render_width,
            field="margin-right",
            maximum=geometry.render_width,
        ),
        margin_top=resolve_relative_length(
            layout.margin_top,
            geometry.render_height,
            field="margin-top",
            maximum=geometry.render_height,
        ),
        margin_bottom=resolve_relative_length(
            layout.margin_bottom,
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
    )
    resolve_safe_rectangle(geometry, resolved.layout)
    return resolved


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
