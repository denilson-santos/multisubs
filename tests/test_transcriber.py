import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import transcriber
from multisubs.config import validate_subtitle_config
from multisubs.errors import TranscriptionError
from multisubs.models import TranscriptDocument, VideoGeometry

GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1920,
    render_height=1080,
    rotation_degrees=0,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(16, 9),
    duration_seconds=12.5,
)


def _word(text: str, start: float, end: float, **extra):
    return {"word": text, "start": start, "end": end, **extra}


def test_build_subtitle_segments_prefers_sentence_and_pause_boundaries():
    segments = transcriber._build_subtitle_segments(
        [
            {
                "start": 0,
                "end": 2,
                "words": [
                    _word("Hello", 0, 0.5),
                    _word("world.", 0.6, 1.2),
                    _word("Next", 1.8, 2.2),
                ],
            }
        ]
    )

    assert [segment["text"] for segment in segments] == ["Hello world.", "Next"]
    assert [segment["id"] for segment in segments] == [0, 1]


def test_build_subtitle_segments_uses_coarse_fallback_without_word_timestamps():
    segments = transcriber._build_subtitle_segments(
        [{"start": 1, "end": 2.5, "text": "Fallback text"}]
    )

    assert segments == [
        {"id": 0, "start": 1.0, "end": 2.5, "text": "Fallback text", "words": []}
    ]


def test_build_subtitle_segments_rejects_invalid_coarse_timestamps():
    with pytest.raises(TranscriptionError):
        transcriber._build_subtitle_segments(
            [{"start": 3, "end": 2, "text": "invalid"}]
        )


def test_subtitle_writers_preserve_unicode_and_escape_ass_text(tmp_path: Path):
    segments = [
        {
            "id": 0,
            "start": 0.001,
            "end": 61.239,
            "text": "Olá {mundo}\\\n字幕",
            "words": [],
        }
    ]
    srt_path = tmp_path / "captions.srt"
    transcriber._write_srt(srt_path, segments)

    srt = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,001 --> 00:01:01,239" in srt
    assert "Olá" in srt and "字幕" in srt


def test_model_loading_retries_transient_connection_failures(monkeypatch):
    calls = 0
    delays = []
    progress = []

    def flaky_loader():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("remote end closed connection without response")
        return "loaded-model"

    monkeypatch.setattr(transcriber.time, "sleep", delays.append)

    result = transcriber._load_model_with_retries(
        flaky_loader,
        operation="Loading model",
        progress=progress.append,
    )

    assert result == "loaded-model"
    assert calls == 3
    assert delays == [1.0, 2.0]
    assert progress == [
        "Loading model encountered a temporary connection error; "
        "retrying (2/3) in 1s...",
        "Loading model encountered a temporary connection error; "
        "retrying (3/3) in 2s...",
    ]


def test_model_loading_does_not_retry_deterministic_failures(monkeypatch):
    calls = 0

    def invalid_loader():
        nonlocal calls
        calls += 1
        raise ValueError("unknown model")

    monkeypatch.setattr(
        transcriber.time,
        "sleep",
        lambda _: pytest.fail("deterministic failures must not sleep"),
    )

    with pytest.raises(ValueError, match="unknown model"):
        transcriber._load_model_with_retries(
            invalid_loader,
            operation="Loading model",
            progress=None,
        )

    assert calls == 1


def test_silero_model_load_blocks_unused_onnxruntime_probe(monkeypatch):
    monkeypatch.delitem(sys.modules, "onnxruntime", raising=False)
    observed = {}

    class FakeWhisper:
        @staticmethod
        def load_model(*args, **kwargs):
            observed["module_entry"] = sys.modules.get("onnxruntime")
            observed["vad_method"] = kwargs["vad_method"]
            return "loaded-model"

    result = transcriber._load_silero_whisperx_model(
        FakeWhisper,
        model_name="turbo",
        device="cuda",
        compute_type="float16",
        language="pt",
        task="transcribe",
    )

    assert result == "loaded-model"
    assert observed == {"module_entry": None, "vad_method": "silero"}
    assert "onnxruntime" not in sys.modules


def test_generate_transcriptions_uses_fake_whisper_runtime(tmp_path: Path, monkeypatch):
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"not real media")
    output_dir = tmp_path / "output"
    load_calls = {"count": 0}

    class FakeCuda:
        @staticmethod
        def is_available():
            return False

    class FakeTorch:
        cuda = FakeCuda()

    class FakeModel:
        def transcribe(self, audio):
            assert audio == "audio"
            return {
                "text": "Hello world.",
                "language": "en",
                "segments": [{"start": 0, "end": 1, "text": "Hello world."}],
            }

    class FakeWhisper:
        @staticmethod
        def load_model(*args, **kwargs):
            load_calls["count"] += 1
            if load_calls["count"] == 1:
                raise ConnectionError("remote end closed connection")
            assert kwargs["task"] == "transcribe"
            assert kwargs["vad_method"] == "silero"
            return FakeModel()

        @staticmethod
        def load_audio(path):
            assert path == str(input_path.resolve())
            return "audio"

        @staticmethod
        def load_align_model(**kwargs):
            return "align", "metadata"

        @staticmethod
        def align(segments, model, metadata, audio, device, **kwargs):
            return {
                "segments": [
                    {
                        "start": 0,
                        "end": 1,
                        "text": "Hello world.",
                        "words": [_word("Hello", 0, 0.4), _word("world.", 0.5, 1)],
                    }
                ]
            }

    monkeypatch.setattr(
        transcriber, "_load_runtime_dependencies", lambda: (FakeTorch, FakeWhisper)
    )
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry", lambda path: GEOMETRY
    )
    monkeypatch.setattr(transcriber.time, "sleep", lambda _: None)
    paths = transcriber.generate_transcriptions(input_path, output_dir)

    json_path, srt_path, ass_path = map(Path, paths)
    assert load_calls["count"] == 2
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["language"] == "en"
    assert payload["schema_version"] == 1
    assert payload["metadata"]["created_at"].endswith("+00:00")
    assert payload["metadata"]["rendering"] == {
        "video_stream_index": 0,
        "coded_width": 1920,
        "coded_height": 1080,
        "render_width": 1920,
        "render_height": 1080,
        "rotation_degrees": 0,
        "sample_aspect_ratio": "1:1",
        "display_aspect_ratio": "16:9",
        "container_duration": 12.5,
        "requested_preset": "auto",
        "resolved_preset": "landscape",
        "requested_position": "bottom-center",
        "resolved_position": "bottom-center",
        "margins": {
            "left": 115,
            "right": 115,
            "top": 0,
            "bottom": 65,
        },
        "requested": {
            "font_size": "43px",
            "backdrop_size": "0px",
            "shadow_size": "2px",
            "margins": {
                "left": "0px",
                "right": "0px",
                "top": "35px",
                "bottom": "35px",
            },
        },
        "resolved": {
            "font_size": 43,
            "backdrop_size": 0,
            "shadow_size": 2,
            "margins": {
                "left": 115,
                "right": 115,
                "top": 0,
                "bottom": 65,
            },
        },
        "safe_rectangle": {
            "left": 115,
            "top": 0,
            "right": 1805,
            "bottom": 1015,
            "width": 1690,
            "height": 1015,
        },
    }
    assert srt_path.exists() and ass_path.exists()


def test_write_transcription_artifacts_does_not_load_model_runtime(
    tmp_path: Path, monkeypatch
):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello.",
        segments=(
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "Hello.",
                "words": [],
            },
        ),
    )
    monkeypatch.setattr(
        transcriber,
        "_load_runtime_dependencies",
        lambda: pytest.fail("artifact writing must not load WhisperX or PyTorch"),
    )

    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            relative_values={
                "font_size": "4.5%",
                "margin_left": "8%",
                "margin_right": "8%",
            },
        ),
        geometry=GEOMETRY,
    )

    assert all(Path(path).exists() for path in paths)
    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    rendering = payload["metadata"]["rendering"]
    assert rendering["requested"]["font_size"] == "4.5%"
    assert rendering["requested"]["margins"] == {
        "left": "8%",
        "right": "8%",
        "top": "35px",
        "bottom": "35px",
    }
    assert rendering["resolved"]["font_size"] == 49
    assert rendering["resolved"]["margins"] == {
        "left": 154,
        "right": 154,
        "top": 0,
        "bottom": 65,
    }
    assert rendering["requested_preset"] == "auto"
    assert rendering["resolved_preset"] == "landscape"


def test_custom_coordinates_are_recorded_in_rendering_metadata(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello.",
        segments=(
            {"id": 0, "start": 0.0, "end": 1.0, "text": "Hello.", "words": []},
        ),
    )

    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            relative_values={"position_x": "50%", "position_y": "86%"},
            anchor="bottom-center",
        ),
        geometry=GEOMETRY,
    )

    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    rendering = payload["metadata"]["rendering"]
    assert rendering["requested_position"] is None
    assert rendering["resolved_position"] is None
    assert rendering["requested_coordinates"] == {
        "x": "50%",
        "y": "86%",
        "anchor": "bottom-center",
    }
    assert rendering["resolved_coordinates"] == {
        "x": 960,
        "y": 929,
        "anchor": "bottom-center",
    }
