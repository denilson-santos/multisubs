from dataclasses import replace
from fractions import Fraction

import pytest

from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.layout import (
    classify_layout_preset,
    resolve_cue_placement,
    resolve_relative_length,
    resolve_safe_rectangle,
    resolve_subtitle_config,
)
from multisubs.models import SubtitleLayoutPreset, SubtitlePosition, VideoGeometry

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
        (SubtitlePosition.TOP_LEFT, (40, 15, 1880, 1065)),
        (SubtitlePosition.TOP_CENTER, (40, 15, 1880, 1065)),
        (SubtitlePosition.TOP_RIGHT, (40, 15, 1880, 1065)),
        (SubtitlePosition.MIDDLE_LEFT, (40, 15, 1880, 1065)),
        (SubtitlePosition.CENTER, (40, 15, 1880, 1065)),
        (SubtitlePosition.MIDDLE_RIGHT, (40, 15, 1880, 1065)),
        (SubtitlePosition.BOTTOM_LEFT, (40, 15, 1880, 1065)),
        (SubtitlePosition.BOTTOM_CENTER, (40, 15, 1880, 1065)),
        (SubtitlePosition.BOTTOM_RIGHT, (40, 15, 1880, 1065)),
    ],
)
def test_named_positions_share_the_configured_safe_rectangle(position, expected):
    config = validate_subtitle_config(
        {"margin_l": 40, "margin_r": 40, "margin_v": 15},
        position=position,
    )

    rectangle = resolve_safe_rectangle(GEOMETRY, config.layout)

    assert (
        rectangle.left,
        rectangle.top,
        rectangle.right,
        rectangle.bottom,
    ) == expected
    assert (rectangle.width, rectangle.height) == (1840, 1050)


@pytest.mark.parametrize(
    "options",
    [
        {"margin_l": 1920, "margin_r": 1, "margin_v": 15},
        {"margin_l": 1, "margin_r": 1, "margin_v": 1080},
    ],
)
def test_margins_that_remove_the_safe_rectangle_are_rejected(options):
    config = validate_subtitle_config(options)

    with pytest.raises(
        ValidationError,
        match="leave no usable safe rectangle",
    ):
        resolve_safe_rectangle(GEOMETRY, config.layout)


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
    assert resolved.appearance.outline_weight == 3
    assert resolved.appearance.shadow_weight == 2
    assert resolved.layout.margin_left == 154
    assert resolved.layout.margin_right == 72
    assert resolved.layout.margin_top == 54
    assert resolved.layout.margin_bottom == 72


def test_custom_coordinates_resolve_against_render_axes():
    config = validate_subtitle_config(
        None,
        relative_values={
            "position_x": "50%",
            "position_y": "86%",
        },
        anchor="bottom-center",
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)
    placement = resolve_cue_placement(resolved, GEOMETRY)

    assert resolved.layout.position_x == 960
    assert resolved.layout.position_y == 929
    assert placement is not None
    assert (placement.position_x, placement.position_y) == (960, 929)
    assert placement.anchor is SubtitlePosition.BOTTOM_CENTER


@pytest.mark.parametrize(
    ("anchor", "position_x", "position_y"),
    [
        (SubtitlePosition.TOP_LEFT, "6%", "0%"),
        (SubtitlePosition.TOP_CENTER, "50%", "0%"),
        (SubtitlePosition.TOP_RIGHT, "94%", "0%"),
        (SubtitlePosition.MIDDLE_LEFT, "6%", "50%"),
        (SubtitlePosition.CENTER, "50%", "50%"),
        (SubtitlePosition.MIDDLE_RIGHT, "94%", "50%"),
        (SubtitlePosition.BOTTOM_LEFT, "6%", "94%"),
        (SubtitlePosition.BOTTOM_CENTER, "50%", "94%"),
        (SubtitlePosition.BOTTOM_RIGHT, "94%", "94%"),
    ],
)
def test_all_custom_anchors_resolve_inside_landscape_safe_rectangle(
    anchor, position_x, position_y
):
    config = validate_subtitle_config(
        None,
        relative_values={"position_x": position_x, "position_y": position_y},
        anchor=anchor,
    )

    placement = resolve_cue_placement(config, GEOMETRY)

    assert placement is not None
    assert placement.anchor is anchor


@pytest.mark.parametrize(
    ("position_x", "position_y", "message"),
    [
        ("0%", "86%", "position-x.*outside"),
        ("50%", "100%", "position-y.*outside"),
        ("100%", "50%", "position-x.*outside"),
    ],
)
def test_custom_anchor_outside_safe_rectangle_is_rejected(
    position_x, position_y, message
):
    config = validate_subtitle_config(
        None,
        relative_values={"position_x": position_x, "position_y": position_y},
        anchor="bottom-center",
    )

    with pytest.raises(ValidationError, match=message):
        resolve_cue_placement(config, GEOMETRY)


def test_custom_pixel_coordinates_are_bounded_by_the_canvas():
    config = validate_subtitle_config(
        None,
        relative_values={"position_x": "1921px", "position_y": "929px"},
    )

    with pytest.raises(ValidationError, match="position-x"):
        resolve_subtitle_config(config, GEOMETRY)


@pytest.mark.parametrize(
    ("position_x", "position_y", "anchor", "expected"),
    [
        ("0%", "0%", "top-left", (0, 0)),
        ("100%", "100%", "bottom-right", (1920, 1080)),
    ],
)
def test_custom_percentage_coordinates_support_canvas_edges(
    position_x, position_y, anchor, expected
):
    config = validate_subtitle_config(
        {"margin_l": 0, "margin_r": 0, "margin_v": 0},
        relative_values={"position_x": position_x, "position_y": position_y},
        anchor=anchor,
    )

    placement = resolve_cue_placement(config, GEOMETRY)

    assert placement is not None
    assert (placement.position_x, placement.position_y) == expected


def test_auto_preset_uses_post_rotation_render_aspect_ratio():
    assert classify_layout_preset(GEOMETRY) is SubtitleLayoutPreset.LANDSCAPE
    assert (
        classify_layout_preset(
            replace(
                GEOMETRY,
                render_width=90,
                render_height=160,
                coded_width=160,
                coded_height=90,
                rotation_degrees=90,
            )
        )
        is SubtitleLayoutPreset.PORTRAIT
    )


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (110, 100, SubtitleLayoutPreset.SQUARE),
        (111, 100, SubtitleLayoutPreset.LANDSCAPE),
        (90, 100, SubtitleLayoutPreset.SQUARE),
        (89, 100, SubtitleLayoutPreset.PORTRAIT),
    ],
)
def test_auto_preset_boundaries_are_exact(width, height, expected):
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

    assert classify_layout_preset(geometry) is expected


def test_preset_merge_applies_only_explicit_layout_overrides():
    config = validate_subtitle_config(
        None,
        layout_preset="portrait",
        position="top-right",
        relative_values={"margin_right": "72px"},
    )

    resolved = resolve_subtitle_config(config, GEOMETRY)

    assert resolved.layout_preset is SubtitleLayoutPreset.PORTRAIT
    assert resolved.layout.position is SubtitlePosition.TOP_RIGHT
    assert resolved.layout.margin_left == 154
    assert resolved.layout.margin_right == 72
    assert resolved.layout.margin_top == 0
    assert resolved.layout.margin_bottom == 86


@pytest.mark.parametrize(
    "relative_values",
    [
        {"font_size": "0px"},
        {"font_size": "600px"},
        {"margin_left": "100%", "margin_right": "1px"},
        {"margin_top": "100%", "margin_bottom": "1px"},
        {"outline_weight": "200%"},
    ],
)
def test_resolve_subtitle_config_rejects_geometry_dependent_values(relative_values):
    config = validate_subtitle_config(None, relative_values=relative_values)

    with pytest.raises(ValidationError):
        resolve_subtitle_config(config, GEOMETRY)
