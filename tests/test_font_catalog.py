import hashlib
import tempfile
from pathlib import Path

import pytest
from PIL import ImageFont

from multisubs import font_catalog
from multisubs.font_catalog import (
    bundled_font_directory,
    find_bundled_font_family,
    load_bundled_font_catalog,
    verify_bundled_font_assets,
)

EXPECTED_FACES = {
    "Roboto": {
        (weight, italic) for weight in range(100, 1000, 100) for italic in (False, True)
    },
    "Inter": {
        (weight, italic) for weight in range(100, 1000, 100) for italic in (False, True)
    },
    "Montserrat": {
        (weight, italic) for weight in range(100, 1000, 100) for italic in (False, True)
    },
    "Oswald": {(weight, False) for weight in range(200, 800, 100)},
    "Lora": {
        (weight, italic) for weight in range(400, 800, 100) for italic in (False, True)
    },
    "Atkinson Hyperlegible Next": {
        (weight, italic) for weight in range(200, 900, 100) for italic in (False, True)
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_declares_the_complete_pinned_face_inventory():
    catalog = load_bundled_font_catalog()

    assert catalog.schema_version == 2
    assert catalog.face_count == 82
    assert {family.family for family in catalog.families} == set(EXPECTED_FACES)
    for family in catalog.families:
        assert {(face.weight, face.italic) for face in family.faces} == EXPECTED_FACES[
            family.family
        ]
        assert family.license == "OFL-1.1"
        assert len(family.revision) == 40
        assert family.upstream_url.startswith("https://github.com/")
        assert family.source_url.startswith("https://fonts.googleapis.com/")
        assert all(
            face.source_url.startswith("https://fonts.gstatic.com/")
            for face in family.faces
        )


def test_manifest_hashes_sizes_and_pillow_metadata_match_packaged_files():
    catalog = load_bundled_font_catalog()

    for family in catalog.families:
        directory = font_catalog.bundled_filesystem_directory(family.family)
        assert directory is not None
        license_path = directory / family.license_file
        assert "SIL OPEN FONT LICENSE Version 1.1" in license_path.read_text(
            encoding="utf-8"
        )
        assert license_path.stat().st_size == family.license_size
        assert _sha256(license_path) == family.license_sha256
        for face in family.faces:
            path = directory / face.filename
            assert path.stat().st_size == face.size
            assert _sha256(path) == face.sha256
            assert path.suffix.casefold() == f".{face.format}"
            loaded = ImageFont.truetype(path, 32)
            assert loaded.getname() == (
                face.internal_family,
                face.style,
            )
            with pytest.raises(OSError):
                loaded.get_variation_axes()

    assert verify_bundled_font_assets() == 82


@pytest.mark.parametrize(
    "name",
    (
        "roboto",
        "ROBOTO",
        "Atkinson-Hyperlegible-Next",
        "atkinson hyperlegible next",
    ),
)
def test_family_lookup_is_case_and_punctuation_insensitive(name: str):
    assert find_bundled_font_family(name) is not None


def test_unknown_family_has_no_bundled_provider():
    assert find_bundled_font_family("Fixture Sans") is None
    with bundled_font_directory("Fixture Sans") as directory:
        assert directory is None


def test_non_filesystem_resource_materializes_only_one_family_and_cleans_up(
    monkeypatch,
):
    original_temporary_directory = tempfile.TemporaryDirectory

    def temporary_directory(*, prefix: str):
        del prefix
        return original_temporary_directory(prefix="fontes ç com espaços-")

    monkeypatch.setattr(font_catalog, "bundled_filesystem_directory", lambda name: None)
    monkeypatch.setattr(
        font_catalog.tempfile, "TemporaryDirectory", temporary_directory
    )

    with bundled_font_directory("Lora") as directory:
        assert directory is not None
        materialized = directory
        lora = find_bundled_font_family("Lora")
        assert lora is not None
        assert " " in str(directory)
        assert {path.name for path in directory.iterdir()} == {
            "OFL.txt",
            *(face.filename for face in lora.faces),
        }
        assert not any(
            path.name == "Roboto-Regular.ttf" for path in directory.iterdir()
        )

    assert not materialized.exists()

    with pytest.raises(OSError, match="consumer failure"):
        with bundled_font_directory("Lora"):
            raise OSError("consumer failure")
