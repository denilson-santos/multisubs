from pathlib import Path
from types import SimpleNamespace

import ffmpeg
import pytest

from multisubs.errors import RenderingError
from multisubs.subtitler import (
    _build_output_stream,
    _short_output,
    embed_subtitles,
)


def test_subtitle_filter_is_structured_and_escapes_special_paths(tmp_path: Path):
    source = tmp_path / "video source.mp4"
    subtitle = tmp_path / "odd:comma,quote'back\\slash.ass"
    output = tmp_path / "output.mp4"

    command = ffmpeg.compile(_build_output_stream(ffmpeg, source, subtitle, output))
    command_text = " ".join(command)

    assert "subtitles=filename=" in command_text
    assert "0:a?" in command
    assert "\\:" in command_text
    assert "\\," in command_text
    assert "\\'" in command_text
    assert "\\\\slash.ass" in command_text


def test_render_failure_removes_temporary_media(tmp_path: Path, monkeypatch):
    source = tmp_path / "video.mp4"
    subtitle = tmp_path / "subtitle.ass"
    output_dir = tmp_path / "output"
    source.write_bytes(b"input")
    subtitle.write_text("ASS", encoding="utf-8")

    class FakeFfmpegError(Exception):
        stderr = "render failed"

    class FakeOutput:
        def run(self, **kwargs):
            raise FakeFfmpegError()

    fake_ffmpeg = SimpleNamespace(Error=FakeFfmpegError)
    monkeypatch.setattr("multisubs.subtitler._load_ffmpeg_python", lambda: fake_ffmpeg)
    monkeypatch.setattr(
        "multisubs.subtitler._build_output_stream",
        lambda *args: FakeOutput(),
    )

    with pytest.raises(RenderingError):
        embed_subtitles(source, subtitle, output_dir)

    assert list(output_dir.glob(".*.mp4")) == []
    assert not (output_dir / "video-en.mp4").exists()


def test_short_output_compacts_and_limits_ffmpeg_diagnostics():
    assert _short_output("first\nsecond", limit=20) == "first second"
    assert len(_short_output("x" * 100, limit=10)) == 10
