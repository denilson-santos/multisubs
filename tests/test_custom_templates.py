import json
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import cli, transcriber
from multisubs.custom_templates import (
    load_custom_template_directory,
    resolve_subtitle_template,
)
from multisubs.errors import TemplateError, ValidationError
from multisubs.models import (
    CueAnimationType,
    PreviewMode,
    PreviewRequest,
    TranscriptDocument,
    VideoGeometry,
)
from multisubs.preview import build_preview_ass
from multisubs.templates import get_subtitle_template

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


def _write_template(directory: Path, filename: str, **values: object) -> Path:
    path = directory / filename
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_custom_template_uses_json_name_and_builtin_base(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(
        directory,
        "arbitrary-file-name.json",
        schema_version=1,
        name="my-yellow-captions",
        base="yellow-pop",
        style={"typography": {"font_size": "4%"}},
        layout={"margins": {"bottom": "15%"}},
    )

    selection = resolve_subtitle_template("my-yellow-captions", directory)

    assert selection.source == "custom"
    assert selection.base == "yellow-pop"
    assert selection.template.name == "my-yellow-captions"
    assert (
        getattr(selection.template.config.style.typography.font_size, "original", None)
        == "4%"
    )
    assert (
        getattr(selection.template.config.layout.margin_bottom, "original", None)
        == "15%"
    )
    assert (
        selection.template.config.animation.word.text.emphasis.type
        is CueAnimationType.HIGHLIGHT
    )


def test_custom_default_precedes_builtin_only_for_that_directory(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(
        directory,
        "custom.json",
        schema_version=1,
        name="default",
        style={"typography": {"font_size": "5%"}},
    )

    custom = resolve_subtitle_template(None, directory)
    builtin = resolve_subtitle_template(None)

    assert custom.source == "custom"
    assert (
        getattr(custom.template.config.style.typography.font_size, "original", None)
        == "5%"
    )
    assert builtin.source == "builtin"
    assert builtin.template.config == get_subtitle_template("default").config


def test_empty_directory_keeps_builtins_available(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()

    selection = resolve_subtitle_template("golden-title", directory)

    assert selection.source == "builtin"
    assert selection.template.name == "golden-title"


def test_all_custom_files_are_validated_before_selection(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(directory, "selected.json", schema_version=1, name="selected")
    (directory / "unselected.json").write_text("{", encoding="utf-8")

    with pytest.raises(TemplateError, match="unselected.json"):
        resolve_subtitle_template("selected", directory)


def test_duplicate_names_are_rejected_deterministically(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(directory, "a.json", schema_version=1, name="same")
    _write_template(directory, "b.json", schema_version=1, name="same")

    with pytest.raises(TemplateError, match="same"):
        load_custom_template_directory(directory)


def test_custom_animation_type_change_uses_new_default_duration(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(
        directory,
        "custom.json",
        schema_version=1,
        name="custom",
        base="yellow-pop",
        animation={
            "word": {"text": {"entrance": {"type": "fade"}}},
        },
    )

    custom = load_custom_template_directory(directory)["custom"][0].config
    base = get_subtitle_template("yellow-pop").config

    assert custom.animation.word.text.entrance.type is CueAnimationType.FADE
    assert (
        custom.animation.word.text.entrance.duration_ms
        != base.animation.word.text.entrance.duration_ms
    )


def test_disabling_inherited_highlight_clears_its_color(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(
        directory,
        "custom.json",
        schema_version=1,
        name="custom",
        base="yellow-pop",
        animation={"word": {"text": {"emphasis": {"type": "none"}}}},
    )

    custom = load_custom_template_directory(directory)["custom"][0].config

    assert custom.animation.word.text.emphasis.type is CueAnimationType.NONE
    assert custom.style.typography.highlight_color is None


def test_unknown_selection_suggests_custom_directory(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()

    with pytest.raises(ValidationError, match="--template-dir"):
        resolve_subtitle_template("missing", directory)


def test_cli_resolves_custom_template_with_both_argument_forms(tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(directory, "custom.json", schema_version=1, name="custom")
    parser = cli.build_parser()

    for option in ("--template custom", "--template=custom"):
        args = parser.parse_args(
            [
                "-i",
                str(video),
                "--template-dir",
                str(directory),
                *option.split(" ", 1),
            ]
        )
        request = cli._build_request(args, parser)
        assert request.subtitle_template_source == "custom"
        assert request.subtitle_template_resolved == "custom"


def test_custom_metadata_adds_source_without_paths(tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"input")
    template_dir = tmp_path / "private-templates"
    template_dir.mkdir()
    _write_template(
        template_dir,
        "custom.json",
        schema_version=1,
        name="custom",
        base="yellow-pop",
    )
    selection = resolve_subtitle_template("custom", template_dir)
    document = TranscriptDocument(
        source_path=source,
        language="pt",
        task="transcribe",
        model_name="turbo",
        full_text="Olá.",
        segments=({"id": 0, "start": 0.0, "end": 1.0, "text": "Olá.", "words": []},),
    )

    json_path, _, _ = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        selection.template.config,
        geometry=GEOMETRY,
        template_requested="custom",
        template_resolved=selection.template.name,
        template_source=selection.source,
        template_base=selection.base,
    )

    rendering = json.loads(Path(json_path).read_text(encoding="utf-8"))["metadata"][
        "rendering"
    ]
    assert rendering["template"] == {
        "requested": "custom",
        "resolved": "custom",
        "source": "custom",
        "schema_version": 1,
        "base": "yellow-pop",
    }
    assert str(template_dir) not in json.dumps(rendering)


def test_custom_template_compiles_in_static_preview(tmp_path: Path):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"input")
    directory = tmp_path / "templates"
    directory.mkdir()
    _write_template(
        directory,
        "custom.json",
        schema_version=1,
        name="custom",
        base="yellow-pop",
    )
    selection = resolve_subtitle_template("custom", directory)
    request = PreviewRequest(
        input_path=video,
        output_dir=tmp_path,
        subtitle_config=selection.template.config,
        preview_at=0.0,
        preview_text="Custom preview",
        guides=False,
        subtitle_template_requested="custom",
        subtitle_template_resolved="custom",
        subtitle_template_source="custom",
        subtitle_template_base="yellow-pop",
        preview_mode=PreviewMode.LAYOUT,
    )
    ass_path = tmp_path / "preview.ass"

    build_preview_ass(ass_path, request, GEOMETRY, 0.0)

    assert ass_path.read_text(encoding="utf-8").startswith("[Script Info]")


def test_json_symlink_is_rejected_and_json_directories_are_ignored(tmp_path: Path):
    directory = tmp_path / "templates"
    directory.mkdir()
    (directory / "nested.json").mkdir()
    target = tmp_path / "target.json"
    target.write_text(
        json.dumps({"schema_version": 1, "name": "linked"}), encoding="utf-8"
    )
    link = directory / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable")

    with pytest.raises(TemplateError, match="symbolic link"):
        load_custom_template_directory(directory)
