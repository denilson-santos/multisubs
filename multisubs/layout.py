"""Semantic subtitle layout validation against the resolved video canvas."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import cast

from .errors import ValidationError
from .models import (
    CuePlacement,
    RelativeLength,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleLayout,
    SubtitleLayoutPreset,
    SubtitlePosition,
    VideoGeometry,
)
from .text_measurement import TextMeasurer, build_text_measurer

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
        resolved = int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
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
        validated.appearance.backdrop_size,
        font_size,
        field="backdrop-size",
        maximum=font_size,
    )
    shadow_weight = resolve_relative_length(
        validated.appearance.shadow_size,
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
        default_margins=(0, 0, 0, 0),
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
        position_x=layout.position_x,
        position_y=layout.position_y,
        anchor=layout.anchor,
        max_width=(
            layout.max_width
            if "max_width" in layout_overrides
            else preset_layout.max_width
        ),
        max_lines=(
            layout.max_lines
            if "max_lines" in layout_overrides
            else preset_layout.max_lines
        ),
    )
    resolved_margin_layout = replace(
        merged_layout,
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
    safe_rectangle = resolve_safe_rectangle(geometry, resolved_margin_layout)
    resolved_layout = replace(
        resolved_margin_layout,
        position_x=(
            resolve_relative_length(
                merged_layout.position_x,
                safe_rectangle.width,
                field="position-x",
                maximum=safe_rectangle.width,
            )
            if merged_layout.position_x is not None
            else None
        ),
        position_y=(
            resolve_relative_length(
                merged_layout.position_y,
                safe_rectangle.height,
                field="position-y",
                maximum=safe_rectangle.height,
            )
            if merged_layout.position_y is not None
            else None
        ),
        anchor=merged_layout.anchor,
        max_width=resolve_relative_length(
            _require_resolved_layout_length(merged_layout.max_width, "max-width"),
            safe_rectangle.width,
            field="max-width",
            maximum=safe_rectangle.width,
        ),
        max_lines=_require_max_lines(merged_layout.max_lines),
    )
    resolved_appearance = replace(
        validated.appearance,
        font_size=font_size,
        backdrop_size=outline_weight,
        shadow_size=shadow_weight,
    )
    resolved = SubtitleConfig(
        appearance=resolved_appearance,
        layout=resolved_layout,
        layout_preset=resolved_preset,
        layout_overrides=layout_overrides,
    )
    resolve_safe_rectangle(geometry, resolved.layout)
    _validated_cue_placement(resolved, geometry)
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


@dataclass(frozen=True)
class WrappingMetrics:
    """Resolved geometry and font inputs used by adaptive subtitle wrapping."""

    safe_width: int
    max_width: int
    anchor_width: int
    width_budget: int
    font_size: int
    backdrop_size: int
    shadow_size: int
    max_lines: int
    anchor: SubtitlePosition
    anchor_x: int
    text_measurer: TextMeasurer = field(repr=False, compare=False)

    @property
    def decoration_width(self) -> int:
        """Return the horizontal outline/shadow allowance in PlayRes pixels."""
        return 2 * (self.backdrop_size + self.shadow_size)


def resolve_wrapping_metrics(
    config: SubtitleConfig,
    geometry: VideoGeometry,
    *,
    language: str | None = None,
    text_measurer: TextMeasurer | None = None,
) -> WrappingMetrics:
    """Resolve the geometry-aware inputs used by adaptive cue wrapping."""
    resolved = resolve_subtitle_config(config, geometry)
    return _build_wrapping_metrics(
        resolved,
        geometry,
        language=language,
        text_measurer=text_measurer,
    )


def _build_wrapping_metrics(
    config: SubtitleConfig,
    geometry: VideoGeometry,
    *,
    language: str | None,
    text_measurer: TextMeasurer | None,
) -> WrappingMetrics:
    layout = config.layout
    safe_rectangle = resolve_safe_rectangle(geometry, layout)
    max_width = _require_resolved_layout_int(layout.max_width, "max-width")
    if max_width <= 0:
        raise ValidationError("max-width must resolve to a value greater than zero")
    max_lines = _require_max_lines(layout.max_lines)
    placement = _validated_cue_placement(config, geometry)
    anchor = placement.anchor
    anchor_x = placement.position_x
    anchor_width = _anchor_width(anchor, anchor_x, safe_rectangle)
    width_budget = max(1, min(safe_rectangle.width, max_width, anchor_width))
    return WrappingMetrics(
        safe_width=safe_rectangle.width,
        max_width=max_width,
        anchor_width=anchor_width,
        width_budget=width_budget,
        font_size=_require_resolved_layout_int(
            config.appearance.font_size, "font-size"
        ),
        backdrop_size=(
            0
            if config.appearance.backdrop is SubtitleBackdrop.NONE
            else _require_resolved_layout_int(
                config.appearance.backdrop_size, "backdrop-size"
            )
        ),
        shadow_size=_require_resolved_layout_int(
            config.appearance.shadow_size, "shadow-size"
        ),
        max_lines=max_lines,
        anchor=anchor,
        anchor_x=anchor_x,
        text_measurer=text_measurer
        or build_text_measurer(config.appearance, language=language),
    )


def estimate_text_width(text: str, metrics: WrappingMetrics) -> float:
    """Measure a line's PlayRes width including its visual decorations."""
    return metrics.text_measurer.measure(text) + metrics.decoration_width


def unicode_display_width(text: str) -> int:
    """Return a conservative terminal-like display width for Unicode text."""
    width = 0
    for cluster in _grapheme_clusters(text):
        if not cluster or all(
            unicodedata.category(char) in {"Mn", "Me", "Cf"} for char in cluster
        ):
            continue
        if any(_is_wide_character(char) for char in cluster):
            width += 2
        else:
            width += 1
    return width


def _grapheme_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    current = ""
    for character in text:
        category = unicodedata.category(character)
        if current and (
            category in {"Mn", "Me", "Cf"}
            or character in {"\ufe0e", "\ufe0f"}
            or current.endswith("\u200d")
        ):
            current += character
            continue
        if current:
            clusters.append(current)
        current = character
    if current:
        clusters.append(current)
    return clusters


def _is_wide_character(character: str) -> bool:
    if unicodedata.east_asian_width(character) in {"W", "F"}:
        return True
    codepoint = ord(character)
    return 0x1F000 <= codepoint <= 0x1FAFF or 0x2600 <= codepoint <= 0x27BF


def resolve_ass_horizontal_margins(
    config: SubtitleConfig,
    geometry: VideoGeometry,
) -> tuple[int, int]:
    """Express the effective anchored line region as private ASS margins."""
    layout = config.layout
    safe_rectangle = resolve_safe_rectangle(geometry, layout)
    max_width = _require_resolved_layout_int(layout.max_width, "max-width")
    placement = _validated_cue_placement(config, geometry)
    anchor_width = _anchor_width(placement.anchor, placement.position_x, safe_rectangle)
    width_budget = max(1, min(safe_rectangle.width, max_width, anchor_width))
    if placement.anchor.value.endswith("left"):
        region_left = placement.position_x
        region_right = region_left + width_budget
    elif placement.anchor.value.endswith("right"):
        region_right = placement.position_x
        region_left = region_right - width_budget
    else:
        region_left = placement.position_x - width_budget // 2
        region_right = region_left + width_budget
    return region_left, geometry.render_width - region_right


def _effective_layout_overrides(
    config: SubtitleConfig,
    *,
    default_position: object,
    default_margins: tuple[object, object, object, object],
) -> frozenset[str]:
    """Return explicit fields, inferring legacy typed replacements when needed."""
    overrides = set(config.layout_overrides)
    if overrides:
        return frozenset(overrides)

    layout = config.layout
    if config.layout_preset is SubtitleLayoutPreset.AUTO:
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
    if layout.max_width is not None:
        overrides.add("max_width")
    if layout.max_lines is not None:
        overrides.add("max_lines")
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


def resolve_cue_placement(
    config: SubtitleConfig,
    geometry: VideoGeometry,
) -> CuePlacement:
    """Resolve a named or custom safe-area placement for every visual cue."""
    resolved = resolve_subtitle_config(config, geometry)
    return _validated_cue_placement(resolved, geometry)


def _validated_cue_placement(
    resolved: SubtitleConfig,
    geometry: VideoGeometry,
) -> CuePlacement:
    """Build a placement from a geometry-resolved configuration."""
    layout = resolved.layout
    safe_rectangle = resolve_safe_rectangle(geometry, layout)
    if layout.position_x is None and layout.position_y is None:
        anchor = layout.position
        placement = CuePlacement(
            anchor=anchor,
            position_x=_named_horizontal_coordinate(anchor, safe_rectangle),
            position_y=_named_vertical_coordinate(anchor, safe_rectangle),
        )
    else:
        if layout.position_x is None or layout.position_y is None:
            raise ValidationError("position-x and position-y must be supplied together")
        if layout.anchor is None:
            raise ValidationError("custom coordinates require an anchor")
        if not isinstance(layout.position_x, int) or not isinstance(
            layout.position_y, int
        ):
            raise ValidationError(
                "custom coordinates must be resolved against video geometry first"
            )
        placement = CuePlacement(
            anchor=layout.anchor,
            position_x=safe_rectangle.left + layout.position_x,
            position_y=safe_rectangle.top + layout.position_y,
        )
    _validate_cue_placement_bounds(
        placement,
        safe_rectangle,
        font_size=resolved.appearance.font_size,
        outline_weight=(
            0
            if resolved.appearance.backdrop is SubtitleBackdrop.NONE
            else resolved.appearance.backdrop_size
        ),
        shadow_weight=resolved.appearance.shadow_size,
    )
    return placement


def _validate_cue_placement_bounds(
    placement: CuePlacement,
    safe_rectangle: SafeRectangle,
    *,
    font_size: object,
    outline_weight: object,
    shadow_weight: object,
) -> None:
    """Reject custom anchors that cannot contain even a minimal subtitle line."""
    if not safe_rectangle.left <= placement.position_x <= safe_rectangle.right:
        raise ValidationError(
            "position-x places the subtitle anchor outside the safe rectangle"
        )
    if not safe_rectangle.top <= placement.position_y <= safe_rectangle.bottom:
        raise ValidationError(
            "position-y places the subtitle anchor outside the safe rectangle"
        )

    values = (font_size, outline_weight, shadow_weight)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValidationError(
            "subtitle appearance must be resolved before custom placement"
        )
    font_size_value = cast(int, font_size)
    outline_weight_value = cast(int, outline_weight)
    shadow_weight_value = cast(int, shadow_weight)
    extent = max(1, font_size_value + 2 * (outline_weight_value + shadow_weight_value))
    anchor = placement.anchor.value
    if anchor.endswith("left") and placement.position_x + extent > safe_rectangle.right:
        raise ValidationError(
            "position-x leaves no room for a subtitle line inside the safe rectangle"
        )
    if anchor.endswith("right") and placement.position_x - extent < safe_rectangle.left:
        raise ValidationError(
            "position-x leaves no room for a subtitle line inside the safe rectangle"
        )
    if anchor in {"top-center", "center", "bottom-center"}:
        half_extent = (extent + 1) // 2
        if (
            placement.position_x - half_extent < safe_rectangle.left
            or placement.position_x + half_extent > safe_rectangle.right
        ):
            raise ValidationError(
                "position-x leaves no room for a subtitle line inside the safe "
                "rectangle"
            )

    if (
        anchor.startswith("top-")
        and placement.position_y + extent > safe_rectangle.bottom
    ):
        raise ValidationError(
            "position-y leaves no room for a subtitle line inside the safe rectangle"
        )
    if (
        anchor.startswith("bottom-")
        and placement.position_y - extent < safe_rectangle.top
    ):
        raise ValidationError(
            "position-y leaves no room for a subtitle line inside the safe rectangle"
        )
    if anchor in {"middle-left", "center", "middle-right"}:
        half_extent = (extent + 1) // 2
        if (
            placement.position_y - half_extent < safe_rectangle.top
            or placement.position_y + half_extent > safe_rectangle.bottom
        ):
            raise ValidationError(
                "position-y leaves no room for a subtitle line inside the safe "
                "rectangle"
            )


def _resolved_layout_int(value: int | RelativeLength, field: str) -> int:
    if isinstance(value, RelativeLength):
        raise ValidationError(
            f"{field} must be resolved against video geometry before safe-area use"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field} must be an integer")
    return value


def _require_resolved_layout_length(
    value: int | RelativeLength | None, field: str
) -> int | RelativeLength:
    if value is None:
        raise ValidationError(f"{field} must be supplied by the selected layout")
    return value


def _require_resolved_layout_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            f"{field} must be resolved against video geometry before use"
        )
    return value


def _require_max_lines(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in {1, 2, 3}:
        raise ValidationError("max-lines must resolve to an integer from 1 to 3")
    return value


def _named_horizontal_coordinate(
    position: SubtitlePosition,
    safe_rectangle: SafeRectangle,
) -> int:
    if position.value.endswith("left"):
        return safe_rectangle.left
    if position.value.endswith("right"):
        return safe_rectangle.right
    return safe_rectangle.left + safe_rectangle.width // 2


def _named_vertical_coordinate(
    position: SubtitlePosition,
    safe_rectangle: SafeRectangle,
) -> int:
    if position.value.startswith("top-"):
        return safe_rectangle.top
    if position.value.startswith("bottom-"):
        return safe_rectangle.bottom
    return safe_rectangle.top + safe_rectangle.height // 2


def _anchor_width(
    anchor: SubtitlePosition,
    anchor_x: int,
    safe_rectangle: SafeRectangle,
) -> int:
    value = anchor.value
    if value.endswith("left"):
        return safe_rectangle.right - anchor_x
    if value.endswith("right"):
        return anchor_x - safe_rectangle.left
    return 2 * min(anchor_x - safe_rectangle.left, safe_rectangle.right - anchor_x)
