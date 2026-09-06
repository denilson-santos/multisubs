"""Cue- and word-relative subtitle animation timing and state calculation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .errors import ArtifactError
from .models import (
    CueAnimationType,
    SubtitleAnimationPhase,
    SubtitleElementAnimation,
    SubtitleWordElementAnimation,
)

_SLIDE_DISTANCE_PERCENT = Decimal(75)
_WORD_SLIDE_DISTANCE_PERCENT = Decimal(35)
_POP_START_SCALE = Decimal(76)
_POP_PEAK_SCALE = Decimal(112)
_POP_PEAK_AT_MS = 130
_WORD_POP_PEAK_AT_MS = 90
_ZOOM_START_SCALE = Decimal(88)
_ZOOM_EXIT_SCALE = Decimal(88)
_CUE_PULSE_SCALE = Decimal(106)
_WORD_PULSE_SCALE = Decimal(108)
_BOUNCE_DISTANCE_PERCENT = Decimal(20)
_FLOAT_DISTANCE_PERCENT = Decimal(12)
_SHAKE_DISTANCE_PERCENT = Decimal(12)
_FLASH_ALPHA = 89
_BREATHE_ALPHA = 64
_MAX_EMPHASIS_BOUNDARIES = 64


@dataclass(frozen=True)
class CueAnimationTiming:
    """Normalized cue-global phase boundaries in ASS centiseconds."""

    cue_start: int
    cue_end: int
    entrance_end: int
    emphasis_end: int
    exit_start: int
    entrance_duration: int
    emphasis_duration: int
    exit_duration: int
    shortened: bool


@dataclass(frozen=True)
class CueAnimationState:
    """Animation state sampled on the logical cue timeline."""

    fade_alpha: int = 0
    offset_x: int = 0
    offset_y: int = 0
    scale_percent: int = 100


@dataclass(frozen=True)
class WordAnimationTiming:
    """Normalized phase boundaries for one aligned word interval."""

    word_start: int
    word_end: int
    entrance_end: int
    emphasis_end: int
    exit_start: int
    entrance_duration: int
    emphasis_duration: int
    exit_duration: int
    shortened: bool


def normalize_cue_animation(
    cue_start: int,
    cue_end: int,
    animation: SubtitleElementAnimation,
) -> CueAnimationTiming:
    """Fit configured cue phases inside one quantized cue deterministically."""
    if (
        isinstance(cue_start, bool)
        or not isinstance(cue_start, int)
        or isinstance(cue_end, bool)
        or not isinstance(cue_end, int)
        or cue_start < 0
        or cue_end < cue_start
    ):
        raise ArtifactError("Cue animation requires valid centisecond timestamps")
    entrance_requested = _milliseconds_to_centiseconds(animation.entrance.duration_ms)
    exit_requested = _milliseconds_to_centiseconds(animation.exit.duration_ms)
    emphasis_requested = _milliseconds_to_centiseconds(animation.emphasis.duration_ms)
    cue_duration = cue_end - cue_start
    entrance_duration = entrance_requested
    exit_duration = exit_requested
    if entrance_duration + exit_duration > cue_duration:
        total = entrance_duration + exit_duration
        if total == 0:
            entrance_duration = 0
            exit_duration = 0
        else:
            entrance_duration = _round_decimal(
                Decimal(cue_duration) * Decimal(entrance_duration) / Decimal(total)
            )
            entrance_duration = min(cue_duration, max(0, entrance_duration))
            exit_duration = cue_duration - entrance_duration
    stable_duration = max(0, cue_duration - entrance_duration - exit_duration)
    emphasis_duration = stable_duration if emphasis_requested else 0
    emphasis_shortened = emphasis_requested > stable_duration > 0
    return CueAnimationTiming(
        cue_start=cue_start,
        cue_end=cue_end,
        entrance_end=cue_start + entrance_duration,
        emphasis_end=cue_start + entrance_duration + emphasis_duration,
        exit_start=cue_end - exit_duration,
        entrance_duration=entrance_duration,
        emphasis_duration=emphasis_duration,
        exit_duration=exit_duration,
        shortened=(
            entrance_duration != entrance_requested
            or emphasis_shortened
            or exit_duration != exit_requested
        ),
    )


def animation_boundaries(
    timing: CueAnimationTiming,
    animation: SubtitleElementAnimation,
) -> tuple[int, ...]:
    """Return interior boundaries needed for continuous piecewise ASS events."""
    boundaries = {timing.entrance_end, timing.emphasis_end, timing.exit_start}
    if animation.entrance.type is CueAnimationType.POP and timing.entrance_duration > 0:
        requested = max(1, animation.entrance.duration_ms)
        peak_offset = _round_decimal(
            Decimal(timing.entrance_duration)
            * Decimal(_POP_PEAK_AT_MS)
            / Decimal(requested)
        )
        boundaries.add(
            timing.cue_start + min(timing.entrance_duration, max(0, peak_offset))
        )
    boundaries.update(_emphasis_boundaries(timing, animation.emphasis))
    return tuple(
        sorted(
            boundary
            for boundary in boundaries
            if timing.cue_start < boundary < timing.cue_end
        )
    )


def sample_cue_animation(
    animation: SubtitleElementAnimation,
    timing: CueAnimationTiming,
    at_centiseconds: int,
    *,
    font_size: int,
) -> CueAnimationState:
    """Sample one deterministic state without restarting at derived events."""
    if at_centiseconds < timing.cue_start or at_centiseconds > timing.cue_end:
        raise ArtifactError("Cue animation sample must be inside the logical cue")
    if isinstance(font_size, bool) or not isinstance(font_size, int) or font_size <= 0:
        raise ArtifactError("Cue animation requires a resolved positive font size")
    if timing.entrance_duration > 0 and at_centiseconds < timing.entrance_end:
        progress = _progress(
            at_centiseconds - timing.cue_start,
            timing.entrance_duration,
        )
        return _sample_entrance(animation.entrance, progress, font_size)
    if timing.exit_duration > 0 and at_centiseconds > timing.exit_start:
        progress = _progress(
            at_centiseconds - timing.exit_start,
            timing.exit_duration,
        )
        return _sample_exit(animation.exit.type, progress, font_size)
    if timing.emphasis_duration > 0 and at_centiseconds < timing.emphasis_end:
        progress = _repeating_progress(
            at_centiseconds,
            timing.entrance_end,
            timing.emphasis_end,
            _milliseconds_to_centiseconds(animation.emphasis.duration_ms),
        )
        return _sample_emphasis(animation.emphasis.type, progress, font_size)
    return CueAnimationState()


def normalize_word_animation(
    word_start: int,
    word_end: int,
    animation: SubtitleWordElementAnimation,
) -> WordAnimationTiming:
    """Fit one word's transform phases inside its aligned interval."""
    if (
        isinstance(word_start, bool)
        or not isinstance(word_start, int)
        or isinstance(word_end, bool)
        or not isinstance(word_end, int)
        or word_start < 0
        or word_end < word_start
    ):
        raise ArtifactError("Word animation requires valid centisecond timestamps")
    entrance_requested = _milliseconds_to_centiseconds(animation.entrance.duration_ms)
    exit_requested = _milliseconds_to_centiseconds(animation.exit.duration_ms)
    emphasis_requested = _milliseconds_to_centiseconds(animation.emphasis.duration_ms)
    duration = word_end - word_start
    entrance_duration = entrance_requested
    exit_duration = exit_requested
    if entrance_duration + exit_duration > duration:
        total = entrance_duration + exit_duration
        entrance_duration = (
            _round_decimal(
                Decimal(duration) * Decimal(entrance_duration) / Decimal(total)
            )
            if total
            else 0
        )
        entrance_duration = min(duration, max(0, entrance_duration))
        exit_duration = duration - entrance_duration
    stable_duration = max(0, duration - entrance_duration - exit_duration)
    emphasis_duration = stable_duration if emphasis_requested else 0
    emphasis_shortened = emphasis_requested > stable_duration > 0
    return WordAnimationTiming(
        word_start=word_start,
        word_end=word_end,
        entrance_end=word_start + entrance_duration,
        emphasis_end=word_start + entrance_duration + emphasis_duration,
        exit_start=word_end - exit_duration,
        entrance_duration=entrance_duration,
        emphasis_duration=emphasis_duration,
        exit_duration=exit_duration,
        shortened=(
            entrance_duration != entrance_requested
            or emphasis_shortened
            or exit_duration != exit_requested
        ),
    )


def word_animation_boundaries(
    timing: WordAnimationTiming,
    animation: SubtitleWordElementAnimation,
) -> tuple[int, ...]:
    """Return the fixed interior boundaries for one word animation."""
    boundaries = {
        timing.entrance_end,
        timing.emphasis_end,
        timing.exit_start,
    }
    if animation.entrance.type is CueAnimationType.POP and timing.entrance_duration > 0:
        requested = max(1, animation.entrance.duration_ms)
        boundaries.add(
            timing.word_start
            + min(
                timing.entrance_duration,
                _round_decimal(
                    Decimal(timing.entrance_duration)
                    * Decimal(_WORD_POP_PEAK_AT_MS)
                    / Decimal(requested)
                ),
            )
        )
    boundaries.update(_emphasis_boundaries(timing, animation.emphasis))
    return tuple(
        sorted(
            boundary
            for boundary in boundaries
            if timing.word_start < boundary < timing.word_end
        )
    )


def sample_word_animation(
    animation: SubtitleWordElementAnimation,
    timing: WordAnimationTiming,
    at_centiseconds: int,
    *,
    font_size: int,
) -> CueAnimationState:
    """Sample word-local motion without changing its aligned interval."""
    if at_centiseconds < timing.word_start or at_centiseconds > timing.word_end:
        return CueAnimationState()
    if isinstance(font_size, bool) or not isinstance(font_size, int) or font_size <= 0:
        raise ArtifactError("Word animation requires a resolved positive font size")
    if timing.entrance_duration > 0 and at_centiseconds < timing.entrance_end:
        progress = _progress(
            at_centiseconds - timing.word_start,
            timing.entrance_duration,
        )
        return _sample_word_entrance(animation.entrance, progress, font_size)
    if timing.exit_duration > 0 and at_centiseconds > timing.exit_start:
        progress = _progress(
            at_centiseconds - timing.exit_start,
            timing.exit_duration,
        )
        return _sample_word_exit(animation.exit.type, progress, font_size)
    if timing.emphasis_duration > 0 and at_centiseconds < timing.emphasis_end:
        progress = _repeating_progress(
            at_centiseconds,
            timing.entrance_end,
            timing.emphasis_end,
            _milliseconds_to_centiseconds(animation.emphasis.duration_ms),
        )
        if animation.emphasis.type is CueAnimationType.PULSE:
            return CueAnimationState(
                scale_percent=_triangle_value(100, int(_WORD_PULSE_SCALE), progress)
            )
        if animation.emphasis.type is CueAnimationType.BOUNCE:
            distance = _round_decimal(
                Decimal(font_size) * _BOUNCE_DISTANCE_PERCENT / Decimal(100)
            )
            return CueAnimationState(offset_y=-_triangle_value(0, distance, progress))
        return _sample_emphasis(animation.emphasis.type, progress, font_size)
    return CueAnimationState()


def _sample_word_entrance(
    phase: SubtitleAnimationPhase,
    progress: Decimal,
    font_size: int,
) -> CueAnimationState:
    if phase.type is CueAnimationType.FADE:
        return CueAnimationState(fade_alpha=_interpolate(255, 0, progress))
    if phase.type in {CueAnimationType.SLIDE_UP, CueAnimationType.SLIDE_DOWN}:
        distance = _round_decimal(
            Decimal(font_size) * _WORD_SLIDE_DISTANCE_PERCENT / Decimal(100)
        )
        y = distance if phase.type is CueAnimationType.SLIDE_UP else -distance
        return CueAnimationState(
            offset_y=_round_decimal(Decimal(y) * (Decimal(1) - progress))
        )
    if phase.type is CueAnimationType.POP:
        peak_ratio = min(
            Decimal(1), Decimal(_WORD_POP_PEAK_AT_MS) / Decimal(phase.duration_ms)
        )
        if progress <= peak_ratio:
            scale = _interpolate_decimal(
                _POP_START_SCALE, _POP_PEAK_SCALE, progress / peak_ratio
            )
        else:
            scale = _interpolate_decimal(
                _POP_PEAK_SCALE,
                Decimal(100),
                (progress - peak_ratio) / (Decimal(1) - peak_ratio),
            )
        return CueAnimationState(scale_percent=_round_decimal(scale))
    if phase.type is CueAnimationType.ZOOM:
        return CueAnimationState(scale_percent=_interpolate(88, 100, progress))
    return CueAnimationState()


def _sample_word_exit(
    animation_type: CueAnimationType,
    progress: Decimal,
    font_size: int,
) -> CueAnimationState:
    if animation_type is CueAnimationType.FADE:
        return CueAnimationState(fade_alpha=_interpolate(0, 255, progress))
    if animation_type in {CueAnimationType.SLIDE_UP, CueAnimationType.SLIDE_DOWN}:
        distance = _round_decimal(
            Decimal(font_size) * _WORD_SLIDE_DISTANCE_PERCENT / Decimal(100)
        )
        y = -distance if animation_type is CueAnimationType.SLIDE_UP else distance
        return CueAnimationState(offset_y=_round_decimal(Decimal(y) * progress))
    if animation_type is CueAnimationType.ZOOM:
        return CueAnimationState(
            fade_alpha=_interpolate(0, 255, progress),
            scale_percent=_interpolate(100, 88, progress),
        )
    return CueAnimationState()


def _sample_emphasis(
    animation_type: CueAnimationType,
    progress: Decimal,
    font_size: int,
) -> CueAnimationState:
    if animation_type is CueAnimationType.PULSE:
        return CueAnimationState(
            scale_percent=_triangle_value(100, int(_CUE_PULSE_SCALE), progress)
        )
    if animation_type in {CueAnimationType.BOUNCE, CueAnimationType.FLOAT}:
        percent = (
            _BOUNCE_DISTANCE_PERCENT
            if animation_type is CueAnimationType.BOUNCE
            else _FLOAT_DISTANCE_PERCENT
        )
        distance = _round_decimal(Decimal(font_size) * percent / Decimal(100))
        return CueAnimationState(offset_y=-_triangle_value(0, distance, progress))
    if animation_type is CueAnimationType.SHAKE:
        distance = _round_decimal(
            Decimal(font_size) * _SHAKE_DISTANCE_PERCENT / Decimal(100)
        )
        return CueAnimationState(offset_x=_shake_offset(distance, progress))
    if animation_type is CueAnimationType.FLASH:
        return CueAnimationState(fade_alpha=_triangle_value(0, _FLASH_ALPHA, progress))
    if animation_type is CueAnimationType.BREATHE:
        return CueAnimationState(
            fade_alpha=_triangle_value(0, _BREATHE_ALPHA, progress),
            scale_percent=_triangle_value(100, 103, progress),
        )
    return CueAnimationState()


def _emphasis_boundaries(
    timing: CueAnimationTiming | WordAnimationTiming,
    phase: SubtitleAnimationPhase,
) -> set[int]:
    if timing.emphasis_duration <= 0 or phase.duration_ms <= 0:
        return set()
    cycle = max(1, _milliseconds_to_centiseconds(phase.duration_ms))
    fractions = (
        (Decimal("0.2"), Decimal("0.4"), Decimal("0.6"), Decimal("0.8"))
        if phase.type is CueAnimationType.SHAKE
        else (Decimal("0.5"),)
    )
    start = timing.entrance_end
    end = timing.emphasis_end
    segments: list[tuple[int, int]] = []
    cursor = start
    while cursor < end and len(segments) < _MAX_EMPHASIS_BOUNDARIES:
        segment_end = min(end, cursor + cycle)
        segments.append((cursor, segment_end))
        cursor = segment_end
    boundaries: set[int] = set()
    for segment_start, segment_end in segments:
        length = segment_end - segment_start
        for fraction in fractions:
            if len(boundaries) >= _MAX_EMPHASIS_BOUNDARIES:
                return boundaries
            boundaries.add(segment_start + _round_decimal(Decimal(length) * fraction))
        if len(boundaries) >= _MAX_EMPHASIS_BOUNDARIES:
            return boundaries
        boundaries.add(segment_end)
    return boundaries


def _repeating_progress(at: int, start: int, end: int, cycle: int) -> Decimal:
    """Return cycle progress, compressing the last partial cycle to settle cleanly."""
    if cycle <= 0 or end <= start:
        return Decimal(1)
    total = end - start
    full_cycles, remainder = divmod(total, cycle)
    final_start = start + full_cycles * cycle
    if remainder and at >= final_start:
        return _progress(at - final_start, remainder)
    return _progress((at - start) % cycle, cycle)


def _sample_entrance(
    phase: SubtitleAnimationPhase,
    progress: Decimal,
    font_size: int,
) -> CueAnimationState:
    animation_type = phase.type
    if animation_type is CueAnimationType.FADE:
        return CueAnimationState(fade_alpha=_interpolate(255, 0, progress))
    if animation_type in _SLIDE_TYPES:
        distance = _slide_distance(font_size)
        remaining = Decimal(1) - progress
        x, y = _slide_offset(animation_type, distance, entrance=True)
        return CueAnimationState(
            offset_x=_round_decimal(Decimal(x) * remaining),
            offset_y=_round_decimal(Decimal(y) * remaining),
        )
    if animation_type is CueAnimationType.POP:
        peak_ratio = min(
            Decimal(1),
            Decimal(_POP_PEAK_AT_MS) / Decimal(phase.duration_ms),
        )
        if progress <= peak_ratio:
            local = progress / peak_ratio
            scale = _interpolate_decimal(_POP_START_SCALE, _POP_PEAK_SCALE, local)
        else:
            local = (progress - peak_ratio) / (Decimal(1) - peak_ratio)
            scale = _interpolate_decimal(_POP_PEAK_SCALE, Decimal(100), local)
        return CueAnimationState(scale_percent=_round_decimal(scale))
    if animation_type is CueAnimationType.ZOOM:
        return CueAnimationState(scale_percent=_interpolate(88, 100, progress))
    return CueAnimationState()


def _sample_exit(
    animation_type: CueAnimationType,
    progress: Decimal,
    font_size: int,
) -> CueAnimationState:
    if animation_type is CueAnimationType.FADE:
        return CueAnimationState(fade_alpha=_interpolate(0, 255, progress))
    if animation_type in _SLIDE_TYPES:
        distance = _slide_distance(font_size)
        x, y = _slide_offset(animation_type, distance, entrance=False)
        return CueAnimationState(
            offset_x=_round_decimal(Decimal(x) * progress),
            offset_y=_round_decimal(Decimal(y) * progress),
        )
    if animation_type is CueAnimationType.ZOOM:
        return CueAnimationState(
            fade_alpha=_interpolate(0, 255, progress),
            scale_percent=_interpolate(100, 88, progress),
        )
    return CueAnimationState()


_SLIDE_TYPES = frozenset(
    {
        CueAnimationType.SLIDE_UP,
        CueAnimationType.SLIDE_DOWN,
        CueAnimationType.SLIDE_LEFT,
        CueAnimationType.SLIDE_RIGHT,
    }
)


def _slide_distance(font_size: int) -> int:
    return _round_decimal(Decimal(font_size) * _SLIDE_DISTANCE_PERCENT / Decimal(100))


def _slide_offset(
    animation_type: CueAnimationType,
    distance: int,
    *,
    entrance: bool,
) -> tuple[int, int]:
    direction = -1 if not entrance else 1
    if animation_type is CueAnimationType.SLIDE_UP:
        return 0, direction * distance
    if animation_type is CueAnimationType.SLIDE_DOWN:
        return 0, -direction * distance
    if animation_type is CueAnimationType.SLIDE_LEFT:
        return direction * distance, 0
    if animation_type is CueAnimationType.SLIDE_RIGHT:
        return -direction * distance, 0
    return 0, 0


def _milliseconds_to_centiseconds(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArtifactError("Animation duration must be a non-negative integer")
    return _round_decimal(Decimal(value) / Decimal(10))


def _progress(elapsed: int, duration: int) -> Decimal:
    if duration <= 0:
        return Decimal(1)
    return min(Decimal(1), max(Decimal(0), Decimal(elapsed) / Decimal(duration)))


def _interpolate(start: int, end: int, progress: Decimal) -> int:
    return _round_decimal(_interpolate_decimal(Decimal(start), Decimal(end), progress))


def _triangle_value(start: int, peak: int, progress: Decimal) -> int:
    if progress <= Decimal("0.5"):
        return _interpolate(start, peak, progress * 2)
    return _interpolate(peak, start, (progress - Decimal("0.5")) * 2)


def _shake_offset(distance: int, progress: Decimal) -> int:
    points = (
        (Decimal(0), 0),
        (Decimal("0.2"), distance),
        (Decimal("0.4"), -distance),
        (Decimal("0.6"), distance),
        (Decimal("0.8"), -distance),
        (Decimal(1), 0),
    )
    for (start_at, start), (end_at, end) in zip(points[:-1], points[1:], strict=True):
        if progress <= end_at:
            local = (progress - start_at) / (end_at - start_at)
            return _interpolate(start, end, local)
    return 0


def _interpolate_decimal(
    start: Decimal,
    end: Decimal,
    progress: Decimal,
) -> Decimal:
    return start + (end - start) * progress


def _round_decimal(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
