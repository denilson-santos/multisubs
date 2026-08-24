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


class SubtitleBackdrop(str, Enum):
    """Supported semantic background treatments for subtitle text."""

    NONE = "none"
    OUTLINE = "outline"
    BOX = "box"


@dataclass(frozen=True)
class SubtitleAppearance:
    """Validated semantic appearance values passed through the pipeline."""

    font: str
    font_size: int | RelativeLength
    text_color: str
    bold: bool
    italic: bool
    backdrop: SubtitleBackdrop
    backdrop_color: str
    backdrop_size: int | RelativeLength
    shadow_size: int | RelativeLength
    fonts_dir: Path | None = None


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


class SubtitleLayoutPreset(str, Enum):
    """Named layout families resolved against the autorotated video canvas."""

    AUTO = "auto"
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"
    VERTICAL_SOCIAL = "vertical-social"
    UPPER_THIRD = "upper-third"
    CENTERED = "centered"


class SubtitlePlacementMode(str, Enum):
    """How subtitle placement is represented in the generated ASS file."""

    NATIVE_STYLE = "native-style"
    EXPLICIT = "explicit"


@dataclass(frozen=True)
class SubtitleLayout:
    """Semantic layout values before or after geometry resolution."""

    position: SubtitlePosition
    margin_left: int | RelativeLength
    margin_right: int | RelativeLength
    margin_top: int | RelativeLength
    margin_bottom: int | RelativeLength
    placement_mode: SubtitlePlacementMode = SubtitlePlacementMode.NATIVE_STYLE
    position_x: int | RelativeLength | None = None
    position_y: int | RelativeLength | None = None
    anchor: SubtitlePosition | None = None
    max_width: int | RelativeLength | None = None
    max_height: int | RelativeLength | None = None

    @property
    def has_custom_coordinates(self) -> bool:
        """Return whether this layout uses a per-event X/Y placement."""
        return self.placement_mode is SubtitlePlacementMode.EXPLICIT


@dataclass(frozen=True)
class CuePlacement:
    """One resolved ASS anchor and position for a visual subtitle cue."""

    anchor: SubtitlePosition
    position_x: int
    position_y: int

    @property
    def x(self) -> int:
        """Return the resolved horizontal PlayRes coordinate."""
        return self.position_x

    @property
    def y(self) -> int:
        """Return the resolved vertical PlayRes coordinate."""
        return self.position_y


@dataclass(frozen=True)
class LayoutPreset:
    """Immutable source definition for one concrete subtitle layout preset."""

    name: SubtitleLayoutPreset
    description: str
    layout: SubtitleLayout


@dataclass(frozen=True)
class SubtitleConfig:
    """Typed subtitle configuration passed through the orchestration layer."""

    appearance: SubtitleAppearance
    layout: SubtitleLayout
    layout_preset: SubtitleLayoutPreset = SubtitleLayoutPreset.AUTO
    layout_overrides: frozenset[str] = frozenset()


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
