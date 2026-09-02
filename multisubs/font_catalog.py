"""Validated access to the bundled, offline OFL font catalog."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from .errors import DependencyError

_RESOURCE_ROOT = ("assets", "fonts")
_MANIFEST_NAME = "manifest.json"
_SUPPORTED_FORMATS = frozenset({"otf", "ttf"})
_MAX_FAMILIES = 32
_MAX_FACES_PER_FAMILY = 64


@dataclass(frozen=True)
class BundledFontFace:
    """One immutable font face declared by the packaged manifest."""

    filename: str
    internal_family: str
    style: str
    weight: int
    italic: bool
    format: str
    size: int
    sha256: str
    source_url: str


@dataclass(frozen=True)
class BundledFontFamily:
    """One immutable family and its pinned provider provenance."""

    identifier: str
    family: str
    version: str
    revision: str
    upstream_url: str
    source_url: str
    license_url: str
    license: str
    license_file: str
    license_size: int
    license_sha256: str
    faces: tuple[BundledFontFace, ...]


@dataclass(frozen=True)
class BundledFontCatalog:
    """The complete validated catalog shipped in package resources."""

    schema_version: int
    face_count: int
    families: tuple[BundledFontFamily, ...]

    def family(self, name: str) -> BundledFontFamily | None:
        """Return a family using case- and punctuation-insensitive matching."""
        normalized = _normalise_family_name(name)
        return next(
            (
                family
                for family in self.families
                if _normalise_family_name(family.family) == normalized
            ),
            None,
        )


@lru_cache(maxsize=1)
def load_bundled_font_catalog() -> BundledFontCatalog:
    """Load and validate the packaged manifest without hashing font binaries."""
    manifest = _font_resource_root().joinpath(_MANIFEST_NAME)
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DependencyError(
            "Bundled font catalog is missing or invalid; reinstall multisubs."
        ) from exc
    try:
        return _parse_catalog(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise DependencyError(
            "Bundled font manifest is invalid; reinstall multisubs."
        ) from exc


def find_bundled_font_family(name: str) -> BundledFontFamily | None:
    """Find a bundled family without touching any system font provider."""
    return load_bundled_font_catalog().family(name)


def verify_bundled_font_assets() -> int:
    """Verify packaged sizes and hashes on explicit audit requests only."""
    catalog = load_bundled_font_catalog()
    verified = 0
    for family in catalog.families:
        with bundled_font_directory(family.family) as directory:
            if directory is None:
                raise DependencyError(
                    f"Bundled font family '{family.family}' is unavailable."
                )
            _verify_resource(
                directory / family.license_file,
                expected_size=family.license_size,
                expected_sha256=family.license_sha256,
            )
            for face in family.faces:
                _verify_resource(
                    directory / face.filename,
                    expected_size=face.size,
                    expected_sha256=face.sha256,
                )
                verified += 1
    return verified


def bundled_filesystem_directory(name: str) -> Path | None:
    """Return a direct family directory when package resources are unpacked."""
    family = find_bundled_font_family(name)
    if family is None:
        return None
    resource = _font_resource_root().joinpath(family.identifier)
    try:
        candidate = Path(os.fspath(resource)).resolve(strict=False)
    except TypeError:
        return None
    return candidate if candidate.is_dir() else None


@contextmanager
def bundled_font_directory(name: str) -> Iterator[Path | None]:
    """Keep the selected bundled family available for one pipeline invocation."""
    family = find_bundled_font_family(name)
    if family is None:
        yield None
        return

    direct = bundled_filesystem_directory(name)
    if direct is not None:
        yield direct
        return

    family_resource = _font_resource_root().joinpath(family.identifier)
    with tempfile.TemporaryDirectory(prefix="multisubs-fonts-") as directory:
        materialized = Path(directory) / family.identifier
        try:
            materialized.mkdir()
            names = (family.license_file, *(face.filename for face in family.faces))
            for filename in names:
                source = family_resource.joinpath(filename)
                with source.open("rb") as source_file:
                    with (materialized / filename).open("wb") as destination:
                        shutil.copyfileobj(source_file, destination)
        except (FileNotFoundError, OSError) as exc:
            raise DependencyError(
                f"Bundled font resources for '{family.family}' are incomplete; "
                "reinstall multisubs."
            ) from exc
        yield materialized


def _font_resource_root() -> Any:
    root = resources.files("multisubs")
    for part in _RESOURCE_ROOT:
        root = root.joinpath(part)
    return root


def _verify_resource(
    path: Path,
    *,
    expected_size: int,
    expected_sha256: str,
) -> None:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise DependencyError(
            "Bundled font resources are incomplete; reinstall multisubs."
        ) from exc
    if (
        len(payload) != expected_size
        or hashlib.sha256(payload).hexdigest() != expected_sha256
    ):
        raise DependencyError(
            "Bundled font resource integrity check failed; reinstall multisubs."
        )


def _parse_catalog(payload: object) -> BundledFontCatalog:
    root = _require_mapping(payload, "catalog")
    schema_version = _require_int(root, "schema_version", minimum=2, maximum=2)
    declared_face_count = _require_int(root, "face_count", minimum=1)
    raw_families = root.get("families")
    if (
        not isinstance(raw_families, list)
        or not 1 <= len(raw_families) <= _MAX_FAMILIES
    ):
        raise ValueError("families must be a bounded non-empty list")

    families = tuple(_parse_family(item) for item in raw_families)
    identifiers = {family.identifier for family in families}
    names = {_normalise_family_name(family.family) for family in families}
    if len(identifiers) != len(families) or len(names) != len(families):
        raise ValueError("font family identifiers and names must be unique")
    face_count = sum(len(family.faces) for family in families)
    if face_count != declared_face_count:
        raise ValueError("declared face count does not match the manifest")
    return BundledFontCatalog(schema_version, face_count, families)


def _parse_family(payload: object) -> BundledFontFamily:
    item = _require_mapping(payload, "family")
    identifier = _require_text(item, "id")
    family_name = _require_text(item, "family")
    if not identifier.replace("-", "").isalnum() or identifier != identifier.casefold():
        raise ValueError("family id must be lowercase kebab-case")
    raw_faces = item.get("faces")
    if (
        not isinstance(raw_faces, list)
        or not 1 <= len(raw_faces) <= _MAX_FACES_PER_FAMILY
    ):
        raise ValueError("faces must be a bounded non-empty list")
    faces = tuple(_parse_face(face) for face in raw_faces)
    if len({face.filename.casefold() for face in faces}) != len(faces):
        raise ValueError("face filenames must be unique within a family")
    if len({(face.weight, face.italic) for face in faces}) != len(faces):
        raise ValueError("face weight and italic pairs must be unique within a family")
    if any(
        _normalise_family_name(face.internal_family)
        != _normalise_family_name(family_name)
        for face in faces
    ):
        raise ValueError("face internal family does not match its catalog family")
    return BundledFontFamily(
        identifier=identifier,
        family=family_name,
        version=_require_text(item, "version"),
        revision=_require_sha256_like_revision(item, "revision"),
        upstream_url=_require_https_url(item, "upstream_url"),
        source_url=_require_https_url(item, "source_url"),
        license_url=_require_https_url(item, "license_url"),
        license=_require_license(item),
        license_file=_require_safe_filename(item, "license_file"),
        license_size=_require_int(item, "license_size", minimum=1),
        license_sha256=_require_sha256(item, "license_sha256"),
        faces=faces,
    )


def _parse_face(payload: object) -> BundledFontFace:
    item = _require_mapping(payload, "face")
    font_format = _require_text(item, "format").casefold()
    if font_format not in _SUPPORTED_FORMATS:
        raise ValueError("unsupported bundled font format")
    filename = _require_safe_filename(item, "filename")
    if Path(filename).suffix.casefold() != f".{font_format}":
        raise ValueError("face format does not match its filename")
    return BundledFontFace(
        filename=filename,
        internal_family=_require_text(item, "internal_family"),
        style=_require_text(item, "style"),
        weight=_require_int(item, "weight", minimum=100, maximum=900),
        italic=_require_bool(item, "italic"),
        format=font_format,
        size=_require_int(item, "size", minimum=1),
        sha256=_require_sha256(item, "sha256"),
        source_url=_require_https_url(item, "source_url"),
    )


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    return value


def _require_text(item: Mapping[str, object], key: str) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty text")
    return value


def _require_int(
    item: Mapping[str, object],
    key: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    value = item[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{key} is outside the supported range")
    return value


def _require_bool(item: Mapping[str, object], key: str) -> bool:
    value = item[key]
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _require_safe_filename(item: Mapping[str, object], key: str) -> str:
    value = _require_text(item, key)
    if Path(value).name != value or value in {".", ".."}:
        raise ValueError(f"{key} must be one filename")
    return value


def _require_https_url(item: Mapping[str, object], key: str) -> str:
    value = _require_text(item, key)
    if not value.startswith("https://"):
        raise ValueError(f"{key} must use HTTPS")
    return value


def _require_sha256(item: Mapping[str, object], key: str) -> str:
    value = _require_text(item, key).casefold()
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{key} must be a SHA-256 digest")
    return value


def _require_sha256_like_revision(item: Mapping[str, object], key: str) -> str:
    value = _require_text(item, key).casefold()
    if len(value) != 40 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{key} must be a full Git commit hash")
    return value


def _require_license(item: Mapping[str, object]) -> str:
    value = _require_text(item, "license")
    if value != "OFL-1.1":
        raise ValueError("bundled fonts must use OFL-1.1")
    return value


def _normalise_family_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    return "".join(character for character in name.casefold() if character.isalnum())
