"""Bounded local storage of source speech before presentation decisions."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .errors import ArtifactError, ValidationError
from .speech import SpeechTranscript
from .utils import atomic_write_text

_CACHE_VERSION = 1
_RECOGNITION_REVISION = 1
_MAX_BYTES = 16 * 1024 * 1024
_RUNTIME_PACKAGES = {
    "whisperx": ("whisperx", "torch", "faster-whisper", "ctranslate2"),
    "faster-whisper": ("faster-whisper", "ctranslate2"),
    "parakeet": ("nemo-toolkit", "torch"),
    "qwen": ("transformers", "torch", "librosa", "nagisa", "soynlp"),
}


def _versions(backend: str) -> dict[str, str]:
    result = {}
    for package in _RUNTIME_PACKAGES[backend]:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            pass
    return result


def _source_state(path: Path) -> tuple[int, ...]:
    value = path.stat()
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate cache field")
        result[key] = value
    return result


def _read_entry(
    path: Path, identity: dict[str, Any], versions: dict[str, str]
) -> SpeechTranscript:
    if path.is_symlink():
        raise ArtifactError(f"Refusing to read a symbolic-link cache entry '{path}'")
    with path.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValidationError("Speech cache entry exceeds 16 MiB")
    payload = json.loads(raw, object_pairs_hook=_unique_object)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"cache_version", "identity", "runtime_versions", "speech"}
        or type(payload["cache_version"]) is not int
        or payload["cache_version"] != _CACHE_VERSION
        or payload["identity"] != identity
        or not isinstance(payload["runtime_versions"], dict)
    ):
        raise ValidationError("Speech cache entry is incompatible")
    if any(
        payload["runtime_versions"].get(name) != value
        for name, value in versions.items()
    ):
        raise ValidationError("Speech cache runtime versions have changed")
    speech = SpeechTranscript.from_dict(payload["speech"])
    if (
        speech.asr_backend != identity["backend"]
        or speech.model_name != identity["model"]
        or (
            identity["language"] is not None and speech.language != identity["language"]
        )
    ):
        raise ValidationError("Speech cache provenance does not match the request")
    return speech


def get_cached_speech(
    source: Path,
    cache_dir: Path,
    *,
    language: str | None,
    backend: str,
    model: str,
    refresh: bool = False,
    progress: Callable[[str], None] | None = None,
    verbose: bool = False,
) -> SpeechTranscript:
    """Reuse source speech or recognize and atomically save it before layout.

    The caller supplies the directory; the CLI defaults it below its output.
    Entries contain source text and observed times, never media, fonts, layout,
    or runtime objects. Missing optional runtimes do not prevent a hit;
    installed incompatible versions require recognition.
    """
    from .transcriber import transcribe_speech

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    try:
        report(f"Checking source speech cache in '{cache_dir}'...")
        state = _source_state(source)
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if _source_state(source) != state:
            raise ArtifactError("Input video changed while checking the speech cache")
        identity = {
            "source_sha256": digest.hexdigest(),
            "backend": backend,
            "model": model,
            "language": language,
            "task": "transcribe",
            "recognition_revision": _RECOGNITION_REVISION,
        }
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        directory = cache_dir / "transcriptions" / f"v{_CACHE_VERSION}"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / f"{key}.json"
        versions = _versions(backend)
        if not refresh:
            try:
                try:
                    speech = _read_entry(path, identity, versions)
                except FileNotFoundError:
                    # Reuse entries created before the directory was renamed.
                    speech = _read_entry(
                        cache_dir / "speech-v1" / path.name, identity, versions
                    )
            except FileNotFoundError:
                pass
            except (ValueError, UnicodeError, RecursionError, ValidationError):
                report(
                    "Speech cache entry is invalid or incompatible; transcribing again."
                )
            else:
                report(
                    "Reusing cached source transcription; ASR and alignment skipped."
                )
                return speech
        # Check write access before loading an expensive runtime. A refresh
        # preserves the old complete entry until recognition succeeds.
        with tempfile.TemporaryFile(dir=directory):
            pass
        report("Transcribing the full input video for the source speech cache...")
        speech = transcribe_speech(
            source,
            lang=language,
            model_name=model,
            asr_backend=backend,
            progress=progress,
            verbose=verbose,
        )
        if _source_state(source) != state:
            raise ArtifactError(
                "Input video changed during transcription; cache not saved"
            )
        content = json.dumps(
            {
                "cache_version": _CACHE_VERSION,
                "identity": identity,
                "runtime_versions": versions,
                "speech": speech.to_dict(),
            },
            ensure_ascii=False,
            allow_nan=False,
        )
        if len(content.encode("utf-8")) > _MAX_BYTES:
            raise ArtifactError(
                "Source transcription exceeds the 16 MiB speech cache limit"
            )
        atomic_write_text(path, content)
        report("Source transcription saved to the speech cache.")
        return speech
    except OSError as exc:
        raise ArtifactError(
            f"Could not access speech cache '{cache_dir}': {exc}"
        ) from exc
