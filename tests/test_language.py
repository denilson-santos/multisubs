"""Language selection across the CLI, speech boundary, and artifact lifecycle."""

import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from multisubs import cli, transcriber
from multisubs.errors import TranscriptionError, ValidationError
from multisubs.models import VideoGeometry


@pytest.fixture
def speech_runtime(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    state = {
        "result": {
            "language": "pt",
            "segments": [{"start": 0.0, "end": 1.0, "text": "Hello."}],
        },
        "loads": [],
        "alignments": [],
    }

    def load_model(*args, **kwargs):
        state["loads"].append(kwargs)
        return SimpleNamespace(transcribe=lambda audio: state["result"])

    def load_align_model(**kwargs):
        state["alignments"].append(kwargs["language_code"])
        return "model", "metadata"

    whisper = SimpleNamespace(
        load_model=load_model,
        load_audio=lambda path: "audio",
        load_align_model=load_align_model,
        align=lambda segments, *args, **kwargs: {"segments": segments},
    )
    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    monkeypatch.setattr(
        transcriber, "_load_runtime_dependencies", lambda: (torch, whisper)
    )
    geometry = VideoGeometry(
        0, 1920, 1080, 1920, 1080, 0, Fraction(1), Fraction(16, 9), 1.0
    )
    monkeypatch.setattr("multisubs.subtitler.probe_video_geometry", lambda _: geometry)
    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    return source, state


@pytest.mark.parametrize(
    ("lang", "model", "task", "expected_source", "expected_alignment"),
    [
        (None, "turbo", "transcribe", "pt", "pt"),
        ("ja", "turbo", "transcribe", "ja", "ja"),
        (None, "small.en", "transcribe", "en", "en"),
        ("en", "small.en", "transcribe", "en", "en"),
        (None, "medium", "translate", "pt", "en"),
        ("ja", "medium", "translate", "ja", "en"),
    ],
)
def test_source_selection_and_alignment(
    speech_runtime, lang, model, task, expected_source, expected_alignment
):
    source, state = speech_runtime
    messages = []
    document = transcriber.transcribe_video(
        source, lang, task, model, progress=messages.append
    )
    assert state["loads"][0]["language"] == ("en" if model.endswith(".en") else lang)
    assert state["loads"][0]["task"] == task
    assert state["alignments"] == [expected_alignment]
    assert document.language == expected_source
    if lang is None and not model.endswith(".en"):
        assert f"Detected source language: {expected_source}." in messages


@pytest.mark.parametrize("detected", [None, "", 42, "af", "../pt"])
def test_invalid_detection_fails_before_alignment(speech_runtime, detected):
    source, state = speech_runtime
    state["result"]["language"] = detected
    with pytest.raises(TranscriptionError, match="--lang CODE"):
        transcriber.transcribe_video(source)
    assert state["alignments"] == []


def test_explicit_language_does_not_require_detection(speech_runtime):
    source, state = speech_runtime
    del state["result"]["language"]
    assert transcriber.transcribe_video(source, "pt").language == "pt"


@pytest.mark.parametrize(("lang", "model"), [("pt", "small.en"), ("af", "turbo")])
def test_invalid_explicit_language_fails_before_model_loading(
    speech_runtime, lang, model
):
    source, state = speech_runtime
    with pytest.raises(ValidationError):
        transcriber.transcribe_video(source, lang, model_name=model)
    assert state["loads"] == []


@pytest.mark.parametrize(
    ("options", "expected"),
    [([], None), (["--lang", "zh"], "zh"), (["--model", "small.en"], "en")],
)
def test_cli_language_selection(speech_runtime, monkeypatch, options, expected):
    source, state = speech_runtime
    requests = []

    def run(request, progress):
        requests.append(request)
        return source

    monkeypatch.setattr(cli, "_run_request", run)
    assert cli.main(["-i", str(source), *options]) == 0
    assert requests[0].language == expected
    assert state["loads"] == []


def test_cli_rejects_non_english_language_with_english_model(speech_runtime, capsys):
    source, state = speech_runtime
    with pytest.raises(SystemExit) as error:
        cli.main(["-i", str(source), "--model", "small.en", "--lang", "pt"])
    assert error.value.code == 2
    assert "English-only" in capsys.readouterr().err
    assert state["loads"] == []


@pytest.mark.parametrize("keep", [False, True])
def test_detected_language_reaches_files_and_metadata(
    speech_runtime, tmp_path, monkeypatch, keep
):
    source, _ = speech_runtime
    output = tmp_path / "output"
    output.mkdir()
    (output / "video-pt.mp4").write_bytes(b"existing")
    (output / "video").mkdir()
    measured_languages = []
    original_metrics = cli.resolve_wrapping_metrics

    def metrics(*args, **kwargs):
        measured_languages.append(kwargs.get("language"))
        return original_metrics(*args, **kwargs)

    def render(input_path, ass, destination, lang, *, output_path, **kwargs):
        assert lang == "pt"
        assert Path(ass).name == "video-pt.ass"
        payload = json.loads((Path(destination) / "video-pt.json").read_text())
        assert payload["metadata"]["language"] == "pt"
        Path(output_path).write_bytes(b"rendered")
        return str(output_path)

    monkeypatch.setattr(cli, "resolve_wrapping_metrics", metrics)
    monkeypatch.setattr("multisubs.subtitler.embed_subtitles", render)
    options = ["-i", str(source), "-o", str(output)]
    if keep:
        options.append("--keep-transcriptions")
    assert cli.main(options) == 0
    assert measured_languages == [None, "pt"]
    assert (output / "video-pt.mp4").read_bytes() == b"existing"
    if keep:
        retained = output / "video (1)"
        assert (retained / "video-pt.mp4").read_bytes() == b"rendered"
        assert sorted(p.name for p in (retained / "subtitles").iterdir()) == [
            "video-pt.ass",
            "video-pt.json",
            "video-pt.srt",
        ]
    else:
        assert (output / "video-pt (1).mp4").read_bytes() == b"rendered"
        assert not list(output.rglob("*.json"))
        assert not list(output.rglob("*.srt"))
        assert not list(output.rglob("*.ass"))
    assert not list(output.glob(".multisubs-*"))


def test_programmatic_generation_uses_detected_language(speech_runtime, tmp_path):
    source, _ = speech_runtime
    paths = transcriber.generate_transcriptions(source, tmp_path / "output")
    assert [Path(p).name for p in paths] == [
        "video-pt.json",
        "video-pt.srt",
        "video-pt.ass",
    ]
    assert json.loads(Path(paths[0]).read_text())["metadata"]["language"] == "pt"
