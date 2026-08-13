from pathlib import Path

import pytest

from multisubs.errors import ArtifactError
from multisubs.utils import (
    atomic_write_text,
    create_unique_dir,
    find_unique_stem,
    get_unique_path,
    publish_files,
)


def test_unique_path_and_stem_consider_all_related_artifacts(tmp_path: Path):
    (tmp_path / "video-pt.json").write_text("existing", encoding="utf-8")

    assert get_unique_path(tmp_path / "video-pt.json").endswith("video-pt (1).json")
    assert (
        find_unique_stem(tmp_path, "video-pt", (".json", ".srt", ".ass"))
        == "video-pt (1)"
    )


def test_unique_names_treat_dangling_symlinks_as_occupied(tmp_path: Path):
    dangling_target = tmp_path / "missing.json"
    dangling_path = tmp_path / "video-pt.json"
    dangling_path.symlink_to(dangling_target)

    assert get_unique_path(dangling_path).endswith("video-pt (1).json")
    assert (
        find_unique_stem(tmp_path, "video-pt", (".json", ".srt", ".ass"))
        == "video-pt (1)"
    )


def test_create_unique_dir_is_collision_safe(tmp_path: Path):
    first = create_unique_dir(tmp_path / "video")
    second = create_unique_dir(tmp_path / "video")

    assert first.name == "video"
    assert second.name == "video (1)"


def test_atomic_write_text_writes_utf8_and_leaves_no_temp_files(tmp_path: Path):
    destination = tmp_path / "nested" / "字幕.txt"

    atomic_write_text(destination, "Olá\n字幕\n")

    assert destination.read_text(encoding="utf-8") == "Olá\n字幕\n"
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []


def test_publish_files_does_not_overwrite_or_leave_partial_outputs(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    second_source = tmp_path / "second-source.txt"
    second_source.write_text("second", encoding="utf-8")
    existing = tmp_path / "existing.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        publish_files({source: tmp_path / "published.txt", second_source: existing})

    assert not (tmp_path / "published.txt").exists()
    assert existing.read_text(encoding="utf-8") == "keep"


def test_publish_files_wraps_missing_source(tmp_path: Path):
    with pytest.raises(ArtifactError):
        publish_files({tmp_path / "missing": tmp_path / "output"})
