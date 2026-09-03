import json
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import cli, transcriber
from multisubs.ass import write_ass
from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.font_catalog import find_bundled_font_family
from multisubs.layout import resolve_subtitle_config
from multisubs.models import (
    FontWeight,
    KaraokeMode,
    PreviewRequest,
    RelativeLength,
    SubtitleBackdrop,
    SubtitlePosition,
    TextCase,
    TranscriptDocument,
    VideoGeometry,
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
        "0px",
        "4%",
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
    "clean-outline": (
        "Inter",
        FontWeight.MEDIUM,
        False,
        "4%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#000000CC",
        "5%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "14%",
        "14%",
        "0%",
        "3%",
        "100%",
        "14%",
        None,
        None,
    ),
    "social-bold": (
        "Montserrat",
        FontWeight.EXTRA_BOLD,
        False,
        "5%",
        "#FFFFFF",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.OUTLINE,
        "#000000E6",
        "8%",
        "3%",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "8%",
        "8%",
        "0%",
        "3%",
        "100%",
        "22%",
        None,
        None,
    ),
    "classic-yellow": (
        "Roboto",
        FontWeight.BOLD,
        False,
        "4.2%",
        "#FFD54F",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#000000E6",
        "6%",
        "3%",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "12%",
        "12%",
        "0%",
        "3%",
        "100%",
        "16%",
        None,
        None,
    ),
    "newsroom": (
        "Oswald",
        FontWeight.SEMI_BOLD,
        False,
        "4.2%",
        "#FFFFFF",
        "100%",
        TextCase.UPPERCASE,
        SubtitleBackdrop.BOX,
        "#0B1F3ACC",
        "8%",
        "0px",
        "1%",
        SubtitlePosition.BOTTOM_LEFT,
        "5%",
        "35%",
        "0%",
        "3%",
        "100%",
        "16%",
        None,
        None,
    ),
    "editorial": (
        "Lora",
        FontWeight.SEMI_BOLD,
        True,
        "4%",
        "#FFF8E7",
        "95%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#111111CC",
        "4%",
        "3%",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "16%",
        "16%",
        "0%",
        "3%",
        "100%",
        "15%",
        None,
        None,
    ),
    "high-contrast": (
        "Atkinson Hyperlegible Next",
        FontWeight.BOLD,
        False,
        "4.3%",
        "#000000",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.BOX,
        "#FFD600FF",
        "10%",
        "0px",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "10%",
        "10%",
        "0%",
        "3%",
        "100%",
        "18%",
        None,
        None,
    ),
    "neon-karaoke": (
        "Montserrat",
        FontWeight.BOLD,
        False,
        "5%",
        "#FFFFFF",
        "100%",
        TextCase.ORIGINAL,
        SubtitleBackdrop.OUTLINE,
        "#080012E6",
        "7%",
        "5%",
        "0px",
        SubtitlePosition.BOTTOM_CENTER,
        "8%",
        "8%",
        "0%",
        "3%",
        "100%",
        "20%",
        KaraokeMode.PROGRESSIVE,
        "#00F5D4",
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
    appearance = config.appearance
    layout = config.layout
    return (
        appearance.font,
        appearance.font_weight,
        appearance.italic,
        _relative_original(appearance.font_size),
        appearance.text_color,
        appearance.opacity.original,
        appearance.text_case,
        appearance.backdrop,
        appearance.backdrop_color,
        _relative_original(appearance.backdrop_size),
        _relative_original(appearance.shadow_size),
        _relative_original(appearance.letter_spacing),
        layout.position,
        _relative_original(layout.margin_left),
        _relative_original(layout.margin_right),
        _relative_original(layout.margin_top),
        _relative_original(layout.margin_bottom),
        _relative_original(layout.max_width),
        _relative_original(layout.max_height),
        config.effects.karaoke_mode,
        config.effects.highlight_color,
    )


def _relative_original(value: int | RelativeLength | None) -> str:
    assert isinstance(value, RelativeLength)
    return value.original


def test_registry_has_stable_order_and_immutable_templates():
    assert DEFAULT_SUBTITLE_TEMPLATE == "default"
    assert TEMPLATE_CHOICES == tuple(EXPECTED_TEMPLATES)
    assert tuple(template.name for template in SUBTITLE_TEMPLATES) == TEMPLATE_CHOICES
    assert len(set(TEMPLATE_CHOICES)) == len(TEMPLATE_CHOICES)
    assert all(hash(template) for template in SUBTITLE_TEMPLATES)


@pytest.mark.parametrize("name", TEMPLATE_CHOICES)
def test_template_has_exact_documented_baseline_and_bundled_face(name: str):
    assert _template_snapshot(name) == EXPECTED_TEMPLATES[name]

    config = get_subtitle_template(name).config
    family = find_bundled_font_family(config.appearance.font)
    assert family is not None
    assert any(
        face.weight == config.appearance.font_weight.rank
        and face.italic is config.appearance.italic
        for face in family.faces
    )


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

    assert request.subtitle_config.appearance == expected.appearance
    assert request.subtitle_config.layout == expected.layout
    assert request.subtitle_config.effects == expected.effects


def test_omitted_and_explicit_default_generate_identical_ass(tmp_path: Path):
    omitted = _build_request(tmp_path)
    explicit = _build_request(tmp_path, "--template", "default")
    cues = [{"id": 0, "start": 0.0, "end": 1.0, "text": "Legenda", "words": []}]
    omitted_path = tmp_path / "omitted.ass"
    explicit_path = tmp_path / "explicit.ass"

    write_ass(omitted_path, cues, omitted.subtitle_config, GEOMETRY)
    write_ass(explicit_path, cues, explicit.subtitle_config, GEOMETRY)

    assert omitted_path.read_bytes() == explicit_path.read_bytes()


def test_parser_rejects_unknown_template_before_request_build(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["-i", str(input_path), "--template", "unknown-template"])

    assert error.value.code == 2


def test_parser_exposes_only_the_template_option(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    assert "--template" in parser.format_help()
    assert "--subtitle-template" not in parser.format_help()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(
            ["-i", str(input_path), "--subtitle-template", "classic-yellow"]
        )

    assert error.value.code == 2


def test_explicit_appearance_and_layout_fields_override_only_their_fields(
    tmp_path: Path,
):
    baseline = get_subtitle_template("editorial").config
    request = _build_request(
        tmp_path,
        "--template",
        "editorial",
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
    appearance = request.subtitle_config.appearance
    layout = request.subtitle_config.layout

    assert appearance.font == "Inter"
    assert appearance.font_weight is FontWeight.LIGHT
    assert appearance.italic is False
    assert appearance.font_size == parse_relative_length("6%")
    assert appearance.text_color == "#12345678"
    assert appearance.opacity.original == "80%"
    assert appearance.text_case is TextCase.LOWERCASE
    assert appearance.backdrop is SubtitleBackdrop.BOX
    assert appearance.backdrop_color == "#ABCDEF"
    assert appearance.backdrop_size == parse_relative_length("9%")
    assert appearance.shadow_size == parse_relative_length("2%")
    assert appearance.letter_spacing == parse_relative_length("3%")
    assert appearance.line_height == parse_relative_length("120%")
    assert layout.position is SubtitlePosition.TOP_RIGHT
    assert layout.margin_left == parse_relative_length("4%")
    assert layout.margin_right == parse_relative_length("5%")
    assert layout.margin_top == parse_relative_length("6%")
    assert layout.max_width == parse_relative_length("90%")
    assert layout.max_height == parse_relative_length("30%")
    assert layout.margin_bottom == baseline.layout.margin_bottom


def test_single_override_preserves_unrelated_template_values(tmp_path: Path):
    baseline = get_subtitle_template("social-bold").config
    request = _build_request(
        tmp_path,
        "--template",
        "social-bold",
        "--text-color",
        "#00FF00",
    )

    assert request.subtitle_config.appearance.text_color == "#00FF00"
    assert request.subtitle_config.appearance.font == baseline.appearance.font
    assert request.subtitle_config.appearance.font_weight is FontWeight.EXTRA_BOLD
    assert request.subtitle_config.appearance.text_case is TextCase.UPPERCASE
    assert request.subtitle_config.layout == baseline.layout


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--bold", FontWeight.BOLD), ("--no-bold", FontWeight.REGULAR)],
)
def test_bold_shorthand_overrides_template_weight(
    tmp_path: Path, flag: str, expected: FontWeight
):
    request = _build_request(tmp_path, "--template", "social-bold", flag)

    assert request.subtitle_config.appearance.font_weight is expected
    assert request.subtitle_config.appearance.font == "Montserrat"


def test_custom_fonts_directory_is_compatible_with_template(tmp_path: Path):
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()

    request = _build_request(
        tmp_path,
        "--template",
        "editorial",
        "--fonts-dir",
        str(fonts_dir),
    )

    assert request.subtitle_config.appearance.fonts_dir == fonts_dir.resolve()
    assert request.subtitle_config.appearance.font == "Lora"
    assert request.subtitle_config.appearance.italic is True


def test_template_margin_is_not_treated_as_explicit_after_position_override(
    tmp_path: Path,
):
    request = _build_request(
        tmp_path,
        "--template",
        "newsroom",
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
            "newsroom",
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
            "social-bold",
            "--position-x",
            "50%",
            "--position-y",
            "80%",
            "--anchor",
            "bottom-center",
        )

    assert error.value.code == 2


def test_neon_template_effects_can_be_overridden_or_disabled(tmp_path: Path):
    active = _build_request(
        tmp_path,
        "--template",
        "neon-karaoke",
        "--karaoke-mode",
        "active-word",
        "--karaoke-highlight-color",
        "#FF00FF",
    )
    disabled = _build_request(
        tmp_path,
        "--template",
        "neon-karaoke",
        "--no-karaoke",
    )

    assert active.subtitle_config.effects.karaoke_mode is KaraokeMode.ACTIVE_WORD
    assert active.subtitle_config.effects.highlight_color == "#FF00FF"
    assert disabled.subtitle_config.effects.karaoke is False
    assert disabled.subtitle_config.appearance == active.subtitle_config.appearance
    assert disabled.subtitle_config.layout == active.subtitle_config.layout


@pytest.mark.parametrize(
    "option",
    ["--karaoke-mode=active-word", "--karaoke-highlight-color=#FF00FF"],
)
def test_explicit_effect_value_is_invalid_with_no_karaoke(tmp_path: Path, option: str):
    with pytest.raises(SystemExit) as error:
        _build_request(
            tmp_path,
            "--template",
            "neon-karaoke",
            "--no-karaoke",
            option,
        )

    assert error.value.code == 2


def test_neon_karaoke_rejects_translation(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        _build_request(
            tmp_path,
            "--template",
            "neon-karaoke",
            "--task",
            "translate",
            "--model",
            "medium",
        )

    assert error.value.code == 2


def test_neon_karaoke_is_valid_for_preview(tmp_path: Path):
    request = _build_request(
        tmp_path,
        "--template",
        "neon-karaoke",
        "--preview-layout",
    )

    assert isinstance(request, PreviewRequest)
    assert request.subtitle_config.effects.karaoke is True


def test_no_karaoke_makes_neon_template_valid_for_translation(tmp_path: Path):
    request = _build_request(
        tmp_path,
        "--template",
        "neon-karaoke",
        "--no-karaoke",
        "--task",
        "translate",
        "--model",
        "medium",
    )

    assert request.subtitle_config.effects.karaoke is False


def test_preview_request_records_template_identity(tmp_path: Path):
    request = _build_request(
        tmp_path,
        "--preview-layout",
        "--template",
        "classic-yellow",
    )

    assert isinstance(request, PreviewRequest)
    assert request.subtitle_template_requested == "classic-yellow"
    assert request.subtitle_template_resolved == "classic-yellow"


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
    template = get_subtitle_template("classic-yellow")

    json_path, _, _ = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        template.config,
        geometry=GEOMETRY,
        template_requested=template.name,
        template_resolved=template.name,
    )

    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    rendering = payload["metadata"]["rendering"]
    assert rendering["template"] == {
        "requested": "classic-yellow",
        "resolved": "classic-yellow",
    }
    assert set(rendering["template"]) == {"requested", "resolved"}
    assert "assets/fonts" not in json.dumps(rendering)
