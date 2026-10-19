"""Real CPU/NVENC encodes through the public API and native CLI, without ASR."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from multisubs import VideoEncodingConfig, cli, render_transcript, transcriber

pytestmark = pytest.mark.integration


def _run(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(arguments), check=True, capture_output=True, timeout=60)


def _probe(path: Path):
    return json.loads(
        _run("ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)).stdout
    )


def _audio_hash(path: Path, index: int):
    return _run(
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        f"0:a:{index}",
        "-c:a",
        "copy",
        "-f",
        "hash",
        "-hash",
        "sha256",
        "-",
    ).stdout


@pytest.mark.parametrize("encoder", ["libx264", "h264_nvenc"])
@pytest.mark.parametrize("entry", ["external-cli", "transcript-api", "animation-cli"])
def test_real_video_encoding_preserves_media_and_collision_safety(
    tmp_path,
    monkeypatch,
    encoder,
    entry,
):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    if encoder == "h264_nvenc" and os.environ.get("MULTISUBS_TEST_NVENC") != "1":
        pytest.skip("Set MULTISUBS_TEST_NVENC=1 to require a working NVIDIA encoder")
    monkeypatch.setattr(
        transcriber,
        "create_adapter",
        lambda *_a, **_kw: pytest.fail("rendering must not call ASR"),
    )
    source = tmp_path / "video.mp4"
    _run(
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=640x360:r=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-map",
        "2:a:0",
        "-t",
        "1",
        "-c:v",
        "mpeg4",
        "-c:a",
        "aac",
        str(source),
    )
    subtitle = tmp_path / "captions.srt"
    subtitle.write_text(
        "1\n00:00:00,100 --> 00:00:00,900\nHello video\n", encoding="utf-8"
    )
    config = VideoEncodingConfig(encoder)
    output = tmp_path / "output"
    common = [
        "-i",
        str(source),
        "-o",
        str(output),
        "--video-encoder",
        encoder,
    ]
    document = {
        "schema_version": 1,
        "language": "en",
        "task": "transcribe",
        "asr_backend": "synthetic",
        "model_name": "synthetic",
        "full_text": "Hello video",
        "segments": [{"start": 0.1, "end": 0.9, "text": "Hello video"}],
    }

    def render():
        if entry == "external-cli":
            assert cli.main([*common, "--subtitle-file", str(subtitle)]) == 0
        elif entry == "animation-cli":
            assert (
                cli.main(
                    [
                        *common,
                        "--preview-animation",
                        "--preview-duration",
                        "1s",
                        "--preview-at",
                        "00:00:00.500",
                        "--preview-text",
                        "Hello video",
                    ]
                )
                == 0
            )
        else:
            render_transcript(document, source, output, video_encoding=config)

    render()
    first = next(output.glob("*.mp4"))
    original = first.read_bytes()
    render()
    videos = list(output.glob("*.mp4"))
    assert len(videos) == 2
    assert first.read_bytes() == original
    assert any("(1)" in video.name for video in videos)
    assert subtitle.read_text() == "1\n00:00:00,100 --> 00:00:00,900\nHello video\n"
    assert not list(output.glob(".multisubs-*"))
    for video in videos:
        streams = _probe(video)["streams"]
        video_stream = next(s for s in streams if s["codec_type"] == "video")
        assert video_stream["codec_name"] == "h264"
        assert (video_stream["width"], video_stream["height"]) == (640, 360)
        assert int(video_stream["nb_frames"]) == (
            60 if entry == "animation-cli" else 30
        )
        audio = [s for s in streams if s["codec_type"] == "audio"]
        assert len(audio) == (0 if entry == "animation-cli" else 2)
        for index in range(len(audio)):
            assert _audio_hash(video, index) == _audio_hash(source, index)
    # The synthetic source is black; visible bright pixels prove a subtitle burn.
    timestamp = "1" if entry == "animation-cli" else "0.5"
    frame = _run(
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        timestamp,
        "-i",
        str(first),
        "-frames:v",
        "1",
        "-pix_fmt",
        "gray",
        "-f",
        "rawvideo",
        "-",
    ).stdout
    assert max(frame) > 100
