"""Collision-safe paths and project-owned file operations."""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from .errors import ArtifactError


def get_unique_path(path: str | os.PathLike[str]) -> str:
    """Return a non-existing filename by appending `` (n)`` when needed."""
    candidate = Path(path)
    if not os.path.lexists(candidate):
        return str(candidate)

    index = 1
    while True:
        numbered = candidate.with_name(f"{candidate.stem} ({index}){candidate.suffix}")
        if not os.path.lexists(numbered):
            return str(numbered)
        index += 1


def get_unique_dir_path(path: str | os.PathLike[str]) -> str:
    """Return a non-existing directory name by appending `` (n)`` when needed."""
    candidate = Path(path)
    if not os.path.lexists(candidate):
        return str(candidate)

    index = 1
    while True:
        numbered = candidate.with_name(f"{candidate.name} ({index})")
        if not os.path.lexists(numbered):
            return str(numbered)
        index += 1


def create_unique_dir(path: Path) -> Path:
    """Atomically create a uniquely named directory and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = path if index == 0 else path.with_name(f"{path.name} ({index})")
        try:
            candidate.mkdir()
        except FileExistsError:
            index += 1
            continue
        except OSError as exc:
            raise ArtifactError(
                f"Could not create output directory '{candidate}': {exc}"
            ) from exc
        return candidate


def create_work_dir(output_dir: Path) -> Path:
    """Create a private work directory adjacent to the requested output."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=".multisubs-", dir=output_dir))
    except OSError as exc:
        raise ArtifactError(
            f"Could not create output directory '{output_dir}': {exc}"
        ) from exc


def find_unique_stem(directory: Path, stem: str, suffixes: Iterable[str]) -> str:
    """Find one available stem across a related set of output suffixes."""
    suffixes = tuple(suffixes)
    index = 0
    while True:
        candidate = stem if index == 0 else f"{stem} ({index})"
        if not any(
            os.path.lexists(directory / f"{candidate}{suffix}") for suffix in suffixes
        ):
            return candidate
        index += 1


def atomic_write_text(path: Path, content: str) -> None:
    """Write UTF-8 text through a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        raise ArtifactError(f"Could not write '{path}': {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def publish_files(files: Mapping[Path, Path]) -> None:
    """Publish project-owned files without overwriting existing destinations.

    Sources and destinations should live on the same filesystem. Hard links make
    publication atomic on supported filesystems; an exclusive-copy fallback keeps
    the no-overwrite guarantee where links are unavailable.
    """
    created: list[Path] = []
    try:
        for source, destination in files.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            _publish_one(source, destination)
            created.append(destination)
    except FileExistsError:
        for destination in reversed(created):
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    except (ArtifactError, OSError) as exc:
        for destination in reversed(created):
            try:
                destination.unlink()
            except OSError:
                pass
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError(f"Could not publish output artifacts: {exc}") from exc


def _publish_one(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
        return
    except FileExistsError:
        raise
    except OSError as exc:
        if exc.errno not in {errno.EPERM, errno.EXDEV, errno.ENOSYS, errno.EOPNOTSUPP}:
            raise ArtifactError(
                f"Could not publish '{source}' to '{destination}': {exc}"
            ) from exc

    created_destination = False
    try:
        with source.open("rb") as source_stream:
            with destination.open("xb") as destination_stream:
                created_destination = True
                shutil.copyfileobj(source_stream, destination_stream)
    except OSError as exc:
        if created_destination:
            try:
                destination.unlink()
            except OSError:
                pass
        raise ArtifactError(
            f"Could not publish '{source}' to '{destination}': {exc}"
        ) from exc
