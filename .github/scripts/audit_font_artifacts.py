#!/usr/bin/env python3
"""Audit bundled-font inventories and hashes inside built wheel/sdist files."""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

RESOURCE_ROOT = "multisubs/assets/fonts"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _expected_assets(manifest: Mapping[str, object]) -> dict[str, tuple[int, str]]:
    expected: dict[str, tuple[int, str]] = {}
    families = manifest.get("families")
    if not isinstance(families, list):
        raise ValueError("font manifest families must be a list")
    for raw_family in families:
        if not isinstance(raw_family, Mapping):
            raise ValueError("font manifest family must be an object")
        identifier = str(raw_family["id"])
        license_file = str(raw_family["license_file"])
        expected[f"{identifier}/{license_file}"] = (
            int(raw_family["license_size"]),
            str(raw_family["license_sha256"]),
        )
        faces = raw_family.get("faces")
        if not isinstance(faces, list):
            raise ValueError("font manifest faces must be a list")
        for raw_face in faces:
            if not isinstance(raw_face, Mapping):
                raise ValueError("font manifest face must be an object")
            expected[f"{identifier}/{raw_face['filename']}"] = (
                int(raw_face["size"]),
                str(raw_face["sha256"]),
            )
    return expected


def _relative_resource_name(name: str) -> str | None:
    marker = f"{RESOURCE_ROOT}/"
    if name.startswith(marker):
        return name[len(marker) :]
    embedded = f"/{marker}"
    if embedded in name:
        return name.split(embedded, 1)[1]
    return None


def _audit_entries(
    archive: Path,
    names: Sequence[str],
    read: Callable[[str], bytes],
) -> None:
    resources: dict[str, str] = {}
    for name in names:
        relative = _relative_resource_name(name)
        if relative is None or not Path(relative).suffix:
            continue
        if relative in resources:
            raise ValueError(f"{archive.name}: duplicate font resource {relative}")
        resources[relative] = name
    manifest_name = resources.pop("manifest.json", None)
    if manifest_name is None:
        raise ValueError(f"{archive.name}: font manifest is missing")
    manifest_payload = read(manifest_name)
    manifest = json.loads(manifest_payload.decode("utf-8"))
    expected = _expected_assets(manifest)
    if set(resources) != set(expected):
        missing = sorted(set(expected).difference(resources))
        extra = sorted(set(resources).difference(expected))
        raise ValueError(
            f"{archive.name}: font inventory differs; missing={missing}, extra={extra}"
        )
    for relative, (expected_size, expected_digest) in expected.items():
        payload = read(resources[relative])
        if len(payload) != expected_size or _digest(payload) != expected_digest:
            raise ValueError(f"{archive.name}: integrity mismatch for {relative}")


def audit_archive(path: Path) -> None:
    """Audit one wheel or source archive against its packaged manifest."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            _audit_entries(path, archive.namelist(), archive.read)
        return
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, mode="r:gz") as archive:
            members = {member.name: member for member in archive.getmembers()}

            def read(name: str) -> bytes:
                extracted = archive.extractfile(members[name])
                if extracted is None:
                    raise ValueError(f"{path.name}: could not read {name}")
                return extracted.read()

            _audit_entries(path, tuple(members), read)
        return
    raise ValueError(f"Unsupported distribution artifact: {path}")


def main(argv: Sequence[str] | None = None) -> int:
    paths = tuple(Path(argument) for argument in (argv or sys.argv[1:]))
    if not paths:
        print("usage: audit_font_artifacts.py DIST [DIST ...]", file=sys.stderr)
        return 2
    try:
        for path in paths:
            audit_archive(path)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"font artifact audit failed: {exc}", file=sys.stderr)
        return 1
    print(f"Verified bundled fonts in {len(paths)} distribution artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
