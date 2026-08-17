from dataclasses import replace
from typing import Any, cast

import pytest

from multisubs.config import (
    DEFAULT_STYLE,
    LAYOUT_PRESET_CHOICES,
    LAYOUT_PRESETS,
    MODELS,
    POSITION_CHOICES,
    SUPPORTED_LANGUAGES,
    get_layout_preset,
    parse_layout_preset,
    parse_position,
    parse_relative_length,
    parse_style_option,
    subtitle_config_to_style_options,
    validate_style_options,
    validate_subtitle_config,
)
from multisubs.errors import ValidationError
from multisubs.models import (
    RelativeLength,
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


def test_default_style_is_complete_and_copy_is_independent():
    style = validate_style_options(None)

    assert style == DEFAULT_STYLE
    style["font_size"] = 22
    assert DEFAULT_STYLE["font_size"] == 43


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
        {"margin_l": 24},
        layout_preset="portrait",
        position="top-right",
        relative_values={"margin_bottom": "12%"},
    )

    assert config.layout_preset is SubtitleLayoutPreset.PORTRAIT
    assert config.layout_overrides == frozenset(
        {"position", "margin_left", "margin_bottom"}
    )


def test_legacy_style_options_round_trip_through_typed_config():
    config = validate_subtitle_config(
        {
            "font_size": 22,
            "margin_v": 30,
        },
        position="top-right",
    )

    assert isinstance(config, SubtitleConfig)
    assert config.appearance.font_size == 22
    assert config.layout.position is SubtitlePosition.TOP_RIGHT
    assert config.layout.margin_top == 30
    assert config.layout.margin_bottom == 30
    assert subtitle_config_to_style_options(config) == {
        **DEFAULT_STYLE,
        "font_size": 22,
        "margin_v": 30,
    }


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
    assert config.appearance.outline_weight == parse_relative_length("6%")
    assert config.appearance.shadow_weight == parse_relative_length("4%")
    assert config.layout.margin_left == parse_relative_length("8%")
    assert config.layout.margin_bottom == parse_relative_length("72px")


def test_typed_subtitle_config_is_revalidated():
    config = validate_subtitle_config(None)
    config = replace(
        config,
        layout=replace(config.layout, position=SubtitlePosition.CENTER),
    )

    assert validate_subtitle_config(config).layout.position is SubtitlePosition.CENTER


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("bold", "1"),
        ("primary_color", "&H80ABCDEF"),
    ],
)
def test_parse_style_option_accepts_ass_values(key, value):
    assert parse_style_option(key, value) == (
        int(value) if key not in {"primary_color"} else value
    )


def test_parse_style_option_rejects_oversized_integer():
    with pytest.raises(ValidationError, match="must be finite"):
        parse_style_option("font_size", str(10**400))


@pytest.mark.parametrize(
    "options",
    [
        {"bold": 2},
        {"alignment": 0},
        {"border_style": 2},
        {"font_size": 0},
        {"primary_color": "white"},
        {"font": "Roboto,Arial"},
    ],
)
def test_validate_style_options_rejects_invalid_values(options):
    with pytest.raises(ValidationError):
        validate_style_options(options)
