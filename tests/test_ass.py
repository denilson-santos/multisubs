from fractions import Fraction
from pathlib import Path

import pytest

from multisubs.ass import (
    _ass_alignment_for_position,
    _compile_style,
    compose_rgba_opacity,
    escape_ass_text,
    format_ass_time,
    rgba_to_ass_color,
    serialize_ass_placement,
    write_ass,
)
from multisubs.config import parse_opacity, validate_subtitle_config
from multisubs.errors import ArtifactError
from multisubs.layout import resolve_subtitle_config, resolve_wrapping_metrics
from multisubs.models import (
    AssDrawingEvent,
    CuePlacement,
    FontWeight,
    KaraokeCue,
    SubtitleDisplayFragment,
    SubtitlePosition,
    VideoGeometry,
)

GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1080,
    render_height=1920,
    rotation_degrees=90,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(9, 16),
    duration_seconds=61.5,
)


def test_write_ass_compiles_semantic_style_and_escapes_dialogue(tmp_path: Path):
    path = tmp_path / "captions.ass"
    segments = [
        {
            "id": 0,
            "start": 0.001,
            "end": 61.239,
            "text": "Olá {mundo}\\\n字幕",
            "words": [],
        }
    ]

    write_ass(path, segments, validate_subtitle_config(None), GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert "ScriptType: v4.00+" in content
    assert (
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 0\n"
    ) in content
    assert (
        "Style: Default,Roboto,43,&H00FFFFFF,&H00FFFFFF,&H66000000,"
        "&H66000000,0,0,0,0,100,100,0,0,4,0,2,2,65,65,115,1"
    ) in content
    assert content.split("Style: Default,", 1)[1].split(",")[17] == "2"
    assert r"{\pos" not in content
    assert "0:00:00.00,0:01:01.24" in content
    assert r"{\b400}Olá" in content
    assert "\\{mundo\\}" in content
    assert "\\N字幕" in content


@pytest.mark.parametrize(
    ("rgba", "ass"),
    [
        ("#112233", "&H00332211"),
        ("#112233FF", "&H00332211"),
        ("#11223300", "&HFF332211"),
        ("#11223380", "&H7F332211"),
    ],
)
def test_rgba_color_conversion_uses_bgr_and_inverted_alpha(rgba, ass):
    assert rgba_to_ass_color(rgba) == ass


@pytest.mark.parametrize(
    ("rgba", "opacity", "effective"),
    [
        ("#112233", "100%", "#112233FF"),
        ("#112233", "50%", "#11223380"),
        ("#11223380", "50%", "#11223340"),
        ("#11223301", "50%", "#11223301"),
        ("#112233FF", "0%", "#11223300"),
    ],
)
def test_rgba_opacity_composes_conventional_alpha_once(rgba, opacity, effective):
    assert compose_rgba_opacity(rgba, parse_opacity(opacity)) == effective


def test_opacity_compiles_text_backdrop_shadow_and_positioned_box_once(
    tmp_path: Path,
):
    path = tmp_path / "opacity.ass"
    config = validate_subtitle_config(
        None,
        appearance_values={
            "text_color": "#11223380",
            "backdrop_color": "#44556699",
            "opacity": "50%",
        },
        relative_values={
            "line_height": "64px",
            "max_width": "600px",
            "max_height": "200px",
        },
    )

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "first\nsecond"}],
        config,
        GEOMETRY,
        preserve_line_breaks=True,
    )

    content = path.read_text(encoding="utf-8")
    default_style = next(
        line for line in content.splitlines() if line.startswith("Style: Default,")
    ).split(",")
    assert default_style[3:7] == [
        "&HBF332211",
        "&HBF332211",
        "&HB2665544",
        "&HB2665544",
    ]
    assert r"\1c&H665544&\1a&HB2&" in content


def test_explicit_full_opacity_preserves_default_ass_bytes(tmp_path: Path):
    default_path = tmp_path / "default-opacity.ass"
    explicit_path = tmp_path / "explicit-opacity.ass"
    segment = {"start": 0.0, "end": 1.0, "text": "sample"}

    write_ass(default_path, [segment], validate_subtitle_config(None), GEOMETRY)
    write_ass(
        explicit_path,
        [segment],
        validate_subtitle_config(None, appearance_values={"opacity": "100%"}),
        GEOMETRY,
    )

    assert default_path.read_bytes() == explicit_path.read_bytes()


@pytest.mark.parametrize(
    ("backdrop", "border_style", "outline_weight"),
    [("none", 1, 0), ("outline", 1, 3), ("box", 4, 3)],
)
def test_semantic_backdrops_compile_to_private_ass_fields(
    backdrop, border_style, outline_weight
):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "bold": True,
            "italic": True,
            "backdrop": backdrop,
        },
        relative_values={"outline_weight": "6%"},
    )

    style = _compile_style(resolve_subtitle_config(config, GEOMETRY))

    assert style["border_style"] == border_style
    assert style["outline_weight"] == outline_weight
    assert style["bold"] == 0
    assert style["italic"] == -1


def test_letter_spacing_compiles_to_ass_style_spacing_without_event_tag(
    tmp_path: Path,
):
    path = tmp_path / "spacing.ass"
    config = validate_subtitle_config(
        None,
        relative_values={"letter_spacing": "2px"},
    )

    style = _compile_style(resolve_subtitle_config(config, GEOMETRY))
    write_ass(path, [{"start": 0.0, "end": 1.0, "text": "sample"}], config, GEOMETRY)

    assert style["spacing"] == 2
    content = path.read_text(encoding="utf-8")
    assert r"{\fsp" not in content
    assert r"{\b400}sample" in content


@pytest.mark.parametrize("font_weight", list(FontWeight))
def test_all_font_weights_compile_to_exact_event_override(
    tmp_path: Path, font_weight: FontWeight
):
    path = tmp_path / f"{font_weight.canonical_name}.ass"
    config = validate_subtitle_config(
        None,
        appearance_values={"font_weight": font_weight.canonical_name},
    )

    style = _compile_style(resolve_subtitle_config(config, GEOMETRY))
    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "sample"}],
        config,
        GEOMETRY,
    )

    assert style["bold"] == 0
    assert rf"{{\b{font_weight.rank}}}sample" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_format_ass_time_rejects_invalid_values(value):
    with pytest.raises(ArtifactError):
        format_ass_time(value)


def test_escape_ass_text_neutralizes_override_syntax_and_line_endings():
    assert escape_ass_text("{\\an8}\r\ntext") == "\\{\\\\an8\\}\\Ntext"


def test_write_ass_serializes_generated_guide_events_and_rejects_raw_newlines(
    tmp_path: Path,
):
    path = tmp_path / "guides.ass"
    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "sample"}],
        validate_subtitle_config(None),
        GEOMETRY,
        guide_events=(AssDrawingEvent(0.0, 1.0, r"{\p1}m 0 0 l 1 1{\p0}"),),
    )
    assert r"{\p1}m 0 0 l 1 1{\p0}" in path.read_text(encoding="utf-8")

    with pytest.raises(ArtifactError, match="guide events"):
        write_ass(
            path,
            [{"start": 0.0, "end": 1.0, "text": "sample"}],
            validate_subtitle_config(None),
            GEOMETRY,
            guide_events=(AssDrawingEvent(0.0, 1.0, "bad\ntext"),),
        )


@pytest.mark.parametrize(
    ("position", "alignment"),
    [
        (SubtitlePosition.BOTTOM_LEFT, 1),
        (SubtitlePosition.BOTTOM_CENTER, 2),
        (SubtitlePosition.BOTTOM_RIGHT, 3),
        (SubtitlePosition.MIDDLE_LEFT, 4),
        (SubtitlePosition.CENTER, 5),
        (SubtitlePosition.MIDDLE_RIGHT, 6),
        (SubtitlePosition.TOP_LEFT, 7),
        (SubtitlePosition.TOP_CENTER, 8),
        (SubtitlePosition.TOP_RIGHT, 9),
    ],
)
def test_named_positions_use_private_ass_alignment_codes(position, alignment):
    assert _ass_alignment_for_position(position) == alignment


def test_custom_ass_placement_is_serialized_before_escaped_text(tmp_path: Path):
    path = tmp_path / "custom.ass"
    config = validate_subtitle_config(
        None,
        relative_values={
            "position_x": "50%",
            "position_y": "86%",
            "max_width": "60%",
            "max_height": "20%",
        },
        anchor="bottom-center",
    )

    write_ass(
        path,
        [
            {"start": 0.0, "end": 1.0, "text": r"Text, {\an9}\\value"},
            {"start": 1.0, "end": 2.0, "text": "Segundo"},
        ],
        config,
        GEOMETRY,
    )

    content = path.read_text(encoding="utf-8")
    assert content.count(r"{\an2\pos(540,1651)}") == 2
    assert r"{\an9}" not in content
    assert r"Text, \{\\an9\}\\\\value" in content


def test_ass_can_preserve_intentional_line_breaks_without_changing_default(
    tmp_path: Path,
):
    preserved_path = tmp_path / "preserved.ass"
    write_ass(
        preserved_path,
        [{"start": 0.0, "end": 1.0, "text": "one\ntwo"}],
        validate_subtitle_config(None),
        GEOMETRY,
        preserve_line_breaks=True,
    )

    preserved = preserved_path.read_text(encoding="utf-8")
    assert r"{\q2}one\Ntwo" in preserved

    default_path = tmp_path / "default.ass"
    write_ass(
        default_path,
        [{"start": 0.0, "end": 1.0, "text": "one\ntwo"}],
        validate_subtitle_config(None),
        GEOMETRY,
    )
    assert r"{\q2}" not in default_path.read_text(encoding="utf-8")


def test_explicit_line_height_positions_lines_and_shares_box_backdrop(
    tmp_path: Path,
):
    path = tmp_path / "line-height.ass"
    config = validate_subtitle_config(
        None,
        relative_values={
            "line_height": "64px",
            "max_width": "600px",
            "max_height": "200px",
        },
    )

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "first\nsecond"}],
        config,
        GEOMETRY,
        preserve_line_breaks=True,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert len(dialogue) == 3
    content = path.read_text(encoding="utf-8")
    default_style = next(
        line for line in content.splitlines() if line.startswith("Style: Default,")
    ).split(",")
    positioned_style = next(
        line for line in content.splitlines() if line.startswith("Style: Positioned,")
    ).split(",")
    assert default_style[15:17] == ["4", "0"]
    assert positioned_style[15:17] == ["1", "0"]
    assert dialogue[0].startswith("Dialogue: 0,")
    assert all(line.startswith("Dialogue: 1,") for line in dialogue[1:])
    assert all(",Positioned,," in line for line in dialogue)
    assert dialogue[1].count(r"\pos(540,") == 1
    assert dialogue[2].count(r"\pos(540,") == 1
    assert r"\p1" in dialogue[0]
    assert "first\\Nsecond" not in "\n".join(dialogue[1:])


def test_explicit_line_height_keeps_single_line_on_traditional_ass_path(
    tmp_path: Path,
):
    path = tmp_path / "single-line-height.ass"
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "line_height": "100%",
            "max_width": "100px",
            "max_height": "200px",
        },
    )

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "one-unbreakable-long-token"}],
        config,
        GEOMETRY,
    )

    content = path.read_text(encoding="utf-8")
    dialogue = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue) == 1
    assert ",Default,," in dialogue[0]
    assert r"\pos(" not in dialogue[0]
    assert "Style: Positioned," not in content
    default_style = next(
        line for line in content.splitlines() if line.startswith("Style: Default,")
    ).split(",")
    assert default_style[15] == "4"


def test_write_ass_reuses_supplied_wrapping_metrics(tmp_path: Path, monkeypatch):
    path = tmp_path / "shared-metrics.ass"
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "line_height": "125%",
            "max_width": "300px",
            "max_height": "200px",
        },
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)

    def reject_recomputation(*args, **kwargs):
        pytest.fail("write_ass recomputed wrapping metrics")

    monkeypatch.setattr("multisubs.ass.resolve_wrapping_metrics", reject_recomputation)

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "first\nsecond"}],
        config,
        GEOMETRY,
        wrapping_metrics=metrics,
    )

    assert path.exists()


def test_auto_line_height_skips_wrapping_metrics_in_ass_writer(
    tmp_path: Path,
    monkeypatch,
):
    path = tmp_path / "auto-line-height.ass"
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "18px",
            "max_height": "9px",
        },
    )

    def reject_resolution(*args, **kwargs):
        pytest.fail("auto line height resolved wrapping metrics in the ASS writer")

    monkeypatch.setattr("multisubs.ass.resolve_wrapping_metrics", reject_resolution)

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "sample"}],
        config,
        GEOMETRY,
    )

    assert path.exists()


def test_explicit_progressive_lines_keep_cue_global_word_boundaries(
    tmp_path: Path,
):
    path = tmp_path / "line-height-progressive.ass"
    config = validate_subtitle_config(
        None,
        relative_values={
            "line_height": "64px",
            "max_width": "600px",
            "max_height": "200px",
        },
        effects_values={"karaoke": True},
    )
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": "one two\nthree",
        "_karaoke_cue": KaraokeCue(
            (
                SubtitleDisplayFragment("one", 0),
                SubtitleDisplayFragment(" "),
                SubtitleDisplayFragment("two", 1),
                SubtitleDisplayFragment("\n"),
                SubtitleDisplayFragment("three", 2),
            ),
            (20, 30, 50),
            ((0, 20), (20, 50), (50, 100)),
        ),
    }

    write_ass(path, [segment], config, GEOMETRY)

    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: 1,")
    ]
    assert len(lines) == 6
    assert sum(r"{\k" in line for line in lines) == 3
    assert sum("0:00:00.00,0:00:00.20" in line for line in lines) == 2
    second_line = lines[3:]
    assert len(second_line) == 3
    assert r"\1c&H4FD5FF&" not in second_line[0]
    assert r"\1c&H4FD5FF&" not in second_line[1]
    assert r"\1c&H4FD5FF&" in second_line[2]


def test_named_center_uses_native_alignment_and_actual_margins(
    tmp_path: Path,
):
    path = tmp_path / "center.ass"
    config = validate_subtitle_config(
        None,
        position="center",
        relative_values={
            "margin_left": "40px",
            "margin_right": "140px",
            "margin_top": "100px",
            "margin_bottom": "300px",
        },
    )

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "Centered"}],
        config,
        GEOMETRY,
    )

    content = path.read_text(encoding="utf-8")
    style = content.split("Style: Default,", 1)[1].splitlines()[0].split(",")
    assert style[17:21] == ["5", "40", "140", "0"]
    assert r"{\pos" not in content
    assert content.endswith("Centered\n")


@pytest.mark.parametrize(
    ("anchor", "alignment"),
    [
        (position, alignment)
        for position, alignment in (
            (SubtitlePosition.TOP_LEFT, 7),
            (SubtitlePosition.TOP_CENTER, 8),
            (SubtitlePosition.TOP_RIGHT, 9),
            (SubtitlePosition.MIDDLE_LEFT, 4),
            (SubtitlePosition.CENTER, 5),
            (SubtitlePosition.MIDDLE_RIGHT, 6),
            (SubtitlePosition.BOTTOM_LEFT, 1),
            (SubtitlePosition.BOTTOM_CENTER, 2),
            (SubtitlePosition.BOTTOM_RIGHT, 3),
        )
    ],
)
def test_serialize_ass_placement_uses_private_anchor_code(anchor, alignment):
    placement = CuePlacement(anchor=anchor, position_x=10, position_y=20)

    assert serialize_ass_placement(placement) == (f"{{\\an{alignment}\\pos(10,20)}}")
