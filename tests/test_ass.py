from fractions import Fraction
from pathlib import Path

import pytest

from multisubs.ass import (
    _ass_alignment_for_position,
    _compile_style,
    escape_ass_text,
    format_ass_time,
    rgba_to_ass_color,
    serialize_ass_placement,
    write_ass,
)
from multisubs.config import validate_subtitle_config
from multisubs.errors import ArtifactError
from multisubs.layout import resolve_subtitle_config
from multisubs.models import CuePlacement, SubtitlePosition, VideoGeometry

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
        "&H66000000,0,0,0,0,100,100,0,0,4,0,2,2,86,86,154,1"
    ) in content
    assert content.split("Style: Default,", 1)[1].split(",")[17] == "2"
    assert "0:00:00.00,0:01:01.24" in content
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
    assert style["bold"] == -1
    assert style["italic"] == -1


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_format_ass_time_rejects_invalid_values(value):
    with pytest.raises(ArtifactError):
        format_ass_time(value)


def test_escape_ass_text_neutralizes_override_syntax_and_line_endings():
    assert escape_ass_text("{\\an8}\r\ntext") == "\\{\\\\an8\\}\\Ntext"


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
        relative_values={"position_x": "50%", "position_y": "86%"},
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
