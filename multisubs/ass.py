"""ASS subtitle serialization isolated from transcription and rendering."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from numbers import Real
from pathlib import Path
from typing import Any

from .animation import (
    CueAnimationState,
    WordAnimationTiming,
    animation_boundaries,
    normalize_cue_animation,
    normalize_word_animation,
    sample_cue_animation,
    sample_word_animation,
    word_animation_boundaries,
)
from .config import validate_subtitle_config
from .errors import ArtifactError
from .layout import (
    PositionedVisualLine,
    WrappingMetrics,
    position_visual_lines,
    resolve_cue_placement,
    resolve_native_anchor_point,
    resolve_native_layout_region,
    resolve_subtitle_config,
    resolve_wrapping_metrics,
)
from .models import (
    AssDrawingEvent,
    CueAnimationType,
    CuePlacement,
    KaraokeCue,
    SubtitleBackdrop,
    SubtitleConfig,
    SubtitleDisplayFragment,
    SubtitleElementAnimation,
    SubtitleOpacity,
    SubtitlePlacementMode,
    SubtitlePosition,
    SubtitleWordElementAnimation,
    VideoGeometry,
    WordAnimationMode,
)
from .utils import atomic_write_text
from .wrapping import build_visual_lines

ASS_STYLE_FIELDS = (
    "font",
    "font_size",
    "primary_color",
    "secondary_color",
    "outline_color",
    "back_color",
    "bold",
    "italic",
    "underline",
    "strikeout",
    "scale_x",
    "scale_y",
    "spacing",
    "angle",
    "border_style",
    "outline_weight",
    "shadow_weight",
    "alignment",
    "margin_l",
    "margin_r",
    "margin_v",
)

_ASS_ALIGNMENT_BY_POSITION = {
    SubtitlePosition.BOTTOM_LEFT: 1,
    SubtitlePosition.BOTTOM_CENTER: 2,
    SubtitlePosition.BOTTOM_RIGHT: 3,
    SubtitlePosition.MIDDLE_LEFT: 4,
    SubtitlePosition.CENTER: 5,
    SubtitlePosition.MIDDLE_RIGHT: 6,
    SubtitlePosition.TOP_LEFT: 7,
    SubtitlePosition.TOP_CENTER: 8,
    SubtitlePosition.TOP_RIGHT: 9,
}


@dataclass(frozen=True)
class SubtitlePalette:
    """Conventional RGBA colors used by one compiled subtitle composition."""

    text_color: str
    backdrop_color: str
    word_backdrop_color: str
    highlight_color: str | None


@dataclass(frozen=True)
class _DialogueEvent:
    """One derived ASS event tied to its original logical cue timeline."""

    logical_start: int
    logical_end: int
    start: int
    end: int
    generated_override: str
    text: str
    placement: CuePlacement | None = None
    animation_origin: CuePlacement | None = None
    word_timing: WordAnimationTiming | None = None
    cue_animation: SubtitleElementAnimation = SubtitleElementAnimation()
    word_animation: SubtitleWordElementAnimation | None = None
    layer: int = 0
    style_name: str = "Default"


def write_ass(
    path: Path,
    segments: Sequence[Mapping[str, Any]],
    subtitle_config: SubtitleConfig | None,
    geometry: VideoGeometry,
    *,
    placements: Sequence[CuePlacement | None] | None = None,
    guide_events: Sequence[AssDrawingEvent] | None = None,
    preserve_line_breaks: bool = False,
    wrapping_metrics: WrappingMetrics | None = None,
    suppress_animation: bool = False,
) -> None:
    """Write safe ASS dialogue on the probed, autorotated video canvas.

    ``placements`` is an internal per-cue contract for explicit placement.
    Native style placement emits no event-level position override. When
    ``preserve_line_breaks`` is enabled, the generated dialogue keeps only the
    caller's intentional line breaks instead of being wrapped again by libass.
    """
    if geometry.render_width <= 0 or geometry.render_height <= 0:
        raise ArtifactError("ASS canvas dimensions must be positive")
    config = resolve_subtitle_config(
        validate_subtitle_config(subtitle_config),
        geometry,
        text_measurer=(
            wrapping_metrics.text_measurer if wrapping_metrics is not None else None
        ),
    )
    explicit_line_height = _uses_explicit_line_height(config)
    metrics = wrapping_metrics
    if explicit_line_height and metrics is None:
        metrics = resolve_wrapping_metrics(config, geometry)
    _, effective_palette = resolve_subtitle_palettes(config)
    animate_cues = not suppress_animation and _has_cue_animation(config)
    animate_words = not suppress_animation and _has_positioned_word_animation(config)
    style = _compile_style(config, geometry, palette=effective_palette)
    default_placement = resolve_cue_placement(config, geometry)
    if placements is not None and len(placements) != len(segments):
        raise ArtifactError("ASS cue placements must match the segment count")
    positioned_lines: list[tuple[PositionedVisualLine, ...]] = []
    backdrop_bounds: list[tuple[int, int, int, int] | None] = []
    for segment in segments:
        karaoke_cue = segment.get("_karaoke_cue")
        karaoke_preview_cue = segment.get("_karaoke_preview_cue")
        preview_word_behavior = (
            suppress_animation
            and isinstance(karaoke_preview_cue, KaraokeCue)
            and (
                config.animation.word.text.enabled
                or config.style.word_backdrop.kind is not SubtitleBackdrop.NONE
            )
        )
        needs_positioned_lines = (
            explicit_line_height
            or (animate_words and isinstance(karaoke_cue, KaraokeCue))
            or preview_word_behavior
            or (
                animate_cues and config.style.backdrop.kind is not SubtitleBackdrop.NONE
            )
        )
        if not needs_positioned_lines:
            backdrop_bounds.append(None)
            positioned_lines.append(())
            continue
        if metrics is None:
            metrics = resolve_wrapping_metrics(config, geometry)
        fragments = (
            karaoke_cue.fragments
            if isinstance(karaoke_cue, KaraokeCue)
            else karaoke_preview_cue.fragments
            if isinstance(karaoke_preview_cue, KaraokeCue)
            else segment.get("display_fragments")
        )
        visual_lines = build_visual_lines(
            str(segment.get("text", "")),
            fragments
            if isinstance(fragments, Sequence)
            and not isinstance(fragments, (str, bytes))
            and all(isinstance(item, SubtitleDisplayFragment) for item in fragments)
            else None,
            metrics,
        )
        placement = (
            placements[len(positioned_lines)]
            if placements is not None
            else default_placement
        )
        if (
            (explicit_line_height and len(visual_lines) > 1)
            or (animate_words and isinstance(karaoke_cue, KaraokeCue))
            or preview_word_behavior
        ):
            line_layout = position_visual_lines(
                visual_lines,
                config,
                geometry,
                metrics,
                placement,
            )
            backdrop_bounds.append(line_layout[0].block_bounds if line_layout else None)
            positioned_lines.append(line_layout)
        else:
            backdrop_bounds.append(None)
            positioned_lines.append(())
    needs_separate_backdrop = any(positioned_lines) and (
        config.style.backdrop.kind is not SubtitleBackdrop.NONE
    )
    needs_shared_backdrop = (
        needs_separate_backdrop and config.style.backdrop.kind is SubtitleBackdrop.BOX
    )
    positioned_style_name = "Default"
    positioned_style: dict[str, str | int] | None = None
    if needs_separate_backdrop:
        # BorderStyle 3 would draw one box per generated line. Keep Default
        # unchanged for single-line cues and neutralize only the generated
        # per-line text style; the vector event owns their complete box.
        positioned_style_name = "Positioned"
        positioned_style = dict(style)
        positioned_style["border_style"] = 1
        positioned_style["outline_weight"] = 0
        positioned_style["shadow_weight"] = 0
    style_lines = [_serialize_style_line("Default", style)]
    if positioned_style is not None:
        style_lines.append(
            _serialize_style_line(positioned_style_name, positioned_style)
        )
    lines = [
        "[Script Info]",
        "Title: multisubs generated subtitles",
        "ScriptType: v4.00+",
        f"PlayResX: {geometry.render_width}",
        f"PlayResY: {geometry.render_height}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        *style_lines,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    for index, segment in enumerate(segments):
        placement = placements[index] if placements is not None else default_placement
        # Older libass releases normalize positive values in the style Bold
        # field to boolean bold. Event-level \b accepts the exact OpenType rank
        # across those releases, so keep the base style neutral and apply the
        # validated semantic weight through the trusted override path.
        generated_override = rf"{{\b{config.style.typography.font_weight.rank}}}"
        if preserve_line_breaks:
            generated_override += r"{\q2}"
        cue_start = quantize_ass_centiseconds(segment["start"])
        cue_end = quantize_ass_centiseconds(segment["end"])

        def append_event(
            event_start: int,
            event_end: int,
            event_override: str,
            event_text: str,
            *,
            event_placement: CuePlacement | None = placement,
            layer: int = 0,
            style_name: str = "Default",
            _logical_start: int = cue_start,
            _logical_end: int = cue_end,
            animation_origin: CuePlacement | None = None,
            word_timing: WordAnimationTiming | None = None,
            cue_animation: SubtitleElementAnimation = config.animation.cue.text,
            word_animation: SubtitleWordElementAnimation | None = None,
        ) -> None:
            _append_dialogue_event(
                lines,
                _DialogueEvent(
                    logical_start=_logical_start,
                    logical_end=_logical_end,
                    start=event_start,
                    end=event_end,
                    generated_override=event_override,
                    text=event_text,
                    placement=event_placement,
                    animation_origin=animation_origin,
                    word_timing=word_timing,
                    cue_animation=cue_animation,
                    word_animation=word_animation,
                    layer=layer,
                    style_name=style_name,
                ),
                config,
                geometry,
                animate=not suppress_animation,
            )

        karaoke_cue = segment.get("_karaoke_cue")
        karaoke_preview_cue = segment.get("_karaoke_preview_cue")
        visual_line_events = positioned_lines[index]
        if visual_line_events:
            if metrics is None:
                raise ArtifactError(
                    "Positioned subtitle lines require wrapping metrics"
                )
            current_backdrop_bounds = backdrop_bounds[index]
            if needs_shared_backdrop and current_backdrop_bounds is not None:
                backdrop_anchor = visual_line_events[0]
                _append_shared_backdrop_event(
                    lines,
                    cue_start,
                    cue_end,
                    current_backdrop_bounds,
                    backdrop_anchor.block_placement,
                    effective_palette.backdrop_color,
                    metrics.shadow_size,
                    config=config,
                    geometry=geometry,
                    animate=animate_cues,
                    style_name=positioned_style_name,
                )
            elif config.style.backdrop.kind is SubtitleBackdrop.OUTLINE:
                if (
                    config.style.word_backdrop.kind is SubtitleBackdrop.OUTLINE
                    and isinstance(karaoke_cue, KaraokeCue)
                ):
                    _append_cue_outline_around_word_decoration(
                        append_event,
                        karaoke_cue,
                        visual_line_events,
                        config,
                        cue_start,
                        cue_end,
                        effective_palette.backdrop_color,
                        style_name=positioned_style_name,
                    )
                elif (
                    config.style.word_backdrop.kind is SubtitleBackdrop.OUTLINE
                    and isinstance(karaoke_preview_cue, KaraokeCue)
                ):
                    _append_cue_outline_around_word_decoration(
                        append_event,
                        karaoke_preview_cue,
                        visual_line_events,
                        config,
                        cue_start,
                        cue_end,
                        effective_palette.backdrop_color,
                        preview=True,
                        style_name=positioned_style_name,
                    )
                elif (
                    animate_words and isinstance(karaoke_cue, KaraokeCue)
                ) or preview_word_behavior:
                    _append_fragmented_cue_outline_events(
                        append_event,
                        visual_line_events,
                        config,
                        cue_start,
                        cue_end,
                        effective_palette.backdrop_color,
                        cue=(
                            karaoke_cue if isinstance(karaoke_cue, KaraokeCue) else None
                        ),
                        style_name=positioned_style_name,
                    )
                else:
                    for item in visual_line_events:
                        _append_cue_outline_event(
                            append_event,
                            item.line.text,
                            CuePlacement(item.anchor, item.position_x, item.position_y),
                            item.block_placement,
                            cue_start,
                            cue_end,
                            effective_palette.backdrop_color,
                            config,
                            style_name=positioned_style_name,
                        )
            line_placements = [
                CuePlacement(
                    anchor=item.anchor,
                    position_x=item.position_x,
                    position_y=item.position_y,
                )
                for item in visual_line_events
            ]
            if animate_words and isinstance(karaoke_cue, KaraokeCue):
                _append_word_animation_events(
                    append_event,
                    karaoke_cue,
                    visual_line_events,
                    config,
                    cue_start,
                    cue_end,
                    effective_palette,
                    metrics,
                    generated_override=generated_override,
                    style_name=positioned_style_name,
                )
                continue
            if preview_word_behavior and isinstance(karaoke_preview_cue, KaraokeCue):
                _append_word_preview_events(
                    append_event,
                    karaoke_preview_cue,
                    visual_line_events,
                    config,
                    cue_start,
                    cue_end,
                    effective_palette,
                    metrics,
                    generated_override=generated_override,
                    style_name=positioned_style_name,
                )
                continue
            if isinstance(karaoke_preview_cue, KaraokeCue):
                for line_placement, item in zip(
                    line_placements, visual_line_events, strict=True
                ):
                    preview_text = serialize_karaoke_preview_cue(
                        karaoke_preview_cue,
                        config,
                        fragments=item.line.fragments,
                        palette=effective_palette,
                    )
                    if preview_text is None:
                        preview_text = escape_ass_text(item.line.text)
                    append_event(
                        cue_start,
                        cue_end,
                        generated_override,
                        preview_text,
                        event_placement=line_placement,
                        animation_origin=item.block_placement,
                        layer=1,
                        style_name=positioned_style_name,
                    )
                continue
            if (
                config.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD
                and isinstance(karaoke_cue, KaraokeCue)
            ):
                for line_placement, item in zip(
                    line_placements, visual_line_events, strict=True
                ):
                    for (
                        event_start,
                        event_end,
                        event_text,
                    ) in serialize_active_word_line_events(
                        karaoke_cue,
                        item.line.fragments,
                        config,
                        cue_start,
                        cue_end,
                        palette=effective_palette,
                    ):
                        append_event(
                            event_start,
                            event_end,
                            generated_override,
                            event_text,
                            event_placement=line_placement,
                            animation_origin=item.block_placement,
                            layer=1,
                            style_name=positioned_style_name,
                        )
                continue
            if (
                config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE
                and isinstance(karaoke_cue, KaraokeCue)
            ):
                for line_placement, item in zip(
                    line_placements, visual_line_events, strict=True
                ):
                    for (
                        event_start,
                        event_end,
                        event_text,
                    ) in serialize_progressive_line_events(
                        karaoke_cue,
                        item.line.fragments,
                        config,
                        cue_start,
                        cue_end,
                        palette=effective_palette,
                    ):
                        append_event(
                            event_start,
                            event_end,
                            generated_override,
                            event_text,
                            event_placement=line_placement,
                            animation_origin=item.block_placement,
                            layer=1,
                            style_name=positioned_style_name,
                        )
                continue
            for line_placement, item in zip(
                line_placements, visual_line_events, strict=True
            ):
                append_event(
                    cue_start,
                    cue_end,
                    generated_override,
                    escape_ass_text(item.line.text),
                    event_placement=line_placement,
                    animation_origin=item.block_placement,
                    layer=1,
                    style_name=positioned_style_name,
                )
            continue
        preview_text = serialize_karaoke_preview_cue(
            karaoke_preview_cue,
            config,
            palette=effective_palette,
        )
        if preview_text is not None:
            append_event(
                cue_start,
                cue_end,
                generated_override,
                preview_text,
            )
            continue
        if (
            config.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD
            and isinstance(karaoke_cue, KaraokeCue)
        ):
            for event_start, event_end, event_text in serialize_active_word_events(
                karaoke_cue,
                config,
                cue_start,
                cue_end,
                palette=effective_palette,
            ):
                append_event(
                    event_start,
                    event_end,
                    generated_override,
                    event_text,
                )
            continue
        if (
            animate_cues
            and config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE
            and isinstance(karaoke_cue, KaraokeCue)
        ):
            for event_start, event_end, event_text in serialize_progressive_line_events(
                karaoke_cue,
                karaoke_cue.fragments,
                config,
                cue_start,
                cue_end,
                palette=effective_palette,
            ):
                append_event(
                    event_start,
                    event_end,
                    generated_override,
                    event_text,
                )
            continue
        karaoke_text = (
            serialize_karaoke_cue(
                karaoke_cue,
                config,
                palette=effective_palette,
            )
            if config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE
            else None
        )
        dialogue_text = (
            karaoke_text
            if karaoke_text is not None
            else escape_ass_text(str(segment["text"]))
        )
        append_event(
            cue_start,
            cue_end,
            generated_override,
            dialogue_text,
        )
    for event in guide_events or ():
        _append_guide_event(lines, event)
    atomic_write_text(path, "\n".join(lines) + "\n")


def _append_word_animation_events(
    append_event: Callable[..., None],
    cue: KaraokeCue,
    visual_lines: Sequence[PositionedVisualLine],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    palette: SubtitlePalette,
    metrics: WrappingMetrics,
    *,
    generated_override: str,
    style_name: str,
) -> None:
    """Render measured fragments independently for word-local effects."""
    _validate_karaoke_cue(cue)
    word = config.animation.word
    for positioned in visual_lines:
        for fragment, placement in zip(
            positioned.line.fragments,
            positioned.fragment_placements,
            strict=True,
        ):
            if not fragment.text or fragment.text.isspace():
                continue
            escaped = escape_ass_text(fragment.text)
            word_index = fragment.word_index
            if word_index is None:
                append_event(
                    cue_start,
                    cue_end,
                    generated_override,
                    escaped,
                    event_placement=placement,
                    animation_origin=positioned.block_placement,
                    layer=2,
                    style_name=style_name,
                )
                continue
            if word_index < 0 or word_index >= len(cue.active_intervals):
                raise ArtifactError("Word animation fragment index is invalid")
            word_start, word_end = cue.active_intervals[word_index]
            text_end = (
                cue_end if word.text.mode is WordAnimationMode.PROGRESSIVE else word_end
            )
            text_timing = normalize_word_animation(word_start, text_end, word.text)
            visible_start = (
                word_start
                if word.text.entrance.type is not CueAnimationType.NONE
                else cue_start
            )
            visible_end = (
                text_end
                if word.text.exit.type is not CueAnimationType.NONE
                else cue_end
            )
            if visible_end <= visible_start:
                continue
            if config.style.word_backdrop.kind is not SubtitleBackdrop.NONE:
                backdrop_end = (
                    word_end
                    if word.backdrop.mode is WordAnimationMode.ACTIVE_WORD
                    else cue_end
                )
                if backdrop_end > word_start:
                    backdrop_timing = normalize_word_animation(
                        word_start, backdrop_end, word.backdrop
                    )
                    _append_word_backdrop_event(
                        append_event,
                        fragment.text,
                        placement,
                        positioned.block_placement,
                        word_start,
                        backdrop_end,
                        palette,
                        metrics,
                        config,
                        word_timing=backdrop_timing,
                        style_name=style_name,
                    )
            boundaries = {visible_start, visible_end, word_start, word_end}
            for boundary in word_animation_boundaries(text_timing, word.text):
                boundaries.add(boundary)
            points = sorted(
                point for point in boundaries if visible_start <= point <= visible_end
            )
            for event_start, event_end in zip(points[:-1], points[1:], strict=True):
                if event_end <= event_start:
                    continue
                highlight = _word_is_highlighted(
                    config,
                    word_start,
                    word_end,
                    event_start,
                )
                color_override = _word_color_override(palette, highlight)
                append_event(
                    event_start,
                    event_end,
                    generated_override + color_override,
                    escaped,
                    event_placement=placement,
                    animation_origin=positioned.block_placement,
                    layer=2,
                    style_name=style_name,
                    word_timing=text_timing,
                    word_animation=word.text,
                )


def _append_cue_outline_event(
    append_event: Callable[..., None],
    text: str,
    placement: CuePlacement,
    animation_origin: CuePlacement,
    start: int,
    end: int,
    color: str,
    config: SubtitleConfig,
    *,
    style_name: str,
    word_timing: WordAnimationTiming | None = None,
    word_animation: SubtitleWordElementAnimation | None = None,
) -> None:
    """Render a cue glyph outline independently below the text layer."""
    ass_color = rgba_to_ass_color(color)
    outline_size = _resolved_style_int(config.style.backdrop.size, "backdrop-size")
    font_weight = config.style.typography.font_weight.rank
    outline = (
        f"{{\\b{font_weight}\\1a&HFF&\\3c&H{ass_color[4:10]}&"
        f"\\3a&H{ass_color[2:4]}&"
        f"\\bord{outline_size}\\shad0}}{escape_ass_text(text)}"
    )
    append_event(
        start,
        end,
        "",
        outline,
        event_placement=placement,
        animation_origin=animation_origin,
        layer=0,
        style_name=style_name,
        cue_animation=config.animation.cue.text,
        word_timing=word_timing,
        word_animation=word_animation,
    )


def _append_fragmented_cue_outline_events(
    append_event: Callable[..., None],
    visual_lines: Sequence[PositionedVisualLine],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    color: str,
    *,
    cue: KaraokeCue | None = None,
    style_name: str,
) -> None:
    """Render cue outlines with the exact placement and motion of word text."""
    if cue is not None:
        _validate_karaoke_cue(cue)
    for positioned in visual_lines:
        for fragment, placement in zip(
            positioned.line.fragments,
            positioned.fragment_placements,
            strict=True,
        ):
            if not fragment.text or fragment.text.isspace():
                continue
            start = cue_start
            end = cue_end
            word_timing: WordAnimationTiming | None = None
            word_animation: SubtitleWordElementAnimation | None = None
            word_index = fragment.word_index
            if cue is not None and word_index is not None:
                if word_index < 0 or word_index >= len(cue.active_intervals):
                    raise ArtifactError("Word outline fragment index is invalid")
                word_start, word_end = cue.active_intervals[word_index]
                text_end = (
                    cue_end
                    if config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE
                    else word_end
                )
                word_animation = config.animation.word.text
                word_timing = normalize_word_animation(
                    word_start, text_end, word_animation
                )
                start = (
                    word_start
                    if word_animation.entrance.type is not CueAnimationType.NONE
                    else cue_start
                )
                end = (
                    text_end
                    if word_animation.exit.type is not CueAnimationType.NONE
                    else cue_end
                )
                if end <= start:
                    continue
            _append_cue_outline_event(
                append_event,
                fragment.text,
                placement,
                positioned.block_placement,
                start,
                end,
                color,
                config,
                style_name=style_name,
                word_timing=word_timing,
                word_animation=word_animation,
            )


def _append_cue_outline_around_word_decoration(
    append_event: Callable[..., None],
    cue: KaraokeCue,
    visual_lines: Sequence[PositionedVisualLine],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    color: str,
    *,
    preview: bool = False,
    style_name: str,
) -> None:
    """Remove the cue outline only while a word outline replaces it."""
    _validate_karaoke_cue(cue)
    preview_indexes = (
        set(range((len(cue.durations) + 1) // 2))
        if config.animation.word.backdrop.mode is WordAnimationMode.PROGRESSIVE
        else {0}
    )
    for positioned in visual_lines:
        for fragment, placement in zip(
            positioned.line.fragments,
            positioned.fragment_placements,
            strict=True,
        ):
            if not fragment.text or fragment.text.isspace():
                continue
            intervals = [(cue_start, cue_end)]
            word_index = fragment.word_index
            if word_index is not None:
                if word_index < 0 or word_index >= len(cue.active_intervals):
                    raise ArtifactError("Word outline fragment index is invalid")
                if preview:
                    intervals = [] if word_index in preview_indexes else intervals
                else:
                    word_start, word_end = cue.active_intervals[word_index]
                    decoration_end = (
                        cue_end
                        if config.animation.word.backdrop.mode
                        is WordAnimationMode.PROGRESSIVE
                        else word_end
                    )
                    intervals = [
                        (cue_start, word_start),
                        (decoration_end, cue_end),
                    ]
            for start, end in intervals:
                if end <= start:
                    continue
                _append_cue_outline_event(
                    append_event,
                    fragment.text,
                    placement,
                    positioned.block_placement,
                    start,
                    end,
                    color,
                    config,
                    style_name=style_name,
                )


def _append_word_preview_events(
    append_event: Callable[..., None],
    cue: KaraokeCue,
    visual_lines: Sequence[PositionedVisualLine],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    palette: SubtitlePalette,
    metrics: WrappingMetrics,
    *,
    generated_override: str,
    style_name: str,
) -> None:
    """Render the documented static representative state for word tracks."""
    _validate_karaoke_cue(cue)
    backdrop_indexes = (
        set(range((len(cue.durations) + 1) // 2))
        if config.animation.word.backdrop.mode is WordAnimationMode.PROGRESSIVE
        else {0}
    )
    text_indexes: set[int] = set()
    if config.animation.word.uses_timed_highlight:
        text_indexes = (
            set(range((len(cue.durations) + 1) // 2))
            if config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE
            else {0}
        )

    for positioned in visual_lines:
        for fragment, placement in zip(
            positioned.line.fragments,
            positioned.fragment_placements,
            strict=True,
        ):
            if not fragment.text or fragment.text.isspace():
                continue
            backdrop_active = fragment.word_index in backdrop_indexes
            highlighted = fragment.word_index in text_indexes
            if (
                backdrop_active
                and config.style.word_backdrop.kind is not SubtitleBackdrop.NONE
            ):
                _append_word_backdrop_event(
                    append_event,
                    fragment.text,
                    placement,
                    positioned.block_placement,
                    cue_start,
                    cue_end,
                    palette,
                    metrics,
                    config,
                    word_timing=None,
                    style_name=style_name,
                )
            append_event(
                cue_start,
                cue_end,
                generated_override + _word_color_override(palette, highlighted),
                escape_ass_text(fragment.text),
                event_placement=placement,
                animation_origin=positioned.block_placement,
                layer=2,
                style_name=style_name,
            )


def _append_word_backdrop_event(
    append_event: Callable[..., None],
    text: str,
    placement: CuePlacement,
    animation_origin: CuePlacement,
    start: int,
    end: int,
    palette: SubtitlePalette,
    metrics: WrappingMetrics,
    config: SubtitleConfig,
    *,
    word_timing: WordAnimationTiming | None,
    style_name: str,
) -> None:
    """Append one measured word box or glyph outline below its text."""
    padding = _resolved_style_int(
        config.style.word_backdrop.size,
        "word-backdrop-size",
    )
    fragment_width = metrics.text_measurer.measure(text)
    left = _round_playres(placement.position_x - fragment_width / 2 - padding)
    if placement.anchor.value.startswith("top-"):
        top = placement.position_y - padding
    elif placement.anchor.value.startswith("bottom-"):
        top = _round_playres(
            placement.position_y - metrics.natural_line_height - padding
        )
    else:
        top = _round_playres(
            placement.position_y - metrics.natural_line_height / 2 - padding
        )
    width = _round_playres(fragment_width + 2 * padding)
    height = _round_playres(metrics.natural_line_height + 2 * padding)
    ass_color = rgba_to_ass_color(palette.word_backdrop_color)
    alpha = ass_color[2:4]
    bgr = ass_color[4:10]
    if config.style.word_backdrop.kind is SubtitleBackdrop.OUTLINE:
        drawing = (
            f"{{\\b{config.style.typography.font_weight.rank}\\1a&HFF&"
            f"\\3c&H{bgr}&\\3a&H{alpha}&\\bord{padding}\\shad0}}"
            + escape_ass_text(text)
        )
        backdrop_placement = placement
    elif config.style.word_backdrop.kind is SubtitleBackdrop.BOX:
        drawing = (
            f"{{\\p1\\1c&H{bgr}&\\1a&H{alpha}&\\3a&HFF&\\4a&HFF&"
            f"\\bord0\\shad0}}m 0 0 l {width} 0 l {width} {height} "
            f"l 0 {height} l 0 0{{\\p0}}"
        )
        backdrop_placement = CuePlacement(SubtitlePosition.TOP_LEFT, left, top)
    else:
        return
    append_event(
        start,
        end,
        "",
        drawing,
        event_placement=backdrop_placement,
        animation_origin=animation_origin,
        layer=1,
        style_name=style_name,
        word_timing=word_timing,
        cue_animation=SubtitleElementAnimation(),
        word_animation=(
            config.animation.word.backdrop if word_timing is not None else None
        ),
    )


def _round_playres(value: float) -> int:
    """Round one measured coordinate consistently with layout resolution."""
    return int(math.floor(value + 0.5))


def _word_is_highlighted(
    config: SubtitleConfig,
    word_start: int,
    word_end: int,
    at_centiseconds: int,
) -> bool:
    if not config.animation.word.uses_timed_highlight:
        return False
    if config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE:
        return at_centiseconds >= word_start
    if config.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD:
        return word_start <= at_centiseconds < word_end
    return False


def _word_color_override(palette: SubtitlePalette, highlighted: bool) -> str:
    if not highlighted:
        return ""
    if palette.highlight_color is None:
        raise ArtifactError("Timed word highlight color is not resolved")
    return "{" + rgba_to_ass_color_override(palette.highlight_color, 1) + "}"


def _append_dialogue_event(
    lines: list[str],
    event: _DialogueEvent,
    config: SubtitleConfig,
    geometry: VideoGeometry,
    *,
    animate: bool,
) -> None:
    """Serialize one typed event, slicing only at cue-global phase boundaries."""
    if not isinstance(event, _DialogueEvent):
        raise ArtifactError("ASS dialogue must use the typed event contract")
    if event.end < event.start:
        raise ArtifactError("ASS dialogue end must not precede its start")
    if not animate or (
        not event.cue_animation.enabled and event.word_animation is None
    ):
        placement_override = (
            serialize_ass_placement(event.placement)
            if event.placement is not None
            else ""
        )
        _append_dialogue_line(
            lines,
            event.start,
            event.end,
            event.generated_override + placement_override,
            event.text,
            layer=event.layer,
            style_name=event.style_name,
        )
        return

    timing = normalize_cue_animation(
        event.logical_start,
        event.logical_end,
        event.cue_animation,
    )
    points = [event.start]
    points.extend(
        boundary
        for boundary in animation_boundaries(timing, event.cue_animation)
        if event.start < boundary < event.end
    )
    if event.word_timing is not None and event.word_animation is not None:
        points.extend(
            boundary
            for boundary in word_animation_boundaries(
                event.word_timing, event.word_animation
            )
            if event.start < boundary < event.end
        )
        points.extend(
            boundary
            for boundary in (event.word_timing.word_start, event.word_timing.word_end)
            if event.start < boundary < event.end
        )
    points = sorted(set(points))
    points.append(event.end)
    font_size = _resolved_style_int(config.style.typography.font_size, "font-size")
    slide_enabled = _track_has_motion(event.cue_animation) or (
        event.word_animation is not None and _track_has_motion(event.word_animation)
    )
    stable_placement = event.placement
    if slide_enabled and stable_placement is None:
        region = resolve_native_layout_region(geometry, config.layout)
        anchor = config.layout.position
        anchor_x, anchor_y = resolve_native_anchor_point(anchor, region)
        stable_placement = CuePlacement(anchor, anchor_x, anchor_y)

    for interval_start, interval_end in zip(points[:-1], points[1:], strict=True):
        start_state = sample_cue_animation(
            event.cue_animation,
            timing,
            interval_start,
            font_size=font_size,
        )
        end_state = sample_cue_animation(
            event.cue_animation,
            timing,
            interval_end,
            font_size=font_size,
        )
        if stable_placement is not None and event.animation_origin is not None:
            start_state = _rebase_cue_scale(
                start_state,
                placement=stable_placement,
                origin=event.animation_origin,
            )
            end_state = _rebase_cue_scale(
                end_state,
                placement=stable_placement,
                origin=event.animation_origin,
            )
        if event.word_timing is not None and event.word_animation is not None:
            start_state = _combine_animation_states(
                start_state,
                sample_word_animation(
                    event.word_animation,
                    event.word_timing,
                    interval_start,
                    font_size=font_size,
                ),
            )
            end_state = _combine_animation_states(
                end_state,
                sample_word_animation(
                    event.word_animation,
                    event.word_timing,
                    interval_end,
                    font_size=font_size,
                ),
            )
        animation_override = _serialize_animation_override(
            start_state,
            end_state,
            interval_end - interval_start,
            stable_placement=stable_placement,
            force_animated_placement=slide_enabled,
        )
        if not slide_enabled and event.placement is not None:
            animation_override = (
                serialize_ass_placement(event.placement) + animation_override
            )
        _append_dialogue_line(
            lines,
            interval_start,
            interval_end,
            event.generated_override + animation_override,
            event.text,
            layer=event.layer,
            style_name=event.style_name,
        )


def _combine_animation_states(
    cue: CueAnimationState,
    word: CueAnimationState,
) -> CueAnimationState:
    """Compose cue-global and word-local state exactly once."""
    cue_visibility = Decimal(255 - cue.fade_alpha) / Decimal(255)
    word_visibility = Decimal(255 - word.fade_alpha) / Decimal(255)
    fade_alpha = 255 - int(
        (cue_visibility * word_visibility * Decimal(255)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    scale = int(
        (
            Decimal(cue.scale_percent) * Decimal(word.scale_percent) / Decimal(100)
        ).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    )
    return CueAnimationState(
        fade_alpha=fade_alpha,
        offset_x=cue.offset_x + word.offset_x,
        offset_y=cue.offset_y + word.offset_y,
        scale_percent=scale,
    )


def _rebase_cue_scale(
    state: CueAnimationState,
    *,
    placement: CuePlacement,
    origin: CuePlacement,
) -> CueAnimationState:
    """Move a positioned layer as cue-global scale changes around its origin."""
    scale_delta = Decimal(state.scale_percent - 100) / Decimal(100)
    offset_x = int(
        (Decimal(placement.position_x - origin.position_x) * scale_delta).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    offset_y = int(
        (Decimal(placement.position_y - origin.position_y) * scale_delta).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    return CueAnimationState(
        fade_alpha=state.fade_alpha,
        offset_x=state.offset_x + offset_x,
        offset_y=state.offset_y + offset_y,
        scale_percent=state.scale_percent,
    )


def _serialize_animation_override(
    start: CueAnimationState,
    end: CueAnimationState,
    duration_centiseconds: int,
    *,
    stable_placement: CuePlacement | None,
    force_animated_placement: bool,
) -> str:
    duration_ms = max(0, duration_centiseconds * 10)
    tags = ""
    if force_animated_placement:
        if stable_placement is None:
            raise ArtifactError("Slide animation requires a stable cue placement")
        alignment = _ass_alignment_for_position(stable_placement.anchor)
        start_x = stable_placement.position_x + start.offset_x
        start_y = stable_placement.position_y + start.offset_y
        end_x = stable_placement.position_x + end.offset_x
        end_y = stable_placement.position_y + end.offset_y
        if (start_x, start_y) == (end_x, end_y) or duration_ms == 0:
            tags += f"{{\\an{alignment}\\pos({start_x},{start_y})}}"
        else:
            tags += (
                f"{{\\an{alignment}\\move({start_x},{start_y},"
                f"{end_x},{end_y},0,{duration_ms})}}"
            )
    if start.scale_percent != 100 or end.scale_percent != 100:
        scale = f"\\fscx{start.scale_percent}\\fscy{start.scale_percent}"
        if start.scale_percent != end.scale_percent and duration_ms > 0:
            scale += (
                f"\\t(0,{duration_ms},\\fscx{end.scale_percent}"
                f"\\fscy{end.scale_percent})"
            )
        tags += "{" + scale + "}"
    if start.fade_alpha != 0 or end.fade_alpha != 0:
        if start.fade_alpha == end.fade_alpha or duration_ms == 0:
            tags += (
                f"{{\\fade({start.fade_alpha},{start.fade_alpha},"
                f"{start.fade_alpha},0,0,{duration_ms},{duration_ms})}}"
            )
        else:
            tags += (
                f"{{\\fade({start.fade_alpha},{end.fade_alpha},"
                f"{end.fade_alpha},0,{duration_ms},{duration_ms},{duration_ms})}}"
            )
    return tags


def _has_cue_animation(config: SubtitleConfig) -> bool:
    cue = config.animation.cue
    return cue.text.enabled or cue.backdrop.enabled


def _has_positioned_word_animation(config: SubtitleConfig) -> bool:
    """Return whether aligned words require independent positioned events."""
    word = config.animation.word
    return (
        word.text.enabled
        or config.style.word_backdrop.kind is not SubtitleBackdrop.NONE
    )


def _track_has_motion(animation: SubtitleElementAnimation) -> bool:
    slide_types = {
        CueAnimationType.SLIDE_UP,
        CueAnimationType.SLIDE_DOWN,
        CueAnimationType.SLIDE_LEFT,
        CueAnimationType.SLIDE_RIGHT,
        CueAnimationType.BOUNCE,
        CueAnimationType.FLOAT,
        CueAnimationType.SHAKE,
    }
    return any(
        phase.type in slide_types
        for phase in (animation.entrance, animation.emphasis, animation.exit)
    )


def _append_dialogue_line(
    lines: list[str],
    start_centiseconds: int,
    end_centiseconds: int,
    generated_override: str,
    dialogue_text: str,
    *,
    layer: int = 0,
    style_name: str = "Default",
) -> None:
    if end_centiseconds < start_centiseconds:
        raise ArtifactError("ASS dialogue end must not precede its start")
    lines.append(
        f"Dialogue: {layer},"
        f"{format_ass_centiseconds(start_centiseconds)},"
        f"{format_ass_centiseconds(end_centiseconds)},"
        f"{style_name},,0,0,0,,{generated_override}{dialogue_text}"
    )


def _serialize_style_line(
    name: str,
    style: Mapping[str, str | int],
) -> str:
    """Serialize one trusted internal ASS style in canonical field order."""
    return (
        f"Style: {name},"
        + ",".join(str(style[field]) for field in ASS_STYLE_FIELDS)
        + ",1"
    )


def _uses_explicit_line_height(config: SubtitleConfig) -> bool:
    requested = config.style.typography.line_height_requested
    if requested is None:
        requested = config.style.typography.line_height
    return not (isinstance(requested, str) and requested.casefold() == "auto")


def _append_shared_backdrop_event(
    lines: list[str],
    start_centiseconds: int,
    end_centiseconds: int,
    bounds: tuple[int, int, int, int],
    animation_origin: CuePlacement,
    color: str,
    shadow_size: int,
    *,
    config: SubtitleConfig,
    geometry: VideoGeometry,
    animate: bool,
    style_name: str,
) -> None:
    """Append one lower-layer vector backdrop for a positioned visual block."""
    left, top, right, bottom = bounds
    ass_color = rgba_to_ass_color(color)
    alpha = ass_color[2:4]
    bgr = ass_color[4:10]
    path = (
        f"m {left} {top} l {right} {top} l {right} {bottom} "
        f"l {left} {bottom} l {left} {top}"
    )
    text = (
        f"{{\\an7\\pos(0,0)\\p1\\1c&H{bgr}&\\1a&H{alpha}&"
        f"\\3a&HFF&\\4a&HFF&\\bord0\\shad{shadow_size}}}{path}{{\\p0}}"
    )
    if not animate:
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_centiseconds(start_centiseconds)},"
            f"{format_ass_centiseconds(end_centiseconds)},"
            f"{style_name},,0,0,0,,{text}"
        )
        return
    width = right - left
    height = bottom - top
    local_path = f"m 0 0 l {width} 0 l {width} {height} l 0 {height} l 0 0"
    animated_text = (
        f"{{\\p1\\1c&H{bgr}&\\1a&H{alpha}&"
        f"\\3a&HFF&\\4a&HFF&\\bord0\\shad{shadow_size}}}{local_path}{{\\p0}}"
    )
    top_left = CuePlacement(SubtitlePosition.TOP_LEFT, left, top)
    _append_dialogue_event(
        lines,
        _DialogueEvent(
            logical_start=start_centiseconds,
            logical_end=end_centiseconds,
            start=start_centiseconds,
            end=end_centiseconds,
            generated_override="",
            text=animated_text,
            placement=top_left,
            animation_origin=animation_origin,
            cue_animation=config.animation.cue.backdrop,
            layer=0,
            style_name=style_name,
        ),
        config,
        geometry,
        animate=True,
    )


def _append_guide_event(lines: list[str], event: AssDrawingEvent) -> None:
    """Append one generated diagnostic event without treating it as user text."""
    if not isinstance(event, AssDrawingEvent):
        raise ArtifactError("ASS guide events must use the typed drawing contract")
    if (
        isinstance(event.start, bool)
        or not isinstance(event.start, Real)
        or isinstance(event.end, bool)
        or not isinstance(event.end, Real)
        or not math.isfinite(float(event.start))
        or not math.isfinite(float(event.end))
        or event.start < 0
        or event.end < event.start
        or not isinstance(event.text, str)
        or not event.text
        or "\n" in event.text
        or "\r" in event.text
    ):
        raise ArtifactError("ASS guide events must contain valid timestamps and text")
    lines.append(
        "Dialogue: 0,"
        f"{format_ass_time(event.start)},{format_ass_time(event.end)},"
        f"Default,,0,0,0,,{event.text}"
    )


def _compile_style(
    config: SubtitleConfig,
    geometry: VideoGeometry | None = None,
    *,
    palette: SubtitlePalette | None = None,
) -> dict[str, str | int]:
    """Compile semantic layout into the private numeric ASS style fields."""
    appearance = config.style.typography
    if palette is None:
        _, palette = resolve_subtitle_palettes(config)
    layout = config.layout
    backdrop_size = _resolved_style_int(config.style.backdrop.size, "backdrop-size")
    margin_top = _resolved_style_int(layout.margin_top, "margin-top")
    margin_bottom = _resolved_style_int(layout.margin_bottom, "margin-bottom")
    explicit = layout.placement_mode is SubtitlePlacementMode.EXPLICIT
    margin_v = (
        0
        if explicit
        else margin_top
        if layout.position.value.startswith("top-")
        else margin_bottom
        if layout.position.value.startswith("bottom-")
        else 0
    )
    backdrop_color = rgba_to_ass_color(palette.backdrop_color)
    if explicit:
        margin_l = 0
        margin_r = 0
    else:
        margin_l = _resolved_style_int(layout.margin_left, "margin-left")
        margin_r = _resolved_style_int(layout.margin_right, "margin-right")
    return {
        "font": appearance.font,
        "font_size": _resolved_style_int(appearance.font_size, "font-size"),
        "primary_color": rgba_to_ass_color(palette.text_color),
        # SecondaryColour is mandatory in a V4+ Style. It remains the neutral
        # inactive color for ordinary cues; karaoke events override both colors.
        "secondary_color": rgba_to_ass_color(palette.text_color),
        "outline_color": backdrop_color,
        "back_color": backdrop_color,
        # Exact weight is emitted as a trusted event-level \b override because
        # older libass style parsers coerce every positive value to bold.
        "bold": 0,
        "italic": -1 if appearance.italic else 0,
        "underline": 0,
        "strikeout": 0,
        "scale_x": 100,
        "scale_y": 100,
        "spacing": _resolved_style_int(appearance.letter_spacing, "letter-spacing"),
        "angle": 0,
        # BorderStyle 3 is the standard ASS opaque box. libass treats the
        # unsupported value 4 like an outline, which makes non-zero padding
        # follow glyph contours instead of filling the backdrop.
        "border_style": (
            3 if config.style.backdrop.kind is SubtitleBackdrop.BOX else 1
        ),
        "outline_weight": (
            0 if config.style.backdrop.kind is SubtitleBackdrop.NONE else backdrop_size
        ),
        "shadow_weight": _resolved_style_int(config.style.shadow.size, "shadow-size"),
        "alignment": _ass_alignment_for_position(
            layout.anchor if explicit and layout.anchor is not None else layout.position
        ),
        "margin_l": margin_l,
        "margin_r": margin_r,
        "margin_v": margin_v,
    }


def resolve_subtitle_palettes(
    config: SubtitleConfig,
) -> tuple[SubtitlePalette, SubtitlePalette]:
    """Return canonical base colors and their once-composed effective palette."""
    base = SubtitlePalette(
        text_color=_canonical_rgba(config.style.typography.color),
        backdrop_color=_canonical_rgba(config.style.backdrop.color),
        word_backdrop_color=_canonical_rgba(config.style.word_backdrop.color),
        highlight_color=(
            _canonical_rgba(config.style.typography.highlight_color)
            if config.style.typography.highlight_color is not None
            else None
        ),
    )
    opacity = config.style.opacity
    effective = SubtitlePalette(
        text_color=compose_rgba_opacity(base.text_color, opacity),
        backdrop_color=compose_rgba_opacity(base.backdrop_color, opacity),
        word_backdrop_color=compose_rgba_opacity(
            base.word_backdrop_color,
            opacity,
        ),
        highlight_color=(
            compose_rgba_opacity(base.highlight_color, opacity)
            if base.highlight_color is not None
            else None
        ),
    )
    return base, effective


def compose_rgba_opacity(value: str, opacity: SubtitleOpacity) -> str:
    """Multiply conventional RGBA alpha by one validated global opacity."""
    canonical = _canonical_rgba(value)
    if not isinstance(opacity, SubtitleOpacity):
        raise ArtifactError("Subtitle opacity must use the typed opacity contract")
    percentage = opacity.percentage
    if (
        not isinstance(percentage, Decimal)
        or not percentage.is_finite()
        or percentage < 0
        or percentage > 100
    ):
        raise ArtifactError("Subtitle opacity must be between 0% and 100%")
    base_alpha = int(canonical[7:9], 16)
    effective_alpha = int(
        (Decimal(base_alpha) * percentage / Decimal(100)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    effective_alpha = min(255, max(0, effective_alpha))
    return canonical[:7] + f"{effective_alpha:02X}"


def _canonical_rgba(value: str) -> str:
    """Validate a conventional color and return uppercase #RRGGBBAA."""
    if (
        not isinstance(value, str)
        or len(value) not in {7, 9}
        or not value.startswith("#")
    ):
        raise ArtifactError("ASS colors require #RRGGBB or #RRGGBBAA notation")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ArtifactError("ASS colors require hexadecimal digits") from exc
    return value.upper() + ("FF" if len(value) == 7 else "")


def rgba_to_ass_color(value: str) -> str:
    """Convert #RRGGBB[AA] into ASS &HAABBGGRR notation."""
    canonical = _canonical_rgba(value)
    red = int(canonical[1:3], 16)
    green = int(canonical[3:5], 16)
    blue = int(canonical[5:7], 16)
    conventional_alpha = int(canonical[7:9], 16)
    ass_alpha = 255 - conventional_alpha
    return f"&H{ass_alpha:02X}{blue:02X}{green:02X}{red:02X}"


def _resolved_style_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactError(
            f"{field} must be resolved against video geometry before ASS compilation"
        )
    return value


def serialize_ass_placement(placement: CuePlacement) -> str:
    """Serialize one generated ASS anchor override without transcript text."""
    if not isinstance(placement, CuePlacement):
        raise ArtifactError("ASS cue placement must use the typed placement contract")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (placement.position_x, placement.position_y)
    ):
        raise ArtifactError(
            "ASS cue placement coordinates must be non-negative integers"
        )
    alignment = _ass_alignment_for_position(placement.anchor)
    return f"{{\\an{alignment}\\pos({placement.position_x},{placement.position_y})}}"


def _ass_alignment_for_position(position: SubtitlePosition) -> int:
    """Return the private ASS alignment code for one semantic position."""
    try:
        return _ASS_ALIGNMENT_BY_POSITION[position]
    except KeyError as exc:
        raise ArtifactError(f"Unsupported subtitle position: {position}") from exc


def format_ass_time(seconds: object) -> str:
    """Format one finite non-negative time using ASS centiseconds."""
    return format_ass_centiseconds(quantize_ass_centiseconds(seconds))


def format_ass_centiseconds(total_centiseconds: object) -> str:
    """Format one already quantized non-negative ASS timestamp."""
    if (
        isinstance(total_centiseconds, bool)
        or not isinstance(total_centiseconds, int)
        or total_centiseconds < 0
    ):
        raise ArtifactError("ASS centiseconds must be a non-negative integer")
    hours, remainder = divmod(total_centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def quantize_ass_centiseconds(seconds: object) -> int:
    """Quantize one timestamp using the rounding policy shared by ASS output."""
    value = _finite_time(seconds)
    if value is None:
        raise ArtifactError("ASS timestamp must be a finite, non-negative number")
    return round(value * 100)


def allocate_karaoke_durations(
    cue_start: object,
    cue_end: object,
    words: Sequence[Mapping[str, Any]],
) -> tuple[int, ...]:
    """Allocate exact non-negative ASS centiseconds between word starts."""
    start_centiseconds, end_centiseconds, starts, _ = _quantized_karaoke_boundaries(
        cue_start, cue_end, words
    )
    boundaries = (*starts[1:], end_centiseconds)
    durations = tuple(
        next_boundary - current
        for current, next_boundary in zip(starts, boundaries, strict=True)
    )
    if any(duration < 0 for duration in durations):
        raise ArtifactError("Karaoke durations must be non-negative")
    if sum(durations) != end_centiseconds - start_centiseconds:
        raise ArtifactError("Karaoke durations must conserve cue duration")
    return durations


def allocate_active_word_intervals(
    cue_start: object,
    cue_end: object,
    words: Sequence[Mapping[str, Any]],
) -> tuple[tuple[int, int], ...]:
    """Return non-overlapping absolute centisecond intervals for active words."""
    _, end_centiseconds, starts, ends = _quantized_karaoke_boundaries(
        cue_start, cue_end, words
    )
    next_starts = (*starts[1:], end_centiseconds)
    return tuple(
        (start, min(end, next_start))
        for start, end, next_start in zip(starts, ends, next_starts, strict=True)
    )


def _quantized_karaoke_boundaries(
    cue_start: object,
    cue_end: object,
    words: Sequence[Mapping[str, Any]],
) -> tuple[int, int, tuple[int, ...], tuple[int, ...]]:
    start_centiseconds = quantize_ass_centiseconds(cue_start)
    end_centiseconds = quantize_ass_centiseconds(cue_end)
    if end_centiseconds < start_centiseconds or not words:
        raise ArtifactError("Karaoke cue timestamps are invalid")

    starts: list[int] = []
    ends: list[int] = []
    previous_start: float | None = None
    for word in words:
        if not isinstance(word, Mapping):
            raise ArtifactError("Karaoke words must use mapping records")
        start = _finite_time(word.get("start"))
        end = _finite_time(word.get("end"))
        if start is None or end is None or end < start:
            raise ArtifactError("Karaoke words must have valid timestamps")
        if previous_start is not None and start < previous_start:
            raise ArtifactError("Karaoke word starts must be chronological")
        previous_start = start
        starts.append(quantize_ass_centiseconds(start))
        ends.append(quantize_ass_centiseconds(end))

    if starts[0] != start_centiseconds:
        raise ArtifactError(
            "Karaoke cue must start at the first displayed word timestamp"
        )
    if any(start > end_centiseconds for start in starts) or any(
        end > end_centiseconds for end in ends
    ):
        raise ArtifactError("Karaoke word timestamps must fit inside the cue")
    return start_centiseconds, end_centiseconds, tuple(starts), tuple(ends)


def serialize_karaoke_cue(
    cue: object,
    config: SubtitleConfig,
    *,
    palette: SubtitlePalette | None = None,
) -> str | None:
    """Compile one prepared karaoke cue without escaping generated overrides."""
    if (
        not isinstance(cue, KaraokeCue)
        or config.animation.word.text.mode is not WordAnimationMode.PROGRESSIVE
    ):
        return None
    if palette is None:
        _, palette = resolve_subtitle_palettes(config)
    if palette.highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    _validate_karaoke_cue(cue)
    return _serialize_karaoke_fragments(cue.fragments, cue.durations, palette)


def serialize_karaoke_preview_cue(
    cue: object,
    config: SubtitleConfig,
    *,
    fragments: Sequence[SubtitleDisplayFragment] | None = None,
    palette: SubtitlePalette | None = None,
) -> str | None:
    """Compile a static preview snapshot of the selected word-text mode."""
    if (
        not isinstance(cue, KaraokeCue)
        or not config.animation.word.uses_timed_highlight
    ):
        return None
    _validate_karaoke_cue(cue)
    visible_fragments = cue.fragments if fragments is None else fragments
    if not all(
        isinstance(fragment, SubtitleDisplayFragment) for fragment in visible_fragments
    ):
        raise ArtifactError("Karaoke preview fragments must use the typed contract")
    if palette is None:
        _, palette = resolve_subtitle_palettes(config)
    if config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE:
        highlighted_words = (len(cue.durations) + 1) // 2
        return _serialize_progressive_state(
            visible_fragments,
            palette,
            highlighted_words,
        )
    if config.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD:
        return _serialize_active_word_fragments(visible_fragments, palette, 0)
    return None


def _serialize_karaoke_fragments(
    fragments: Sequence[SubtitleDisplayFragment],
    durations: Sequence[int],
    palette: SubtitlePalette,
) -> str:
    """Serialize one visual line while retaining cue-global word durations."""
    highlight_color = palette.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    result = (
        "{"
        + rgba_to_ass_color_override(highlight_color, 1)
        + rgba_to_ass_color_override(palette.text_color, 2)
        + "}"
    )
    for fragment in fragments:
        if fragment.word_index is not None:
            if fragment.word_index < 0 or fragment.word_index >= len(durations):
                raise ArtifactError("Karaoke fragment word indexes are invalid")
            result += f"{{\\k{durations[fragment.word_index]}}}"
        result += escape_ass_text(fragment.text)
    return result


def serialize_active_word_events(
    cue: KaraokeCue,
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    *,
    palette: SubtitlePalette | None = None,
) -> tuple[tuple[int, int, str], ...]:
    """Split one cue into stable full-text intervals with one active word."""
    if config.animation.word.text.mode is not WordAnimationMode.ACTIVE_WORD:
        raise ArtifactError("Active-word events require active-word text mode")
    _validate_karaoke_cue(cue)
    if cue_end < cue_start:
        raise ArtifactError("Karaoke cue timestamps are invalid")
    if len(cue.active_intervals) != len(cue.durations):
        raise ArtifactError("Active-word intervals must match karaoke word count")
    if palette is None:
        _, palette = resolve_subtitle_palettes(config)

    plain_text = escape_ass_text("".join(fragment.text for fragment in cue.fragments))
    events: list[tuple[int, int, str]] = []
    cursor = cue_start
    for word_index, interval in enumerate(cue.active_intervals):
        if (
            not isinstance(interval, tuple)
            or len(interval) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in interval
            )
        ):
            raise ArtifactError("Active-word intervals must use integer boundaries")
        start, end = interval
        if start < cursor or end < start or end > cue_end:
            raise ArtifactError("Active-word intervals must be ordered inside the cue")
        if cursor < start:
            events.append((cursor, start, plain_text))
        if start < end:
            events.append(
                (start, end, _serialize_active_word_text(cue, palette, word_index))
            )
        cursor = end
    if cursor < cue_end:
        events.append((cursor, cue_end, plain_text))
    if not events:
        events.append((cue_start, cue_end, plain_text))
    return tuple(events)


def serialize_progressive_line_events(
    cue: KaraokeCue,
    fragments: Sequence[SubtitleDisplayFragment],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    *,
    palette: SubtitlePalette | None = None,
) -> tuple[tuple[int, int, str], ...]:
    """Serialize one visual line with cue-relative progressive colors.

    A standalone ASS event starts its karaoke clock at the event start.  A
    per-line event therefore cannot use only the line's local ``\\k`` tags:
    words on later visual lines would highlight at cue start.  Explicit
    line-height rendering uses stable intervals instead, changing each line's
    color state at the original cue-global word boundaries.
    """
    if config.animation.word.text.mode is not WordAnimationMode.PROGRESSIVE:
        raise ArtifactError(
            "Progressive line events require progressive word-text mode"
        )
    _validate_karaoke_cue(cue)
    if cue_end < cue_start:
        raise ArtifactError("Karaoke line timestamps are invalid")
    duration = cue_end - cue_start
    if sum(cue.durations) != duration:
        raise ArtifactError("Karaoke durations must conserve cue duration")
    if palette is None:
        _, palette = resolve_subtitle_palettes(config)

    boundaries = [cue_start]
    for word_duration in cue.durations:
        boundaries.append(boundaries[-1] + word_duration)

    events: list[tuple[int, int, str]] = []
    for activated_count, (start, end) in enumerate(
        zip(boundaries[:-1], boundaries[1:], strict=True)
    ):
        if end <= start:
            continue
        events.append(
            (
                start,
                end,
                _serialize_progressive_state(
                    fragments,
                    palette,
                    activated_count,
                    duration=end - start,
                ),
            )
        )
    if not events:
        events.append(
            (
                cue_start,
                cue_end,
                _serialize_progressive_state(
                    fragments,
                    palette,
                    len(cue.durations),
                ),
            )
        )
    return tuple(events)


def _serialize_progressive_state(
    fragments: Sequence[SubtitleDisplayFragment],
    palette: SubtitlePalette,
    activated_count: int,
    *,
    duration: int | None = None,
) -> str:
    """Compile one progressive interval for a visual line.

    The active word, when present on this line, retains a ``\\k`` tag for the
    interval's original duration.  Earlier words are statically highlighted;
    later words remain in the normal color.  This keeps the word sweep while
    ensuring a line event starts at the cue-global word boundary.
    """
    highlight_color = palette.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    if activated_count < 0:
        raise ArtifactError("Progressive activation count must be non-negative")
    normal_override = "{" + rgba_to_ass_color_override(palette.text_color, 1) + "}"
    highlight_override = "{" + rgba_to_ass_color_override(highlight_color, 1) + "}"
    progressive_setup = (
        "{"
        + rgba_to_ass_color_override(highlight_color, 1)
        + rgba_to_ass_color_override(palette.text_color, 2)
        + "}"
    )
    result = normal_override
    for fragment in fragments:
        if not isinstance(fragment, SubtitleDisplayFragment):
            raise ArtifactError("Karaoke fragments must use the typed display contract")
        if fragment.word_index is not None:
            if fragment.word_index < 0:
                raise ArtifactError("Karaoke fragment word indexes are invalid")
            if fragment.word_index < activated_count:
                result += highlight_override
            elif (
                duration is not None
                and fragment.word_index == activated_count
                and duration > 0
            ):
                result += progressive_setup + f"{{\\k{duration}}}"
            else:
                result += normal_override
        result += escape_ass_text(fragment.text)
    return result


def serialize_active_word_line_events(
    cue: KaraokeCue,
    fragments: Sequence[SubtitleDisplayFragment],
    config: SubtitleConfig,
    cue_start: int,
    cue_end: int,
    *,
    palette: SubtitlePalette | None = None,
) -> tuple[tuple[int, int, str], ...]:
    """Serialize active-word intervals for one visual line of a cue."""
    if config.animation.word.text.mode is not WordAnimationMode.ACTIVE_WORD:
        raise ArtifactError("Active-word events require active-word text mode")
    _validate_karaoke_cue(cue)
    if cue_end < cue_start or len(cue.active_intervals) != len(cue.durations):
        raise ArtifactError("Karaoke line timestamps are invalid")
    if palette is None:
        _, palette = resolve_subtitle_palettes(config)
    plain_text = escape_ass_text("".join(fragment.text for fragment in fragments))
    events: list[tuple[int, int, str]] = []
    cursor = cue_start
    for word_index, interval in enumerate(cue.active_intervals):
        if (
            not isinstance(interval, tuple)
            or len(interval) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in interval
            )
        ):
            raise ArtifactError("Active-word intervals must use integer boundaries")
        start, end = interval
        if start < cursor or end < start or end > cue_end:
            raise ArtifactError("Active-word intervals must be ordered inside the cue")
        if cursor < start:
            events.append((cursor, start, plain_text))
        if start < end:
            events.append(
                (
                    start,
                    end,
                    _serialize_active_word_fragments(
                        fragments,
                        palette,
                        word_index,
                    ),
                )
            )
        cursor = end
    if cursor < cue_end:
        events.append((cursor, cue_end, plain_text))
    if not events:
        events.append((cue_start, cue_end, plain_text))
    return tuple(events)


def _serialize_active_word_text(
    cue: KaraokeCue,
    palette: SubtitlePalette,
    active_word_index: int,
) -> str:
    return _serialize_active_word_fragments(cue.fragments, palette, active_word_index)


def _serialize_active_word_fragments(
    fragments: Sequence[SubtitleDisplayFragment],
    palette: SubtitlePalette,
    active_word_index: int,
) -> str:
    """Apply one active-word color to a fragment subset."""
    highlight_color = palette.highlight_color
    if highlight_color is None:
        raise ArtifactError("Karaoke highlight color is not resolved")
    normal_override = "{" + rgba_to_ass_color_override(palette.text_color, 1) + "}"
    highlight_override = "{" + rgba_to_ass_color_override(highlight_color, 1) + "}"
    result = normal_override
    for fragment in fragments:
        if fragment.word_index == active_word_index:
            result += (
                highlight_override + escape_ass_text(fragment.text) + normal_override
            )
        else:
            result += escape_ass_text(fragment.text)
    return result


def _validate_karaoke_cue(cue: KaraokeCue) -> None:
    durations = cue.durations
    if not durations or any(
        isinstance(duration, bool) or not isinstance(duration, int) or duration < 0
        for duration in durations
    ):
        raise ArtifactError("Karaoke durations must be non-negative integers")
    timed_indexes: list[int] = []
    for fragment in cue.fragments:
        if not isinstance(fragment, SubtitleDisplayFragment):
            raise ArtifactError("Karaoke fragments must use the typed display contract")
        if not isinstance(fragment.text, str):
            raise ArtifactError("Karaoke fragment text must be a string")
        if fragment.word_index is not None:
            if (
                isinstance(fragment.word_index, bool)
                or not isinstance(fragment.word_index, int)
                or fragment.word_index < 0
                or fragment.word_index >= len(durations)
            ):
                raise ArtifactError("Karaoke fragment word indexes are invalid")
            timed_indexes.append(fragment.word_index)
    if timed_indexes != list(range(len(durations))):
        raise ArtifactError("Karaoke fragments must map each duration exactly once")


def rgba_to_ass_color_override(value: str, channel: int) -> str:
    """Compile one semantic RGBA color into ASS color and alpha overrides."""
    if channel not in {1, 2, 3, 4}:
        raise ArtifactError("ASS color override channel must be between 1 and 4")
    ass_color = rgba_to_ass_color(value)
    alpha = ass_color[2:4]
    blue_green_red = ass_color[4:10]
    return f"\\{channel}c&H{blue_green_red}&\\{channel}a&H{alpha}&"


def escape_ass_text(text: str) -> str:
    """Escape transcription-derived dialogue text without accepting overrides."""
    escaped = text.replace("\r\n", "\n").replace("\r", "\n")
    escaped = escaped.replace("\\", "\\\\")
    escaped = escaped.replace("{", "\\{").replace("}", "\\}")
    return escaped.replace("\n", "\\N")


def _finite_time(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        return None
    return result
