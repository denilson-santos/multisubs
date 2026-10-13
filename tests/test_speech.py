"""Public source transcription, interchange, and deferred native rendering."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import (
    GeneratedSubtitleArtifacts,
    SpeechTranscript,
    build_subtitle_config,
    render_transcript,
    subtitler,
    transcribe_speech,
    transcriber,
)
from multisubs.asr.base import ASRResult
from multisubs.config import validate_subtitle_config
from multisubs.errors import ArtifactError, ValidationError
from multisubs.models import RelativeLength, VideoGeometry
from multisubs.templates import get_subtitle_template


def _unexpected_asr(*args, **kwargs):
    pytest.fail("rendering must never create an ASR adapter")


@pytest.fixture(autouse=True)
def _forbid_asr_by_default(monkeypatch):
    monkeypatch.setattr(transcriber, "create_adapter", _unexpected_asr)


def _source(case):
    text = " Olá,  mundo!"
    words = [
        {"word": " Olá,", "start": 0.2, "end": 0.5, "score": None},
        {"word": " mundo!", "start": 0.6, "end": 1.0, "score": 0.8},
    ]
    language = "pt"
    if case in {"initial-point", "middle-points", "trailing-points"}:
        text = (
            "Hoje começamos uma nova história com muitas palavras "
            "para mostrar como ficam as legendas."
        )
        words = [
            {"word": token, "start": 0.2 + i * 0.2, "end": 0.3 + i * 0.2}
            for i, token in enumerate(text.split())
        ]
        if case == "initial-point":
            words[0]["end"] = words[0]["start"]
        elif case == "middle-points":
            for i in range(4, 7):
                words[i]["start"] = words[i]["end"] = 1.0
        else:
            for i in range(len(words) - 2, len(words)):
                words[i]["start"] = words[i]["end"] = 2.9
    elif case == "all-points":
        for word in words:
            word["start"] = word["end"] = 0.6
    elif case == "no-words":
        words = []
    elif case == "partial":
        words[0].pop("end")
        words[1]["start"] = None
    elif case == "unknown-language":
        language = None
    elif case == "overlap":
        words[0]["end"] = 0.7
    segment = {"text": text, "start": 0.0, "end": 4.0, "words": words}
    if case == "absent-words":
        segment.pop("words")
    elif case == "null-words":
        segment["words"] = None
    return ASRResult(language, text, (segment,))


def _mock_asr(monkeypatch, result):
    requests = []

    class Adapter:
        def transcribe(self, request):
            requests.append(request)
            return deepcopy(result)

    monkeypatch.setattr(transcriber, "create_adapter", lambda _backend: Adapter())
    return requests


def _media(tmp_path, monkeypatch, dimensions=(1080, 1920)):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    width, height = dimensions
    geometry = VideoGeometry(
        0, width, height, width, height, 0, Fraction(1), Fraction(width, height), 10.0
    )
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda _: geometry)
    monkeypatch.setattr(
        subtitler,
        "embed_subtitles",
        lambda _video, _ass, _dir, *args, **kw: Path(kw["output_path"]).write_bytes(
            b"rendered"
        ),
    )
    return video, geometry


def test_transcription_keeps_source_segments_and_no_subtitle_work(
    tmp_path, monkeypatch
):
    result = _source("partial")
    second = {"text": " Próxima.", "start": 4.0, "end": 5.0}
    result = ASRResult(None, result.text + second["text"], (*result.segments, second))
    requests = _mock_asr(monkeypatch, result)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")

    def unexpected(*args, **kwargs):
        pytest.fail("transcribe_speech must not select cues, probe, or resolve layout")

    for name in (
        "_build_subtitle_segments",
        "layout_subtitle_cues",
        "write_transcription_artifacts",
    ):
        monkeypatch.setattr(transcriber, name, unexpected)
    monkeypatch.setattr(subtitler, "probe_video_geometry", unexpected)
    speech = transcribe_speech(video, asr_backend="parakeet")
    assert speech.segments == result.segments
    assert speech.full_text == result.text
    assert speech.language is None
    assert speech.asr_backend == "parakeet"
    assert speech.model_name == "nvidia/parakeet-tdt-0.6b-v3"
    assert speech.duration == 5.0
    assert len(requests) == 1
    assert list(tmp_path.iterdir()) == [video]


@pytest.mark.parametrize(
    "case",
    [
        "spaces",
        "all-points",
        "no-words",
        "absent-words",
        "null-words",
        "partial",
        "unknown-language",
        "overlap",
    ],
)
def test_interchange_is_lossless_and_detached(case):
    source = _source(case)
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    payload = json.loads(json.dumps(speech.to_dict(), ensure_ascii=False))
    assert "format" not in payload
    loaded = SpeechTranscript.from_dict(payload)
    assert loaded == speech
    assert loaded.segments == source.segments
    payload["segments"][0]["text"] = "changed"
    assert loaded.segments[0]["text"] == source.segments[0]["text"]
    edited = loaded.to_dict()
    edited["segments"][0]["text"] = "another change"
    assert loaded == speech


@pytest.mark.parametrize("dimensions", [(1920, 1080), (1080, 1920)])
@pytest.mark.parametrize("template", ["default", "yellow-pop"])
@pytest.mark.parametrize(
    "case",
    [
        "spaces",
        "initial-point",
        "middle-points",
        "trailing-points",
        "all-points",
        "no-words",
        "absent-words",
        "null-words",
        "partial",
        "unknown-language",
        "overlap",
    ],
)
def test_deferred_render_equals_normal_srt_and_ass(
    tmp_path, monkeypatch, dimensions, template, case
):
    video, _ = _media(tmp_path, monkeypatch, dimensions)
    source = _source(case)
    requests = _mock_asr(monkeypatch, source)
    speech = transcribe_speech(video)
    config = get_subtitle_template(template).config
    native_json, native_srt, native_ass = transcriber.generate_transcriptions(
        video, tmp_path / "native", config
    )
    assert len(requests) == 2

    def unexpected(*args, **kwargs):
        pytest.fail("deferred rendering must not invoke ASR")

    monkeypatch.setattr(transcriber, "create_adapter", unexpected)
    messages = []
    artifacts = render_transcript(
        speech.to_dict(),
        video,
        tmp_path / "rendered",
        template=template,
        progress=messages.append,
    )
    assert isinstance(artifacts, GeneratedSubtitleArtifacts)
    assert artifacts.srt_path.read_bytes() == Path(native_srt).read_bytes()
    assert artifacts.ass_path.read_bytes() == Path(native_ass).read_bytes()
    assert artifacts.video_path.read_bytes() == b"rendered"
    assert artifacts.video_path.name == (
        "video.mp4" if source.language is None else "video-pt.mp4"
    )
    assert speech.segments == source.segments
    assert sorted(path.suffix for path in artifacts.video_path.parent.iterdir()) == [
        ".ass",
        ".mp4",
        ".srt",
    ]
    if (
        case in {"partial", "no-words", "absent-words", "null-words", "all-points"}
        and template == "yellow-pop"
    ):
        assert any("could not safely use" in message for message in messages)
    payload = json.loads(Path(native_json).read_text())
    if case in {"initial-point", "middle-points", "trailing-points"}:
        cues = payload["transcription"]["segments"]
        if dimensions == (1080, 1920):
            assert len(cues) > 1
        assert all(cue["end"] > cue["start"] for cue in cues)
        assert [word for cue in cues for word in cue["words"]] == source.segments[0][
            "words"
        ]


@pytest.mark.parametrize("case", ["aligned", "partial", "absent-words", "all-points"])
def test_public_config_is_reusable_across_final_geometries(tmp_path, monkeypatch, case):
    source = _source(case)
    speech = SpeechTranscript(
        source.language,
        "transcribe",
        "faster-whisper",
        "turbo",
        source.text,
        source.segments,
    )
    before = speech.to_dict()
    config = build_subtitle_config(
        template="yellow-pop",
        overrides={
            "font_size": "4.5%",
            "margin_bottom": "8%",
            "italic": False,
        },
    )
    for dimensions, expected_size in [((1080, 1920), "86"), ((1920, 1080), "49")]:
        video, _ = _media(tmp_path, monkeypatch, dimensions)
        messages = []
        artifacts = render_transcript(
            speech,
            video,
            tmp_path / "output",
            subtitle_config=config,
            progress=messages.append,
        )
        ass = artifacts.ass_path.read_text()
        width, height = dimensions
        assert f"PlayResX: {width}" in ass and f"PlayResY: {height}" in ass
        style = next(line for line in ass.splitlines() if line.startswith("Style:"))
        assert style.split(",")[2] == expected_size
        assert speech.to_dict() == before
        assert isinstance(config.style.typography.font_size, RelativeLength)
        assert config.style.typography.font_size.original == "4.5%"
        if case in {"partial", "absent-words", "all-points"}:
            assert any("could not safely use" in message for message in messages)


def test_cut_local_times_and_explicit_positioning(tmp_path, monkeypatch):
    video, geometry = _media(tmp_path, monkeypatch)
    source = _source("partial")
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    payload = speech.to_dict()
    for segment in payload["segments"]:
        segment["start"] += 10
        segment["end"] += 10
        for word in segment["words"]:
            for key in ("start", "end"):
                if word.get(key) is not None:
                    word[key] += 10
    cached = SpeechTranscript.from_dict(payload)
    local = cached.to_dict()
    for segment in local["segments"]:
        for key in ("start", "end"):
            segment[key] -= 10
        for word in segment["words"]:
            for key in ("start", "end"):
                if word.get(key) is not None:
                    word[key] -= 10
    config = validate_subtitle_config(
        None,
        position_x="50%",
        position_y="80%",
        anchor="bottom-center",
        relative_values={"max_width": "60%", "max_height": "20%"},
    )
    messages = []
    artifacts = render_transcript(
        local, video, tmp_path / "cut", subtitle_config=config, progress=messages.append
    )
    assert artifacts.srt_path.exists()
    assert "PlayResX: 1080" in artifacts.ass_path.read_text()
    assert "PlayResY: 1920" in artifacts.ass_path.read_text()
    assert cached.segments[0]["start"] == 10.0
    assert local["segments"][0]["words"][1]["start"] is None
    assert "end" not in local["segments"][0]["words"][0]
    assert geometry.render_width == 1080
    _mock_asr(
        monkeypatch,
        ASRResult(local["language"], local["full_text"], tuple(local["segments"])),
    )
    _, normal_srt, normal_ass = transcriber.generate_transcriptions(
        video, tmp_path / "normal-cut", config
    )
    assert artifacts.srt_path.read_bytes() == Path(normal_srt).read_bytes()
    assert artifacts.ass_path.read_bytes() == Path(normal_ass).read_bytes()


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda data: data.update(schema_version=True), "schema_version"),
        (lambda data: data.update(schema_version=2), "schema_version"),
        (lambda data: data.update(format="multisubs-speech"), "unknown fields"),
        (lambda data: data.update(task="translate"), "only task"),
        (lambda data: data.update(language="pt/BR"), "language"),
        (lambda data: data.update(extra=True), "unknown fields"),
        (lambda data: data["segments"][0].update(start=float("nan")), "finite JSON"),
        (lambda data: data["segments"][0].update(start=-1), "segment 0.start"),
        (lambda data: data["segments"][0]["words"][0].update(end=0.1), "reversed"),
        (lambda data: data["segments"][0].update(words="invalid"), "array"),
    ],
)
def test_invalid_input_is_rejected_before_media(tmp_path, monkeypatch, change, match):
    source = _source("spaces")
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    payload = speech.to_dict()
    change(payload)

    def unexpected(*args, **kwargs):
        pytest.fail("invalid transcripts must fail before probing")

    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", unexpected)
    with pytest.raises(ValidationError, match=match):
        render_transcript(payload, tmp_path / "missing.mp4", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_translation_rejected_before_asr(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("translation must be rejected before loading ASR")

    monkeypatch.setattr(transcriber, "create_adapter", unexpected)
    with pytest.raises(ValidationError, match="only task"):
        transcribe_speech(tmp_path / "missing.mp4", task="translate")


def test_fallback_without_callback_emits_warning(tmp_path, monkeypatch):
    video, _ = _media(tmp_path, monkeypatch)
    source = _source("partial")
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    with pytest.warns(UserWarning, match="could not safely use"):
        render_transcript(speech, video, tmp_path / "out", template="yellow-pop")


@pytest.mark.parametrize("failure_phase", ["render", "publication"])
def test_collisions_and_failure_publish_nothing_partial(
    tmp_path, monkeypatch, failure_phase
):
    video, _ = _media(tmp_path, monkeypatch)
    source = _source("spaces")
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    destination = tmp_path / "out"
    first = render_transcript(speech, video, destination)
    second = render_transcript(speech, video, destination)
    assert first.video_path.name == "video-pt.mp4"
    assert second.video_path.name == "video-pt (1).mp4"
    original_files = {path.name: path.read_bytes() for path in destination.iterdir()}

    def failed(*args, **kwargs):
        Path(kwargs["output_path"]).write_bytes(b"partial")
        raise ArtifactError("render failed")

    if failure_phase == "render":
        monkeypatch.setattr(subtitler, "embed_subtitles", failed)
    else:
        from multisubs import utils

        def failed_publication(files):
            raise ArtifactError("publication failed")

        monkeypatch.setattr(utils, "publish_files", failed_publication)
    with pytest.raises(ArtifactError, match=f"{failure_phase} failed"):
        render_transcript(speech, video, destination)
    assert {
        path.name: path.read_bytes() for path in destination.iterdir()
    } == original_files


def test_observed_coarse_bounds_match_normal_even_past_media_end(tmp_path, monkeypatch):
    video, _ = _media(tmp_path, monkeypatch)
    source = _source("no-words")
    segment = dict(source.segments[0], end=10.01)
    source = ASRResult(source.language, source.text, (segment,))
    _mock_asr(monkeypatch, source)
    speech = transcribe_speech(video)
    _, normal_srt, normal_ass = transcriber.generate_transcriptions(
        video, tmp_path / "normal"
    )
    monkeypatch.setattr(transcriber, "create_adapter", _unexpected_asr)
    artifacts = render_transcript(speech, video, tmp_path / "out")
    assert artifacts.srt_path.read_bytes() == Path(normal_srt).read_bytes()
    assert artifacts.ass_path.read_bytes() == Path(normal_ass).read_bytes()
    assert speech.segments[0]["end"] == 10.01


def test_unicode_interchange_and_overlapping_segment_duration():
    text = " Olá,\u00a0世界! 👨‍👩‍👧\r\n"
    source = (
        {"text": text, "start": 0.0, "end": 3.0, "words": [{"word": " Olá,"}]},
        {"text": "é", "start": 1.0, "end": 2.0},
    )
    speech = SpeechTranscript(
        None, "transcribe", "parakeet", "model", text + "é", source
    )
    restored = SpeechTranscript.from_dict(json.loads(json.dumps(speech.to_dict())))
    assert restored == speech
    assert speech.duration == 3.0


def test_point_only_without_observed_interval_fails_explicitly(tmp_path, monkeypatch):
    video, _ = _media(tmp_path, monkeypatch)
    source = _source("all-points")
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    payload = speech.to_dict()
    payload["segments"][0]["start"] = payload["segments"][0]["end"] = 0.6
    with pytest.raises(ValidationError, match="no visible observed segment interval"):
        render_transcript(payload, video, tmp_path / "out")
    assert not list((tmp_path / "out").glob("*"))


def test_unfit_point_only_text_never_publishes_overflow(tmp_path, monkeypatch):
    video, _ = _media(tmp_path, monkeypatch)
    source = _source("initial-point")
    for word in source.segments[0]["words"]:
        word["start"] = word["end"] = 1.0
    speech = SpeechTranscript(
        source.language, "transcribe", "whisperx", "turbo", source.text, source.segments
    )
    with pytest.raises(ValidationError, match="max-width|max-height"):
        render_transcript(speech, video, tmp_path / "out")
    assert not list((tmp_path / "out").glob("*"))


def test_public_import_does_not_load_asr_runtimes():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util, sys, multisubs; "
                "from multisubs import GeneratedSubtitleArtifacts, "
                "SpeechTranscript, transcribe_speech, "
                "render_transcript; "
                "assert not hasattr(multisubs, 'generate_subtitles_from_json'); "
                "assert importlib.util.find_spec('multisubs.timed_cues') is None; "
                "assert not any(name == 'torch' or name.startswith("
                "('whisperx', 'faster_whisper', 'nemo', 'transformers')) "
                "for name in sys.modules)"
            ),
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
@pytest.mark.parametrize("size", ["360x640", "640x360"])
def test_real_ffmpeg_deferred_render_keeps_geometry_audio_and_visible_text(
    tmp_path, monkeypatch, size
):
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
            f"color=c=black:s={size}:d=4:r=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4",
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
    source = _source("initial-point")
    requests = _mock_asr(monkeypatch, source)
    speech = transcribe_speech(video, asr_backend="faster-whisper")
    monkeypatch.setattr(transcriber, "create_adapter", _unexpected_asr)
    config = build_subtitle_config(
        template="yellow-pop",
        overrides={
            "font_size": "4.5%",
            "margin_bottom": "8%",
            "italic": False,
        },
    )
    artifacts = render_transcript(
        speech, video, tmp_path / "output", subtitle_config=config
    )
    assert len(requests) == 1
    width, height = size.split("x")
    ass = artifacts.ass_path.read_text()
    assert f"PlayResX: {width}" in ass and f"PlayResY: {height}" in ass
    probe = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,width,height",
                "-of",
                "json",
                str(artifacts.video_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert any(stream["codec_type"] == "audio" for stream in probe["streams"])
    assert any(
        stream.get("width") == int(width) and stream.get("height") == int(height)
        for stream in probe["streams"]
    )

    def frame(path, timestamp):
        return subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(timestamp),
                "-i",
                str(path),
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

    assert frame(video, 0.8) != frame(artifacts.video_path, 0.8)
