"""Public timed-cue JSON contract and ASR-free publication tests."""

import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from typer.testing import CliRunner

from multisubs import cli
from multisubs.errors import ArtifactError, ValidationError
from multisubs.models import VideoGeometry
from multisubs.timed_cues import generate_subtitles_from_json, load_timed_cues


def _document(text="Isso é importante", words=None):
    if words is None:
        words = [
            {"start": 0.4, "end": 0.7, "text": "Isso"},
            {"start": 0.8, "end": 1.0, "text": "é"},
            {"start": 1.1, "end": 1.8, "text": "importante"},
        ]
    return {
        "schema_version": 1,
        "language": "pt-BR",
        "cues": [{"start": 0.4, "end": 1.8, "text": text, "words": words}],
    }


def _write(tmp_path, document):
    path = tmp_path / "cues.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "change, match",
    [
        (lambda d: d.update(schema_version=True), "schema_version"),
        (lambda d: d.update(extra=1), "unknown key"),
        (lambda d: d.update(language="pt/BR"), "language"),
        (lambda d: d["cues"][0].update(start=-1), "cue 0.start"),
        (lambda d: d["cues"][0].update(end=0.4), "cue 0"),
        (lambda d: d["cues"][0]["words"][1].update(start=True), "words\\[1\\]"),
        (lambda d: d["cues"][0]["words"][1].update(start=0.6), "words\\[1\\]"),
        (lambda d: d["cues"][0]["words"][1].update(text="e"), "words\\[1\\]"),
        (lambda d: d["cues"][0].update(text="Isso é importante!"), "outside"),
    ],
)
def test_rejects_invalid_contract(tmp_path, change, match):
    document = _document()
    change(document)
    with pytest.raises(ValidationError, match=match):
        load_timed_cues(_write(tmp_path, document))


def test_rejects_duplicate_keys_nonfinite_and_invalid_utf8(tmp_path):
    path = tmp_path / "cues.json"
    for payload, match in (
        (b'{"schema_version":1,"schema_version":1}', "Duplicate"),
        (b'{"schema_version":NaN}', "constant"),
        (b"\xff", "UTF-8"),
    ):
        path.write_bytes(payload)
        with pytest.raises(ValidationError, match=match):
            load_timed_cues(path)


def test_preserves_source_separators_and_timing(tmp_path):
    document = _document(
        "A\u00a0é! 👨‍👩‍👧",
        [
            {"start": 0.4, "end": 0.6, "text": "A"},
            {"start": 0.8, "end": 1.0, "text": "é!"},
            {"start": 1.1, "end": 1.8, "text": "👨‍👩‍👧"},
        ],
    )
    loaded = load_timed_cues(_write(tmp_path, document))
    assert loaded.cues[0].text == document["cues"][0]["text"]
    assert loaded.cues[0].words[1].start == 0.8


def test_rejects_cue_that_collapses_at_ass_precision(tmp_path):
    document = _document(
        "Oi",
        [{"start": 0.0001, "end": 0.0002, "text": "Oi"}],
    )
    document["cues"][0]["start"] = 0.0001
    document["cues"][0]["end"] = 0.0002
    with pytest.raises(ValidationError, match="centisecond"):
        load_timed_cues(_write(tmp_path, document))


def test_overlapping_cues_keep_input_order(tmp_path):
    document = _document()
    document["cues"].append(
        {
            "start": 1.0,
            "end": 2.0,
            "text": "Sim!",
            "words": [{"start": 1.0, "end": 2.0, "text": "Sim!"}],
        }
    )
    loaded = load_timed_cues(_write(tmp_path, document))
    assert [(cue.start, cue.end) for cue in loaded.cues] == [(0.4, 1.8), (1.0, 2.0)]


def test_resource_and_unicode_limits(tmp_path):
    document = _document()
    document["cues"][0]["text"] = "x" * 1_000_001
    with pytest.raises(ValidationError, match="1,000,000"):
        load_timed_cues(_write(tmp_path, document))
    document = _document()
    document["cues"][0]["words"][0]["start"] = 10**400
    with pytest.raises(ValidationError, match="86,400"):
        load_timed_cues(_write(tmp_path, document))
    document = _document()
    document["cues"][0]["words"][0]["text"] = chr(0xD800)
    path = tmp_path / "surrogate.json"
    path.write_text(json.dumps(document, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(ValidationError, match="surrogate"):
        load_timed_cues(path)


def test_generates_pair_and_video_from_new_ass(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    cues = _write(tmp_path, _document())
    original_json = cues.read_bytes()
    from multisubs import subtitler

    geometry = VideoGeometry(
        0, 1920, 1080, 1920, 1080, 0, Fraction(1), Fraction(16, 9), 10.0
    )
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: geometry)
    rendered_ass = []

    def render(_video, ass, _directory, **kwargs):
        rendered_ass.append(Path(ass).read_text(encoding="utf-8"))
        Path(kwargs["output_path"]).write_bytes(b"rendered")
        return str(kwargs["output_path"])

    monkeypatch.setattr(subtitler, "embed_subtitles", render)
    output = tmp_path / "output"
    first = generate_subtitles_from_json(cues, video, output)
    second = generate_subtitles_from_json(cues, video, output)
    assert first.srt_path.name == "video-pt-br.srt"
    assert second.srt_path.name == "video-pt-br (1).srt"
    assert first.video_path.read_bytes() == b"rendered"
    assert first.ass_path.read_text(encoding="utf-8") == rendered_ass[0]
    assert "00:00:00,400 --> 00:00:01,800" in first.srt_path.read_text()
    assert "Isso é importante" in first.srt_path.read_text()
    assert "PlayResX: 1920" in rendered_ass[0]
    assert cues.read_bytes() == original_json
    assert video.read_bytes() == b"input"


def test_rejects_cue_after_known_video_duration_before_output(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    cues = _write(tmp_path, _document())
    from multisubs import subtitler

    short_video = VideoGeometry(
        0, 640, 360, 640, 360, 0, Fraction(1), Fraction(16, 9), 1.0
    )
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: short_video)
    output = tmp_path / "output"
    with pytest.raises(ValidationError, match="video duration"):
        generate_subtitles_from_json(cues, video, output)
    assert not output.exists()


def test_rejects_unfit_cue_without_splitting(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    word = "W" * 500
    cues = _write(
        tmp_path,
        _document(word, [{"start": 0.4, "end": 1.8, "text": word}]),
    )
    from multisubs import subtitler

    geometry = VideoGeometry(
        0, 640, 360, 640, 360, 0, Fraction(1), Fraction(16, 9), 10.0
    )
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: geometry)
    output = tmp_path / "output"
    with pytest.raises(ValidationError, match="cue 0 exceeds"):
        generate_subtitles_from_json(cues, video, output)
    assert not output.exists()


def test_publication_failure_rolls_back(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    cues = _write(tmp_path, _document())
    from multisubs import subtitler, timed_cues

    geometry = VideoGeometry(
        0, 1920, 1080, 1920, 1080, 0, Fraction(1), Fraction(16, 9), 10.0
    )
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda path: geometry)
    monkeypatch.setattr(
        subtitler,
        "embed_subtitles",
        lambda _video, _ass, _dir, **kw: Path(kw["output_path"]).write_bytes(b"x"),
    )

    def fail(files):
        raise ArtifactError("publication failed")

    monkeypatch.setattr(timed_cues, "publish_files", fail)
    output = tmp_path / "output"
    with pytest.raises(ArtifactError, match="publication failed"):
        generate_subtitles_from_json(cues, video, output)
    assert not list(output.glob("*.srt"))
    assert not list(output.glob(".multisubs-*"))


def test_cli_rejects_explicit_asr_default_before_video_probe(tmp_path):
    result = CliRunner().invoke(
        cli.app,
        [
            "-i",
            str(tmp_path / "missing.mp4"),
            "--cues-json",
            "cues.json",
            "--asr",
            "whisperx",
        ],
    )
    assert result.exit_code == 2
    assert "--asr cannot be used with --cues-json" in result.output


def test_public_api_does_not_import_asr_runtime_in_fresh_process():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from multisubs import generate_subtitles_from_json; "
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
def test_real_ffmpeg_json_render_preserves_canvas_audio_and_visible_cue(tmp_path):
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
    cues = _write(tmp_path, _document())
    artifacts = generate_subtitles_from_json(cues, video, tmp_path / "output")
    ass = artifacts.ass_path.read_text(encoding="utf-8")
    assert "PlayResX: 640" in ass and "PlayResY: 360" in ass
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height",
            "-of",
            "csv=p=0",
            str(artifacts.video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "video,640,360" in probe
    assert "audio" in probe

    def frame_at(second):
        return subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(artifacts.video_path),
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
