"""Encoding choices, early initialization, and CLI/API propagation."""

import subprocess
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import ffmpeg
import pytest
from typer.testing import CliRunner

from multisubs import (
    VideoEncodingConfig,
    cli,
    render_transcript,
    subtitler,
    transcriber,
)
from multisubs.config import validate_subtitle_config, validate_video_encoding_config
from multisubs.errors import DependencyError, ValidationError
from multisubs.models import RunRequest, VideoGeometry

GEOMETRY = VideoGeometry(0, 640, 360, 640, 360, 0, Fraction(1), Fraction(16, 9), 2.0)


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (None, VideoEncodingConfig()),
        (VideoEncodingConfig("libx264"), VideoEncodingConfig("libx264", "medium", 23)),
        (
            VideoEncodingConfig("h264_nvenc"),
            VideoEncodingConfig("h264_nvenc", "p4", 28),
        ),
        (
            VideoEncodingConfig("h264_nvenc", "p7"),
            VideoEncodingConfig("h264_nvenc", "p7", 28),
        ),
        (
            VideoEncodingConfig("h264_nvenc", quality=23),
            VideoEncodingConfig("h264_nvenc", "p4", 23),
        ),
        (
            VideoEncodingConfig("h264_nvenc", quality=0),
            VideoEncodingConfig("h264_nvenc", "p4", 0),
        ),
        (
            VideoEncodingConfig("libx264", "veryfast", 0),
            VideoEncodingConfig("libx264", "veryfast", 0),
        ),
        (
            VideoEncodingConfig("h264_nvenc", "p7", 51),
            VideoEncodingConfig("h264_nvenc", "p7", 51),
        ),
    ],
)
def test_encoding_defaults_and_quality_boundaries(config, expected):
    assert validate_video_encoding_config(config) == expected


@pytest.mark.parametrize(
    "config",
    [
        {},
        VideoEncodingConfig("unknown"),
        VideoEncodingConfig(preset="veryfast"),
        VideoEncodingConfig(quality=23),
        VideoEncodingConfig("libx264", "p4"),
        VideoEncodingConfig("h264_nvenc", "veryfast"),
        VideoEncodingConfig("h264_nvenc", "p4 -gpu 1"),
        VideoEncodingConfig("libx264", quality=-1),
        VideoEncodingConfig("libx264", quality=52),
        VideoEncodingConfig("h264_nvenc", quality=True),
        VideoEncodingConfig("h264_nvenc", quality=cast(Any, 23.0)),
    ],
)
def test_invalid_encoding_is_rejected_without_ffmpeg(config, monkeypatch):
    monkeypatch.setattr(
        subtitler.subprocess,
        "run",
        lambda *_a, **_k: pytest.fail("FFmpeg must not run"),
    )
    with pytest.raises(ValidationError):
        validate_video_encoding_config(config)


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("encoder", [None, "libx264", "h264_nvenc"])
def test_encoding_graph_preserves_filters_audio_and_default_codec(
    tmp_path, encoder, preview
):
    config = validate_video_encoding_config(VideoEncodingConfig(encoder))
    source, subtitle, output = (
        tmp_path / name for name in ("source.mp4", "caption.ass", "output.mp4")
    )
    if preview:
        graph = subtitler._build_animation_preview_stream(
            ffmpeg,
            source,
            subtitle,
            output,
            GEOMETRY,
            2.0,
            video_encoding=config,
        )
    else:
        graph = subtitler._build_output_stream(
            ffmpeg,
            source,
            subtitle,
            output,
            GEOMETRY,
            video_encoding=config,
        )
    # ffmpeg-python uses a Python 2 basestring shim for its inferred argv type.
    command = cast(list[str], ffmpeg.compile(graph))
    assert "subtitles=" in " ".join(command)
    if preview:
        assert "-an" in command
        assert command[command.index("-r") + 1] == "30"
    else:
        assert "0:a?" in command
        assert command[command.index("-acodec") + 1] == "copy"
    if encoder is None:
        assert ("-vcodec" in command) == preview
        assert (
            "-preset" not in command and "-crf" not in command and "-cq" not in command
        )
    else:
        assert command[command.index("-vcodec") + 1] == encoder
        assert command[command.index("-preset") + 1] == config.preset
        flag = "-crf" if encoder == "libx264" else "-cq"
        assert command[command.index(flag) + 1] == (
            "23" if encoder == "libx264" else "28"
        )
        if encoder == "h264_nvenc":
            assert "-crf" not in command
            assert command[command.index("-b:v") + 1] == "0"
            assert command[command.index("-rc") + 1] == "vbr"


def test_default_encoding_never_starts_a_preflight(monkeypatch):
    monkeypatch.setattr(
        subtitler.subprocess,
        "run",
        lambda *_a, **_kw: pytest.fail("no default preflight"),
    )
    subtitler.validate_video_encoding_support(None)
    subtitler.validate_video_encoding_support(VideoEncodingConfig())


def test_nvenc_preflight_uses_real_initialization_and_is_not_cached(monkeypatch):
    commands = []
    monkeypatch.setattr(subtitler.shutil, "which", lambda _: "/bin/ffmpeg")

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["timeout"] == 30
        assert "color=c=black:s=320x180:r=1" in command
        assert command[-3:] == ["-f", "null", "-"]
        assert command[command.index("-cq") + 1] == "28"
        if len(commands) == 1:
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="Driver does not support required nvenc API version 13.1",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subtitler.subprocess, "run", run)
    config = VideoEncodingConfig("h264_nvenc")
    with pytest.raises(DependencyError, match="NVIDIA.*13.1"):
        subtitler.validate_video_encoding_support(config)
    subtitler.validate_video_encoding_support(config)
    assert len(commands) == 2


def test_preflight_timeout_has_an_actionable_error(monkeypatch):
    monkeypatch.setattr(subtitler.shutil, "which", lambda _: "/bin/ffmpeg")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 30)

    monkeypatch.setattr(subtitler.subprocess, "run", timeout)
    with pytest.raises(DependencyError, match="h264_nvenc.*timed out"):
        subtitler.validate_video_encoding_support(VideoEncodingConfig("h264_nvenc"))


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize(
    "arguments",
    [
        ["--video-preset", "veryfast"],
        ["--video-encoder", "libx264", "--video-preset", "p4"],
        ["--video-encoder", "h264_nvenc", "--video-quality", "52"],
    ],
)
def test_cli_rejects_invalid_encoding_before_processing(
    tmp_path, monkeypatch, arguments, preview
):
    source = tmp_path / "source.mp4"
    source.touch()
    monkeypatch.setattr(
        cli,
        "_run_request",
        lambda *_a, **_kw: pytest.fail("invalid request must not run"),
    )
    if preview:
        arguments = [*arguments, "--preview-layout"]
    assert CliRunner().invoke(cli.app, ["-i", str(source), *arguments]).exit_code == 2


@pytest.mark.parametrize("preview", [None, "--preview-layout", "--preview-animation"])
@pytest.mark.parametrize("quality", [None, 23])
def test_cli_carries_normalized_encoding_independently_of_subtitle_style(
    tmp_path, monkeypatch, preview, quality
):
    source = tmp_path / "source.mp4"
    source.touch()
    requests = []

    def run(request, *args, **kwargs):
        requests.append(request)
        return tmp_path / "result.mp4"

    monkeypatch.setattr(cli, "_run_request", run)
    args = ["-i", str(source), "--video-encoder", "h264_nvenc"]
    if quality is not None:
        args.extend(["--video-quality", str(quality)])
    if preview:
        args.append(preview)
    assert cli.main(args) == 0
    assert requests[0].video_encoding == VideoEncodingConfig(
        "h264_nvenc", "p4", 28 if quality is None else quality
    )
    assert requests[0].subtitle_config == validate_subtitle_config(None)


def test_preflight_failure_precedes_asr_and_work_directory(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.touch()
    output = tmp_path / "output"
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)

    def fail(config):
        raise DependencyError("NVENC driver unavailable")

    monkeypatch.setattr(subtitler, "validate_video_encoding_support", fail)
    monkeypatch.setattr(
        transcriber,
        "transcribe_video",
        lambda *_a, **_kw: pytest.fail("no ASR after failed preflight"),
    )
    request = RunRequest(
        source,
        output,
        "pt",
        "transcribe",
        "turbo",
        validate_subtitle_config(None),
        False,
        video_encoding=VideoEncodingConfig("h264_nvenc"),
    )
    with pytest.raises(DependencyError, match="driver"):
        cli._run_request(request, lambda _: None)
    assert not output.exists()


@pytest.mark.parametrize("entry", ["external", "transcript"])
def test_python_render_apis_preflight_and_forward_encoding(
    tmp_path, monkeypatch, entry
):
    source = tmp_path / "source.mp4"
    source.touch()
    subtitle = tmp_path / "source.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    config = VideoEncodingConfig("libx264", "veryfast", 25)
    events = []
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda _: GEOMETRY)
    monkeypatch.setattr(
        subtitler,
        "validate_video_encoding_support",
        lambda config: events.append(("preflight", config)),
    )

    def embed(*args, **kwargs):
        events.append(("encode", kwargs["video_encoding"]))
        Path(kwargs["output_path"]).write_bytes(b"video")

    monkeypatch.setattr(subtitler, "embed_subtitles", embed)
    if entry == "external":
        subtitler.render_subtitle_file(
            source, subtitle, tmp_path / "out", video_encoding=config
        )
    else:
        document = {
            "schema_version": 1,
            "language": "en",
            "task": "transcribe",
            "asr_backend": "synthetic",
            "model_name": "synthetic",
            "full_text": "Hello",
            "segments": [{"text": "Hello", "start": 0, "end": 1}],
        }
        render_transcript(document, source, tmp_path / "out", video_encoding=config)
    assert events == [("preflight", config), ("encode", config)]


def test_external_cli_accepts_encoding_options(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.touch()
    subtitle = tmp_path / "source.srt"
    subtitle.write_text("captions")
    calls = []

    def render(*args, **kwargs):
        calls.append(kwargs["video_encoding"])
        return tmp_path / "render.mp4"

    monkeypatch.setattr(subtitler, "render_subtitle_file", render)
    assert (
        cli.main(
            [
                "-i",
                str(source),
                "--subtitle-file",
                str(subtitle),
                "--video-encoder",
                "libx264",
                "--video-preset",
                "veryfast",
            ]
        )
        == 0
    )
    assert calls == [VideoEncodingConfig("libx264", "veryfast", 23)]
