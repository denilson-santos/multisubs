"""Semantic subtitle layout validation against the resolved video canvas."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from .errors import ValidationError
from .models import (
    CuePlacement,
    RelativeLength,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleLayout,
    SubtitleLayoutPreset,
    SubtitlePlacementMode,
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
    from .config import DEFAULT_POSITION, get_layout_preset, validate_subtitle_config

    _validate_geometry(geometry)
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
    explicit = layout.placement_mode is SubtitlePlacementMode.EXPLICIT
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
        placement_mode=layout.placement_mode,
        position_x=layout.position_x,
        position_y=layout.position_y,
        anchor=layout.anchor,
        max_width=(
            layout.max_width
            if explicit or "max_width" in layout_overrides
            else preset_layout.max_width
        ),
        max_height=(
            layout.max_height
            if explicit or "max_height" in layout_overrides
            else preset_layout.max_height
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

    if explicit:
        width_basis = geometry.render_width
        height_basis = geometry.render_height
    else:
        region = resolve_native_layout_region(geometry, resolved_margin_layout)
        width_basis = region.width
        height_basis = region.height

    max_width = resolve_relative_length(
        _require_resolved_layout_length(merged_layout.max_width, "max-width"),
        width_basis,
        field="max-width",
        maximum=width_basis,
    )
    max_height = resolve_relative_length(
        _require_resolved_layout_length(merged_layout.max_height, "max-height"),
        height_basis,
        field="max-height",
        maximum=height_basis,
    )
    if max_width <= 0:
        raise ValidationError("max-width must resolve to a value greater than zero")
    if max_height <= 0:
        raise ValidationError("max-height must resolve to a value greater than zero")

    resolved_layout = replace(
        resolved_margin_layout,
        position_x=(
            resolve_relative_length(
                _require_resolved_layout_length(merged_layout.position_x, "position-x"),
                geometry.render_width,
                field="position-x",
                maximum=geometry.render_width,
            )
            if explicit
            else None
        ),
        position_y=(
            resolve_relative_length(
                _require_resolved_layout_length(merged_layout.position_y, "position-y"),
                geometry.render_height,
                field="position-y",
                maximum=geometry.render_height,
            )
            if explicit
            else None
        ),
        anchor=merged_layout.anchor if explicit else None,
        max_width=max_width,
        max_height=max_height,
    )
    resolved = SubtitleConfig(
        appearance=replace(
            validated.appearance,
            font_size=font_size,
            backdrop_size=outline_weight,
            shadow_size=shadow_weight,
        ),
        layout=resolved_layout,
        layout_preset=resolved_preset,
        layout_overrides=layout_overrides,
        effects=validated.effects,
    )
    if explicit:
        _validated_explicit_placement(resolved, geometry)
    else:
        resolve_native_layout_region(geometry, resolved.layout)
    return resolved


def classify_layout_preset(geometry: VideoGeometry) -> SubtitleLayoutPreset:
    """Select a concrete preset from the autorotated render aspect ratio."""
    _validate_geometry(geometry)
    aspect_ratio = Fraction(geometry.render_width, geometry.render_height)
    if aspect_ratio > _LANDSCAPE_ASPECT_THRESHOLD:
        return SubtitleLayoutPreset.LANDSCAPE
    if aspect_ratio < _PORTRAIT_ASPECT_THRESHOLD:
        return SubtitleLayoutPreset.PORTRAIT
    return SubtitleLayoutPreset.SQUARE


@dataclass(frozen=True)
class NativeLayoutRegion:
    """The region left by the margins that native ASS alignment applies."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class WrappingMetrics:
    """Resolved geometry and font inputs used by adaptive subtitle wrapping."""

    placement_mode: SubtitlePlacementMode
    available_width: int
    available_height: int
    max_width: int
    max_height: int
    width_budget: int
    line_height: float
    vertical_decoration: int
    line_capacity: int
    font_size: int
    backdrop_size: int
    shadow_size: int
    anchor: SubtitlePosition | None
    anchor_x: int | None
    anchor_y: int | None
    text_measurer: TextMeasurer = field(repr=False, compare=False)

    @property
    def decoration_width(self) -> int:
        """Return the horizontal backdrop/shadow allowance in PlayRes pixels."""
        return 2 * self.backdrop_size + self.shadow_size


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
    max_width = _require_resolved_layout_int(layout.max_width, "max-width")
    max_height = _require_resolved_layout_int(layout.max_height, "max-height")
    backdrop_size = (
        0
        if config.appearance.backdrop is SubtitleBackdrop.NONE
        else _require_resolved_layout_int(
            config.appearance.backdrop_size, "backdrop-size"
        )
    )
    shadow_size = _require_resolved_layout_int(
        config.appearance.shadow_size, "shadow-size"
    )
    measurer = text_measurer or build_text_measurer(
        config.appearance, language=language
    )
    decoration_width = 2 * backdrop_size + shadow_size
    vertical_decoration = 2 * backdrop_size + shadow_size
    width_budget = max_width - decoration_width
    content_height = max_height - vertical_decoration
    if width_budget <= 0:
        raise ValidationError(
            "max-width is too small for the configured backdrop and shadow"
        )
    if content_height < measurer.line_height:
        required = math.ceil(measurer.line_height + vertical_decoration)
        raise ValidationError(
            "max-height resolves to "
            f"{max_height}px, but at least {required}px is required for one "
            "subtitle line with the configured font and decorations"
        )
    line_capacity = max(1, int(content_height // measurer.line_height))
    placement = _validated_explicit_placement(config, geometry)
    if layout.placement_mode is SubtitlePlacementMode.NATIVE_STYLE:
        region = resolve_native_layout_region(geometry, layout)
        available_width = region.width
        available_height = region.height
    else:
        available_width = geometry.render_width
        available_height = geometry.render_height
    return WrappingMetrics(
        placement_mode=layout.placement_mode,
        available_width=available_width,
        available_height=available_height,
        max_width=max_width,
        max_height=max_height,
        width_budget=width_budget,
        line_height=measurer.line_height,
        vertical_decoration=vertical_decoration,
        line_capacity=line_capacity,
        font_size=_require_resolved_layout_int(
            config.appearance.font_size, "font-size"
        ),
        backdrop_size=backdrop_size,
        shadow_size=shadow_size,
        anchor=placement.anchor if placement is not None else None,
        anchor_x=placement.position_x if placement is not None else None,
        anchor_y=placement.position_y if placement is not None else None,
        text_measurer=measurer,
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


def resolve_native_layout_region(
    geometry: VideoGeometry,
    layout: SubtitleLayout,
) -> NativeLayoutRegion:
    """Return the real region controlled by native ASS alignment and margins."""
    _validate_geometry(geometry)
    if layout.placement_mode is not SubtitlePlacementMode.NATIVE_STYLE:
        raise ValidationError("native layout region is unavailable in explicit mode")
    margin_left = _resolved_layout_int(layout.margin_left, "margin-left")
    margin_right = _resolved_layout_int(layout.margin_right, "margin-right")
    margin_top = _resolved_layout_int(layout.margin_top, "margin-top")
    margin_bottom = _resolved_layout_int(layout.margin_bottom, "margin-bottom")
    if any(
        margin < 0 for margin in (margin_left, margin_right, margin_top, margin_bottom)
    ):
        raise ValidationError("Subtitle margins must be non-negative")
    left = margin_left
    right = geometry.render_width - margin_right
    if right <= left:
        raise ValidationError(
            "Subtitle left and right margins leave no usable native layout width"
        )
    if layout.position.value.startswith("top-"):
        top, bottom = margin_top, geometry.render_height
    elif layout.position.value.startswith("bottom-"):
        top, bottom = 0, geometry.render_height - margin_bottom
    else:
        top, bottom = 0, geometry.render_height
    if bottom <= top:
        active = "top" if layout.position.value.startswith("top-") else "bottom"
        raise ValidationError(
            f"Subtitle {active} margin leaves no usable native layout height"
        )
    return NativeLayoutRegion(left=left, top=top, right=right, bottom=bottom)


def resolve_cue_placement(
    config: SubtitleConfig,
    geometry: VideoGeometry,
) -> CuePlacement | None:
    """Resolve explicit per-event placement; native style placement returns None."""
    resolved = resolve_subtitle_config(config, geometry)
    return _validated_explicit_placement(resolved, geometry)


def _validated_explicit_placement(
    resolved: SubtitleConfig,
    geometry: VideoGeometry,
) -> CuePlacement | None:
    layout = resolved.layout
    if layout.placement_mode is SubtitlePlacementMode.NATIVE_STYLE:
        return None
    if layout.position_x is None or layout.position_y is None or layout.anchor is None:
        raise ValidationError(
            "explicit placement requires position-x, position-y, and anchor"
        )
    x = _require_resolved_layout_int(layout.position_x, "position-x")
    y = _require_resolved_layout_int(layout.position_y, "position-y")
    max_width = _require_resolved_layout_int(layout.max_width, "max-width")
    max_height = _require_resolved_layout_int(layout.max_height, "max-height")
    placement = CuePlacement(anchor=layout.anchor, position_x=x, position_y=y)
    _validate_explicit_axis(
        coordinate=x,
        canvas_size=geometry.render_width,
        envelope_size=max_width,
        alignment=_horizontal_alignment(layout.anchor),
        field="position-x",
        dimension="max-width",
    )
    _validate_explicit_axis(
        coordinate=y,
        canvas_size=geometry.render_height,
        envelope_size=max_height,
        alignment=_vertical_alignment(layout.anchor),
        field="position-y",
        dimension="max-height",
    )
    return placement


def _validate_explicit_axis(
    *,
    coordinate: int,
    canvas_size: int,
    envelope_size: int,
    alignment: str,
    field: str,
    dimension: str,
) -> None:
    if envelope_size <= 0 or envelope_size > canvas_size:
        raise ValidationError(
            f"{dimension} must resolve between 1px and {canvas_size}px"
        )
    if alignment in {"left", "top"}:
        minimum, maximum = 0, canvas_size - envelope_size
        valid = minimum <= coordinate <= maximum
    elif alignment in {"right", "bottom"}:
        minimum, maximum = envelope_size, canvas_size
        valid = minimum <= coordinate <= maximum
    else:
        minimum = (envelope_size + 1) // 2
        maximum = canvas_size - minimum
        valid = envelope_size <= 2 * coordinate and envelope_size <= 2 * (
            canvas_size - coordinate
        )
    if not valid:
        raise ValidationError(
            f"{field}={coordinate}px cannot anchor a {envelope_size}px "
            f"{dimension} with {alignment} alignment inside a {canvas_size}px "
            f"canvas; valid {field} range is {minimum}px to {maximum}px"
        )


def _horizontal_alignment(anchor: SubtitlePosition) -> str:
    if anchor.value.endswith("left"):
        return "left"
    if anchor.value.endswith("right"):
        return "right"
    return "center"


def _vertical_alignment(anchor: SubtitlePosition) -> str:
    if anchor.value.startswith("top-"):
        return "top"
    if anchor.value.startswith("bottom-"):
        return "bottom"
    return "middle"


def _effective_layout_overrides(
    config: SubtitleConfig,
    *,
    default_position: object,
    default_margins: tuple[object, object, object, object],
) -> frozenset[str]:
    """Return explicit fields, inferring typed replacements when needed."""
    overrides = set(config.layout_overrides)
    if overrides:
        return frozenset(overrides)

    layout = config.layout
    if config.layout_preset is SubtitleLayoutPreset.AUTO:
        if layout.position != default_position:
            overrides.add("position")
        for field_name, default_value in zip(
            ("margin_left", "margin_right", "margin_top", "margin_bottom"),
            default_margins,
            strict=True,
        ):
            if getattr(layout, field_name) != default_value:
                overrides.add(field_name)
    if layout.max_width is not None:
        overrides.add("max_width")
    if layout.max_height is not None:
        overrides.add("max_height")
    return frozenset(overrides)


def _validate_geometry(geometry: VideoGeometry) -> None:
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ValidationError("Video geometry must have positive render dimensions")


def _resolved_layout_int(value: int | RelativeLength, field: str) -> int:
    if isinstance(value, RelativeLength):
        raise ValidationError(
            f"{field} must be resolved against video geometry before layout use"
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
