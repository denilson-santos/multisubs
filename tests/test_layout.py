from dataclasses import replace
from fractions import Fraction

import pytest

from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.layout import (
    resolve_cue_placement,
    resolve_line_height,
    resolve_native_layout_region,
    resolve_relative_length,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
    unicode_display_width,
)
from multisubs.models import SubtitlePlacementMode, SubtitlePosition, VideoGeometry
from multisubs.text_measurement import (
    TextMeasurementInfo,
    TextMeasurer,
    build_unicode_text_measurer,
)

GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1920,
    render_height=1080,
    rotation_degrees=0,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(16, 9),
    duration_seconds=10.0,
)


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        ("top-left", (40, 15, 1880, 1080)),
        ("top-center", (40, 15, 1880, 1080)),
        ("top-right", (40, 15, 1880, 1080)),
        ("middle-left", (40, 0, 1880, 1080)),
        ("center", (40, 0, 1880, 1080)),
        ("middle-right", (40, 0, 1880, 1080)),
        ("bottom-left", (40, 0, 1880, 1055)),
        ("bottom-center", (40, 0, 1880, 1055)),
        ("bottom-right", (40, 0, 1880, 1055)),
    ],
)
def test_native_positions_use_only_the_active_vertical_margin(position, expected):
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values={
            "margin_left": "40px",
            "margin_right": "40px",
            "margin_top": "15px",
            "margin_bottom": "25px",
        },
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)
    region = resolve_native_layout_region(GEOMETRY, resolved.layout)

    assert (region.left, region.top, region.right, region.bottom) == expected
    assert region.width == 1840
    assert resolve_cue_placement(resolved, GEOMETRY) is None


@pytest.mark.parametrize(
    ("position", "options", "message"),
    [
        (
            "bottom-center",
            {"margin_left": "1920px", "margin_right": "1px"},
            "native layout width",
        ),
        ("top-center", {"margin_top": "1080px"}, "top margin"),
        ("bottom-center", {"margin_bottom": "1080px"}, "bottom margin"),
    ],
)
def test_native_margins_that_remove_the_active_region_are_rejected(
    position, options, message
):
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values=options,
    )

    with pytest.raises(ValidationError, match=message):
        resolve_subtitle_config(config, GEOMETRY)


def test_unknown_position_is_rejected_before_layout_resolution():
    with pytest.raises(ValidationError, match="position must be one of"):
        validate_subtitle_config(None, position="5")


@pytest.mark.parametrize(
    ("raw_value", "basis", "expected"),
    [
        ("4.5%", 1080, 49),
        ("8%", 1920, 154),
        ("72px", 1920, 72),
        ("0px", 1080, 0),
    ],
)
def test_resolve_relative_length_uses_axis_and_deterministic_rounding(
    raw_value, basis, expected
):
    assert (
        resolve_relative_length(parse_relative_length(raw_value), basis, field="test")
        == expected
    )


def test_resolve_subtitle_config_uses_render_geometry_for_each_axis():
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "4.5%",
            "letter_spacing": "4%",
            "outline_weight": "6%",
            "shadow_weight": "4%",
            "margin_left": "8%",
            "margin_right": "72px",
            "margin_top": "5%",
            "margin_bottom": "72px",
        },
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.appearance.font_size == 49
    assert resolved.appearance.letter_spacing == 2
    assert resolved.appearance.backdrop_size == 3
    assert resolved.appearance.shadow_size == 2
    assert resolved.layout.margin_left == 154
    assert resolved.layout.margin_right == 72
    assert resolved.layout.margin_top == 54
    assert resolved.layout.margin_bottom == 72


def test_fixed_defaults_resolve_against_portrait_geometry():
    portrait_geometry = replace(
        GEOMETRY,
        coded_width=1080,
        coded_height=1920,
        render_width=1080,
        render_height=1920,
        rotation_degrees=90,
        display_aspect_ratio=Fraction(9, 16),
    )
    config = validate_subtitle_config(None)
    resolved = resolve_subtitle_config(config, portrait_geometry)
    assert isinstance(resolved.appearance.font_size, int)
    assert resolved.appearance.font_size == 77
    measurer = build_unicode_text_measurer(
        resolved.appearance.font,
        resolved.appearance.font_size,
    )
    metrics = resolve_wrapping_metrics(
        resolved,
        portrait_geometry,
        text_measurer=measurer,
    )

    assert config.layout.margin_left == parse_relative_length("18%")
    assert config.layout.max_height == parse_relative_length("10%")
    assert resolved.layout.margin_left == 194
    assert resolved.layout.margin_right == 194
    assert resolved.layout.margin_top == 96
    assert resolved.layout.margin_bottom == 96
    assert resolved.layout.max_width == 692
    assert isinstance(resolved.layout.max_height, int)
    assert resolved.layout.max_height == 182
    assert metrics.available_width == 692
    assert metrics.max_width == 692
    assert metrics.line_capacity == 1


@pytest.mark.parametrize("width", [1920, 608])
def test_percentage_font_size_uses_render_height_across_aspect_ratios(width):
    geometry = replace(
        GEOMETRY,
        coded_width=width,
        render_width=width,
        display_aspect_ratio=Fraction(width, 1080),
    )

    resolved = resolve_subtitle_config(validate_subtitle_config(None), geometry)

    assert resolved.appearance.font_size == 43


def test_pixel_font_size_is_independent_of_render_height():
    config = validate_subtitle_config(
        None,
        relative_values={"font_size": "40px"},
    )
    portrait_geometry = replace(
        GEOMETRY,
        coded_width=608,
        render_width=608,
        display_aspect_ratio=Fraction(9, 16),
    )

    assert resolve_subtitle_config(config, GEOMETRY).appearance.font_size == 40
    assert resolve_subtitle_config(config, portrait_geometry).appearance.font_size == 40


def test_letter_spacing_percentage_uses_resolved_font_size():
    config = validate_subtitle_config(
        None,
        relative_values={"font_size": "40px", "letter_spacing": "50%"},
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.appearance.font_size == 40
    assert resolved.appearance.letter_spacing == 20


def test_letter_spacing_is_bounded_relative_to_font_size():
    config = validate_subtitle_config(
        None,
        relative_values={"font_size": "40px", "letter_spacing": "161px"},
    )

    with pytest.raises(ValidationError, match="letter-spacing"):
        resolve_subtitle_config(config, GEOMETRY)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("abc", 3), ("e\u0301", 1), ("字幕", 4), ("🙂", 2)],
)
def test_unicode_display_width_is_conservative_without_string_length(text, expected):
    assert unicode_display_width(text) == expected


def _explicit_config(
    *,
    position_x: str = "50%",
    position_y: str = "86%",
    anchor: str = "bottom-center",
    max_width: str = "60%",
    max_height: str = "20%",
    margins: dict[str, str] | None = None,
):
    values = {
        "position_x": position_x,
        "position_y": position_y,
        "max_width": max_width,
        "max_height": max_height,
        **(margins or {}),
    }
    return validate_subtitle_config(None, relative_values=values, anchor=anchor)


def test_custom_coordinates_resolve_against_global_playres_axes():
    resolved = resolve_subtitle_config(_explicit_config(), GEOMETRY)
    placement = resolve_cue_placement(resolved, GEOMETRY)

    assert resolved.layout.placement_mode is SubtitlePlacementMode.EXPLICIT
    assert resolved.layout.position_x == 960
    assert resolved.layout.position_y == 929
    assert resolved.layout.max_width == 1152
    assert resolved.layout.max_height == 216
    assert placement is not None
    assert (placement.position_x, placement.position_y) == (960, 929)
    assert placement.anchor is SubtitlePosition.BOTTOM_CENTER


def test_explicit_coordinates_and_envelope_ignore_margins():
    zero = resolve_subtitle_config(_explicit_config(), GEOMETRY)
    inset = resolve_subtitle_config(
        _explicit_config(
            margins={
                "margin_left": "100px",
                "margin_right": "300px",
                "margin_top": "80px",
                "margin_bottom": "160px",
            }
        ),
        GEOMETRY,
    )

    assert inset.layout.position_x == zero.layout.position_x == 960
    assert inset.layout.position_y == zero.layout.position_y == 929
    assert inset.layout.max_width == zero.layout.max_width == 1152
    assert inset.layout.max_height == zero.layout.max_height == 216


@pytest.mark.parametrize(
    ("anchor", "position_x", "position_y"),
    [
        ("top-left", "0px", "0px"),
        ("top-center", "960px", "0px"),
        ("top-right", "1920px", "0px"),
        ("middle-left", "0px", "540px"),
        ("center", "960px", "540px"),
        ("middle-right", "1920px", "540px"),
        ("bottom-left", "0px", "1080px"),
        ("bottom-center", "960px", "1080px"),
        ("bottom-right", "1920px", "1080px"),
    ],
)
def test_all_explicit_anchors_accept_their_canvas_boundary_coordinate(
    anchor, position_x, position_y
):
    config = _explicit_config(
        position_x=position_x,
        position_y=position_y,
        anchor=anchor,
        max_width="200px",
        max_height="100px",
    )

    placement = resolve_cue_placement(config, GEOMETRY)

    assert placement is not None
    assert placement.anchor.value == anchor


def test_center_anchor_rejects_envelope_overflow_without_clamping():
    invalid = _explicit_config(
        position_x="300px",
        position_y="540px",
        anchor="center",
        max_width="1152px",
        max_height="200px",
    )

    with pytest.raises(ValidationError, match="valid position-x range is 576px"):
        resolve_subtitle_config(invalid, GEOMETRY)

    valid = _explicit_config(
        position_x="576px",
        position_y="540px",
        anchor="center",
        max_width="1152px",
        max_height="200px",
    )
    resolved = resolve_subtitle_config(valid, GEOMETRY)
    assert resolved.layout.max_width == 1152


@pytest.mark.parametrize(
    ("anchor", "position_x", "valid"),
    [
        ("top-left", "0px", True),
        ("top-left", "1px", False),
        ("top-center", "960px", True),
        ("top-center", "959px", False),
        ("top-right", "1920px", True),
        ("top-right", "1919px", False),
    ],
)
def test_full_width_explicit_envelope_has_only_one_coordinate_per_anchor(
    anchor, position_x, valid
):
    config = _explicit_config(
        position_x=position_x,
        position_y="0px",
        anchor=anchor,
        max_width="100%",
        max_height="100px",
    )

    if valid:
        assert resolve_cue_placement(config, GEOMETRY) is not None
    else:
        with pytest.raises(ValidationError, match="position-x"):
            resolve_cue_placement(config, GEOMETRY)


def test_native_max_width_percentage_recalculates_after_margin_changes():
    config = validate_subtitle_config(
        None,
        relative_values={
            "margin_left": "100px",
            "margin_right": "300px",
            "max_width": "50%",
        },
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.layout.max_width == 760


@pytest.mark.parametrize(
    ("position", "expected_basis", "expected_height"),
    [
        ("top-center", 980, 490),
        ("bottom-center", 880, 440),
        ("center", 1080, 540),
    ],
)
def test_native_max_height_uses_alignment_specific_available_height(
    position, expected_basis, expected_height
):
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values={
            "margin_top": "100px",
            "margin_bottom": "200px",
            "max_height": "50%",
        },
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)
    region = resolve_native_layout_region(GEOMETRY, resolved.layout)

    assert region.height == expected_basis
    assert resolved.layout.max_height == expected_height


def test_line_capacity_is_derived_from_max_height_and_vertical_metrics():
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Fixture",
        resolved_font="Fixture",
        resolved_style="Regular",
        font_source="fonts-dir",
        shaping="basic",
        metric_size=40,
    )
    measurer = TextMeasurer(info, lambda text: len(text) * 10, line_height=40)
    config = validate_subtitle_config(
        None,
        relative_values={"max_height": "82px", "shadow_weight": "2px"},
    )

    metrics = resolve_wrapping_metrics(config, GEOMETRY, text_measurer=measurer)

    assert metrics.max_height == 82
    assert metrics.vertical_decoration == 2
    assert metrics.line_capacity == 2


@pytest.mark.parametrize(
    ("requested", "expected"),
    [("auto", 40.0), ("100%", 40), ("125%", 50), ("64px", 64), ("64.5px", 65)],
)
def test_line_height_resolves_against_natural_metrics(requested, expected):
    assert (
        resolve_line_height(
            parse_relative_length(requested) if requested != "auto" else requested,
            40.0,
        )
        == expected
    )


def test_numeric_line_height_uses_half_up_playres_rounding():
    assert resolve_line_height(40.5, 40.0) == 41


def test_line_height_equal_to_fractional_natural_metric_never_rounds_below_it():
    assert resolve_line_height(parse_relative_length("100%"), 40.4) == 41


def test_line_height_rejects_values_below_natural_metrics():
    with pytest.raises(ValidationError, match="below the natural"):
        resolve_line_height(parse_relative_length("99%"), 40.0)


def test_explicit_line_height_reduces_capacity_using_baseline_advance():
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Fixture",
        resolved_font="Fixture",
        resolved_style="Regular",
        font_source="fonts-dir",
        shaping="basic",
        metric_size=40,
    )
    measurer = TextMeasurer(info, lambda text: len(text) * 10, line_height=40)
    config = validate_subtitle_config(
        None,
        relative_values={
            "line_height": "60px",
            "max_height": "142px",
            "shadow_weight": "2px",
        },
    )

    metrics = resolve_wrapping_metrics(config, GEOMETRY, text_measurer=measurer)

    assert metrics.natural_line_height == 40
    assert metrics.resolved_line_height == 60
    assert metrics.line_capacity == 2


def test_max_height_too_small_for_one_measured_line_is_rejected():
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Fixture",
        resolved_font="Fixture",
        resolved_style="Regular",
        font_source="fonts-dir",
        shaping="basic",
        metric_size=40,
    )
    measurer = TextMeasurer(info, lambda text: len(text) * 10, line_height=40)
    config = validate_subtitle_config(
        None,
        relative_values={"max_height": "41px", "shadow_weight": "2px"},
    )

    with pytest.raises(ValidationError, match="at least 42px"):
        resolve_wrapping_metrics(config, GEOMETRY, text_measurer=measurer)


@pytest.mark.parametrize(
    ("width", "height", "expected_margins", "expected_maximums"),
    [
        (1920, 1080, (346, 346, 54, 54), (1228, 103)),
        (1080, 1920, (194, 194, 96, 96), (692, 182)),
        (1080, 1080, (194, 194, 54, 54), (692, 103)),
    ],
)
def test_fixed_defaults_do_not_classify_aspect_ratio(
    width, height, expected_margins, expected_maximums
):
    geometry = VideoGeometry(
        stream_index=0,
        coded_width=width,
        coded_height=height,
        render_width=width,
        render_height=height,
        rotation_degrees=0,
        sample_aspect_ratio=Fraction(1, 1),
        display_aspect_ratio=Fraction(width, height),
        duration_seconds=1.0,
    )

    config = validate_subtitle_config(None)
    resolved = resolve_subtitle_config(config, geometry)

    assert config.layout.position is SubtitlePosition.BOTTOM_CENTER
    assert (
        resolved.layout.margin_left,
        resolved.layout.margin_right,
        resolved.layout.margin_top,
        resolved.layout.margin_bottom,
    ) == expected_margins
    assert (resolved.layout.max_width, resolved.layout.max_height) == expected_maximums


def test_explicit_layout_values_override_only_matching_defaults():
    config = validate_subtitle_config(
        None,
        position="top-right",
        relative_values={"margin_right": "72px"},
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.layout.position is SubtitlePosition.TOP_RIGHT
    assert resolved.layout.margin_left == 346
    assert resolved.layout.margin_right == 72
    assert resolved.layout.margin_top == 54
    assert resolved.layout.margin_bottom == 54


@pytest.mark.parametrize(
    "relative_values",
    [
        {"font_size": "0px"},
        {"font_size": "600px"},
        {"margin_left": "100%", "margin_right": "1px"},
        {"margin_bottom": "100%"},
        {"outline_weight": "200%"},
        {"max_width": "0px"},
        {"max_height": "0px"},
    ],
)
def test_resolve_subtitle_config_rejects_geometry_dependent_values(relative_values):
    config = validate_subtitle_config(None, relative_values=relative_values)

    with pytest.raises(ValidationError):
        resolve_subtitle_config(config, GEOMETRY)
