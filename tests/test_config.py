from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest

from multisubs.config import (
    BACKDROP_CHOICES,
    FONT_WEIGHT_ALIASES,
    FONT_WEIGHT_NAMES,
    FONT_WEIGHT_RANKS,
    LAYOUT_PRESET_CHOICES,
    LAYOUT_PRESETS,
    MODELS,
    POSITION_CHOICES,
    SUPPORTED_LANGUAGES,
    get_layout_preset,
    parse_font_weight,
    parse_layout_preset,
    parse_opacity,
    parse_position,
    parse_relative_length,
    validate_subtitle_config,
)
from multisubs.errors import ValidationError
from multisubs.models import (
    FontWeight,
    FontWeightInputForm,
    RelativeLength,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleLayoutPreset,
    SubtitleOpacity,
    SubtitlePlacementMode,
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
    assert appearance.letter_spacing == parse_relative_length("0px")
    assert appearance.text_color == "#FFFFFF"
    assert appearance.font_weight is FontWeight.REGULAR
    assert appearance.font_weight_input == "regular"
    assert appearance.font_weight_input_form is FontWeightInputForm.DEFAULT
    assert appearance.italic is False
    assert appearance.backdrop is SubtitleBackdrop.BOX
    assert appearance.backdrop_color == "#00000099"
    assert appearance.backdrop_size == parse_relative_length("0px")
    assert appearance.shadow_size == parse_relative_length("4%")
    assert appearance.opacity == SubtitleOpacity(Decimal("100"), "100%")
    assert appearance.fonts_dir is None
    assert BACKDROP_CHOICES == ("none", "outline", "box")


def test_default_position_is_bottom_center_and_choices_are_named():
    config = validate_subtitle_config(None)

    assert config.layout.position is SubtitlePosition.BOTTOM_CENTER
    assert config.layout.placement_mode is SubtitlePlacementMode.NATIVE_STYLE
    assert config.layout_preset is SubtitleLayoutPreset.AUTO
    assert config.layout_overrides == frozenset()
    assert POSITION_CHOICES == tuple(position.value for position in SubtitlePosition)
    assert parse_position("top-right") is SubtitlePosition.TOP_RIGHT


def test_maximum_dimensions_are_typed_layout_values():
    config = validate_subtitle_config(
        None,
        relative_values={"max_width": "72%", "max_height": "12%"},
    )

    assert config.layout.max_width == parse_relative_length("72%")
    assert config.layout.max_height == parse_relative_length("12%")
    assert config.layout_overrides == frozenset({"max_width", "max_height"})


def test_letter_spacing_is_a_typed_appearance_length():
    config = validate_subtitle_config(
        None,
        relative_values={"letter_spacing": "4.5%"},
    )

    assert config.appearance.letter_spacing == parse_relative_length("4.5%")


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("auto", "auto"), ("AUTO", "auto"), ("125%", parse_relative_length("125%"))],
)
def test_line_height_accepts_auto_or_positive_typed_lengths(raw_value, expected):
    config = validate_subtitle_config(
        None,
        relative_values={"line_height": raw_value},
    )

    assert config.appearance.line_height == expected


@pytest.mark.parametrize("raw_value", ["0px", "0%", "64", "-1px", "1em"])
def test_line_height_rejects_non_positive_or_unitless_values(raw_value):
    with pytest.raises(ValidationError, match="line-height"):
        validate_subtitle_config(None, relative_values={"line_height": raw_value})


@pytest.mark.parametrize(
    ("raw_value", "percentage"),
    [("0%", "0"), ("75%", "75"), ("32.5%", "32.5"), ("100%", "100")],
)
def test_opacity_accepts_explicit_bounded_percentages(raw_value, percentage):
    opacity = parse_opacity(raw_value)
    config = validate_subtitle_config(
        None,
        appearance_values={"opacity": opacity},
    )

    assert config.appearance.opacity == opacity
    assert opacity.percentage == Decimal(percentage)
    assert opacity.normalized == Decimal(percentage) / Decimal(100)


@pytest.mark.parametrize(
    "raw_value",
    ["", "50", "-1%", "100.1%", "101%", "1px", "nan%", "inf%", True, 50],
)
def test_opacity_rejects_ambiguous_or_out_of_range_values(raw_value):
    with pytest.raises(ValidationError, match="opacity"):
        parse_opacity(raw_value)


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
        assert preset.layout.max_width == parse_relative_length("100%")
        assert isinstance(preset.layout.max_height, RelativeLength)
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
    assert config.appearance.font_weight is FontWeight.BOLD
    assert config.appearance.font_weight_input == "bold"
    assert (
        config.appearance.font_weight_input_form is FontWeightInputForm.BOLD_SHORTHAND
    )
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
    ("raw_value", "expected"),
    [
        ("thin", FontWeight.THIN),
        ("Extra Light", FontWeight.EXTRA_LIGHT),
        ("semi_bold", FontWeight.SEMI_BOLD),
        ("BLACK", FontWeight.BLACK),
        ("hairline", FontWeight.THIN),
        ("ultra-light", FontWeight.EXTRA_LIGHT),
        ("normal", FontWeight.REGULAR),
        ("book", FontWeight.REGULAR),
        ("demi-bold", FontWeight.SEMI_BOLD),
        ("ultra-bold", FontWeight.EXTRA_BOLD),
        ("heavy", FontWeight.BLACK),
        (100, FontWeight.THIN),
        ("400", FontWeight.REGULAR),
        (900, FontWeight.BLACK),
    ],
)
def test_parse_font_weight_accepts_names_aliases_and_numeric_ranks(raw_value, expected):
    assert parse_font_weight(raw_value) is expected


@pytest.mark.parametrize("weight", list(FontWeight))
def test_every_canonical_font_weight_name_and_rank_are_equivalent(weight):
    assert parse_font_weight(weight.canonical_name) is weight
    assert parse_font_weight(weight.canonical_name.upper()) is weight
    assert parse_font_weight(str(weight.rank)) is weight
    assert parse_font_weight(weight.rank) is weight


def test_public_font_weight_names_and_ranks_are_complete():
    assert FONT_WEIGHT_NAMES == tuple(weight.canonical_name for weight in FontWeight)
    assert FONT_WEIGHT_RANKS == tuple(weight.rank for weight in FontWeight)
    assert FONT_WEIGHT_ALIASES == (
        "hairline",
        "ultra-light",
        "normal",
        "book",
        "demi-bold",
        "ultra-bold",
        "heavy",
    )


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "unknown",
        "bold italic",
        "semi--bold",
        "semi__bold",
        "99",
        "350",
        "1000",
        "+400",
        "400.0",
        350,
        400.0,
        True,
    ],
)
def test_parse_font_weight_rejects_unknown_or_noncanonical_values(raw_value):
    with pytest.raises(ValidationError, match="font-weight"):
        parse_font_weight(raw_value)


@pytest.mark.parametrize(
    ("raw_value", "weight", "input_form"),
    [
        ("Semi Bold", FontWeight.SEMI_BOLD, FontWeightInputForm.NAME),
        ("book", FontWeight.REGULAR, FontWeightInputForm.ALIAS),
        ("300", FontWeight.LIGHT, FontWeightInputForm.NUMERIC),
    ],
)
def test_font_weight_request_metadata_preserves_input_form(
    raw_value, weight, input_form
):
    appearance = validate_subtitle_config(
        None, appearance_values={"font_weight": raw_value}
    ).appearance

    assert appearance.font_weight is weight
    assert appearance.font_weight_input == raw_value
    assert appearance.font_weight_input_form is input_form


@pytest.mark.parametrize("bold", [False, True])
def test_bold_shorthand_maps_to_regular_or_bold_weight(bold):
    appearance = validate_subtitle_config(
        None, appearance_values={"bold": bold}
    ).appearance

    assert appearance.font_weight is (FontWeight.BOLD if bold else FontWeight.REGULAR)
    assert appearance.font_weight_input_form is FontWeightInputForm.BOLD_SHORTHAND


def test_font_weight_conflicts_with_bold_shorthand():
    with pytest.raises(ValidationError, match="cannot be combined"):
        validate_subtitle_config(
            None,
            appearance_values={"font_weight": "700", "bold": True},
        )


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


def test_custom_coordinates_accept_explicit_anchor():
    config = validate_subtitle_config(
        None,
        relative_values={
            "position_x": "960px",
            "position_y": "929px",
            "max_width": "60%",
            "max_height": "12%",
        },
        anchor="top-left",
    )

    assert config.layout.anchor is SubtitlePosition.TOP_LEFT
    assert config.layout.placement_mode is SubtitlePlacementMode.EXPLICIT


@pytest.mark.parametrize(
    ("relative_values", "position", "anchor", "message"),
    [
        ({"position_x": "50%"}, None, None, "position-x and position-y"),
        ({"position_y": "86%"}, None, None, "position-x and position-y"),
        (
            {
                "position_x": "50%",
                "position_y": "86%",
                "max_width": "60%",
                "max_height": "12%",
            },
            "top-left",
            None,
            "position cannot be combined",
        ),
        ({}, None, "top-left", "anchor requires"),
        (
            {
                "position_x": "50%",
                "position_y": "86%",
                "max_width": "60%",
                "max_height": "12%",
            },
            None,
            None,
            "explicit anchor",
        ),
        (
            {"position_x": "50%", "position_y": "86%", "max_height": "12%"},
            None,
            "bottom-center",
            "max-width",
        ),
        (
            {"position_x": "50%", "position_y": "86%", "max_width": "60%"},
            None,
            "bottom-center",
            "max-height",
        ),
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


def test_typed_font_weight_metadata_is_revalidated():
    config = validate_subtitle_config(None)
    inconsistent = replace(
        config,
        appearance=replace(config.appearance, font_weight=FontWeight.BOLD),
    )

    with pytest.raises(ValidationError, match="metadata"):
        validate_subtitle_config(inconsistent)


def test_typed_letter_spacing_is_revalidated():
    config = validate_subtitle_config(None)
    inconsistent = replace(
        config,
        appearance=replace(config.appearance, letter_spacing=-1),
    )

    with pytest.raises(ValidationError, match="letter-spacing"):
        validate_subtitle_config(inconsistent)


def test_typed_opacity_metadata_is_revalidated():
    config = validate_subtitle_config(None)
    inconsistent = replace(
        config,
        appearance=replace(
            config.appearance,
            opacity=SubtitleOpacity(Decimal("50"), "75%"),
        ),
    )

    with pytest.raises(ValidationError, match="opacity metadata"):
        validate_subtitle_config(inconsistent)


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
