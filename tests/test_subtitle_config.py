"""Public sparse presentation composition and parity with the native CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from types import MappingProxyType

import pytest
from test_cli_helpers import TestParser

from multisubs import (
    MultisubsError,
    SubtitleConfig,
    TemplateError,
    ValidationError,
    build_subtitle_config,
    cli,
)
from multisubs.layout import resolve_subtitle_config
from multisubs.models import (
    CueAnimationType,
    RelativeLength,
    SubtitleBackdrop,
    VideoGeometry,
)
from multisubs.templates import TEMPLATE_CHOICES, get_subtitle_template

# Independent inventory of the 57 public presentation options and their output.
_OPTION_CASES = [
    ("position", "top-right", "layout.position.value", "top-right"),
    ("font", "Inter", "style.typography.font", "Inter"),
    ("text_color", "#aabbcc80", "style.typography.color", "#AABBCC80"),
    ("font_weight", "600", "style.typography.font_weight.rank", 600),
    ("bold", False, "style.typography.font_weight.rank", 400),
    ("italic", False, "style.typography.italic", False),
    ("backdrop", "outline", "style.backdrop.kind.value", "outline"),
    ("backdrop_color", "#aabbcc80", "style.backdrop.color", "#AABBCC80"),
    ("word_backdrop", "box", "style.word_backdrop.kind.value", "box"),
    ("word_backdrop_color", "#aabbcc80", "style.word_backdrop.color", "#AABBCC80"),
    ("opacity", "32.5%", "style.opacity.original", "32.5%"),
    ("text_case", "UPPERCASE", "style.typography.text_case.value", "uppercase"),
    ("fonts_dir", None, "style.typography.fonts_dir", None),
    ("font_size", "4.5%", "style.typography.font_size.original", "4.5%"),
    ("letter_spacing", "2px", "style.typography.letter_spacing.original", "2px"),
    ("line_height", "125%", "style.typography.line_height.original", "125%"),
    ("backdrop_size", "12%", "style.backdrop.size.original", "12%"),
    ("word_backdrop_size", "3px", "style.word_backdrop.size.original", "3px"),
    ("shadow_size", "4px", "style.shadow.size.original", "4px"),
    ("margin_left", "5%", "layout.margin_left.original", "5%"),
    ("margin_right", "6%", "layout.margin_right.original", "6%"),
    ("margin_top", "7%", "layout.margin_top.original", "7%"),
    ("margin_bottom", "8%", "layout.margin_bottom.original", "8%"),
    ("max_width", "60%", "layout.max_width.original", "60%"),
    ("max_height", "20%", "layout.max_height.original", "20%"),
    ("position_x", "50%", "layout.position_x.original", "50%"),
    ("position_y", "80%", "layout.position_y.original", "80%"),
    ("anchor", "bottom-center", "layout.anchor.value", "bottom-center"),
    (
        "animation_word_text_mode",
        "progressive",
        "animation.word.text.mode.value",
        "progressive",
    ),
    (
        "animation_word_backdrop_mode",
        "progressive",
        "animation.word.backdrop.mode.value",
        "progressive",
    ),
    (
        "animation_word_text_highlight_color",
        "#abcdef",
        "style.typography.highlight_color",
        "#ABCDEF",
    ),
    ("disable_cue_animations", True, "animation.cue.text.enabled", False),
    ("disable_word_animations", True, "animation.word.text.enabled", False),
]
for _scope in ("cue", "word"):
    for _element in ("text", "backdrop"):
        for _phase in ("entrance", "emphasis", "exit"):
            _key = f"animation_{_scope}_{_element}_{_phase}"
            _path = f"animation.{_scope}.{_element}.{_phase}"
            _effect = "pulse" if _phase == "emphasis" else "fade"
            _OPTION_CASES.extend(
                [
                    (_key, _effect, f"{_path}.type.value", _effect),
                    (f"{_key}_duration", "0.25s", f"{_path}.duration_ms", 250),
                ]
            )

_COORDINATES = {
    "position_x": "50%",
    "position_y": "80%",
    "anchor": "bottom-center",
    "max_width": "60%",
    "max_height": "20%",
}


def _cli_config(overrides, *, template="yellow-pop", template_dir=None):
    argv = ["-i", "unused.mp4", "--template", template]
    if template_dir is not None:
        argv.extend(["--template-dir", str(template_dir)])
    for key, value in overrides.items():
        if value is None:
            continue
        flag = "--" + key.replace("_", "-")
        if key in {"bold", "italic"}:
            argv.append(flag if value else "--no-" + key)
        elif isinstance(value, bool):
            if value:
                argv.append(flag)
        else:
            argv.extend([flag, str(value)])
    parser = TestParser()
    return cli._resolve_request_config(parser.parse_args(argv), parser)[1]


@pytest.mark.parametrize("template", TEMPLATE_CHOICES)
def test_empty_overrides_reproduce_every_builtin(template):
    baseline = get_subtitle_template(template).config
    assert build_subtitle_config(template=template) == baseline
    assert build_subtitle_config(template=template, overrides={}) == baseline
    assert (
        build_subtitle_config(template=template, overrides={"italic": None}) == baseline
    )
    assert _cli_config({}, template=template) == baseline


def test_omitted_template_is_default():
    assert build_subtitle_config() == build_subtitle_config(template="default")


def test_one_override_preserves_other_template_fields_and_requests():
    baseline = get_subtitle_template("yellow-pop").config
    values = MappingProxyType({"text_color": "#abcdef", "italic": None})
    first = build_subtitle_config(template="yellow-pop", overrides=values)
    expected = replace(
        baseline,
        style=replace(
            baseline.style,
            typography=replace(baseline.style.typography, color="#ABCDEF"),
        ),
    )
    assert first == expected
    second = build_subtitle_config(
        template="yellow-pop", overrides={"font_size": "50px"}
    )
    assert second.style.typography.color == baseline.style.typography.color
    assert first == expected
    assert get_subtitle_template("yellow-pop").config == baseline
    assert values == {"text_color": "#abcdef", "italic": None}
    assert isinstance(first, SubtitleConfig)
    with pytest.raises(FrozenInstanceError):
        first.style.typography.italic = True  # type: ignore[misc]


@pytest.mark.parametrize("key,value,path,expected", _OPTION_CASES, ids=lambda v: str(v))
def test_all_presentation_options_match_cli(tmp_path, key, value, path, expected):
    assert len(_OPTION_CASES) == 57
    overrides = {}
    if key in {"position_x", "position_y", "anchor"}:
        overrides.update(_COORDINATES)
    if key == "margin_top":
        overrides["position"] = "top-right"
    if key.endswith("_duration"):
        phase = key.removesuffix("_duration")
        overrides[phase] = "pulse" if phase.endswith("_emphasis") else "fade"
    if key == "fonts_dir":
        value = expected = tmp_path
    overrides[key] = value
    config = build_subtitle_config(template="yellow-pop", overrides=overrides)
    assert config == _cli_config(overrides)
    actual = config
    for part in path.split("."):
        actual = getattr(actual, part)
    assert actual == expected


def test_false_zero_and_none_remain_distinct():
    baseline = build_subtitle_config(template="yellow-pop", overrides={"italic": True})
    overrides = {
        "italic": False,
        "bold": False,
        "opacity": "0%",
        "letter_spacing": "0px",
        "backdrop_size": "0%",
        "word_backdrop_size": "0px",
        "shadow_size": "0px",
        "margin_bottom": "0%",
        "disable_word_animations": False,
        "animation_word_text_emphasis": None,
    }
    config = build_subtitle_config(template="yellow-pop", overrides=overrides)
    assert config == _cli_config(overrides)
    assert config.style.typography.italic is False
    assert config.style.typography.font_weight.rank == 400
    assert config.style.opacity.percentage == 0
    assert config.animation == baseline.animation
    assert (
        config.style.typography.highlight_color
        == baseline.style.typography.highlight_color
    )
    for length in (
        config.style.typography.letter_spacing,
        config.style.backdrop.size,
        config.style.word_backdrop.size,
        config.style.shadow.size,
        config.layout.margin_bottom,
    ):
        assert isinstance(length, RelativeLength)
        assert length.value == 0
    inherited = build_subtitle_config(
        template="yellow-pop", overrides={"italic": None, "bold": None}
    )
    assert inherited == get_subtitle_template("yellow-pop").config


@pytest.mark.parametrize("font_size", ["0px", "101%", "999999px"])
def test_geometry_dependent_font_bounds_remain_deferred(font_size):
    from multisubs.layout import resolve_subtitle_config

    overrides = {"font_size": font_size}
    config = build_subtitle_config(template="yellow-pop", overrides=overrides)
    assert config == _cli_config(overrides)
    assert isinstance(config.style.typography.font_size, RelativeLength)
    assert config.style.typography.font_size.original == font_size
    geometry = VideoGeometry(
        0, 640, 360, 640, 360, 0, Fraction(1), Fraction(16, 9), 4.0
    )
    with pytest.raises(ValidationError, match="font-size"):
        resolve_subtitle_config(config, geometry)


@pytest.mark.parametrize("disable_cue", [False, True])
@pytest.mark.parametrize("disable_word", [False, True])
def test_scoped_disables_apply_last(disable_cue, disable_word):
    overrides = {
        "word_backdrop": "box",
        "animation_cue_text_entrance": "fade",
        "animation_cue_backdrop_exit": "zoom",
        "animation_word_text_entrance": "pop",
        "animation_word_backdrop_exit": "fade",
        "disable_cue_animations": disable_cue,
        "disable_word_animations": disable_word,
    }
    baseline = build_subtitle_config(template="yellow-pop")
    config = build_subtitle_config(template="yellow-pop", overrides=overrides)
    assert config == _cli_config(overrides)
    assert config.style.backdrop == baseline.style.backdrop
    assert config.animation.cue.text.enabled is not disable_cue
    assert config.animation.cue.backdrop.enabled is not disable_cue
    assert config.animation.word.text.enabled is not disable_word
    assert config.animation.word.backdrop.enabled is not disable_word
    if disable_word:
        assert config.style.typography.highlight_color is None
        assert config.style.word_backdrop.kind is SubtitleBackdrop.NONE
    else:
        assert config.style.typography.highlight_color is not None
        assert config.style.word_backdrop.kind is SubtitleBackdrop.BOX


def test_disabling_inherited_highlight_clears_its_color():
    config = build_subtitle_config(
        template="yellow-pop", overrides={"animation_word_text_emphasis": "none"}
    )
    assert config.animation.word.text.emphasis.type is CueAnimationType.NONE
    assert config.style.typography.highlight_color is None


@pytest.mark.parametrize("name", ["default", "yellow-pop", "my-caption"])
@pytest.mark.parametrize("string_path", [False, True])
def test_custom_template_precedence_and_sparse_overrides(tmp_path, name, string_path):
    (tmp_path / "custom.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": name,
                "base": "yellow-pop",
                "style": {"typography": {"italic": True}},
                "layout": {"margins": {"bottom": "15%"}},
            }
        ),
        encoding="utf-8",
    )
    directory = str(tmp_path) if string_path else tmp_path
    baseline = build_subtitle_config(template=name, template_dir=directory)
    assert baseline == _cli_config({}, template=name, template_dir=directory)
    assert baseline.style.typography.italic is True
    assert isinstance(baseline.layout.margin_bottom, RelativeLength)
    assert baseline.layout.margin_bottom.original == "15%"
    config = build_subtitle_config(
        template=name, template_dir=directory, overrides={"italic": False}
    )
    assert config.style.typography.italic is False
    assert config.layout == baseline.layout
    assert config.animation == baseline.animation
    assert config == _cli_config(
        {"italic": False}, template=name, template_dir=directory
    )
    assert build_subtitle_config(template=name, template_dir=directory) == baseline
    if name == "default":
        assert build_subtitle_config(template_dir=directory) == baseline
    assert build_subtitle_config() == get_subtitle_template("default").config


def test_every_discovered_custom_file_is_validated(tmp_path):
    (tmp_path / "unselected.json").write_text("{", encoding="utf-8")
    with pytest.raises(TemplateError, match="unselected.json"):
        build_subtitle_config(template="yellow-pop", template_dir=tmp_path)


@pytest.mark.parametrize("as_string", [False, True])
def test_font_directory_accepts_paths_without_loading_fonts(tmp_path, as_string):
    directory = str(tmp_path) if as_string else tmp_path
    config = build_subtitle_config(
        overrides={"fonts_dir": directory, "line_height": "auto"}
    )
    assert config.style.typography.fonts_dir == tmp_path
    assert config.style.typography.line_height == "auto"


_SPARSE_COORDINATES = [
    {"position_x": "50%"},
    {"position_y": "50%"},
    {"anchor": "center"},
    {key: value for key, value in _COORDINATES.items() if key != "anchor"},
    {key: value for key, value in _COORDINATES.items() if key != "max_width"},
    {key: value for key, value in _COORDINATES.items() if key != "max_height"},
]


@pytest.mark.parametrize("overrides", _SPARSE_COORDINATES)
@pytest.mark.parametrize("template", ["default", "golden-title"])
def test_sparse_coordinates_inherit_template_defaults_and_match_cli(
    overrides, template
):
    baseline = get_subtitle_template(template).config
    config = build_subtitle_config(template=template, overrides=overrides)
    assert config == _cli_config(overrides, template=template)
    assert config.layout.has_custom_coordinates
    assert config.layout.anchor is not None
    assert config.layout.anchor.value == overrides.get(
        "anchor", baseline.layout.position.value
    )
    assert config.layout.max_width_inherited == ("max_width" not in overrides)
    if "max_width" not in overrides:
        assert config.layout.max_width == baseline.layout.max_width
    if "max_height" not in overrides:
        assert config.layout.max_height == baseline.layout.max_height
    assert get_subtitle_template(template).config == baseline


@pytest.mark.parametrize("position", ["top-right", "center", "bottom-left"])
def test_custom_coordinate_defaults_use_local_template_layout(tmp_path, position):
    (tmp_path / "caption.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "caption",
                "layout": {
                    "position": position,
                    "margins": {
                        "left": "12.5%",
                        "right": "73px",
                        "top": "21px",
                        "bottom": "15%",
                    },
                    "max_width": "80%",
                    "max_height": "17%",
                },
            }
        ),
        encoding="utf-8",
    )
    baseline = build_subtitle_config(template="caption", template_dir=tmp_path)
    overrides = {"position_y": "50%"}
    custom = build_subtitle_config(
        template="caption", template_dir=tmp_path, overrides=overrides
    )
    assert custom == _cli_config(overrides, template="caption", template_dir=tmp_path)
    geometry = VideoGeometry(
        0, 1920, 1080, 1920, 1080, 0, Fraction(1), Fraction(16, 9), 10
    )
    native = resolve_subtitle_config(baseline, geometry)
    resolved = resolve_subtitle_config(custom, geometry)
    assert resolved.layout.anchor is not None
    assert resolved.layout.anchor.value == position
    assert resolved.layout.position_y == 540
    assert resolved.layout.max_width == native.layout.max_width
    assert resolved.layout.max_height == native.layout.max_height
    assert (
        resolved.layout.position_x
        == {"top-right": 1847, "center": 1043, "bottom-left": 240}[position]
    )


_INVALID_COMBINATIONS = [
    {"font_weight": "bold", "bold": False},
    {"position_x": "50%", "position": "bottom-center"},
    {"position_y": "50%", "position": "bottom-center"},
    {"anchor": "center", "position": "bottom-center"},
    {**_COORDINATES, "position": "bottom-center"},
    *(
        {**_COORDINATES, key: "0px"}
        for key in ("margin_left", "margin_right", "margin_top", "margin_bottom")
    ),
    {"position": "top-left", "margin_bottom": "0%"},
    {"position": "bottom-left", "margin_top": "0%"},
    {"position": "center", "margin_top": "0%"},
    {"position": "center", "margin_bottom": "0%"},
    {"line_height": "0px"},
    {"opacity": "101%"},
    {"font": "bad,font"},
    {"font_weight": "650"},
    {"text_color": "red"},
    {
        "animation_word_text_emphasis": "none",
        "animation_word_text_highlight_color": "#ABCDEF",
    },
    {"animation_cue_text_entrance_duration": "100ms"},
    {"animation_word_text_emphasis_duration": "100ms"},
    {
        "animation_cue_text_entrance": "fade",
        "animation_cue_text_entrance_duration": "0ms",
    },
    {
        "animation_cue_text_entrance": "fade",
        "animation_cue_text_entrance_duration": "5001ms",
    },
    {
        "animation_cue_text_entrance": "fade",
        "animation_cue_text_entrance_duration": "0.1ms",
    },
    {
        "animation_word_text_emphasis": "none",
        "animation_word_text_highlight_color": "#ABCDEF",
        "disable_word_animations": True,
    },
]


@pytest.mark.parametrize("overrides", _INVALID_COMBINATIONS)
def test_combination_errors_match_cli_before_media(overrides):
    with pytest.raises(ValidationError) as error:
        build_subtitle_config(template="yellow-pop", overrides=overrides)
    with pytest.raises(SystemExit) as cli_error:
        _cli_config(overrides)
    assert str(error.value) in str(cli_error.value.__cause__)


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"unknown": None}, "Unknown subtitle override.*unknown"),
        ({"outline_weight": "1px"}, "Unknown subtitle override.*outline_weight"),
        ({"shadow_weight": "1px"}, "Unknown subtitle override.*shadow_weight"),
        ({"--font-size": "4%"}, "Unknown subtitle override.*--font-size"),
        ({1: "value"}, "names must be strings"),
        ([], "must be a mapping"),
        ({"italic": "false"}, "italic must be enabled or disabled"),
        ({"bold": 0}, "bold must be enabled or disabled"),
        ({"disable_cue_animations": 1}, "disable-cue-animations must be enabled"),
        (
            {"disable_word_animations": "true"},
            "disable-word-animations must be enabled",
        ),
        ({"font_size": 0}, "font-size must be a relative length"),
        ({"font_size": "4"}, "length must be a non-negative number"),
        ({"position": []}, "position must be one of"),
        ({"anchor": 5}, "position must be one of"),
        ({"backdrop": "invalid"}, "backdrop must be one of"),
        ({"text_case": "invalid"}, "text-case must be original"),
        ({"opacity": 0}, "opacity must use the typed SubtitleOpacity contract"),
        ({"fonts_dir": 5}, "fonts-dir must be a directory path"),
        ({"animation_word_text_mode": "invalid"}, "word animation mode"),
        ({"animation_cue_text_exit": "pop"}, "animation-cue-text-exit must be one of"),
        ({"animation_word_backdrop_emphasis": "highlight"}, "word-backdrop-emphasis"),
    ],
)
def test_invalid_override_values_have_public_actionable_errors(overrides, match):
    with pytest.raises(ValidationError, match=match):
        build_subtitle_config(overrides=overrides)


def test_public_error_contract_and_bad_template_inputs(tmp_path):
    assert issubclass(ValidationError, MultisubsError)
    assert issubclass(TemplateError, MultisubsError)
    with pytest.raises(ValidationError, match="subtitle-template must be one of"):
        build_subtitle_config(template="missing")
    with pytest.raises(ValidationError, match="template name"):
        build_subtitle_config(template=[])  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="directory path"):
        build_subtitle_config(template_dir=1)  # type: ignore[arg-type]
    with pytest.raises(TemplateError, match="directory not found"):
        build_subtitle_config(template_dir=tmp_path / "missing")
    with pytest.raises(ValidationError, match="Fonts directory not found"):
        build_subtitle_config(overrides={"fonts_dir": tmp_path / "missing"})
    with pytest.raises(
        ValidationError, match="Could not resolve fonts directory"
    ) as error:
        build_subtitle_config(overrides={"fonts_dir": "\0"})
    assert isinstance(error.value.__cause__, ValueError)


def test_imports_and_composition_are_lazy_and_have_no_expensive_io():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import multisubs
assert 'multisubs.subtitle_config' not in sys.modules
assert 'multisubs.models' not in sys.modules

def forbid_work(event, args):
    if event in {'subprocess.Popen', 'os.system', 'socket.connect', 'os.mkdir'}:
        raise AssertionError(event)
    if event == 'open' and isinstance(args[0], str):
        assert not args[0].endswith(('.ttf', '.otf', '.ttc')), args[0]

sys.addaudithook(forbid_work)
from multisubs import build_subtitle_config, SubtitleConfig
from multisubs import MultisubsError, ValidationError, TemplateError
assert isinstance(build_subtitle_config(), SubtitleConfig)
assert isinstance(build_subtitle_config(template='yellow-pop'), SubtitleConfig)
for module in ('typer', 'PIL', 'fontTools', 'ffmpeg', 'torch', 'whisperx',
               'faster_whisper', 'nemo', 'transformers', 'multisubs.cli',
               'multisubs.subtitler', 'multisubs.transcriber',
               'multisubs.font_catalog', 'multisubs.text_measurement'):
    assert module not in sys.modules, module
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == completed.stderr == ""
