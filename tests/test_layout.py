from dataclasses import replace
from fractions import Fraction

import pytest

from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.layout import (
    position_visual_lines,
    resolve_cue_placement,
    resolve_line_height,
    resolve_native_anchor_point,
    resolve_native_layout_region,
    resolve_relative_length,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
    unicode_display_width,
)
from multisubs.models import (
    SubtitleDisplayFragment,
    SubtitlePlacementMode,
    SubtitlePosition,
    SubtitleVisualLine,
    VideoGeometry,
)
from multisubs.templates import TEMPLATE_CHOICES, get_subtitle_template
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


def test_positioned_visual_line_uses_measured_fragment_advances():
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Test",
        resolved_font="Test",
        resolved_style="Regular",
        font_source="test",
        shaping="basic",
        metric_size=40,
    )
    measurer = TextMeasurer(
        info,
        lambda text: len(text) * 10 + max(0, len(text) - 1) * 2,
        line_height=40,
    )
    requested = validate_subtitle_config(
        None,
        position="bottom-left",
        appearance_values={"backdrop": "none"},
        relative_values={
            "font_size": "40px",
            "shadow_weight": "0px",
            "margin_left": "20px",
            "margin_right": "20px",
            "margin_bottom": "20px",
            "max_width": "400px",
            "max_height": "100px",
        },
    )
    resolved = resolve_subtitle_config(
        requested,
        GEOMETRY,
        text_measurer=measurer,
    )
    metrics = resolve_wrapping_metrics(
        resolved,
        GEOMETRY,
        text_measurer=measurer,
    )
    line = SubtitleVisualLine(
        text="one two",
        fragments=(
            SubtitleDisplayFragment("one", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("two", 1),
        ),
        width=82,
        index=0,
    )

    positioned = position_visual_lines(
        (line,),
        resolved,
        GEOMETRY,
        metrics,
        placement=None,
    )

    assert len(positioned) == 1
    assert positioned[0].position_x == 20
    assert [item.position_x for item in positioned[0].fragment_placements] == [
        37,
        61,
        85,
    ]
    assert all(
        item.anchor is SubtitlePosition.BOTTOM_CENTER
        for item in positioned[0].fragment_placements
    )


@pytest.mark.parametrize(
    "position",
    [
        "top-left",
        "top-center",
        "top-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    ],
)
def test_boxed_visual_line_uses_middle_anchor_inside_metric_cell(
    position: str,
):
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Test",
        resolved_font="Test",
        resolved_style="Regular",
        font_source="test",
        shaping="basic",
        metric_size=40,
    )
    measurer = TextMeasurer(info, lambda text: len(text) * 10, line_height=40)
    requested = validate_subtitle_config(
        None,
        position=position,
        relative_values={
            "font_size": "40px",
            "outline_weight": "8px",
            "shadow_weight": "0px",
            "max_width": "400px",
            "max_height": "100px",
        },
    )
    resolved = resolve_subtitle_config(requested, GEOMETRY, text_measurer=measurer)
    metrics = resolve_wrapping_metrics(
        resolved,
        GEOMETRY,
        text_measurer=measurer,
    )
    line = SubtitleVisualLine(
        text="sample",
        fragments=(SubtitleDisplayFragment("sample"),),
        width=60,
        index=0,
    )

    positioned = position_visual_lines(
        (line,),
        resolved,
        GEOMETRY,
        metrics,
        placement=None,
    )[0]

    assert positioned.block_placement.anchor.value == position
    assert positioned.anchor is SubtitlePosition.CENTER
    assert positioned.fragment_placements[0].anchor is SubtitlePosition.CENTER
    content_top = positioned.backdrop_bounds[1] + metrics.backdrop_size
    assert positioned.position_y == round(content_top + metrics.natural_line_height / 2)
    expected_x = round(
        (positioned.backdrop_bounds[0] + positioned.backdrop_bounds[2]) / 2
    )
    assert positioned.position_x == expected_x


def test_positioned_visual_line_separates_filled_box_from_shadow_envelope():
    info = TextMeasurementInfo(
        mode="font-metrics",
        requested_font="Test",
        resolved_font="Test",
        resolved_style="Regular",
        font_source="test",
        shaping="basic",
        metric_size=40,
    )
    measurer = TextMeasurer(info, lambda text: len(text) * 10, line_height=40)
    config = validate_subtitle_config(
        None,
        position="bottom-right",
        relative_values={
            "font_size": "40px",
            "outline_weight": "8px",
            "shadow_weight": "4px",
            "margin_bottom": "20px",
            "max_width": "400px",
            "max_height": "100px",
        },
    )
    resolved = resolve_subtitle_config(config, GEOMETRY, text_measurer=measurer)
    metrics = resolve_wrapping_metrics(
        resolved,
        GEOMETRY,
        text_measurer=measurer,
    )
    line = SubtitleVisualLine(
        text="sample",
        fragments=(SubtitleDisplayFragment("sample"),),
        width=100,
        index=0,
    )

    positioned = position_visual_lines(
        (line,),
        resolved,
        GEOMETRY,
        metrics,
        placement=None,
    )[0]

    assert positioned.block_bounds[2] - positioned.backdrop_bounds[2] == 4
    assert positioned.block_bounds[3] - positioned.backdrop_bounds[3] == 4
    assert positioned.backdrop_bounds[2] - positioned.backdrop_bounds[0] == 116
    assert positioned.backdrop_bounds[3] - positioned.backdrop_bounds[1] == 56


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
def test_native_positions_use_the_active_vertical_margin(position, expected):
    relative_values = {
        "margin_left": "40px",
        "margin_right": "40px",
    }
    if position.startswith("top-"):
        relative_values["margin_top"] = "15px"
    elif position.startswith("bottom-"):
        relative_values["margin_bottom"] = "25px"
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values=relative_values,
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
            "margin_bottom": "72px",
        },
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.style.typography.font_size == 49
    assert resolved.style.typography.letter_spacing == 2
    assert resolved.style.backdrop.size == 3
    assert resolved.style.shadow.size == 2
    assert resolved.layout.margin_left == 154
    assert resolved.layout.margin_right == 72
    assert resolved.layout.margin_top == 0
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
    assert isinstance(resolved.style.typography.font_size, int)
    assert resolved.style.typography.font_size == 77
    measurer = build_unicode_text_measurer(
        resolved.style.typography.font,
        resolved.style.typography.font_size,
    )
    metrics = resolve_wrapping_metrics(
        resolved,
        portrait_geometry,
        text_measurer=measurer,
    )

    assert config.layout.margin_left == parse_relative_length("18%")
    assert config.layout.max_height == parse_relative_length("11.64%")
    assert resolved.layout.margin_left == 194
    assert resolved.layout.margin_right == 194
    assert resolved.layout.margin_top == 0
    assert resolved.layout.margin_bottom == 58
    assert resolved.layout.max_width == 692
    assert isinstance(resolved.layout.max_height, int)
    assert resolved.layout.max_height == 223
    assert metrics.available_width == 692
    assert metrics.max_width == 692
    assert metrics.line_capacity == 2


@pytest.mark.parametrize("width", [1920, 608])
def test_percentage_font_size_uses_render_height_across_aspect_ratios(width):
    geometry = replace(
        GEOMETRY,
        coded_width=width,
        render_width=width,
        display_aspect_ratio=Fraction(width, 1080),
    )

    resolved = resolve_subtitle_config(validate_subtitle_config(None), geometry)

    assert resolved.style.typography.font_size == 43


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

    assert resolve_subtitle_config(config, GEOMETRY).style.typography.font_size == 40
    assert (
        resolve_subtitle_config(config, portrait_geometry).style.typography.font_size
        == 40
    )


def test_letter_spacing_percentage_uses_resolved_font_size():
    config = validate_subtitle_config(
        None,
        relative_values={"font_size": "40px", "letter_spacing": "50%"},
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.style.typography.font_size == 40
    assert resolved.style.typography.letter_spacing == 20


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


@pytest.mark.parametrize("template", TEMPLATE_CHOICES)
@pytest.mark.parametrize("width,height", [(1920, 1080), (1080, 1920), (1279, 719)])
def test_custom_defaults_preserve_every_template_native_geometry(
    template, width, height
):
    geometry = replace(GEOMETRY, render_width=width, render_height=height)
    baseline = get_subtitle_template(template).config
    native = resolve_subtitle_config(baseline, geometry)
    custom = resolve_subtitle_config(
        validate_subtitle_config(
            None, defaults=baseline, anchor=baseline.layout.position
        ),
        geometry,
    )
    region = resolve_native_layout_region(geometry, native.layout)
    assert (
        custom.layout.position_x,
        custom.layout.position_y,
    ) == resolve_native_anchor_point(baseline.layout.position, region)
    assert custom.layout.max_width == native.layout.max_width
    assert custom.layout.max_height == native.layout.max_height
    assert not custom.layout.max_width_inherited
    assert resolve_subtitle_config(custom, geometry) == custom


@pytest.mark.parametrize(
    "anchor,x,y",
    [
        ("top-left", 346, 0),
        ("top-center", 960, 0),
        ("top-right", 1574, 0),
        ("middle-left", 346, 540),
        ("center", 960, 540),
        ("middle-right", 1574, 540),
        ("bottom-left", 346, 1048),
        ("bottom-center", 960, 1048),
        ("bottom-right", 1574, 1048),
    ],
)
def test_anchor_alone_uses_its_native_point_and_preserves_template_dimensions(
    anchor, x, y
):
    resolved = resolve_subtitle_config(
        validate_subtitle_config(None, anchor=anchor), GEOMETRY
    )
    assert (resolved.layout.position_x, resolved.layout.position_y) == (x, y)
    # Resolve each 18% margin before subtraction, just as native ASS does.
    assert resolved.layout.max_width == 1228
    assert resolved.layout.max_height == 126


@pytest.mark.parametrize("max_width,max_height", [("80%", "12.5%"), ("900px", "120px")])
def test_custom_defaults_resolve_asymmetric_mixed_unit_template_margins(
    max_width, max_height
):
    baseline = validate_subtitle_config(
        None,
        relative_values={
            "margin_left": "12.5%",
            "margin_right": "73px",
            "margin_bottom": "34px",
            "max_width": max_width,
            "max_height": max_height,
        },
    )
    native = resolve_subtitle_config(baseline, GEOMETRY)
    resolved = resolve_subtitle_config(
        validate_subtitle_config(None, defaults=baseline, anchor="bottom-center"),
        GEOMETRY,
    )
    assert resolved.layout.position_x == 1043
    assert resolved.layout.position_y == 1046
    assert resolved.layout.max_width == native.layout.max_width
    assert resolved.layout.max_height == native.layout.max_height


@pytest.mark.parametrize(
    "field,value,x,y",
    [("position_x", "60%", 1152, 1048), ("position_y", "86%", 960, 929)],
)
def test_one_coordinate_overrides_only_its_axis(field, value, x, y):
    resolved = resolve_subtitle_config(
        validate_subtitle_config(None, relative_values={field: value}), GEOMETRY
    )
    assert resolved.layout.anchor is SubtitlePosition.BOTTOM_CENTER
    assert (resolved.layout.position_x, resolved.layout.position_y) == (x, y)
    assert resolved.layout.max_width == 1228
    assert resolved.layout.max_height == 126


@pytest.mark.parametrize(
    "overrides,width,height",
    [
        ({"max_width": "70%"}, 1344, 126),
        ({"max_height": "20%"}, 1228, 216),
        ({"max_width": "900px", "max_height": "100px"}, 900, 100),
    ],
)
def test_explicit_dimensions_use_full_canvas_without_reapplying_margins(
    overrides, width, height
):
    resolved = resolve_subtitle_config(
        validate_subtitle_config(
            None, relative_values={"position_y": "86%", **overrides}
        ),
        GEOMETRY,
    )
    assert resolved.layout.max_width == width
    assert resolved.layout.max_height == height


@pytest.mark.parametrize(
    "field,dimension", [("position_x", "max-width"), ("position_y", "max-height")]
)
def test_sparse_coordinate_envelopes_are_rejected_instead_of_shrunk(field, dimension):
    config = validate_subtitle_config(None, relative_values={field: "1%"})
    with pytest.raises(ValidationError, match=dimension):
        resolve_subtitle_config(config, GEOMETRY)


def test_explicit_coordinates_reject_user_supplied_margins():
    with pytest.raises(ValidationError, match="cannot be combined"):
        _explicit_config(
            margins={
                "margin_left": "100px",
                "margin_right": "300px",
                "margin_top": "80px",
                "margin_bottom": "160px",
            }
        )


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
    ("position", "expected_basis"),
    [
        ("top-center", 980),
        ("bottom-center", 880),
        ("center", 1080),
    ],
)
def test_native_max_height_uses_full_height_for_every_alignment(
    position, expected_basis
):
    relative_values = {"max_height": "50%"}
    if position.startswith("top-"):
        relative_values["margin_top"] = "100px"
    elif position.startswith("bottom-"):
        relative_values["margin_bottom"] = "200px"
    config = validate_subtitle_config(
        None, position=position, relative_values=relative_values
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)
    region = resolve_native_layout_region(GEOMETRY, resolved.layout)

    assert region.height == expected_basis
    assert resolved.layout.max_height == 540


@pytest.mark.parametrize("position", ["top-center", "bottom-center"])
@pytest.mark.parametrize("margin", ["0%", "3%", "20%", "300px"])
def test_vertical_margins_preserve_explicit_height_and_line_capacity(position, margin):
    margin_field = "margin_top" if position.startswith("top-") else "margin_bottom"
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values={margin_field: margin, "max_height": "12%"},
    )
    metrics = resolve_wrapping_metrics(config, GEOMETRY)
    assert metrics.max_height == 130
    assert metrics.line_capacity == 2


@pytest.mark.parametrize("position", ["top-center", "bottom-center"])
@pytest.mark.parametrize("height", ["10%", "108px"])
def test_native_max_height_rejects_overflow_without_reducing_height(position, height):
    margin_field = "margin_top" if position.startswith("top-") else "margin_bottom"
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values={margin_field: "972px", "max_height": height},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    assert resolved.layout.max_height == 108
    assert resolve_subtitle_config(resolved, GEOMETRY) == resolved
    invalid = replace(config, layout=replace(config.layout, **{margin_field: 973}))
    with pytest.raises(
        ValidationError, match="leaves only 107px; reduce the margin or max-height"
    ):
        resolve_subtitle_config(invalid, GEOMETRY)


def test_lateral_margins_change_width_while_preserving_height_and_line_capacity():
    baseline = resolve_wrapping_metrics(validate_subtitle_config(None), GEOMETRY)
    narrowed = resolve_wrapping_metrics(
        validate_subtitle_config(
            None, relative_values={"margin_left": "25%", "margin_right": "25%"}
        ),
        GEOMETRY,
    )
    assert narrowed.max_width == 960
    assert narrowed.max_width < baseline.max_width
    assert narrowed.max_height == baseline.max_height
    assert narrowed.line_capacity == baseline.line_capacity == 2


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
        appearance_values={"backdrop": "none"},
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
        appearance_values={"backdrop": "none"},
        relative_values={"max_height": "41px", "shadow_weight": "2px"},
    )

    with pytest.raises(ValidationError, match="at least 42px"):
        resolve_wrapping_metrics(config, GEOMETRY, text_measurer=measurer)


@pytest.mark.parametrize(
    ("width", "height", "expected_margins", "expected_maximums"),
    [
        (1920, 1080, (346, 346, 0, 32), (1228, 126)),
        (1080, 1920, (194, 194, 0, 58), (692, 223)),
        (1080, 1080, (194, 194, 0, 32), (692, 126)),
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
    assert resolved.layout.margin_top == 0
    assert resolved.layout.margin_bottom == 32


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
