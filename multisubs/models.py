"""Small typed value objects shared by the pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
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
class SubtitleOpacity:
    """One validated global subtitle opacity percentage."""

    percentage: Decimal
    original: str

    @property
    def normalized(self) -> Decimal:
        """Return the equivalent zero-to-one multiplier."""
        return self.percentage / Decimal(100)


class SubtitleBackdrop(str, Enum):
    """Supported semantic background treatments for subtitle text."""

    NONE = "none"
    OUTLINE = "outline"
    BOX = "box"


class FontWeight(Enum):
    """Canonical semantic font weights and their OpenType numeric ranks."""

    THIN = ("thin", 100)
    EXTRA_LIGHT = ("extra-light", 200)
    LIGHT = ("light", 300)
    REGULAR = ("regular", 400)
    MEDIUM = ("medium", 500)
    SEMI_BOLD = ("semi-bold", 600)
    BOLD = ("bold", 700)
    EXTRA_BOLD = ("extra-bold", 800)
    BLACK = ("black", 900)

    def __init__(self, canonical_name: str, rank: int) -> None:
        self.canonical_name = canonical_name
        self.rank = rank


class FontWeightInputForm(str, Enum):
    """How one public font-weight request reached typed configuration."""

    DEFAULT = "default"
    NAME = "name"
    ALIAS = "alias"
    NUMERIC = "numeric"
    BOLD_SHORTHAND = "bold-shorthand"


class TextCase(str, Enum):
    """Supported locale-independent subtitle display casing modes."""

    ORIGINAL = "original"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"


class KaraokeMode(str, Enum):
    """Supported word-highlight timing policies."""

    PROGRESSIVE = "progressive"
    ACTIVE_WORD = "active-word"


@dataclass(frozen=True)
class SubtitleAppearance:
    """Validated semantic appearance values passed through the pipeline."""

    font: str
    font_size: int | RelativeLength
    letter_spacing: int | RelativeLength
    text_color: str
    font_weight: FontWeight
    italic: bool
    backdrop: SubtitleBackdrop
    backdrop_color: str
    backdrop_size: int | RelativeLength
    shadow_size: int | RelativeLength
    fonts_dir: Path | None = None
    font_weight_input: str = "regular"
    font_weight_input_form: FontWeightInputForm = FontWeightInputForm.DEFAULT
    # ``line_height`` is the resolved baseline advance after geometry/font
    # resolution, or the requested ``auto``/relative value on a request.
    # Keeping the original token lets serializers distinguish the explicit
    # per-line ASS strategy from the backwards-compatible automatic path.
    line_height: float | int | RelativeLength | str = "auto"
    line_height_requested: float | int | RelativeLength | str | None = None
    opacity: SubtitleOpacity = field(
        default_factory=lambda: SubtitleOpacity(Decimal(100), "100%")
    )
    text_case: TextCase = TextCase.ORIGINAL


@dataclass(frozen=True)
class SubtitleEffects:
    """Validated optional subtitle effects passed through the pipeline."""

    karaoke_mode: KaraokeMode | None = None
    highlight_color: str | None = None

    @property
    def enabled(self) -> bool:
        """Return whether the word-timed karaoke effect is enabled."""
        return self.karaoke_mode is not None

    @property
    def karaoke(self) -> bool:
        """Return whether karaoke is enabled."""
        return self.enabled

    @property
    def mode(self) -> KaraokeMode | None:
        """Return the resolved karaoke mode."""
        return self.karaoke_mode

    @property
    def karaoke_highlight_color(self) -> str | None:
        """Return the highlight color using the public option terminology."""
        return self.highlight_color


@dataclass(frozen=True)
class SubtitleDisplayFragment:
    """One exact display fragment, optionally backed by an aligned word."""

    text: str
    word_index: int | None = None


@dataclass(frozen=True)
class SubtitleVisualLine:
    """One measured visual line retained for explicit line-height rendering."""

    text: str
    fragments: tuple[SubtitleDisplayFragment, ...]
    width: float
    index: int


@dataclass(frozen=True)
class KaraokeCue:
    """Validated fragments plus progressive and active-word timing data."""

    fragments: tuple[SubtitleDisplayFragment, ...]
    durations: tuple[int, ...]
    active_intervals: tuple[tuple[int, int], ...]


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
    effects: SubtitleEffects = field(default_factory=SubtitleEffects)


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
class AssDrawingEvent:
    """Generated ASS event used for non-production preview diagnostics."""

    start: float
    end: float
    text: str


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


@dataclass(frozen=True)
class PreviewRequest:
    """Validated request for a transcription-free subtitle layout preview."""

    input_path: Path
    output_dir: Path
    subtitle_config: SubtitleConfig
    preview_at: float | None
    preview_text: str
    guides: bool
