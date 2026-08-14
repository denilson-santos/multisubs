"""Small typed value objects shared by the pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubtitleAppearance:
    """Validated ASS appearance values hidden behind the typed pipeline."""

    font: str
    font_size: int
    primary_color: str
    secondary_color: str
    outline_color: str
    back_color: str
    bold: int
    italic: int
    underline: int
    strikeout: int
    scale_x: int
    scale_y: int
    spacing: int
    angle: int
    border_style: int
    outline_weight: int
    shadow_weight: int


@dataclass(frozen=True)
class SubtitleLayout:
    """Validated global ASS layout values used before geometry-aware layout."""

    alignment: int
    margin_l: int
    margin_r: int
    margin_v: int


@dataclass(frozen=True)
class SubtitleConfig:
    """Typed subtitle configuration passed through the orchestration layer."""

    appearance: SubtitleAppearance
    layout: SubtitleLayout


@dataclass(frozen=True)
class TranscriptDocument:
    """Semantic transcription result before artifact serialization."""

    source_path: Path
    language: str
    task: str
    model_name: str
    full_text: str
    segments: tuple[Mapping[str, Any], ...]


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
    subtitle_config: SubtitleConfig
    keep_transcriptions: bool
