from fractions import Fraction
from pathlib import Path

import pytest

from multisubs.ass import escape_ass_text, format_ass_time, write_ass
from multisubs.config import DEFAULT_STYLE, validate_subtitle_config
from multisubs.errors import ArtifactError
from multisubs.models import VideoGeometry

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


def test_write_ass_preserves_style_contract_and_escapes_dialogue(tmp_path: Path):
    path = tmp_path / "captions.ass"
    legacy_path = tmp_path / "legacy-captions.ass"
    segments = [
        {
            "id": 0,
            "start": 0.001,
            "end": 61.239,
            "text": "Olá {mundo}\\\n字幕",
            "words": [],
        }
    ]

    write_ass(path, segments, validate_subtitle_config(DEFAULT_STYLE), GEOMETRY)
    write_ass(legacy_path, segments, DEFAULT_STYLE, GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert content == legacy_path.read_text(encoding="utf-8")
    assert "ScriptType: v4.00+" in content
    assert (
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 0\n"
    ) in content
    assert "Style: Default,Roboto,14" in content
    assert "0:00:00.00,0:01:01.24" in content
    assert "\\{mundo\\}" in content
    assert "\\N字幕" in content


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_format_ass_time_rejects_invalid_values(value):
    with pytest.raises(ArtifactError):
        format_ass_time(value)


def test_escape_ass_text_neutralizes_override_syntax_and_line_endings():
    assert escape_ass_text("{\\an8}\r\ntext") == "\\{\\\\an8\\}\\Ntext"
