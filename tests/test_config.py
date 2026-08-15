from dataclasses import replace

import pytest

from multisubs.config import (
    DEFAULT_STYLE,
    MODELS,
    POSITION_CHOICES,
    SUPPORTED_LANGUAGES,
    parse_position,
    parse_style_option,
    subtitle_config_to_style_options,
    validate_style_options,
    validate_subtitle_config,
)
from multisubs.errors import ValidationError
from multisubs.models import SubtitleConfig, SubtitlePosition


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
    assert POSITION_CHOICES == tuple(position.value for position in SubtitlePosition)
    assert parse_position("top-right") is SubtitlePosition.TOP_RIGHT


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
