"""Direct SRT/ASS rendering contract without transcription."""

import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from typer.testing import CliRunner

from multisubs import cli, subtitler
from multisubs.errors import ArtifactError, RenderingError, ValidationError
from multisubs.models import VideoGeometry

GEOMETRY = VideoGeometry(0, 640, 360, 640, 360, 0, Fraction(1), Fraction(16, 9), 4.0)


def _files(
    tmp_path, extension=".srt", content="1\n00:00:00,400 --> 00:00:01,800\nHello\n"
):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    subtitle = tmp_path / f"captions{extension}"
    subtitle.write_text(content, encoding="utf-8")
    return video, subtitle


@pytest.mark.parametrize("extension", [".srt", ".SRT", ".ass", ".ASS"])
def test_external_files_render_without_rewriting(tmp_path, monkeypatch, extension):
    video, subtitle = _files(tmp_path, extension)
    original = subtitle.read_bytes()
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: GEOMETRY)
    calls = []

    def embed(_video, source_subtitle, _output, **kwargs):
        calls.append((Path(source_subtitle), kwargs["geometry"]))
        Path(kwargs["output_path"]).write_bytes(b"rendered")

    monkeypatch.setattr(subtitler, "embed_subtitles", embed)
    first = subtitler.render_subtitle_file(video, subtitle, tmp_path / "output")
    second = subtitler.render_subtitle_file(video, subtitle, tmp_path / "output")
    assert first.name == "video-subtitled.mp4"
    assert second.name == "video-subtitled (1).mp4"
    assert first.read_bytes() == b"rendered"
    assert calls == [(subtitle, GEOMETRY), (subtitle, GEOMETRY)]
    assert subtitle.read_bytes() == original
    assert video.read_bytes() == b"video"


def test_bad_files_fail_before_probe(tmp_path, monkeypatch):
    video, subtitle = _files(tmp_path, ".txt")
    monkeypatch.setattr(
        subtitler,
        "probe_video_geometry",
        lambda path: pytest.fail("invalid subtitle must fail before probing"),
    )
    with pytest.raises(ValidationError, match="extension"):
        subtitler.render_subtitle_file(video, subtitle, tmp_path / "out")
    subtitle = tmp_path / "empty.srt"
    subtitle.write_bytes(b"")
    with pytest.raises(ValidationError, match="empty"):
        subtitler.render_subtitle_file(video, subtitle, tmp_path / "out")


def test_render_failure_cleans_private_files(tmp_path, monkeypatch):
    video, subtitle = _files(tmp_path)
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: GEOMETRY)

    def fail(*args, **kwargs):
        Path(kwargs["output_path"]).write_bytes(b"partial")
        raise RenderingError("invalid subtitles")

    monkeypatch.setattr(subtitler, "embed_subtitles", fail)
    output = tmp_path / "out"
    with pytest.raises(RenderingError, match="captions.srt"):
        subtitler.render_subtitle_file(video, subtitle, output)
    assert not list(output.iterdir())


def test_publish_failure_leaves_no_video(tmp_path, monkeypatch):
    video, subtitle = _files(tmp_path)
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: GEOMETRY)
    monkeypatch.setattr(
        subtitler,
        "embed_subtitles",
        lambda _video, _sub, _out, **kw: Path(kw["output_path"]).write_bytes(b"ok"),
    )
    monkeypatch.setattr(
        subtitler,
        "publish_files",
        lambda files: (_ for _ in ()).throw(ArtifactError("publication failed")),
    )
    output = tmp_path / "out"
    with pytest.raises(ArtifactError, match="publication failed"):
        subtitler.render_subtitle_file(video, subtitle, output)
    assert not list(output.iterdir())


@pytest.mark.parametrize(
    "conflict",
    [
        ("--asr", "whisperx"),
        ("--template", "default"),
        ("--font", "Roboto"),
    ],
)
def test_cli_rejects_explicit_conflicts(tmp_path, conflict):
    video, subtitle = _files(tmp_path)
    # Parameter pairs are tested separately so default-valued options count.
    option, value = conflict
    result = CliRunner().invoke(
        cli.app,
        ["-i", str(video), "--subtitle-file", str(subtitle), option, value],
    )
    assert result.exit_code == 2
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.output)
    assert "cannot be used with --subtitle-file" in " ".join(output.split())


def test_external_mode_skips_template_catalog(tmp_path, monkeypatch, capsys):
    video, subtitle = _files(tmp_path)
    monkeypatch.setattr(
        cli,
        "require_template_catalog",
        lambda: pytest.fail("external mode must not load templates"),
    )
    monkeypatch.setattr(
        subtitler,
        "render_subtitle_file",
        lambda *_args, **_kwargs: tmp_path / "rendered.mp4",
    )
    assert cli.main(["-i", str(video), "--subtitle-file", str(subtitle)]) == 0
    assert "Video saved to:" in capsys.readouterr().out


def test_missing_fonts_directory_fails_before_probe(tmp_path, monkeypatch):
    video, subtitle = _files(tmp_path)
    monkeypatch.setattr(
        subtitler,
        "probe_video_geometry",
        lambda path: pytest.fail("invalid fonts must fail before probing"),
    )
    with pytest.raises(ValidationError, match="Fonts directory"):
        subtitler.render_subtitle_file(
            video, subtitle, tmp_path / "out", fonts_dir=tmp_path / "missing"
        )


def test_public_api_does_not_import_asr_runtime_in_fresh_process():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from multisubs import render_subtitle_file; "
            "assert not any(name == 'torch' or name.startswith("
            "('whisperx', 'faster_whisper', 'nemo')) "
            "for name in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == ""


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg and ffprobe are required",
)
@pytest.mark.parametrize("extension", [".srt", ".ass"])
def test_real_ffmpeg_external_subtitle_render(tmp_path, extension):
    video = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=640x360:d=2:r=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-shortest",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-y",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    if extension == ".srt":
        content = "1\n00:00:00,400 --> 00:00:01,800\nHello\n"
    else:
        content = (
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 640\n"
            "PlayResY: 360\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,DejaVu Sans,48,&H000000FF,&H000000FF,"
            "&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,10,10,10,1\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, "
            "MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.40,0:00:01.80,Default,,0,0,0,,Hello\n"
        )
    subtitle = tmp_path / f"captions{extension}"
    subtitle.write_text(content, encoding="utf-8")
    result = subtitler.render_subtitle_file(video, subtitle, tmp_path / "output")
    assert subtitle.read_text(encoding="utf-8") == content
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height",
            "-of",
            "csv=p=0",
            str(result),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "video,640,360" in probe and "audio" in probe

    def frame_at(second):
        return subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(result),
                "-ss",
                str(second),
                "-frames:v",
                "1",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout

    assert frame_at(0.1) != frame_at(1.0)
    if extension == ".ass":
        frame = frame_at(1.0)
        top = frame[: 640 * 120 * 3]
        red_pixels = sum(
            1
            for index in range(0, len(top), 3)
            if top[index] > 120
            and top[index] > top[index + 1] * 1.4
            and top[index] > top[index + 2] * 1.4
        )
        assert red_pixels > 100
