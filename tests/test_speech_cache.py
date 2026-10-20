"""Source cache identity, bounded input, failure recovery, and runtime isolation."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from typing import Any

import pytest

from multisubs import speech_cache, transcriber
from multisubs.errors import ArtifactError, TranscriptionError
from multisubs.speech import SpeechTranscript


@pytest.fixture
def cached(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source media")
    directory = tmp_path / "cache"
    calls = []

    def recognize(path, *, lang, model_name, asr_backend, **kwargs):
        calls.append(path)
        return SpeechTranscript.from_dict(
            {
                "schema_version": 1,
                "language": lang,
                "task": "transcribe",
                "asr_backend": asr_backend,
                "model_name": model_name,
                "full_text": " Olá, 世界!",
                "segments": [
                    {"text": " Olá,", "start": 0, "end": 1, "words": None},
                    {
                        "text": " 世界!",
                        "start": 1,
                        "end": 2,
                        "words": [
                            {"word": " 世界!", "start": 1, "end": None, "score": 0.8}
                        ],
                    },
                ],
            }
        )

    monkeypatch.setattr(transcriber, "transcribe_speech", recognize)
    monkeypatch.setattr(speech_cache, "_versions", lambda _: {})

    def get(path=source, **overrides):
        settings: dict[str, Any] = {
            "language": "pt",
            "backend": "whisperx",
            "model": "turbo",
        }
        settings.update(overrides)
        return speech_cache.get_cached_speech(path, directory, **settings)

    return source, directory, calls, get


def test_cache_round_trip_preserves_source_and_skips_asr(cached, monkeypatch):
    source, directory, calls, get = cached
    original = get()
    saved = deepcopy(original.to_dict())
    monkeypatch.setattr(
        transcriber,
        "transcribe_speech",
        lambda *a, **kw: pytest.fail("cache hit must not recognize speech"),
    )
    assert get().to_dict() == saved
    renamed = source.with_name("renamed.mp4")
    renamed.write_bytes(source.read_bytes())
    assert get(renamed).to_dict() == saved
    assert len(calls) == 1
    entry = next(directory.rglob("*.json"))
    assert entry.parent == directory / "transcriptions" / "v1"
    if os.name == "posix":
        assert entry.stat().st_mode & 0o777 == 0o600
        assert entry.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("refresh", [False, True])
def test_legacy_cache_is_reused_and_refresh_writes_to_current_layout(cached, refresh):
    _source, directory, calls, get = cached
    original = get()
    current = next(directory.rglob("*.json"))
    legacy = directory / "speech-v1" / current.name
    legacy.parent.mkdir()
    current.rename(legacy)
    before = legacy.read_bytes()

    assert get(refresh=refresh).to_dict() == original.to_dict()
    assert len(calls) == (2 if refresh else 1)
    assert legacy.read_bytes() == before
    if refresh:
        assert current.is_file()
        # Current entries take precedence, even if a legacy entry is unusable.
        legacy.write_text("{")
        assert get().to_dict() == original.to_dict()
        assert len(calls) == 2


def test_failed_refresh_keeps_legacy_cache_reusable(cached, monkeypatch):
    _source, directory, calls, get = cached
    original = get()
    current = next(directory.rglob("*.json"))
    legacy = directory / "speech-v1" / current.name
    legacy.parent.mkdir()
    current.rename(legacy)
    before = legacy.read_bytes()

    def failed(*args, **kwargs):
        raise TranscriptionError("recognition failed")

    monkeypatch.setattr(transcriber, "transcribe_speech", failed)
    with pytest.raises(TranscriptionError):
        get(refresh=True)
    assert legacy.read_bytes() == before
    assert get().to_dict() == original.to_dict()
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"language": None},
        {"language": "en"},
        {"model": "large-v3"},
        {"backend": "faster-whisper"},
    ],
)
def test_recognition_request_changes_miss(cached, changes):
    _source, _directory, calls, get = cached
    get()
    get(**changes)
    assert len(calls) == 2


def test_full_content_hash_detects_equal_size_and_restored_mtime(cached):
    source, _directory, calls, get = cached
    get()
    original = source.stat()
    source.write_bytes(b"changed data")
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    get()
    assert len(calls) == 2


def test_refresh_and_compatibility_revision_miss(cached, monkeypatch):
    _source, _directory, calls, get = cached
    get()
    get(refresh=True)
    monkeypatch.setattr(speech_cache, "_RECOGNITION_REVISION", 2)
    get()
    assert len(calls) == 3


def test_runtime_version_mismatch_invalidates_but_absence_allows_hit(
    cached, monkeypatch
):
    _source, _directory, calls, get = cached
    monkeypatch.setattr(speech_cache, "_versions", lambda _: {"whisperx": "1"})
    get()
    monkeypatch.setattr(speech_cache, "_versions", lambda _: {})
    get()
    assert len(calls) == 1
    monkeypatch.setattr(speech_cache, "_versions", lambda _: {"whisperx": "2"})
    get()
    assert len(calls) == 2


@pytest.mark.parametrize(
    "kind", ["malformed", "version", "provenance", "duplicate", "oversized"]
)
def test_invalid_entries_are_recomputed_visibly(cached, kind):
    _source, directory, calls, get = cached
    get()
    path = next(directory.rglob("*.json"))
    data = json.loads(path.read_text())
    if kind == "malformed":
        content = "{"
    elif kind == "duplicate":
        content = '{"cache_version":1,"cache_version":1}'
    elif kind == "oversized":
        content = " " * (speech_cache._MAX_BYTES + 1)
    else:
        if kind == "version":
            data["cache_version"] = 99
        else:
            data["speech"]["model_name"] = "wrong"
        content = json.dumps(data)
    path.write_text(content)
    messages = []
    get(progress=messages.append)
    assert len(calls) == 2
    assert any("invalid or incompatible" in message for message in messages)


def test_failed_refresh_retains_complete_entry(cached, monkeypatch):
    _source, directory, _calls, get = cached
    original = get()
    before = next(directory.rglob("*.json")).read_bytes()

    def failed(*args, **kwargs):
        raise TranscriptionError("recognition failed")

    monkeypatch.setattr(transcriber, "transcribe_speech", failed)
    with pytest.raises(TranscriptionError):
        get(refresh=True)
    assert next(directory.rglob("*.json")).read_bytes() == before
    assert get().to_dict() == original.to_dict()


def test_source_mutation_does_not_publish_cache(cached, monkeypatch):
    source, directory, _calls, get = cached
    original = transcriber.transcribe_speech

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        source.write_bytes(b"source changed during ASR")
        return result

    monkeypatch.setattr(transcriber, "transcribe_speech", mutate)
    with pytest.raises(ArtifactError, match="changed during transcription"):
        get()
    assert not list(directory.rglob("*.json"))


def test_cache_io_errors_do_not_invoke_asr(cached, monkeypatch):
    _source, _directory, calls, get = cached

    def denied(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(speech_cache, "_read_entry", denied)
    with pytest.raises(ArtifactError, match="Could not access speech cache"):
        get()
    assert not calls


def test_symlink_entry_is_not_followed(cached, tmp_path):
    _source, directory, calls, get = cached
    get()
    path = next(directory.rglob("*.json"))
    target = tmp_path / "private.json"
    target.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(target)
    before = target.read_bytes()
    with pytest.raises(ArtifactError, match="symbolic-link"):
        get()
    assert target.read_bytes() == before
    assert len(calls) == 1


def test_concurrent_writers_only_publish_complete_entries(cached, monkeypatch):
    _source, directory, calls, get = cached
    barrier = Barrier(2)
    original = transcriber.transcribe_speech

    def recognize(*args, **kwargs):
        barrier.wait(timeout=10)
        return original(*args, **kwargs)

    monkeypatch.setattr(transcriber, "transcribe_speech", recognize)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(get) for _ in range(2)]
        results = [future.result(timeout=15).to_dict() for future in futures]
    assert results[0] == results[1]
    assert len(calls) == 2
    assert len(list(directory.rglob("*.json"))) == 1
    assert get().to_dict() == results[0]
    assert not list(directory.rglob("*.tmp"))


def test_new_process_reuses_cache_without_importing_any_asr_runtime(cached):
    source, directory, _calls, get = cached
    get()
    script = """
import builtins
import sys
from pathlib import Path
original = builtins.__import__
blocked = {"torch", "whisperx", "faster_whisper", "ctranslate2", "nemo", "transformers"}
def guarded(name, *args, **kwargs):
    if name.split(".")[0] in blocked:
        raise AssertionError("ASR runtime imported during cache hit")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from multisubs import speech_cache
speech_cache._versions = lambda _: {}
speech = speech_cache.get_cached_speech(
    Path(sys.argv[1]), Path(sys.argv[2]),
    language="pt", backend="whisperx", model="turbo"
)
assert speech.language == "pt"
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(source), str(directory)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
