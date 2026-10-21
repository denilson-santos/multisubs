"""Cancellation and process ownership without requiring an FFmpeg installation."""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace

import ffmpeg
import pytest

from multisubs import (
    CancelledError,
    SpeechTranscript,
    embed_subtitles,
    render_subtitle_file,
    render_transcript,
    subtitler,
)
from multisubs.errors import RenderingError
from multisubs.models import VideoGeometry


def _geometry():
    return VideoGeometry(0, 320, 240, 320, 240, 0, Fraction(1), Fraction(4, 3), 2.0)


def _speech():
    return SpeechTranscript(
        "en",
        "transcribe",
        "parakeet",
        "model",
        "Hello!",
        ({"text": "Hello!", "start": 0.0, "end": 1.0},),
    )


@pytest.mark.parametrize("operation", ["transcript", "file", "embed"])
def test_already_cancelled_operations_do_not_start_media_work(
    tmp_path, monkeypatch, operation
):
    def unexpected(*args, **kwargs):
        pytest.fail("An already cancelled operation must not start a subprocess")

    monkeypatch.setattr(subtitler.subprocess, "Popen", unexpected)
    with pytest.raises(CancelledError):
        if operation == "transcript":
            render_transcript(
                _speech(), "missing.mp4", tmp_path, should_cancel=lambda: True
            )
        else:
            function = render_subtitle_file if operation == "file" else embed_subtitles
            function("missing.mp4", "missing.ass", tmp_path, should_cancel=lambda: True)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["cancel", "callback", "ffmpeg"])
def test_running_encode_is_reaped_and_does_not_affect_another_call(
    tmp_path, monkeypatch, failure
):
    video = tmp_path / "video.mp4"
    subtitles = tmp_path / "source.ass"
    marker = tmp_path / "started"
    video.write_bytes(b"source")
    subtitles.write_text("ASS")
    processes = []
    both_rendering = Barrier(2, timeout=10)

    class Output:
        def __init__(self, target):
            self.target = target

        def run_async(self, **kwargs):
            # An actual owned child verifies termination and reaping. The child
            # stands in for FFmpeg, so the default suite stays hermetic.
            script = (
                "from pathlib import Path; import sys,time; "
                "Path(sys.argv[1]).write_bytes(b'partial'); "
                "Path(sys.argv[2]).touch(); "
                + ("sys.exit(3)" if failure == "ffmpeg" else "time.sleep(30)")
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(self.target), str(marker)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(process)
            return process

        def run(self, **kwargs):
            self.target.write_bytes(b"complete")

    monkeypatch.setattr(
        subtitler, "_load_ffmpeg_python", lambda: SimpleNamespace(Error=ffmpeg.Error)
    )
    monkeypatch.setattr(
        subtitler,
        "_build_output_stream",
        lambda _ffmpeg, _source, _sub, target, *a, **kw: Output(target),
    )

    def should_cancel():
        if marker.exists():
            if failure == "callback":
                raise RuntimeError("cancellation callback failed")
            return failure == "cancel"
        return False

    def render(index):
        both_rendering.wait()
        return embed_subtitles(
            video,
            subtitles,
            tmp_path / str(index),
            geometry=_geometry(),
            should_cancel=should_cancel if index == 0 else None,
        )

    expected = {
        "cancel": CancelledError,
        "callback": RuntimeError,
        "ffmpeg": RenderingError,
    }[failure]
    with ThreadPoolExecutor(max_workers=2) as pool:
        failed = pool.submit(render, 0)
        successful = pool.submit(render, 1)
        with pytest.raises(expected):
            failed.result(timeout=10)
        published = Path(successful.result(timeout=10))
    assert published.read_bytes() == b"complete"
    assert processes and all(process.poll() is not None for process in processes)
    assert not list((tmp_path / "0").iterdir())
    assert list((tmp_path / "1").iterdir()) == [published]


def test_unresponsive_process_is_killed_and_waited(monkeypatch):
    calls = []

    class Process:
        args = ["ffmpeg"]

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def kill(self):
            calls.append("kill")

        def communicate(self, timeout=None):
            calls.append(("communicate", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return b"", b""

    with pytest.raises(CancelledError):
        subtitler._communicate(Process(), lambda: True)  # type: ignore[arg-type]
    assert calls == ["terminate", ("communicate", 2), "kill", ("communicate", None)]


@pytest.mark.parametrize("operation", ["transcript", "file"])
def test_high_level_cancellation_cleans_private_artifacts_and_keeps_completed(
    tmp_path, monkeypatch, operation
):
    video = tmp_path / "source.mp4"
    subtitle = tmp_path / "source.srt"
    output = tmp_path / "out"
    video.write_bytes(b"source")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello!\n")
    output.mkdir()
    previous = output / "completed.mp4"
    previous.write_bytes(b"previous run")
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda **kw: None)
    monkeypatch.setattr(
        subtitler, "validate_video_encoding_support", lambda *a, **kw: None
    )
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda *a, **kw: _geometry())

    def cancel_render(*args, **kwargs):
        Path(kwargs["output_path"]).write_bytes(b"partial")
        raise CancelledError("cancelled during render")

    monkeypatch.setattr(subtitler, "embed_subtitles", cancel_render)
    with pytest.raises(CancelledError):
        if operation == "transcript":
            render_transcript(_speech(), video, output, should_cancel=lambda: False)
        else:
            render_subtitle_file(video, subtitle, output, should_cancel=lambda: False)
    assert list(output.iterdir()) == [previous]
    assert previous.read_bytes() == b"previous run"


def test_concurrent_video_publication_never_overwrites(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    subtitles = tmp_path / "captions.ass"
    destination = tmp_path / "output"
    video.write_bytes(b"input")
    subtitles.write_text("ASS")
    both_chosen = Barrier(2, timeout=10)

    class Output:
        def __init__(self, target):
            self.target = target

        def run(self, **kwargs):
            self.target.write_bytes(self.target.name.encode())
            both_chosen.wait()

    monkeypatch.setattr(
        subtitler, "_load_ffmpeg_python", lambda: SimpleNamespace(Error=ffmpeg.Error)
    )
    monkeypatch.setattr(
        subtitler,
        "_build_output_stream",
        lambda _ffmpeg, _source, _sub, target, *a, **kw: Output(target),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: Path(
                    embed_subtitles(video, subtitles, destination, geometry=_geometry())
                ),
                range(2),
            )
        )
    assert len(set(results)) == 2
    assert len({result.read_bytes() for result in results}) == 2
    assert len(list(destination.iterdir())) == 2


@pytest.mark.parametrize("operation", ["transcript", "file"])
@pytest.mark.parametrize("failure", ["cancel", "render"])
def test_high_level_concurrent_calls_isolate_failed_peer(
    tmp_path, monkeypatch, operation, failure
):
    video = tmp_path / "source.mp4"
    subtitle = tmp_path / "source.srt"
    video.write_bytes(b"input")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello!\n")
    source = _speech()
    before = source.to_dict()
    both_encoding = Barrier(2, timeout=10)
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda **kw: None)
    monkeypatch.setattr(
        subtitler, "validate_video_encoding_support", lambda *a, **kw: None
    )
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda *a, **kw: _geometry())

    def encode(*args, **kwargs):
        path = Path(kwargs["output_path"])
        path.write_bytes(b"partial")
        both_encoding.wait()
        if path.parent.parent.name == "0":
            if failure == "cancel":
                raise CancelledError("cancelled encode")
            raise RenderingError("failed encode")
        path.write_bytes(b"complete")

    monkeypatch.setattr(subtitler, "embed_subtitles", encode)

    def run(index):
        destination = tmp_path / str(index)
        if operation == "transcript":
            return render_transcript(source, video, destination).video_path
        return render_subtitle_file(video, subtitle, destination)

    with ThreadPoolExecutor(max_workers=2) as pool:
        failed = pool.submit(run, 0)
        successful = pool.submit(run, 1)
        with pytest.raises(CancelledError if failure == "cancel" else RenderingError):
            failed.result(timeout=20)
        final = successful.result(timeout=20)
    assert final.read_bytes() == b"complete"
    assert not list((tmp_path / "0").iterdir())
    assert not list(tmp_path.rglob(".multisubs-*"))
    assert source.to_dict() == before


def test_cancellation_after_video_publication_preserves_completed_output(
    tmp_path, monkeypatch
):
    video = tmp_path / "source.mp4"
    subtitle = tmp_path / "captions.ass"
    video.write_bytes(b"input")
    subtitle.write_text("ASS")
    cancelled = Event()

    class Output:
        def __init__(self, target):
            self.target = target

        def run_async(self, **kwargs):
            script = (
                "from pathlib import Path; import sys; "
                "Path(sys.argv[1]).write_bytes(b'complete')"
            )
            return subprocess.Popen(
                [sys.executable, "-c", script, str(self.target)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def progress(message):
        if message == "Subtitle video rendered successfully.":
            cancelled.set()

    monkeypatch.setattr(
        subtitler, "_load_ffmpeg_python", lambda: SimpleNamespace(Error=ffmpeg.Error)
    )
    monkeypatch.setattr(
        subtitler,
        "_build_output_stream",
        lambda _ffmpeg, _source, _sub, target, *a, **kw: Output(target),
    )
    with pytest.raises(CancelledError):
        embed_subtitles(
            video,
            subtitle,
            tmp_path / "out",
            geometry=_geometry(),
            progress=progress,
            should_cancel=cancelled.is_set,
        )
    files = list((tmp_path / "out").iterdir())
    assert len(files) == 1 and files[0].read_bytes() == b"complete"


def test_cancellable_probe_and_preflight_command_output_and_timeout():
    completed = subtitler._run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('ok'); print('details', file=sys.stderr)",
        ],
        should_cancel=lambda: False,
        timeout=5,
    )
    assert completed.returncode == 0
    assert completed.stdout == "ok\n" and completed.stderr == "details\n"
    with pytest.raises(subprocess.TimeoutExpired):
        subtitler._run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            should_cancel=lambda: False,
            timeout=0.15,
        )
