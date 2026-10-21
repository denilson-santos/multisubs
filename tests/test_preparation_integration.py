"""Opt-in single-encode composition and real FFmpeg cancellation evidence."""

from __future__ import annotations

import shutil
import subprocess

import ffmpeg
import pytest

from multisubs import (
    CancelledError,
    SpeechTranscript,
    embed_subtitles,
    font_catalog,
    prepare_subtitles,
    subtitler,
    transcriber,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
        reason="FFmpeg and ffprobe are required",
    ),
]


def _speech():
    return SpeechTranscript(
        "en",
        "transcribe",
        "parakeet",
        "model",
        "Hello world!",
        (
            {
                "text": "Hello world!",
                "start": 0.1,
                "end": 0.9,
                "words": [
                    {"word": "Hello", "start": 0.1, "end": 0.4},
                    {"word": " world!", "start": 0.5, "end": 0.9},
                ],
            },
        ),
    )


@pytest.mark.parametrize("width,height", [(320, 180), (180, 320), (240, 240)])
def test_external_cut_crop_blur_and_subtitles_in_one_encode(
    tmp_path, monkeypatch, width, height
):
    def unexpected(*args, **kwargs):
        pytest.fail("Preparation must not invoke ASR")

    monkeypatch.setattr(transcriber, "create_adapter", unexpected)
    monkeypatch.setattr(font_catalog, "bundled_filesystem_directory", lambda _: None)
    output = tmp_path / "final.mp4"
    with prepare_subtitles(
        _speech(),
        output_dir=tmp_path / "workspace",
        frame_width=width,
        frame_height=height,
        template="yellow-pop",
    ) as prepared:
        fonts = prepared.fonts_dir
        assert fonts is not None and fonts.is_dir()
        video = ffmpeg.input("testsrc2=s=360x360:r=10:d=2", f="lavfi").video
        video = video.filter("trim", start=0.2, end=1.2).filter(
            "setpts", "PTS-STARTPTS"
        )
        video = video.filter("crop", 300, 300).filter("scale", width, height)
        video = video.filter("gblur", sigma=0.5)
        video = video.filter(
            "subtitles",
            filename=str(prepared.ass_path),
            fontsdir=str(fonts),
            original_size=f"{width}x{height}",
        )
        ffmpeg.output(
            video, str(output), vcodec="libx264", pix_fmt="yuv420p", threads=1
        ).run(
            capture_stdout=True,
            capture_stderr=True,
        )
        assert fonts.is_dir()
    assert not fonts.exists()
    assert prepared.srt_path.is_file() and prepared.ass_path.is_file()
    geometry = subtitler.probe_video_geometry(output)
    assert (geometry.render_width, geometry.render_height) == (width, height)
    assert geometry.duration_seconds == pytest.approx(1.0, abs=0.12)
    assert not list((tmp_path / "workspace").glob(".multisubs-*"))


def test_real_ffmpeg_is_terminated_on_cancellation(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=320x180:r=10:d=1",
            "-c:v",
            "mpeg4",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    geometry = subtitler.probe_video_geometry(source)
    processes = []
    popen = subprocess.Popen

    def capture_process(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    with prepare_subtitles(
        _speech(),
        output_dir=tmp_path / "subtitles",
        frame_width=320,
        frame_height=180,
    ) as prepared:
        monkeypatch.setattr(subtitler.subprocess, "Popen", capture_process)
        with pytest.raises(CancelledError):
            embed_subtitles(
                source,
                prepared.ass_path,
                tmp_path / "render",
                geometry=geometry,
                fonts_dir=prepared.fonts_dir,
                should_cancel=lambda: bool(processes),
            )
        assert len(processes) == 1 and processes[0].poll() is not None
        assert not list((tmp_path / "render").iterdir())
        assert prepared.ass_path.is_file()
