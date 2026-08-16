"""Semantic subtitle layout validation against the resolved video canvas."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError
from .models import SubtitleLayout, VideoGeometry


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

    margins = (
        layout.margin_left,
        layout.margin_right,
        layout.margin_top,
        layout.margin_bottom,
    )
    if any(margin < 0 for margin in margins):
        raise ValidationError("Subtitle margins must be non-negative")

    rectangle = SafeRectangle(
        left=layout.margin_left,
        top=layout.margin_top,
        right=geometry.render_width - layout.margin_right,
        bottom=geometry.render_height - layout.margin_bottom,
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
