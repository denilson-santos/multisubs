import json
import shutil
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import cli, transcriber
from multisubs import templates as template_catalog
from multisubs.ass import write_ass
from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.errors import TemplateError
from multisubs.font_catalog import find_bundled_font_family
from multisubs.layout import resolve_subtitle_config
from multisubs.models import (
    FontWeight,
    PreviewRequest,
    RelativeLength,
    SubtitleBackdrop,
    SubtitlePosition,
    TextCase,
    TranscriptDocument,
    VideoGeometry,
    WordAnimationMode,
)
from multisubs.templates import (
    DEFAULT_SUBTITLE_TEMPLATE,
    SUBTITLE_TEMPLATES,
    TEMPLATE_CHOICES,
    get_subtitle_template,
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
    duration_seconds=2.0,
)

EXPECTED_TEMPLATES = {
    "default": (
        "Roboto",
        FontWeight.REGULAR,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.BOX,
        "#00000099",
        "25%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "bold-headline": (
        "Montserrat",
        FontWeight.EXTRA_BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "7%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "amber-word": (
        "Inter",
        FontWeight.SEMI_BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.ACTIVE_WORD,
        "#FFD54F",
    ),
    "mint-progress": (
        "Montserrat",
        FontWeight.MEDIUM,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.BOX,
        "#111827D9",
        "15%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.PROGRESSIVE,
        "#A7F3D0",
    ),
    "focus-marker": (
        "Atkinson Hyperlegible Next",
        FontWeight.BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "4%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.ACTIVE_WORD,
        "#111827",
    ),
    "golden-title": (
        "Oswald",
        FontWeight.BOLD,
        False,
        "4%",
        "#FACC15",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "6%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "emerald-word": (
        "Roboto",
        FontWeight.BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "kinetic-lime": (
        "Montserrat",
        FontWeight.BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.ACTIVE_WORD,
        "#D9F99D",
    ),
    "coral-marker": (
        "Roboto",
        FontWeight.SEMI_BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "4%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.ACTIVE_WORD,
        "#111827",
    ),
    "editorial-reveal": (
        "Lora",
        FontWeight.SEMI_BOLD,
        True,
        "4%",
        "#FFF8ED",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "4%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "headline-bounce": (
        "Oswald",
        FontWeight.SEMI_BOLD,
        False,
        "4%",
        "#FDE68A",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "6%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "yellow-pop": (
        "Montserrat",
        FontWeight.EXTRA_BOLD,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.ACTIVE_WORD,
        "#FBE003",
    ),
    "yellow-trace": (
        "Inter",
        FontWeight.MEDIUM,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.BOX,
        "#111827FF",
        "15%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.PROGRESSIVE,
        "#FBE003",
    ),
    "neon-lime-marker": (
        "Oswald",
        FontWeight.MEDIUM,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "4%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        WordAnimationMode.ACTIVE_WORD,
        "#111827",
    ),
    "neon-cyan-reveal": (
        "Atkinson Hyperlegible Next",
        FontWeight.BOLD,
        False,
        "4%",
        "#00F5FF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
    "neon-magenta-pulse": (
        "Roboto",
        FontWeight.BOLD,
        False,
        "4%",
        "#FF4FD8",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.OUTLINE,
        "#111827",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "18%",
        "18%",
        "0%",
        "3%",
        "100%",
        "10%",
        None,
        None,
    ),
}

EXPECTED_ANIMATIONS = {
    **{
        name: ("none", 0, "none", 0, "none", 0, "none", 0, "none", 0, None, "none", 0)
        for name in (
            "default",
            "golden-title",
            "emerald-word",
        )
    },
    "bold-headline": (
        "pop",
        120,
        "none",
        0,
        "fade",
        100,
        "none",
        0,
        "none",
        0,
        None,
        "none",
        0,
    ),
    "amber-word": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.ACTIVE_WORD,
        "none",
        0,
    ),
    "mint-progress": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.PROGRESSIVE,
        "none",
        0,
    ),
    "focus-marker": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.ACTIVE_WORD,
        "none",
        0,
    ),
    "kinetic-lime": (
        "slide-up",
        180,
        "none",
        0,
        "fade",
        120,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.ACTIVE_WORD,
        "none",
        0,
    ),
    "coral-marker": (
        "fade",
        140,
        "none",
        0,
        "fade",
        120,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.ACTIVE_WORD,
        "none",
        0,
    ),
    "editorial-reveal": (
        "zoom",
        200,
        "none",
        0,
        "fade",
        160,
        "fade",
        100,
        "none",
        0,
        None,
        "none",
        0,
    ),
    "headline-bounce": (
        "fade",
        120,
        "none",
        0,
        "slide-down",
        160,
        "none",
        0,
        "bounce",
        420,
        None,
        "none",
        0,
    ),
    "yellow-pop": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "pop",
        120,
        "highlight",
        0,
        WordAnimationMode.ACTIVE_WORD,
        "none",
        0,
    ),
    "yellow-trace": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.PROGRESSIVE,
        "none",
        0,
    ),
    "neon-lime-marker": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "highlight",
        0,
        WordAnimationMode.ACTIVE_WORD,
        "none",
        0,
    ),
    "neon-cyan-reveal": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "slide-up",
        120,
        "none",
        0,
        None,
        "none",
        0,
    ),
    "neon-magenta-pulse": (
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "none",
        0,
        "pulse",
        400,
        None,
        "none",
        0,
    ),
}


def _build_request(tmp_path: Path, *options: str):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    return cli._build_request(
        parser.parse_args(["-i", str(input_path), *options]), parser
    )


def _template_snapshot(name: str):
    config = get_subtitle_template(name).config
    typography = config.style.typography
    layout = config.layout
    return (
        typography.font,
        typography.font_weight,
        typography.italic,
        _relative_original(typography.font_size),
        typography.color,
        config.style.opacity.original,
        typography.text_case,
        config.style.backdrop.kind,
        config.style.backdrop.color,
        _relative_original(config.style.backdrop.size),
        _relative_original(config.style.shadow.size),
        _relative_original(typography.letter_spacing),
        layout.position,
        _relative_original(layout.margin_left),
        _relative_original(layout.margin_right),
        _relative_original(layout.margin_top),
        _relative_original(layout.margin_bottom),
        _relative_original(layout.max_width),
        _relative_original(layout.max_height),
        (
            config.animation.word.text.mode
            if config.animation.word.text.emphasis.type.value == "highlight"
            else None
        ),
        config.style.typography.highlight_color,
    )


def _relative_original(value: int | RelativeLength | None) -> str:
    assert isinstance(value, RelativeLength)
    return value.original


def _copy_template_catalog(tmp_path: Path) -> Path:
    source = Path(template_catalog.__file__).parent / "assets" / "templates"
    target = tmp_path / "templates"
    shutil.copytree(source, target)
    return target


def _rewrite_json(path: Path, transform) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    transform(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_registry_has_stable_order_and_immutable_templates():
    assert DEFAULT_SUBTITLE_TEMPLATE == "default"
    assert TEMPLATE_CHOICES == tuple(EXPECTED_TEMPLATES)
    assert len(TEMPLATE_CHOICES) == 16
    assert tuple(template.name for template in SUBTITLE_TEMPLATES) == TEMPLATE_CHOICES
    assert len(set(TEMPLATE_CHOICES)) == len(TEMPLATE_CHOICES)
    assert all(hash(template) for template in SUBTITLE_TEMPLATES)


def test_packaged_catalog_has_sparse_deterministic_inventory():
    root = Path(template_catalog.__file__).parent / "assets" / "templates"
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))

    assert index == {
        "schema_version": 5,
        "templates": [f"{name}.json" for name in EXPECTED_TEMPLATES],
    }
    assert {path.name for path in root.glob("*.json")} == {
        "index.json",
        *index["templates"],
    }
    assert json.loads((root / "default.json").read_text(encoding="utf-8")) == {
        "schema_version": 5,
        "name": "default",
        "description": (
            "Current general-purpose white captions on a translucent black box."
        ),
    }


@pytest.mark.parametrize("name", TEMPLATE_CHOICES)
def test_builtin_templates_share_default_layout_and_minimum_font_size(name: str):
    default = get_subtitle_template("default").config
    config = get_subtitle_template(name).config
    assert config.layout == default.layout
    font_size = config.style.typography.font_size
    default_size = default.style.typography.font_size
    assert isinstance(font_size, RelativeLength)
    assert isinstance(default_size, RelativeLength)
    assert font_size.unit == default_size.unit
    assert font_size.value >= default_size.value


def test_schema4_complete_resources_remain_readable(tmp_path: Path):
    root = tmp_path / "templates"
    root.mkdir()
    legacy = template_catalog._default_template_data()
    legacy["schema_version"] = 4
    legacy["description"] = "Legacy complete default resource."
    (root / "default.json").write_text(json.dumps(legacy), encoding="utf-8")
    (root / "index.json").write_text(
        json.dumps({"schema_version": 4, "templates": ["default.json"]}),
        encoding="utf-8",
    )

    templates = template_catalog._load_template_catalog(root)

    assert len(templates) == 1
    assert templates[0].config == validate_subtitle_config(None)


def test_catalog_requires_matching_resource_schema_version(tmp_path: Path):
    root = _copy_template_catalog(tmp_path)
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    index["schema_version"] = 4
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(TemplateError, match="schema_version 4"):
        template_catalog._load_template_catalog(root)


def test_sparse_and_expanded_resources_have_equal_runtime_config(tmp_path: Path):
    root = _copy_template_catalog(tmp_path)
    sparse_path = root / "amber-word.json"
    sparse_data = json.loads(sparse_path.read_text(encoding="utf-8"))
    expanded_data = template_catalog._expand_sparse_template_data(
        sparse_data, expected_name="amber-word"
    )
    expanded_path = root / "expanded.json"
    expanded_data["name"] = "expanded"
    expanded_data["description"] = "Expanded equivalent."
    expanded_path.write_text(json.dumps(expanded_data), encoding="utf-8")
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    index["templates"].append("expanded.json")
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")

    loaded = template_catalog._load_template_catalog(root)

    assert loaded[-1].config == next(t.config for t in loaded if t.name == "amber-word")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.pop("description"), "missing field"),
        (
            lambda payload: (
                payload.setdefault("animation", {})
                .setdefault("word", {})
                .setdefault("text", {})
                .update({"emphasis": {}})
            ),
            "missing field",
        ),
        (
            lambda payload: payload.update({"schema_version": 99}),
            "schema_version 5",
        ),
    ],
)
def test_sparse_resources_reject_missing_identity_and_invalid_versions(
    tmp_path: Path, mutate, message: str
):
    root = _copy_template_catalog(tmp_path)
    _rewrite_json(root / "amber-word.json", mutate)

    with pytest.raises(TemplateError, match=message):
        template_catalog._load_template_catalog(root)


@pytest.mark.parametrize(
    ("filename", "mutate", "message"),
    [
        (
            "amber-word.json",
            lambda payload: payload["style"].update({"unexpected": "value"}),
            "unknown field",
        ),
        (
            "amber-word.json",
            lambda payload: payload.update(
                {"animation": {"cue": {"text": {"entrance": {}}}}}
            ),
            "missing field",
        ),
        (
            "amber-word.json",
            lambda payload: payload["style"]["typography"].update(
                {"font_size": "invalid"}
            ),
            "semantically invalid",
        ),
    ],
)
def test_catalog_rejects_invalid_template_resources(
    tmp_path: Path, filename: str, mutate, message: str
):
    root = _copy_template_catalog(tmp_path)
    _rewrite_json(root / filename, mutate)

    with pytest.raises(TemplateError, match=message):
        template_catalog._load_template_catalog(root)


def test_catalog_rejects_duplicate_index_entries(tmp_path: Path):
    root = _copy_template_catalog(tmp_path)
    _rewrite_json(
        root / "index.json",
        lambda payload: payload["templates"].append("default.json"),
    )

    with pytest.raises(TemplateError, match="duplicate file"):
        template_catalog._load_template_catalog(root)


@pytest.mark.parametrize("version", [[], {}])
def test_catalog_rejects_unhashable_index_schema_version(tmp_path: Path, version):
    root = _copy_template_catalog(tmp_path)
    _rewrite_json(
        root / "index.json", lambda payload: payload.update({"schema_version": version})
    )

    with pytest.raises(TemplateError, match="Template index must use schema_version"):
        template_catalog._load_template_catalog(root)


def test_catalog_rejects_unindexed_resources(tmp_path: Path):
    root = _copy_template_catalog(tmp_path)
    shutil.copyfile(root / "default.json", root / "unindexed.json")

    with pytest.raises(TemplateError, match="unindexed: unindexed.json"):
        template_catalog._load_template_catalog(root)


def test_catalog_rejects_duplicate_json_keys(tmp_path: Path):
    root = _copy_template_catalog(tmp_path)
    (root / "index.json").write_text(
        '{"schema_version": 5, "schema_version": 5, "templates": []}',
        encoding="utf-8",
    )

    with pytest.raises(TemplateError, match="duplicate key"):
        template_catalog._load_template_catalog(root)


def test_cli_reports_a_stored_catalog_failure(monkeypatch, capsys):
    error = TemplateError("Packaged template catalog is damaged")
    monkeypatch.setattr(template_catalog, "_CATALOG_ERROR", error)

    assert cli.main([]) == 1
    assert capsys.readouterr().err == "Error: Packaged template catalog is damaged\n"


@pytest.mark.parametrize("name", TEMPLATE_CHOICES)
def test_template_has_exact_documented_baseline_and_bundled_face(name: str):
    assert _template_snapshot(name) == EXPECTED_TEMPLATES[name]

    config = get_subtitle_template(name).config
    cue = config.animation.cue.text
    word = config.animation.word.text
    assert (
        cue.entrance.type.value,
        cue.entrance.duration_ms,
        cue.emphasis.type.value,
        cue.emphasis.duration_ms,
        cue.exit.type.value,
        cue.exit.duration_ms,
        word.entrance.type.value,
        word.entrance.duration_ms,
        word.emphasis.type.value,
        word.emphasis.duration_ms,
        word.mode if word.emphasis.type.value == "highlight" else None,
        word.exit.type.value,
        word.exit.duration_ms,
    ) == EXPECTED_ANIMATIONS[name]
    if cue.enabled and config.animation.cue.backdrop.enabled:
        assert config.animation.cue.backdrop == cue
    expected_word_backdrop = (
        ("box", "#FFD54F", "12%")
        if name == "focus-marker"
        else ("box", "#166534FF", "12%")
        if name == "emerald-word"
        else ("box", "#FDA4AFFF", "14%")
        if name == "coral-marker"
        else ("box", "#39FF14FF", "12%")
        if name == "neon-lime-marker"
        else (
            "none",
            "#111827E6",
            "25%",
        )
    )
    assert (
        config.style.word_backdrop.kind.value,
        config.style.word_backdrop.color,
        _relative_original(config.style.word_backdrop.size),
    ) == expected_word_backdrop
    family = find_bundled_font_family(config.style.typography.font)
    assert family is not None
    assert any(
        face.weight == config.style.typography.font_weight.rank
        and face.italic is config.style.typography.italic
        for face in family.faces
    )


def test_choreographed_word_tracks_keep_their_declared_modes_and_phases():
    kinetic = get_subtitle_template("kinetic-lime").config.animation
    assert kinetic.word.text.mode is WordAnimationMode.ACTIVE_WORD
    assert kinetic.word.text.emphasis.type.value == "highlight"
    assert kinetic.word.backdrop.enabled is False

    coral = get_subtitle_template("coral-marker").config.animation
    assert coral.word.text.mode is WordAnimationMode.ACTIVE_WORD
    assert coral.word.text.emphasis.type.value == "highlight"
    assert coral.word.backdrop.mode is WordAnimationMode.ACTIVE_WORD
    assert coral.word.backdrop.entrance.type.value == "fade"
    assert coral.word.backdrop.entrance.duration_ms == 70
    assert coral.word.backdrop.exit.type.value == "fade"
    assert coral.word.backdrop.exit.duration_ms == 70

    editorial = get_subtitle_template("editorial-reveal").config.animation
    assert editorial.word.text.mode is WordAnimationMode.PROGRESSIVE
    assert editorial.word.text.entrance.type.value == "fade"
    assert editorial.word.text.entrance.duration_ms == 100

    headline = get_subtitle_template("headline-bounce").config.animation
    assert headline.word.text.emphasis.type.value == "bounce"
    assert headline.word.text.emphasis.duration_ms == 420

    yellow_pop = get_subtitle_template("yellow-pop").config.animation
    assert yellow_pop.word.text.mode is WordAnimationMode.ACTIVE_WORD
    assert yellow_pop.word.text.entrance.type.value == "pop"
    assert yellow_pop.word.text.entrance.duration_ms == 120
    assert yellow_pop.word.text.emphasis.type.value == "highlight"

    yellow_trace = get_subtitle_template("yellow-trace").config.animation
    assert yellow_trace.word.text.mode is WordAnimationMode.PROGRESSIVE
    assert yellow_trace.word.text.emphasis.type.value == "highlight"

    neon_marker = get_subtitle_template("neon-lime-marker").config.animation
    assert neon_marker.word.backdrop.mode is WordAnimationMode.ACTIVE_WORD
    assert neon_marker.word.backdrop.entrance.type.value == "zoom"
    assert neon_marker.word.backdrop.entrance.duration_ms == 100
    assert neon_marker.word.backdrop.exit.type.value == "fade"
    assert neon_marker.word.backdrop.exit.duration_ms == 70

    cyan_reveal = get_subtitle_template("neon-cyan-reveal").config.animation
    assert cyan_reveal.word.text.mode is WordAnimationMode.PROGRESSIVE
    assert cyan_reveal.word.text.entrance.type.value == "slide-up"
    assert cyan_reveal.word.text.entrance.duration_ms == 120

    magenta_pulse = get_subtitle_template("neon-magenta-pulse").config.animation
    assert magenta_pulse.word.text.mode is WordAnimationMode.ACTIVE_WORD
    assert magenta_pulse.word.text.emphasis.type.value == "pulse"
    assert magenta_pulse.word.text.emphasis.duration_ms == 400


def test_default_template_reuses_authoritative_default_configuration():
    assert get_subtitle_template(None) is get_subtitle_template("default")
    assert get_subtitle_template("default").config == validate_subtitle_config(None)
    assert resolve_subtitle_config(
        get_subtitle_template("default").config, GEOMETRY
    ) == resolve_subtitle_config(validate_subtitle_config(None), GEOMETRY)


def test_omitted_and_explicit_default_have_equal_config_but_distinct_identity(
    tmp_path: Path,
):
    omitted = _build_request(tmp_path)
    explicit = _build_request(tmp_path, "--template", "default")

    assert omitted.subtitle_config == explicit.subtitle_config
    assert omitted.subtitle_template_requested is None
    assert omitted.subtitle_template_resolved == "default"
    assert explicit.subtitle_template_requested == "default"
    assert explicit.subtitle_template_resolved == "default"


@pytest.mark.parametrize("name", TEMPLATE_CHOICES)
def test_cli_selection_resolves_exact_registry_baseline(tmp_path: Path, name: str):
    options = ["--template", name]

    request = _build_request(tmp_path, *options)
    expected = get_subtitle_template(name).config

    assert request.subtitle_config.style.typography == expected.style.typography
    assert request.subtitle_config.layout == expected.layout
    assert request.subtitle_config.animation == expected.animation


def test_omitted_and_explicit_default_generate_identical_ass(tmp_path: Path):
    omitted = _build_request(tmp_path)
    explicit = _build_request(tmp_path, "--template", "default")
    cues = [{"id": 0, "start": 0.0, "end": 1.0, "text": "Legenda", "words": []}]
    omitted_path = tmp_path / "omitted.ass"
    explicit_path = tmp_path / "explicit.ass"

    write_ass(omitted_path, cues, omitted.subtitle_config, GEOMETRY)
    write_ass(explicit_path, cues, explicit.subtitle_config, GEOMETRY)

    assert omitted_path.read_bytes() == explicit_path.read_bytes()


def test_request_build_rejects_unknown_template_after_directory_resolution(
    tmp_path: Path,
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    args = parser.parse_args(["-i", str(input_path), "--template", "unknown-template"])

    with pytest.raises(SystemExit) as error:
        cli._build_request(args, parser)

    assert error.value.code == 2


def test_parser_exposes_template_and_template_directory_options(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    assert "--template" in parser.format_help()
    assert "--template-dir" in parser.format_help()
    assert "--subtitle-template" not in parser.format_help()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(
            ["-i", str(input_path), "--subtitle-template", "classic-yellow"]
        )

    assert error.value.code == 2


def test_explicit_appearance_and_layout_fields_override_only_their_fields(
    tmp_path: Path,
):
    baseline = get_subtitle_template("editorial-reveal").config
    request = _build_request(
        tmp_path,
        "--template",
        "editorial-reveal",
        "--font",
        "Inter",
        "--font-weight",
        "300",
        "--no-italic",
        "--font-size",
        "6%",
        "--text-color",
        "#12345678",
        "--opacity",
        "80%",
        "--text-case",
        "lowercase",
        "--backdrop",
        "box",
        "--backdrop-color",
        "#ABCDEF",
        "--backdrop-size",
        "9%",
        "--word-backdrop-color",
        "#FEDCBA",
        "--word-backdrop-size",
        "11%",
        "--shadow-size",
        "2%",
        "--letter-spacing",
        "3%",
        "--line-height",
        "120%",
        "--position",
        "top-right",
        "--margin-left",
        "4%",
        "--margin-right",
        "5%",
        "--margin-top",
        "6%",
        "--max-width",
        "90%",
        "--max-height",
        "30%",
    )
    style = request.subtitle_config.style
    typography = style.typography
    layout = request.subtitle_config.layout

    assert typography.font == "Inter"
    assert typography.font_weight is FontWeight.LIGHT
    assert typography.italic is False
    assert typography.font_size == parse_relative_length("6%")
    assert typography.color == "#12345678"
    assert style.opacity.original == "80%"
    assert typography.text_case is TextCase.LOWERCASE
    assert style.backdrop.kind is SubtitleBackdrop.BOX
    assert style.backdrop.color == "#ABCDEF"
    assert style.backdrop.size == parse_relative_length("9%")
    assert style.word_backdrop.color == "#FEDCBA"
    assert style.word_backdrop.size == parse_relative_length("11%")
    assert style.shadow.size == parse_relative_length("2%")
    assert typography.letter_spacing == parse_relative_length("3%")
    assert typography.line_height == parse_relative_length("120%")
    assert layout.position is SubtitlePosition.TOP_RIGHT
    assert layout.margin_left == parse_relative_length("4%")
    assert layout.margin_right == parse_relative_length("5%")
    assert layout.margin_top == parse_relative_length("6%")
    assert layout.max_width == parse_relative_length("90%")
    assert layout.max_height == parse_relative_length("30%")
    assert layout.margin_bottom == baseline.layout.margin_bottom


def test_single_override_preserves_unrelated_template_values(tmp_path: Path):
    baseline = get_subtitle_template("bold-headline").config
    request = _build_request(
        tmp_path,
        "--template",
        "bold-headline",
        "--text-color",
        "#00FF00",
    )

    assert request.subtitle_config.style.typography.color == "#00FF00"
    assert (
        request.subtitle_config.style.typography.font == baseline.style.typography.font
    )
    assert request.subtitle_config.style.typography.font_weight is FontWeight.EXTRA_BOLD
    assert request.subtitle_config.style.typography.text_case is TextCase.UPPERCASE
    assert request.subtitle_config.layout == baseline.layout


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--bold", FontWeight.BOLD), ("--no-bold", FontWeight.REGULAR)],
)
def test_bold_shorthand_overrides_template_weight(
    tmp_path: Path, flag: str, expected: FontWeight
):
    request = _build_request(tmp_path, "--template", "bold-headline", flag)

    assert request.subtitle_config.style.typography.font_weight is expected
    assert request.subtitle_config.style.typography.font == "Montserrat"


def test_custom_fonts_directory_is_compatible_with_template(tmp_path: Path):
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()

    request = _build_request(
        tmp_path,
        "--template",
        "editorial-reveal",
        "--fonts-dir",
        str(fonts_dir),
    )

    assert request.subtitle_config.style.typography.fonts_dir == fonts_dir.resolve()
    assert request.subtitle_config.style.typography.font == "Lora"
    assert request.subtitle_config.style.typography.italic is True


def test_template_margin_is_not_treated_as_explicit_after_position_override(
    tmp_path: Path,
):
    request = _build_request(
        tmp_path,
        "--template",
        "mint-progress",
        "--position",
        "top-left",
    )

    assert request.subtitle_config.layout.position is SubtitlePosition.TOP_LEFT
    assert request.subtitle_config.layout.margin_bottom == parse_relative_length("3%")


def test_explicit_inactive_template_margin_is_rejected(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        _build_request(
            tmp_path,
            "--template",
            "mint-progress",
            "--position",
            "top-left",
            "--margin-bottom",
            "3%",
        )

    assert error.value.code == 2


def test_template_envelope_does_not_satisfy_explicit_coordinate_requirements(
    tmp_path: Path,
):
    with pytest.raises(SystemExit) as error:
        _build_request(
            tmp_path,
            "--template",
            "bold-headline",
            "--position-x",
            "50%",
            "--position-y",
            "80%",
            "--anchor",
            "bottom-center",
        )

    assert error.value.code == 2


def test_progressive_template_effects_can_be_overridden_or_disabled(tmp_path: Path):
    active = _build_request(
        tmp_path,
        "--template",
        "mint-progress",
        "--animation-word-text-mode",
        "active-word",
        "--animation-word-text-highlight-color",
        "#FF00FF",
    )
    disabled = _build_request(
        tmp_path,
        "--template",
        "mint-progress",
        "--animation-word-text-emphasis",
        "none",
    )

    assert (
        active.subtitle_config.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD
    )
    assert active.subtitle_config.style.typography.highlight_color == "#FF00FF"
    assert disabled.subtitle_config.animation.word.uses_timed_highlight is False
    assert disabled.subtitle_config.style.typography == replace(
        active.subtitle_config.style.typography, highlight_color=None
    )
    assert disabled.subtitle_config.layout == active.subtitle_config.layout


def test_highlight_color_is_invalid_when_emphasis_is_disabled(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        _build_request(
            tmp_path,
            "--template",
            "mint-progress",
            "--animation-word-text-emphasis",
            "none",
            "--animation-word-text-highlight-color=#FF00FF",
        )

    assert error.value.code == 2


def test_progressive_template_rejects_translation(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        _build_request(
            tmp_path,
            "--template",
            "mint-progress",
            "--task",
            "translate",
            "--model",
            "medium",
        )

    assert error.value.code == 2


def test_progressive_template_is_valid_for_preview(tmp_path: Path):
    request = _build_request(
        tmp_path,
        "--template",
        "mint-progress",
        "--preview-layout",
    )

    assert isinstance(request, PreviewRequest)
    assert request.subtitle_config.animation.word.uses_timed_highlight is True


def test_disabling_word_emphasis_makes_progressive_template_valid_for_translation(
    tmp_path: Path,
):
    request = _build_request(
        tmp_path,
        "--template",
        "mint-progress",
        "--animation-word-text-emphasis",
        "none",
        "--task",
        "translate",
        "--model",
        "medium",
    )

    assert request.subtitle_config.animation.word.uses_timed_highlight is False


def test_preview_request_records_template_identity(tmp_path: Path):
    request = _build_request(
        tmp_path,
        "--preview-layout",
        "--template",
        "golden-title",
    )

    assert isinstance(request, PreviewRequest)
    assert request.subtitle_template_requested == "golden-title"
    assert request.subtitle_template_resolved == "golden-title"


def test_json_records_template_identity_without_registry_or_asset_paths(tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source,
        language="pt",
        task="transcribe",
        model_name="turbo",
        full_text="Olá.",
        segments=({"id": 0, "start": 0.0, "end": 1.0, "text": "Olá.", "words": []},),
    )
    template = get_subtitle_template("golden-title")

    json_path, _, _ = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        template.config,
        geometry=GEOMETRY,
        template_requested=template.name,
        template_resolved=template.name,
    )

    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    rendering = payload["metadata"]["rendering"]
    assert rendering["template"] == {
        "requested": "golden-title",
        "resolved": "golden-title",
    }
    assert set(rendering["template"]) == {"requested", "resolved"}
    assert "assets/fonts" not in json.dumps(rendering)
