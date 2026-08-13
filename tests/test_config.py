import pytest

from multisubs.config import DEFAULT_STYLE, parse_style_option, validate_style_options
from multisubs.errors import ValidationError


def test_default_style_is_complete_and_copy_is_independent():
    style = validate_style_options(None)

    assert style == DEFAULT_STYLE
    style["font_size"] = 22
    assert DEFAULT_STYLE["font_size"] == 14


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("bold", "1"),
        ("alignment", "9"),
        ("primary_color", "&H80ABCDEF"),
    ],
)
def test_parse_style_option_accepts_ass_values(key, value):
    assert parse_style_option(key, value) == (
        int(value) if key not in {"primary_color"} else value
    )


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
