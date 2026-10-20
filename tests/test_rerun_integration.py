"""Real excerpt media, original-time animation, and audio checks without ASR."""

import io
import json
import math
import shutil
import subprocess
from array import array

import pytest
from PIL import Image, ImageChops, ImageStat

from multisubs import cli, speech_cache, subtitler, transcriber
from multisubs.asr.base import ASRResult
from multisubs.font_catalog import bundled_font_directory

pytestmark = pytest.mark.integration


def _run(*command):
    return subprocess.run(command, capture_output=True, check=True, timeout=60).stdout


def _probe(path):
    return json.loads(
        _run(
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        )
    )


def _frame(path, timestamp):
    data = _run(
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        str(timestamp),
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-c:v",
        "png",
        "-",
    )
    return Image.open(io.BytesIO(data)).convert("RGB")


def _audio(path, start):
    samples = array("f")
    samples.frombytes(
        _run(
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(start),
            "-i",
            str(path),
            "-t",
            "0.4",
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "f32le",
            "-",
        )
    )
    return samples


def _audio_correlation(reference, actual):
    # Permit subframe codec priming differences, but not the wrong source time.
    scores = []
    for shift in range(-128, 129):
        left = reference[max(0, shift) : len(reference) + min(0, shift)]
        right = actual[max(0, -shift) : len(actual) - max(0, shift)]
        length = min(len(left), len(right))
        left, right = left[:length], right[:length]
        numerator = sum(a * b for a, b in zip(left, right, strict=True))
        denominator = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
        scores.append(numerator / denominator if denominator else 0)
    return max(scores)


@pytest.mark.parametrize(
    ("audio", "rotation", "start", "speech"),
    [
        (True, 0, 1.1, True),
        (False, 90, 1.117, True),
        (True, 180, 1.117, True),
        (False, 270, 3.8, True),
        (False, 0, 0.25, True),
        (False, 0, 1.1, False),
        (True, 90, 1.0, True),
        (False, 270, 3.0, True),
    ],
)
def test_real_clip_matches_source_timeline_and_preserves_media(
    tmp_path,
    monkeypatch,
    audio,
    rotation,
    start,
    speech,
):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required")
    subtitler.validate_ffmpeg_support()
    original = tmp_path / "original.mp4"
    source = tmp_path / "vídeo com espaço.mp4"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=s=640x360:r=30:d=4",
    ]
    if audio:
        # Chirped frequency makes an incorrect audio seek observable.
        command += [
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=0.1*sin(2*PI*(300*t+100*t*t)):s=48000:d=4",
        ]
    command += ["-c:v", "mpeg4", "-q:v", "2"]
    if audio:
        command += ["-c:a", "aac"]
    command += [str(original)]
    _run(*command)
    _run(
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(original),
        "-c",
        "copy",
        "-metadata:s:v:0",
        f"rotate={rotation}",
        str(source),
    )
    output = tmp_path / "output"
    cache = output / ".multisubs-cache"
    calls = []

    class Adapter:
        def transcribe(self, request):
            calls.append(request)
            if not speech:
                return ASRResult("en", "", ())
            return ASRResult(
                "en",
                "Real subtitle clock.",
                (
                    {
                        "start": 0.2,
                        "end": 3.9,
                        "text": "Real subtitle clock.",
                        "words": [
                            {"word": "Real", "start": 0.2, "end": 1.4},
                            {"word": " subtitle", "start": 1.5, "end": 2.5},
                            {"word": " clock.", "start": 2.6, "end": 3.9},
                        ],
                    },
                ),
            )

    monkeypatch.setattr(transcriber, "create_adapter", lambda _: Adapter())
    monkeypatch.setattr(speech_cache, "_versions", lambda _: {})
    common = [
        "-i",
        str(source),
        "-o",
        str(output),
        "--template",
        "yellow-pop",
        "--font-size",
        "8%",
        "--max-height",
        "35%",
    ]
    assert cli.main([*common, "--subtitles-only"]) == 0
    assert len(list((cache / "transcriptions" / "v1").glob("*.json"))) == 1
    ass = next(output.glob("*.ass"))
    reference = tmp_path / "reference.mp4"
    geometry = subtitler.probe_video_geometry(source)
    # Production renderer provides the original full-timeline visual reference.
    with bundled_font_directory("Montserrat") as fonts:
        subtitler.embed_subtitles(
            source,
            ass,
            tmp_path,
            output_path=reference,
            geometry=geometry,
            fonts_dir=fonts,
        )
    before = set(output.iterdir())
    if start == int(start):
        timestamp = f"00:00:{int(start):02d}"
        assert (
            cli.main(
                [
                    *common,
                    "--preview-clip",
                    "--preview-at",
                    timestamp,
                    "--preview-duration",
                    "1500ms",
                ]
            )
            == 0
        )
    else:
        # The CLI accepts whole seconds; the Python rendering boundary keeps
        # precise cuts and existing subframe synchronization coverage.
        with bundled_font_directory("Montserrat") as fonts:
            subtitler.render_subtitle_clip(
                source,
                ass,
                output / "direct-excerpt.mp4",
                geometry=geometry,
                start=start,
                duration=1.5,
                fonts_dir=fonts,
            )
    assert len(calls) == 1
    clip = next(iter(set(output.iterdir()) - before))
    assert clip.suffix == ".mp4"
    info = _probe(clip)
    video = next(
        stream for stream in info["streams"] if stream["codec_type"] == "video"
    )
    assert (video["width"], video["height"]) == (
        geometry.render_width,
        geometry.render_height,
    )
    assert video["codec_name"] == "h264"
    expected_duration = min(1.5, 4 - start)
    assert float(info["format"]["duration"]) == pytest.approx(
        expected_duration, abs=0.08
    )
    audio_streams = [
        stream for stream in info["streams"] if stream["codec_type"] == "audio"
    ]
    assert bool(audio_streams) == audio
    if audio:
        assert audio_streams[0]["codec_name"] == "aac"
        assert _audio_correlation(_audio(source, start), _audio(clip, 0)) > 0.85
    local_frame = 0 if start == 0.25 else 2 / 30
    absolute_frame = math.ceil(start * 30 - 1e-6) / 30 + local_frame
    actual = _frame(clip, local_frame)
    expected = _frame(reference, absolute_frame)
    # Re-encoding the short GOP changes quantization; missing/mistimed word
    # effects must still be more different than this same-time reference.
    region = (0, actual.height // 2, actual.width, actual.height)
    error = (
        sum(ImageStat.Stat(ImageChops.difference(actual, expected).crop(region)).mean)
        / 3
    )
    assert error < 8
    uncaptioned = _frame(source, absolute_frame)
    missing_subtitle_error = (
        sum(
            ImageStat.Stat(ImageChops.difference(actual, uncaptioned).crop(region)).mean
        )
        / 3
    )
    if speech:
        assert error < missing_subtitle_error, (error, missing_subtitle_error)
    assert set(output.glob(".multisubs-*")) == {cache}
