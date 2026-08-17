"""Small typed value objects shared by the pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RelativeLength:
    """One validated layout length before video geometry is known."""

    value: Decimal
    unit: str
    original: str


@dataclass(frozen=True)
class SubtitleAppearance:
    """Validated ASS appearance values hidden behind the typed pipeline."""

    font: str
    font_size: int | RelativeLength
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
    outline_weight: int | RelativeLength
    shadow_weight: int | RelativeLength


class SubtitlePosition(str, Enum):
    """Human-readable screen anchors mapped to private ASS alignments."""

    TOP_LEFT = "top-left"
    TOP_CENTER = "top-center"
    TOP_RIGHT = "top-right"
    MIDDLE_LEFT = "middle-left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT = "bottom-right"


@dataclass(frozen=True)
class SubtitleLayout:
    """Validated semantic layout values before relative-unit resolution."""

    position: SubtitlePosition
    margin_left: int | RelativeLength
    margin_right: int | RelativeLength
    margin_top: int | RelativeLength
    margin_bottom: int | RelativeLength


@dataclass(frozen=True)
class SubtitleConfig:
    """Typed subtitle configuration passed through the orchestration layer."""

    appearance: SubtitleAppearance
    layout: SubtitleLayout


@dataclass(frozen=True)
class VideoGeometry:
    """Validated source and render geometry for one selected video stream."""

    stream_index: int
    coded_width: int
    coded_height: int
    render_width: int
    render_height: int
    rotation_degrees: int
    sample_aspect_ratio: Fraction
    display_aspect_ratio: Fraction
    duration_seconds: float | None

    @property
    def original_size(self) -> str:
        """Return the libass/FFmpeg canvas size for the autorotated frame."""
        return f"{self.render_width}x{self.render_height}"


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
