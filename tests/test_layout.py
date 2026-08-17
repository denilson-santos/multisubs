from fractions import Fraction

import pytest

from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.layout import (
    resolve_relative_length,
    resolve_safe_rectangle,
    resolve_subtitle_config,
)
from multisubs.models import SubtitlePosition, VideoGeometry

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
        resolve_relative_length(
            parse_relative_length(raw_value), basis, field="test"
        )
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
