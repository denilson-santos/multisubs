from dataclasses import replace
from typing import Any, cast

import pytest

from multisubs.config import (
    BACKDROP_CHOICES,
    LAYOUT_PRESET_CHOICES,
    LAYOUT_PRESETS,
    MODELS,
    POSITION_CHOICES,
    SUPPORTED_LANGUAGES,
    get_layout_preset,
    parse_layout_preset,
    parse_position,
    parse_relative_length,
    validate_subtitle_config,
)
from multisubs.errors import ValidationError
from multisubs.models import (
    RelativeLength,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleLayoutPreset,
    SubtitlePosition,
)


def test_public_choices_match_supported_models_and_alignment_languages():
    assert MODELS == (
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
    assert SUPPORTED_LANGUAGES == (
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


def test_default_appearance_is_semantic_and_resolution_independent():
    appearance = validate_subtitle_config(None).appearance

    assert appearance.font == "Roboto"
    assert appearance.font_size == parse_relative_length("4%")
    assert appearance.text_color == "#FFFFFF"
    assert appearance.bold is False
    assert appearance.italic is False
    assert appearance.backdrop is SubtitleBackdrop.BOX
    assert appearance.backdrop_color == "#00000099"
    assert appearance.backdrop_size == parse_relative_length("0px")
    assert appearance.shadow_size == parse_relative_length("4%")
    assert appearance.fonts_dir is None
    assert BACKDROP_CHOICES == ("none", "outline", "box")


def test_default_position_is_bottom_center_and_choices_are_named():
    config = validate_subtitle_config(None)

    assert config.layout.position is SubtitlePosition.BOTTOM_CENTER
    assert config.layout_preset is SubtitleLayoutPreset.AUTO
    assert config.layout_overrides == frozenset()
    assert POSITION_CHOICES == tuple(position.value for position in SubtitlePosition)
    assert parse_position("top-right") is SubtitlePosition.TOP_RIGHT


def test_layout_preset_choices_and_definitions_are_complete_and_immutable():
    assert LAYOUT_PRESET_CHOICES == tuple(
        preset.value for preset in SubtitleLayoutPreset
    )
    assert parse_layout_preset("portrait") is SubtitleLayoutPreset.PORTRAIT
    assert set(LAYOUT_PRESETS) == {
        SubtitleLayoutPreset.LANDSCAPE,
        SubtitleLayoutPreset.PORTRAIT,
        SubtitleLayoutPreset.SQUARE,
        SubtitleLayoutPreset.VERTICAL_SOCIAL,
        SubtitleLayoutPreset.UPPER_THIRD,
        SubtitleLayoutPreset.CENTERED,
    }
    for preset in LAYOUT_PRESETS.values():
        assert preset.layout.position in SubtitlePosition
        assert preset.description
    with pytest.raises(TypeError):
        cast(Any, LAYOUT_PRESETS)[SubtitleLayoutPreset.LANDSCAPE] = get_layout_preset(
            "square"
        )
    with pytest.raises(AttributeError):
        cast(Any, get_layout_preset("portrait").layout).margin_left = 10


def test_explicit_layout_options_record_field_overrides():
    config = validate_subtitle_config(
        None,
        layout_preset="portrait",
        position="top-right",
        relative_values={"margin_left": "24px", "margin_bottom": "12%"},
    )

    assert config.layout_preset is SubtitleLayoutPreset.PORTRAIT
    assert config.layout_overrides == frozenset(
        {"position", "margin_left", "margin_bottom"}
    )


def test_semantic_appearance_options_build_typed_config(tmp_path):
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": "Inter",
            "text_color": "#abcdef80",
            "bold": True,
            "italic": True,
            "backdrop": "box",
            "backdrop_color": "#123456",
            "fonts_dir": fonts_dir,
        },
        position="top-right",
        relative_values={"font_size": "22px"},
    )

    assert isinstance(config, SubtitleConfig)
    assert config.appearance.font == "Inter"
    assert config.appearance.font_size == parse_relative_length("22px")
    assert config.appearance.text_color == "#ABCDEF80"
    assert config.appearance.bold is True
    assert config.appearance.italic is True
    assert config.appearance.backdrop is SubtitleBackdrop.BOX
    assert config.appearance.backdrop_color == "#123456"
    assert config.appearance.fonts_dir == fonts_dir
    assert config.layout.position is SubtitlePosition.TOP_RIGHT


@pytest.mark.parametrize(
    ("raw_value", "value", "unit", "original"),
    [
        ("8%", "8", "%", "8%"),
        (" 4.5% ", "4.5", "%", "4.5%"),
        ("72px", "72", "px", "72px"),
        ("0px", "0", "px", "0px"),
    ],
)
def test_parse_relative_length_accepts_bounded_percent_and_pixel_values(
    raw_value, value, unit, original
):
    parsed = parse_relative_length(raw_value)

    assert isinstance(parsed, RelativeLength)
    assert str(parsed.value) == value
    assert parsed.unit == unit
    assert parsed.original == original


@pytest.mark.parametrize(
    "raw_value",
    [
        "8",
        "-1px",
        "+1%",
        "1e2px",
        "1.2345%",
        "1000000px",
        "8 em",
        "nan%",
    ],
)
def test_parse_relative_length_rejects_ambiguous_or_oversized_values(raw_value):
    with pytest.raises(ValidationError, match="% or px"):
        parse_relative_length(raw_value)


def test_relative_values_are_stored_until_geometry_is_available():
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "4.5%",
            "outline_weight": "6%",
            "shadow_weight": "4%",
            "margin_left": "8%",
            "margin_right": "8%",
            "margin_top": "5px",
            "margin_bottom": "72px",
        },
    )

    assert config.appearance.font_size == parse_relative_length("4.5%")
    assert config.appearance.backdrop_size == parse_relative_length("6%")
    assert config.appearance.shadow_size == parse_relative_length("4%")
    assert config.layout.margin_left == parse_relative_length("8%")
    assert config.layout.margin_bottom == parse_relative_length("72px")


def test_custom_coordinates_store_default_anchor_and_units():
    config = validate_subtitle_config(
        None,
        relative_values={"position_x": "50%", "position_y": "86%"},
    )

    assert config.layout.position_x == parse_relative_length("50%")
    assert config.layout.position_y == parse_relative_length("86%")
    assert config.layout.anchor is SubtitlePosition.BOTTOM_CENTER


def test_custom_coordinates_accept_explicit_anchor():
    config = validate_subtitle_config(
        None,
        relative_values={"position_x": "960px", "position_y": "929px"},
        anchor="top-left",
    )

    assert config.layout.anchor is SubtitlePosition.TOP_LEFT


@pytest.mark.parametrize(
    ("relative_values", "position", "anchor", "message"),
    [
        ({"position_x": "50%"}, None, None, "position-x and position-y"),
        ({"position_y": "86%"}, None, None, "position-x and position-y"),
        (
            {"position_x": "50%", "position_y": "86%"},
            "top-left",
            None,
            "position cannot be combined",
        ),
        ({}, None, "top-left", "anchor requires"),
    ],
)
def test_custom_coordinate_conflicts_are_rejected(
    relative_values, position, anchor, message
):
    with pytest.raises(ValidationError, match=message):
        validate_subtitle_config(
            None,
            relative_values=relative_values,
            position=position,
            anchor=anchor,
        )


def test_typed_subtitle_config_is_revalidated():
    config = validate_subtitle_config(None)
    config = replace(
        config,
        layout=replace(config.layout, position=SubtitlePosition.CENTER),
    )

    assert validate_subtitle_config(config).layout.position is SubtitlePosition.CENTER


@pytest.mark.parametrize(
    "options",
    [
        {"bold": 2},
        {"text_color": "white"},
        {"font": "Roboto,Arial"},
        {"backdrop": "blur"},
        {"unknown": "value"},
    ],
)
def test_validate_semantic_appearance_rejects_invalid_values(options):
    with pytest.raises(ValidationError):
        validate_subtitle_config(None, appearance_values=options)


def test_missing_fonts_directory_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="Fonts directory not found"):
        validate_subtitle_config(
            None, appearance_values={"fonts_dir": tmp_path / "missing"}
        )


def test_raw_ass_style_mapping_is_rejected_after_cutover():
    with pytest.raises(ValidationError, match="raw ASS style mappings"):
        validate_subtitle_config({"font_size": 43})  # type: ignore[arg-type]
