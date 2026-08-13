from pathlib import Path

import ffmpeg

from multisubs.subtitler import _build_output_stream, _short_output


def test_subtitle_filter_is_structured_and_escapes_special_paths(tmp_path: Path):
    source = tmp_path / "video source.mp4"
    subtitle = tmp_path / "odd:comma,quote'back\\slash.ass"
    output = tmp_path / "output.mp4"

    command = ffmpeg.compile(_build_output_stream(ffmpeg, source, subtitle, output))
    command_text = " ".join(command)

    assert "subtitles=filename=" in command_text
    assert "\\:" in command_text
    assert "\\," in command_text
    assert "\\'" in command_text
    assert "\\\\slash.ass" in command_text


def test_short_output_compacts_and_limits_ffmpeg_diagnostics():
    assert _short_output("first\nsecond", limit=20) == "first second"
    assert len(_short_output("x" * 100, limit=10)) == 10
