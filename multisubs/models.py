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


class WordAnimationMode(str, Enum):
    """Supported word-highlight timing policies."""

    PROGRESSIVE = "progressive"
    ACTIVE_WORD = "active-word"


class PreviewMode(str, Enum):
    """Supported transcription-free preview outputs."""

    LAYOUT = "layout"
    ANIMATION = "animation"


@dataclass(frozen=True)
class SubtitleTypography:
    """Validated semantic typography values passed through the pipeline."""

    font: str
    font_size: int | RelativeLength
    letter_spacing: int | RelativeLength
    color: str
    font_weight: FontWeight
    italic: bool
    fonts_dir: Path | None = None
    font_weight_input: str = "regular"
    font_weight_input_form: FontWeightInputForm = FontWeightInputForm.DEFAULT
    # ``line_height`` is the resolved baseline advance after geometry/font
    # resolution, or the requested ``auto``/relative value on a request.
    # Keeping the original token lets serializers distinguish the explicit
    # per-line ASS strategy from the backwards-compatible automatic path.
    line_height: float | int | RelativeLength | str = "auto"
    line_height_requested: float | int | RelativeLength | str | None = None
    text_case: TextCase = TextCase.ORIGINAL
    highlight_color: str | None = None


@dataclass(frozen=True)
class SubtitleBackdropStyle:
    """Validated semantic backdrop values passed through the pipeline."""

    kind: SubtitleBackdrop
    color: str
    size: int | RelativeLength


@dataclass(frozen=True)
class SubtitleWordBackdropStyle:
    """Validated appearance for one timed aligned-word backdrop."""

    kind: SubtitleBackdrop
    color: str
    size: int | RelativeLength


@dataclass(frozen=True)
class SubtitleShadow:
    """Validated semantic shadow values passed through the pipeline."""

    size: int | RelativeLength


@dataclass(frozen=True)
class SubtitleStyle:
    """Validated semantic subtitle style passed through the pipeline."""

    typography: SubtitleTypography
    backdrop: SubtitleBackdropStyle
    word_backdrop: SubtitleWordBackdropStyle
    shadow: SubtitleShadow
    opacity: SubtitleOpacity = field(
        default_factory=lambda: SubtitleOpacity(Decimal(100), "100%")
    )


class CueAnimationType(str, Enum):
    """Supported cue animation phase types."""

    NONE = "none"
    FADE = "fade"
    SLIDE_UP = "slide-up"
    SLIDE_DOWN = "slide-down"
    SLIDE_LEFT = "slide-left"
    SLIDE_RIGHT = "slide-right"
    POP = "pop"
    ZOOM = "zoom"
    PULSE = "pulse"
    BOUNCE = "bounce"
    FLOAT = "float"
    SHAKE = "shake"
    FLASH = "flash"
    BREATHE = "breathe"
    HIGHLIGHT = "highlight"


@dataclass(frozen=True)
class SubtitleAnimationPhase:
    """One validated cue animation phase."""

    type: CueAnimationType = CueAnimationType.NONE
    duration_ms: int = 0


@dataclass(frozen=True)
class SubtitleElementAnimation:
    """Entrance, emphasis, and exit phases for one visual element."""

    entrance: SubtitleAnimationPhase = field(default_factory=SubtitleAnimationPhase)
    emphasis: SubtitleAnimationPhase = field(default_factory=SubtitleAnimationPhase)
    exit: SubtitleAnimationPhase = field(default_factory=SubtitleAnimationPhase)

    @property
    def enabled(self) -> bool:
        """Return whether this element has any non-neutral phase."""
        return any(
            phase.type is not CueAnimationType.NONE
            for phase in (self.entrance, self.emphasis, self.exit)
        )


@dataclass(frozen=True)
class SubtitleCueAnimation:
    """Independent text and backdrop tracks for one logical cue."""

    text: SubtitleElementAnimation = field(default_factory=SubtitleElementAnimation)
    backdrop: SubtitleElementAnimation = field(default_factory=SubtitleElementAnimation)


@dataclass(frozen=True)
class SubtitleWordElementAnimation(SubtitleElementAnimation):
    """One visual word element plus its aligned timing policy."""

    mode: WordAnimationMode = WordAnimationMode.ACTIVE_WORD


@dataclass(frozen=True)
class SubtitleWordAnimation:
    """Independent text and backdrop tracks for aligned words."""

    text: SubtitleWordElementAnimation = field(
        default_factory=lambda: SubtitleWordElementAnimation()
    )
    backdrop: SubtitleWordElementAnimation = field(
        default_factory=lambda: SubtitleWordElementAnimation()
    )

    @property
    def enabled(self) -> bool:
        """Return whether any aligned-word animation phase is enabled."""
        return self.text.enabled or self.backdrop.enabled

    @property
    def uses_timed_highlight(self) -> bool:
        """Return whether emphasis follows progressive or active-word timing."""
        return self.text.emphasis.type is CueAnimationType.HIGHLIGHT


@dataclass(frozen=True)
class SubtitleAnimation:
    """Validated cue and word animation configuration."""

    cue: SubtitleCueAnimation = field(default_factory=SubtitleCueAnimation)
    word: SubtitleWordAnimation = field(default_factory=SubtitleWordAnimation)


@dataclass(frozen=True)
class SubtitleDisplayFragment:
    """One exact display fragment, optionally backed by an effect unit."""

    text: str
    word_index: int | None = None


@dataclass(frozen=True)
class SubtitleSourceSpan:
    """One source range or one retained alignment record."""

    source_segment_index: int
    record_index: int | None
    start: int | None
    end: int | None
    text: str
    kind: str
    start_time: float | None = None
    end_time: float | None = None
    matched: bool = True
    granularity: str = "word"

    @property
    def timed(self) -> bool:
        """Return whether this span has a validated alignment interval."""
        return self.start_time is not None and self.end_time is not None

    @property
    def source_record_identity(self) -> tuple[int, int] | None:
        """Return the stable original segment/record identity when available."""
        if self.record_index is None:
            return None
        return (self.source_segment_index, self.record_index)

    @property
    def alignment_granularity(self) -> str:
        """Return the semantic granularity assigned to this source span."""
        return self.granularity


@dataclass(frozen=True)
class SubtitleSourceMap:
    """Lossless source-to-alignment mapping for one original ASR segment."""

    raw_text: str
    normalized_text: str
    spans: tuple[SubtitleSourceSpan, ...]
    raw_to_normalized: tuple[int | None, ...]
    normalized_to_raw: tuple[int, ...]
    source_provided: bool
    complete: bool
    timing_complete: bool
    fallback_reasons: tuple[str, ...]
    record_count: int
    mapped_record_indexes: tuple[int, ...]
    timed_record_indexes: tuple[int, ...]


@dataclass(frozen=True)
class SubtitleDisplayUnit:
    """One transformed alignment token plus its source separator provenance."""

    source_segment_index: int
    record_index: int
    source_start: int
    source_end: int
    source_prefix: str
    source_token: str
    source_suffix: str
    display_prefix: str
    display_token: str
    display_suffix: str
    can_break_before: bool

    @property
    def source_text(self) -> str:
        """Return the source text represented by this display unit."""
        return self.source_prefix + self.source_token + self.source_suffix

    @property
    def display_text(self) -> str:
        """Return the transformed text represented by this display unit."""
        return self.display_prefix + self.display_token + self.display_suffix


@dataclass(frozen=True)
class SubtitleDisplayGroup:
    """One linguistic display group derived from immutable source records."""

    identity: int
    source_segment_index: int
    record_indexes: tuple[int, ...]
    source_start: int
    source_end: int
    source_text: str
    start_time: float
    end_time: float
    boundary_class: str
    strategy: str
    backend_version: str
    alignment_granularity: str
    emergency_subdivision: bool = False


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
class SubtitleConfig:
    """Typed subtitle configuration passed through the orchestration layer."""

    style: SubtitleStyle
    layout: SubtitleLayout
    animation: SubtitleAnimation = field(default_factory=SubtitleAnimation)


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
    language: str | None
    task: str
    model_name: str
    subtitle_config: SubtitleConfig
    keep_transcriptions: bool
    subtitle_template_requested: str | None = None
    subtitle_template_resolved: str = "default"
    subtitle_template_source: str = "builtin"
    subtitle_template_base: str | None = None


@dataclass(frozen=True)
class PreviewRequest:
    """Validated request for a transcription-free subtitle preview."""

    input_path: Path
    output_dir: Path
    subtitle_config: SubtitleConfig
    preview_at: float | None
    preview_text: str
    guides: bool
    subtitle_template_requested: str | None = None
    subtitle_template_resolved: str = "default"
    preview_mode: PreviewMode = PreviewMode.LAYOUT
    preview_duration_ms: int = 4_000
    subtitle_template_source: str = "builtin"
    subtitle_template_base: str | None = None
