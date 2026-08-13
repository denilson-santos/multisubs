"""Small typed value objects shared by the pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptionPaths:
    """The three subtitle artifacts generated for one source video."""

    json_path: Path
    srt_path: Path
    ass_path: Path

    def as_tuple(self) -> tuple[str, str, str]:
        return (str(self.json_path), str(self.srt_path), str(self.ass_path))


@dataclass(frozen=True)
class RunArtifacts:
    """Artifacts stored in a private work directory before publication."""

    work_dir: Path
    transcripts: TranscriptionPaths
    video_path: Path


@dataclass(frozen=True)
class RunRequest:
    """Validated CLI request passed through the orchestration layer."""

    input_path: Path
    output_dir: Path
    language: str
    task: str
    model_name: str
    style_options: Mapping[str, str | int]
    keep_transcriptions: bool
