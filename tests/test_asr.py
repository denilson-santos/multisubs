"""Backend-neutral ASR selection and adapter normalization."""

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from multisubs import cli, transcriber
from multisubs.asr import (
    ASRRequest,
    ASRResult,
    faster_whisper,
    parakeet,
    parse_backend,
    qwen,
    resolve_model,
    validate_request,
    whisperx,
)
from multisubs.asr.base import temporary_wav
from multisubs.errors import DependencyError, ValidationError
from multisubs.models import RunRequest


def _torch(cuda: bool = False):
    return SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda),
        float16="float16",
        float32="float32",
    )


@contextmanager
def _audio_file(path: Path):
    yield path


@pytest.mark.parametrize(
    ("backend", "expected"),
    [
        ("whisperx", "turbo"),
        ("faster-whisper", "turbo"),
        ("parakeet", "nvidia/parakeet-tdt-0.6b-v3"),
        ("qwen", "Qwen/Qwen3-ASR-1.7B"),
    ],
)
def test_backend_defaults_are_resolved_without_runtime_imports(backend, expected):
    selected = parse_backend(backend)
    assert resolve_model(selected, None) == expected


def test_qwen_rejects_removed_selector_and_smaller_model():
    with pytest.raises(ValidationError, match="Unknown ASR backend 'qwen3-asr'"):
        parse_backend("qwen3-asr")

    with pytest.raises(ValidationError, match="not supported by qwen"):
        resolve_model(parse_backend("qwen"), "Qwen/Qwen3-ASR-0.6B")


@pytest.mark.parametrize(
    ("module", "loader", "install_hint"),
    [
        ("whisperx", whisperx._load_whisperx, "multisubs[whisperx]"),
        ("nemo", parakeet._load_nemo_asr, "multisubs[parakeet]"),
        ("qwen_asr", qwen._load_qwen_asr, "multisubs[qwen]"),
    ],
)
def test_missing_asr_runtime_has_actionable_install_hint(
    monkeypatch, module, loader, install_hint
):
    monkeypatch.setitem(sys.modules, module, None)

    with pytest.raises(DependencyError) as exc_info:
        loader()
    assert install_hint in str(exc_info.value)


def test_missing_faster_whisper_has_actionable_install_hint(monkeypatch):
    def missing_runtime(name):
        raise ImportError(name)

    monkeypatch.setattr(faster_whisper, "import_module", missing_runtime)

    with pytest.raises(DependencyError, match=r"multisubs\[faster-whisper\]"):
        faster_whisper._load_faster_whisper()


@pytest.mark.parametrize(
    ("options", "backend", "model"),
    [
        ([], "whisperx", "turbo"),
        (["--asr", "faster-whisper"], "faster-whisper", "turbo"),
        (
            ["--asr", "parakeet"],
            "parakeet",
            "nvidia/parakeet-tdt-0.6b-v3",
        ),
        (["--asr", "qwen"], "qwen", "Qwen/Qwen3-ASR-1.7B"),
    ],
)
def test_cli_resolves_backend_specific_default_model(tmp_path, options, backend, model):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    parser = cli.build_parser()
    request = cli._build_request(
        parser.parse_args(["-i", str(source), *options]), parser
    )

    assert isinstance(request, RunRequest)
    assert request.asr_backend == backend
    assert request.model_name == model


@pytest.mark.parametrize(
    ("backend", "language", "task", "model", "message"),
    [
        ("parakeet", "pt", "translate", None, "does not support"),
        ("qwen", "pt", "translate", None, "does not support"),
        ("qwen", "uk", "transcribe", None, "not supported"),
        ("whisperx", "pt", "translate", "turbo", "does not support"),
    ],
)
def test_backend_capability_errors_are_raised_before_loading(
    backend, language, task, model, message
):
    selected = parse_backend(backend)
    resolved_model = resolve_model(selected, model)
    with pytest.raises(ValidationError, match=message):
        validate_request(selected, language, task, resolved_model)


def test_transcribe_video_routes_through_selected_adapter(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    calls = []

    class Adapter:
        def transcribe(self, request):
            calls.append(request)
            return ASRResult(
                "pt",
                "Olá.",
                ({"start": 0.0, "end": 1.0, "text": "Olá."},),
            )

    monkeypatch.setattr(transcriber, "create_adapter", lambda backend: Adapter())
    document = transcriber.transcribe_video(
        source,
        "pt",
        model_name="Qwen/Qwen3-ASR-1.7B",
        asr_backend="qwen",
    )

    assert calls[0].model_name == "Qwen/Qwen3-ASR-1.7B"
    assert document.asr_backend == "qwen"
    assert document.model_name == "Qwen/Qwen3-ASR-1.7B"
    assert document.full_text == "Olá."


def test_transcribe_video_keeps_unreported_language_unknown(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")

    class Adapter:
        def transcribe(self, request):
            return ASRResult(
                None,
                "Hello.",
                ({"start": 0.0, "end": 1.0, "text": "Hello."},),
            )

    monkeypatch.setattr(transcriber, "create_adapter", lambda backend: Adapter())
    progress: list[str] = []

    document = transcriber.transcribe_video(
        source,
        asr_backend="parakeet",
        progress=progress.append,
    )

    assert document.language is None
    assert progress[-1].endswith(
        "language metadata and filename suffixes were omitted."
    )


def test_faster_whisper_normalises_native_word_timestamps(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    state = {}

    class Model:
        def __init__(self, name, **kwargs):
            state["load"] = (name, kwargs)

        def transcribe(self, path, **kwargs):
            state["transcribe"] = (path, kwargs)
            word = SimpleNamespace(word=" Olá", start=0.1, end=0.5, probability=0.9)
            segment = SimpleNamespace(start=0.1, end=0.5, text=" Olá", words=[word])
            return iter([segment]), SimpleNamespace(language="pt")

    ctranslate2 = SimpleNamespace(get_cuda_device_count=lambda: 0)
    monkeypatch.setattr(
        faster_whisper, "_load_faster_whisper", lambda: (Model, ctranslate2)
    )
    result = faster_whisper.FasterWhisperAdapter().transcribe(
        ASRRequest(source, None, "transcribe", "turbo")
    )

    assert state["load"] == ("turbo", {"device": "cpu", "compute_type": "int8"})
    assert state["transcribe"][1]["word_timestamps"] is True
    assert result.language == "pt"
    assert result.text == "Olá"
    assert result.segments[0]["words"] == [
        {"word": " Olá", "start": 0.1, "end": 0.5, "score": 0.9}
    ]


def test_faster_whisper_selects_cuda_without_importing_torch(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    state = {}

    class Model:
        def __init__(self, name, **kwargs):
            state["load"] = (name, kwargs)

        def transcribe(self, path, **kwargs):
            segment = SimpleNamespace(start=0.0, end=1.0, text=" Hello", words=[])
            return iter([segment]), SimpleNamespace(language="en")

    ctranslate2 = SimpleNamespace(get_cuda_device_count=lambda: 1)
    monkeypatch.setattr(
        faster_whisper, "_load_faster_whisper", lambda: (Model, ctranslate2)
    )

    faster_whisper.FasterWhisperAdapter().transcribe(
        ASRRequest(source, "en", "transcribe", "turbo")
    )

    assert state["load"] == ("turbo", {"device": "cuda", "compute_type": "float16"})


def test_faster_whisper_bounds_translation_vad_chunks(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    state = {}

    class Model:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, **kwargs):
            state.update(kwargs)
            segment = SimpleNamespace(start=0.0, end=1.0, text=" Hello", words=None)
            return iter([segment]), SimpleNamespace(language="pt")

    ctranslate2 = SimpleNamespace(get_cuda_device_count=lambda: 0)
    monkeypatch.setattr(
        faster_whisper, "_load_faster_whisper", lambda: (Model, ctranslate2)
    )
    faster_whisper.FasterWhisperAdapter().transcribe(
        ASRRequest(source, "pt", "translate", "medium")
    )

    assert state["word_timestamps"] is False
    assert state["vad_filter"] is True
    assert state["vad_parameters"] == {"max_speech_duration_s": 6}


def test_parakeet_normalises_nemo_segments_and_words(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    state = {}
    hypothesis = SimpleNamespace(
        text="Olá mundo.",
        timestamp={
            "segment": [{"start": 0.0, "end": 1.0, "segment": "Olá mundo."}],
            "word": [
                {"start": 0.0, "end": 0.4, "word": "Olá"},
                {"start": 0.5, "end": 1.0, "word": "mundo."},
            ],
        },
    )

    class Model:
        def to(self, device):
            state["device"] = device
            return self

        def eval(self):
            state["eval"] = True

        def transcribe(self, paths, **kwargs):
            state["transcribe"] = (paths, kwargs)
            return [hypothesis]

    nemo = SimpleNamespace(
        models=SimpleNamespace(
            ASRModel=SimpleNamespace(from_pretrained=lambda **kwargs: Model())
        )
    )
    monkeypatch.setattr(parakeet, "load_torch", _torch)
    monkeypatch.setattr(parakeet, "_load_nemo_asr", lambda: nemo)
    monkeypatch.setattr(parakeet, "temporary_wav", lambda _: _audio_file(audio))
    monkeypatch.setattr(parakeet, "wav_duration", lambda _: 1.0)

    result = parakeet.ParakeetAdapter().transcribe(
        ASRRequest(
            tmp_path / "video.mp4",
            None,
            "transcribe",
            "nvidia/parakeet-tdt-0.6b-v3",
        )
    )

    assert state["device"] == "cpu"
    assert state["eval"] is True
    assert state["transcribe"] == ([str(audio)], {"timestamps": True})
    assert result.language is None
    assert result.segments[0]["words"][1]["word"] == "mundo."


def test_parakeet_assigns_boundary_words_to_one_segment():
    hypothesis = SimpleNamespace(
        text="one two",
        timestamp={
            "segment": [
                {"start": 0.0, "end": 1.0, "segment": "one"},
                {"start": 1.0, "end": 2.0, "segment": "two"},
            ],
            "word": [
                {"start": 0.5, "end": 1.0, "word": "one"},
                {"start": 1.0, "end": 1.5, "word": "two"},
            ],
        },
    )

    _, segments = parakeet._normalise_hypothesis(hypothesis, 2.0)

    assert [word["word"] for word in segments[0]["words"]] == ["one"]
    assert [word["word"] for word in segments[1]["words"]] == ["two"]


def test_qwen_uses_integrated_forced_alignment_for_explicit_language(
    tmp_path, monkeypatch
):
    audio = tmp_path / "audio.wav"
    state = {}

    class ModelType:
        @staticmethod
        def from_pretrained(name, **kwargs):
            state["model"] = (name, kwargs)
            return SimpleNamespace(
                transcribe=lambda **options: [
                    SimpleNamespace(
                        language="Portuguese",
                        text="Olá mundo.",
                        time_stamps=SimpleNamespace(
                            items=[
                                SimpleNamespace(
                                    text="Olá", start_time=0.0, end_time=0.4
                                ),
                                SimpleNamespace(
                                    text="mundo.", start_time=0.5, end_time=1.0
                                ),
                            ]
                        ),
                    )
                ]
            )

    monkeypatch.setattr(qwen, "load_torch", _torch)
    monkeypatch.setattr(qwen, "_load_qwen_asr", lambda: ModelType)
    monkeypatch.setattr(qwen, "temporary_wav", lambda _: _audio_file(audio))
    monkeypatch.setattr(qwen, "wav_duration", lambda _: 1.0)

    result = qwen.QwenAdapter().transcribe(
        ASRRequest(
            tmp_path / "video.mp4",
            "pt",
            "transcribe",
            "Qwen/Qwen3-ASR-1.7B",
        )
    )

    assert result.language == "pt"
    assert result.segments[0]["words"][0] == {
        "word": "Olá",
        "start": 0.0,
        "end": 0.4,
    }
    assert state["model"][0] == "Qwen/Qwen3-ASR-1.7B"
    assert state["model"][1]["device_map"] == "cpu"
    assert state["model"][1]["forced_aligner"] == ("Qwen/Qwen3-ForcedAligner-0.6B")
    assert state["model"][1]["forced_aligner_kwargs"] == {
        "dtype": "float32",
        "device_map": "cpu",
    }


def test_qwen_uses_coarse_timing_when_language_has_no_aligner(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    state = {}

    class ModelType:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            state.update(kwargs)
            return SimpleNamespace(
                transcribe=lambda **options: [
                    SimpleNamespace(language="Hindi", text="नमस्ते")
                ]
            )

    monkeypatch.setattr(qwen, "load_torch", _torch)
    monkeypatch.setattr(qwen, "_load_qwen_asr", lambda: ModelType)
    monkeypatch.setattr(qwen, "temporary_wav", lambda _: _audio_file(audio))
    monkeypatch.setattr(qwen, "wav_duration", lambda _: 2.5)

    result = qwen.QwenAdapter().transcribe(
        ASRRequest(
            tmp_path / "video.mp4",
            None,
            "transcribe",
            "Qwen/Qwen3-ASR-1.7B",
        )
    )

    assert result.language == "hi"
    assert result.segments == ({"start": 0.0, "end": 2.5, "text": "नमस्ते"},)
    assert "forced_aligner" not in state


def test_temporary_wav_is_removed_after_adapter_use(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    extracted = None

    def fake_extract(input_path, output_path):
        nonlocal extracted
        assert input_path == source
        extracted = output_path
        output_path.write_bytes(b"audio")
        return output_path

    monkeypatch.setattr("multisubs.subtitler.extract_audio_track", fake_extract)

    with temporary_wav(source) as audio_path:
        assert audio_path.read_bytes() == b"audio"
        assert extracted == audio_path

    assert extracted is not None
    assert not extracted.exists()
