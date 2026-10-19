"""Generated benchmark/media files cannot become distribution contents."""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest


@pytest.mark.integration
def test_generated_directories_are_excluded_but_packaged_assets_are_complete(tmp_path):
    pytest.importorskip("build")
    pytest.importorskip("setuptools", minversion="77.0")
    repository = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copyfile(repository / name, source / name)
    shutil.copytree(
        repository / "multisubs",
        source / "multisubs",
        ignore=shutil.ignore_patterns("data", "__pycache__"),
    )
    for name in (
        "data/benchmarks/generated.mp4",
        "multisubs/data/private.srt",
        "multisubs/assets/unlisted.mp4",
    ):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic media must stay outside distributions")
    # Build from this isolated tree, whose dist directory does not exist yet.
    destination = source / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(destination)],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    expected = {
        path.relative_to(repository).as_posix(): path.read_bytes()
        for path in (repository / "multisubs/assets").rglob("*")
        if path.is_file()
        and (path.suffix in {".json", ".ttf", ".otf"} or path.name == "OFL.txt")
    }
    with zipfile.ZipFile(next(destination.glob("*.whl"))) as archive:
        names = archive.namelist()
        assert "multisubs/asr/__init__.py" in names
        assert not any(name.endswith((".mp4", ".srt", ".ass")) for name in names)
        assert not any(name.startswith(("data/", "multisubs/data/")) for name in names)
        for name, content in expected.items():
            assert archive.read(name) == content
    with tarfile.open(next(destination.glob("*.tar.gz"))) as archive:
        prefix = archive.getnames()[0].split("/")[0]
        names = [name.removeprefix(prefix + "/") for name in archive.getnames()]
        assert not any(name.endswith((".mp4", ".srt", ".ass")) for name in names)
        assert not any(name.startswith(("data/", "multisubs/data/")) for name in names)
        for name, content in expected.items():
            stream = archive.extractfile(f"{prefix}/{name}")
            assert stream is not None
            assert stream.read() == content
