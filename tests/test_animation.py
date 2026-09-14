import hashlib
import json
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import cli, transcriber
from multisubs.animation import (
    normalize_cue_animation,
    normalize_word_animation,
    sample_cue_animation,
    sample_word_animation,
)
from multisubs.ass import (
    allocate_active_word_intervals,
    allocate_karaoke_durations,
    escape_ass_text,
    rgba_to_ass_color_override,
    write_ass,
)
from multisubs.config import (
    CUE_EMPHASIS_ANIMATION_CHOICES,
    CUE_ENTRANCE_ANIMATION_CHOICES,
    CUE_EXIT_ANIMATION_CHOICES,
    DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR,
    WORD_EMPHASIS_ANIMATION_CHOICES,
    WORD_ENTRANCE_ANIMATION_CHOICES,
    WORD_EXIT_ANIMATION_CHOICES,
    parse_animation_duration,
    validate_subtitle_config,
)
from multisubs.errors import ArtifactError, ValidationError
from multisubs.layout import resolve_subtitle_config
from multisubs.models import (
    CueAnimationType,
    KaraokeCue,
    PreviewRequest,
    RelativeLength,
    SubtitleAnimationPhase,
    SubtitleDisplayFragment,
    SubtitleElementAnimation,
    SubtitlePosition,
    SubtitleWordElementAnimation,
    TranscriptDocument,
    VideoGeometry,
    WordAnimationMode,
)
from multisubs.preview import build_preview_ass
from multisubs.subtitler import (
    embed_subtitles,
    probe_video_geometry,
    validate_ffmpeg_support,
)
from multisubs.templates import get_subtitle_template

GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1920,
    render_height=1080,
    rotation_degrees=0,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(16, 9),
    duration_seconds=3.0,
)


WORD_GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1920,
    render_height=1080,
    rotation_degrees=0,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(16, 9),
    duration_seconds=12.5,
)


def _word_animation_record(text: str, start: float, end: float):
    return {"word": text, "start": start, "end": end}


@pytest.mark.parametrize("value", ["150ms", "0.15s", " 150MS "])
def test_animation_duration_accepts_explicit_units(value: str):
    assert parse_animation_duration(value) == 150


@pytest.mark.parametrize(
    "value", ["150", "9ms", "5.001s", ".15s", "10.5ms", "nanms", True]
)
def test_animation_duration_rejects_ambiguous_or_out_of_range_values(value: object):
    with pytest.raises(ValidationError, match="duration"):
        parse_animation_duration(value)


def test_explicit_duration_precedence_preserves_or_overrides_template_duration():
    template = get_subtitle_template("coral-marker").config

    inherited = validate_subtitle_config(None, defaults=template)
    same_type = validate_subtitle_config(
        None,
        defaults=template,
        animation_values={"cue_text_entrance": "fade"},
    )
    explicit = validate_subtitle_config(
        None,
        defaults=template,
        animation_values={"cue_text_entrance_duration": "0.35s"},
    )
    changed_type = validate_subtitle_config(
        None,
        defaults=template,
        animation_values={"cue_text_exit": "zoom"},
    )

    assert inherited.animation.cue.text.entrance.duration_ms == 140
    assert same_type.animation.cue.text.entrance.duration_ms == 140
    assert explicit.animation.cue.text.entrance.duration_ms == 350
    assert changed_type.animation.cue.text.exit.duration_ms == 160


@pytest.mark.parametrize(
    "values",
    [
        {"cue_text_entrance_duration": "150ms"},
        {
            "word_text_emphasis": "highlight",
            "word_text_emphasis_duration": "150ms",
        },
    ],
)
def test_duration_rejects_durationless_animation_types(values: dict[str, str]):
    with pytest.raises(ValidationError, match="cannot be used"):
        validate_subtitle_config(None, animation_values=values)


def test_four_animation_tracks_are_independently_configurable():
    config = validate_subtitle_config(
        None,
        appearance_values={"word_backdrop": "box"},
        animation_values={
            "cue_text_entrance": "fade",
            "cue_backdrop_entrance": "slide-up",
            "word_text_entrance": "pop",
            "word_backdrop_entrance": "zoom",
            "word_text_mode": "progressive",
            "word_backdrop_mode": "active-word",
        },
    )

    assert config.animation.cue.text.entrance.type is CueAnimationType.FADE
    assert config.animation.cue.backdrop.entrance.type is CueAnimationType.SLIDE_UP
    assert config.animation.word.text.entrance.type is CueAnimationType.POP
    assert config.animation.word.backdrop.entrance.type is CueAnimationType.ZOOM
    assert config.animation.word.text.mode is WordAnimationMode.PROGRESSIVE
    assert config.animation.word.backdrop.mode is WordAnimationMode.ACTIVE_WORD


@pytest.mark.parametrize(
    ("key", "phase", "animation_type", "duration_ms"),
    [
        ("cue_text_entrance", "entrance", "none", 0),
        ("cue_text_entrance", "entrance", "fade", 160),
        ("cue_text_entrance", "entrance", "slide-up", 220),
        ("cue_text_entrance", "entrance", "slide-down", 220),
        ("cue_text_entrance", "entrance", "slide-left", 220),
        ("cue_text_entrance", "entrance", "slide-right", 220),
        ("cue_text_entrance", "entrance", "pop", 220),
        ("cue_text_entrance", "entrance", "zoom", 220),
        ("cue_text_emphasis", "emphasis", "none", 0),
        ("cue_text_emphasis", "emphasis", "pulse", 600),
        ("cue_text_emphasis", "emphasis", "bounce", 600),
        ("cue_text_emphasis", "emphasis", "float", 900),
        ("cue_text_emphasis", "emphasis", "shake", 400),
        ("cue_text_emphasis", "emphasis", "flash", 500),
        ("cue_text_emphasis", "emphasis", "breathe", 1200),
        ("cue_text_exit", "exit", "none", 0),
        ("cue_text_exit", "exit", "fade", 120),
        ("cue_text_exit", "exit", "slide-up", 180),
        ("cue_text_exit", "exit", "slide-down", 180),
        ("cue_text_exit", "exit", "slide-left", 180),
        ("cue_text_exit", "exit", "slide-right", 180),
        ("cue_text_exit", "exit", "zoom", 160),
    ],
)
def test_public_cue_animation_types_expand_to_fixed_defaults(
    key: str, phase: str, animation_type: str, duration_ms: int
):
    config = validate_subtitle_config(
        None,
        animation_values={key: animation_type},
    )

    resolved = getattr(config.animation.cue.text, phase)
    assert resolved.type.value == animation_type
    assert resolved.duration_ms == duration_ms


@pytest.mark.parametrize(
    ("key", "phase", "animation_type", "duration_ms"),
    [
        ("word_text_entrance", "entrance", "none", 0),
        ("word_text_entrance", "entrance", "fade", 100),
        ("word_text_entrance", "entrance", "slide-up", 140),
        ("word_text_entrance", "entrance", "slide-down", 140),
        ("word_text_entrance", "entrance", "pop", 160),
        ("word_text_entrance", "entrance", "zoom", 140),
        ("word_text_exit", "exit", "none", 0),
        ("word_text_exit", "exit", "fade", 100),
        ("word_text_exit", "exit", "slide-up", 120),
        ("word_text_exit", "exit", "slide-down", 120),
        ("word_text_exit", "exit", "zoom", 100),
    ],
)
def test_public_word_motion_types_expand_to_fixed_defaults(
    key: str, phase: str, animation_type: str, duration_ms: int
):
    config = validate_subtitle_config(None, animation_values={key: animation_type})

    resolved = getattr(config.animation.word.text, phase)
    assert resolved.type.value == animation_type
    assert resolved.duration_ms == duration_ms


@pytest.mark.parametrize(
    ("animation_type", "duration_ms"),
    [
        ("none", 0),
        ("highlight", 0),
        ("pulse", 240),
        ("bounce", 240),
    ],
)
def test_public_word_emphasis_types_expand_to_fixed_defaults(
    animation_type: str, duration_ms: int
):
    config = validate_subtitle_config(
        None,
        animation_values={"word_text_emphasis": animation_type},
    )

    assert config.animation.word.text.emphasis.type.value == animation_type
    assert config.animation.word.text.emphasis.duration_ms == duration_ms


def test_word_phases_fit_inside_short_aligned_interval():
    animation = SubtitleWordElementAnimation(
        entrance=SubtitleAnimationPhase(CueAnimationType.POP, 160),
        emphasis=SubtitleAnimationPhase(CueAnimationType.BOUNCE, 240),
        exit=SubtitleAnimationPhase(CueAnimationType.FADE, 100),
    )

    timing = normalize_word_animation(100, 110, animation)

    assert timing.entrance_duration + timing.exit_duration == 10
    assert timing.emphasis_duration == 0
    assert timing.entrance_end == timing.exit_start
    assert timing.shortened is True


@pytest.mark.parametrize(
    ("animation_type", "at", "expected"),
    [
        ("pulse", 30, (0, 0, 0, 106)),
        ("bounce", 30, (0, 0, -8, 100)),
        ("float", 45, (0, 0, -5, 100)),
        ("shake", 8, (0, 5, 0, 100)),
        ("flash", 25, (89, 0, 0, 100)),
    ],
)
def test_every_cue_emphasis_reaches_its_fixed_peak_and_settles(
    animation_type: str,
    at: int,
    expected: tuple[int, int, int, int],
):
    config = validate_subtitle_config(
        None,
        animation_values={"cue_text_emphasis": animation_type},
    )
    animation = config.animation.cue.text
    timing = normalize_cue_animation(0, 200, animation)

    peak = sample_cue_animation(animation, timing, at, font_size=40)
    settled = sample_cue_animation(
        animation,
        timing,
        timing.emphasis_end,
        font_size=40,
    )

    assert (
        peak.fade_alpha,
        peak.offset_x,
        peak.offset_y,
        peak.scale_percent,
    ) == expected
    assert settled.fade_alpha == 0
    assert (settled.offset_x, settled.offset_y) == (0, 0)
    assert settled.scale_percent == 100


@pytest.mark.parametrize(
    ("phase", "animation_type", "expected"),
    [
        ("entrance", "fade", (255, 0, 0, 100)),
        ("entrance", "slide-up", (0, 0, 14, 100)),
        ("entrance", "slide-down", (0, 0, -14, 100)),
        ("entrance", "pop", (0, 0, 0, 76)),
        ("entrance", "zoom", (0, 0, 0, 88)),
        ("emphasis", "pulse", (0, 0, 0, 108)),
        ("emphasis", "bounce", (0, 0, -8, 100)),
        ("exit", "fade", (255, 0, 0, 100)),
        ("exit", "slide-up", (0, 0, -14, 100)),
        ("exit", "slide-down", (0, 0, 14, 100)),
        ("exit", "zoom", (255, 0, 0, 88)),
    ],
)
def test_every_word_motion_reaches_its_fixed_extreme(
    phase: str,
    animation_type: str,
    expected: tuple[int, int, int, int],
):
    config = validate_subtitle_config(
        None,
        animation_values={f"word_text_{phase}": animation_type},
    )
    animation = config.animation.word.text
    timing = normalize_word_animation(0, 100, animation)
    at = (
        0
        if phase == "entrance"
        else timing.entrance_end + animation.emphasis.duration_ms // 20
        if phase == "emphasis"
        else 100
    )

    state = sample_word_animation(animation, timing, at, font_size=40)

    assert (
        state.fade_alpha,
        state.offset_x,
        state.offset_y,
        state.scale_percent,
    ) == expected
    if phase == "emphasis":
        settled = sample_word_animation(
            animation,
            timing,
            timing.emphasis_end,
            font_size=40,
        )
        assert (
            settled.fade_alpha,
            settled.offset_x,
            settled.offset_y,
            settled.scale_percent,
        ) == (0, 0, 0, 100)


def test_short_cue_phases_are_scaled_without_changing_cue_bounds():
    cue = SubtitleElementAnimation(
        entrance=SubtitleAnimationPhase(CueAnimationType.FADE, 160),
        exit=SubtitleAnimationPhase(CueAnimationType.FADE, 120),
    )

    timing = normalize_cue_animation(100, 110, cue)

    assert timing.cue_start == 100
    assert timing.cue_end == 110
    assert timing.entrance_duration + timing.exit_duration == 10
    assert timing.entrance_end == timing.exit_start
    assert timing.shortened is True


@pytest.mark.parametrize(
    ("cue_duration", "entrance_duration", "exit_duration", "shortened"),
    [
        (100, 16, 12, False),
        (28, 16, 12, False),
        (20, 11, 9, True),
        (10, 6, 4, True),
        (1, 1, 0, True),
        (0, 0, 0, True),
    ],
)
def test_phase_normalization_is_ordered_and_bounded(
    cue_duration: int,
    entrance_duration: int,
    exit_duration: int,
    shortened: bool,
):
    cue = SubtitleElementAnimation(
        entrance=SubtitleAnimationPhase(CueAnimationType.FADE, 160),
        exit=SubtitleAnimationPhase(CueAnimationType.FADE, 120),
    )

    timing = normalize_cue_animation(40, 40 + cue_duration, cue)

    assert timing.entrance_duration == entrance_duration
    assert timing.exit_duration == exit_duration
    assert timing.cue_start <= timing.entrance_end <= timing.exit_start
    assert timing.exit_start <= timing.cue_end
    assert timing.shortened is shortened


def test_zero_length_cue_uses_stable_final_state():
    cue = SubtitleElementAnimation(
        entrance=SubtitleAnimationPhase(CueAnimationType.POP, 220),
        exit=SubtitleAnimationPhase(CueAnimationType.ZOOM, 160),
    )
    timing = normalize_cue_animation(50, 50, cue)

    assert sample_cue_animation(cue, timing, 50, font_size=40).scale_percent == 100
    assert timing.shortened is True


def test_slide_and_pop_states_follow_documented_directions_and_scales():
    slide = SubtitleElementAnimation(
        entrance=SubtitleAnimationPhase(CueAnimationType.SLIDE_RIGHT, 220),
    )
    slide_timing = normalize_cue_animation(0, 100, slide)
    assert sample_cue_animation(slide, slide_timing, 0, font_size=40).offset_x == -30
    assert sample_cue_animation(slide, slide_timing, 22, font_size=40).offset_x == 0

    pop = SubtitleElementAnimation(
        entrance=SubtitleAnimationPhase(CueAnimationType.POP, 220),
    )
    pop_timing = normalize_cue_animation(0, 100, pop)
    assert sample_cue_animation(pop, pop_timing, 0, font_size=40).scale_percent == 76
    assert sample_cue_animation(pop, pop_timing, 13, font_size=40).scale_percent == 112
    assert sample_cue_animation(pop, pop_timing, 22, font_size=40).scale_percent == 100


@pytest.mark.parametrize(
    ("animation_type", "entrance_offset", "exit_offset"),
    [
        (CueAnimationType.SLIDE_UP, (0, 30), (0, -30)),
        (CueAnimationType.SLIDE_DOWN, (0, -30), (0, 30)),
        (CueAnimationType.SLIDE_LEFT, (30, 0), (-30, 0)),
        (CueAnimationType.SLIDE_RIGHT, (-30, 0), (30, 0)),
    ],
)
def test_slide_names_describe_visible_travel_direction(
    animation_type: CueAnimationType,
    entrance_offset: tuple[int, int],
    exit_offset: tuple[int, int],
):
    cue = SubtitleElementAnimation(
        entrance=SubtitleAnimationPhase(animation_type, 220),
        exit=SubtitleAnimationPhase(animation_type, 180),
    )
    timing = normalize_cue_animation(0, 100, cue)

    entrance = sample_cue_animation(cue, timing, 0, font_size=40)
    exit_state = sample_cue_animation(cue, timing, 100, font_size=40)

    assert (entrance.offset_x, entrance.offset_y) == entrance_offset
    assert (exit_state.offset_x, exit_state.offset_y) == exit_offset


def test_animation_cli_replaces_removed_karaoke_flags(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    request = cli._build_request(
        parser.parse_args(
            [
                "-i",
                str(input_path),
                "--animation-cue-text-entrance",
                "slide-up",
                "--animation-cue-text-exit",
                "fade",
                "--animation-word-text-emphasis",
                "highlight",
                "--animation-word-text-mode",
                "active-word",
            ]
        ),
        parser,
    )

    assert request.subtitle_config.animation.cue.text.entrance.type.value == "slide-up"
    assert request.subtitle_config.animation.cue.text.exit.type.value == "fade"
    assert (
        request.subtitle_config.animation.word.text.mode
        is WordAnimationMode.ACTIVE_WORD
    )
    for removed in (
        "--karaoke",
        "--no-karaoke",
        "--karaoke-mode",
        "--karaoke-highlight-color",
        "--animation-entrance",
        "--animation-exit",
        "--animation-word",
        "--animation-cue-entrance",
        "--animation-word-emphasis",
        "--animation-word-mode",
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(["-i", str(input_path), removed])

    help_text = parser.format_help()
    assert (
        "--animation-cue-text-entrance "
        "{none,fade,slide-up,slide-down,slide-left,slide-right,pop,zoom}" in help_text
    )
    assert (
        "--animation-cue-text-exit "
        "{none,fade,slide-up,slide-down,slide-left,slide-right,zoom}" in help_text
    )
    assert (
        "--animation-cue-text-emphasis "
        "{none,pulse,bounce,float,shake,flash,breathe}" in help_text
    )
    assert (
        "--animation-word-text-entrance {none,fade,slide-up,slide-down,pop,zoom}"
        in help_text
    )
    assert (
        "--animation-word-text-emphasis "
        "{none,pulse,bounce,float,breathe,highlight}" in help_text
    )
    assert (
        "--animation-word-text-exit {none,fade,slide-up,slide-down,zoom}" in help_text
    )
    assert "--animation-word-text-mode {progressive,active-word}" in help_text
    assert "--animation-word-backdrop-mode {progressive,active-word}" in help_text
    assert "--word-backdrop {none,outline,box}" in help_text
    assert "--word-backdrop-color COLOR" in help_text
    assert "--word-backdrop-size LENGTH" in help_text


def test_animation_template_branches_can_be_disabled_independently():
    template = get_subtitle_template("focus-marker").config

    without_word_emphasis = validate_subtitle_config(
        None,
        defaults=template,
        animation_values={"word_text_emphasis": "none"},
    )
    without_cue = validate_subtitle_config(
        None,
        defaults=template,
        animation_values={
            "cue_text_entrance": "none",
            "cue_text_emphasis": "none",
            "cue_text_exit": "none",
            "cue_backdrop_entrance": "none",
            "cue_backdrop_emphasis": "none",
            "cue_backdrop_exit": "none",
        },
    )

    assert without_word_emphasis.animation.word.text.emphasis.type.value == "none"
    assert (
        without_word_emphasis.animation.word.text.entrance
        == template.animation.word.text.entrance
    )
    assert (
        without_word_emphasis.animation.word.text.exit
        == template.animation.word.text.exit
    )
    assert without_word_emphasis.animation.cue == template.animation.cue
    assert without_cue.animation.word == template.animation.word
    assert not without_cue.animation.cue.text.enabled
    assert not without_cue.animation.cue.backdrop.enabled


@pytest.mark.parametrize(
    "options",
    [
        ["--animation-cue-text-entrance", "pop"],
        ["--template", "bold-headline"],
        [
            "--template",
            "focus-marker",
            "--animation-word-text-entrance",
            "none",
            "--animation-word-text-emphasis",
            "none",
            "--word-backdrop",
            "none",
        ],
    ],
)
def test_cue_animation_remains_available_for_translation(
    tmp_path: Path,
    options: list[str],
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    request = cli._build_request(
        parser.parse_args(
            [
                "-i",
                str(input_path),
                "--task",
                "translate",
                "--model",
                "medium",
                *options,
            ]
        ),
        parser,
    )

    assert request.subtitle_config.animation.word.text.emphasis.type.value == "none"


@pytest.mark.parametrize(
    "options",
    [
        ["--animation-word-text-entrance", "fade"],
        ["--animation-word-text-emphasis", "highlight"],
        ["--word-backdrop", "box"],
        ["--animation-word-text-emphasis", "pulse"],
        ["--animation-word-text-exit", "fade"],
    ],
)
def test_every_word_animation_phase_rejects_translation(
    tmp_path: Path,
    options: list[str],
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        cli._build_request(
            parser.parse_args(
                [
                    "-i",
                    str(input_path),
                    "--task",
                    "translate",
                    "--model",
                    "medium",
                    *options,
                ]
            ),
            parser,
        )


def test_ass_compiles_bounded_motion_scale_and_fade_events(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        animation_values={"cue_text_entrance": "pop", "cue_text_exit": "zoom"},
    )
    path = tmp_path / "animated.ass"

    write_ass(
        path, [{"start": 0.0, "end": 1.0, "text": "Safe {text}"}], config, GEOMETRY
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert 3 <= len(dialogue) <= 5
    assert any(r"\fscx76\fscy76" in line for line in dialogue)
    assert any(r"\fscx112\fscy112" in line for line in dialogue)
    assert any(r"\fade(" in line for line in dialogue)
    text_events = [line for line in dialogue if r"\p1" not in line]
    assert text_events
    assert all(r"Safe \{text\}" in line for line in text_events)


def test_animation_alpha_stays_separate_from_component_opacity(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={"opacity": "50%"},
        animation_values={"cue_text_emphasis": "flash"},
    )
    path = tmp_path / "opacity-flash.ass"

    write_ass(path, [{"start": 0.0, "end": 1.0, "text": "flash"}], config, GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert "&H7FFFFFFF" in content
    assert r"\fade(" in content
    assert r"{\alpha" not in content


def test_ass_compiles_word_local_entrance_emphasis_and_exit(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        animation_values={
            "word_text_entrance": "pop",
            "word_text_emphasis": "bounce",
            "word_text_exit": "fade",
        },
    )
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("one", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("two", 1),
        ),
        durations=(50, 50),
        active_intervals=((0, 40), (50, 100)),
    )
    path = tmp_path / "word-animation.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "one two", "_karaoke_cue": cue}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert any(r"\fscx76" in line for line in dialogue)
    assert any(r"\move(" in line for line in dialogue)
    assert any(r"\fade(" in line for line in dialogue)
    assert all(line.count(r"\move(") + line.count(r"\pos(") <= 1 for line in dialogue)
    assert all("one two" not in line for line in dialogue)


@pytest.mark.parametrize(
    ("mode", "expected_intervals"),
    [
        ("active-word", ((10, 40), (50, 80))),
        ("progressive", ((10, 100), (50, 100))),
    ],
)
def test_word_box_emphasis_uses_measured_layers_and_selected_mode(
    tmp_path: Path,
    mode: str,
    expected_intervals: tuple[tuple[int, int], ...],
):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": "DejaVu Sans",
            "backdrop": "none",
            "word_backdrop": "box",
            "word_backdrop_color": "#FF0000",
        },
        relative_values={
            "font_size": "40px",
            "word_backdrop_size": "6px",
        },
        animation_values={
            "word_backdrop_mode": mode,
        },
    )
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("one", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("two", 1),
        ),
        durations=(40, 60),
        active_intervals=((10, 40), (50, 80)),
    )
    path = tmp_path / f"word-box-{mode}.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "one two", "_karaoke_cue": cue}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    boxes = [line for line in dialogue if r"\1c&H0000FF&" in line and r"\p1" in line]
    assert len(boxes) == len(expected_intervals)
    for line, (start, end) in zip(boxes, expected_intervals, strict=True):
        assert (
            f",0:00:{start // 100:02d}.{start % 100:02d},"
            f"0:00:{end // 100:02d}.{end % 100:02d},"
        ) in line
        assert line.startswith("Dialogue: 1,")
        assert r"\an7\pos(" in line
        assert "m 0 0 l " in line
    text_events = [line for line in dialogue if line.startswith("Dialogue: 2,")]
    assert text_events
    assert all(r"\p1" not in line for line in text_events)


def test_word_box_style_can_be_overridden_independently():
    config = validate_subtitle_config(
        None,
        appearance_values={
            "word_backdrop": "box",
            "word_backdrop_color": "#12345678",
        },
        relative_values={"word_backdrop_size": "9%"},
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "active-word",
            "word_text_highlight_color": "#ABCDEF",
        },
    )

    assert config.style.word_backdrop.color == "#12345678"
    assert isinstance(config.style.word_backdrop.size, RelativeLength)
    assert config.style.word_backdrop.size.original == "9%"
    assert config.style.typography.highlight_color == "#ABCDEF"
    assert config.style.word_backdrop.kind.value == "box"
    assert config.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD


def test_active_word_outline_replaces_cue_outline_for_that_fragment(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": "DejaVu Sans",
            "font_weight": "black",
            "backdrop": "outline",
            "backdrop_color": "#000000",
            "word_backdrop": "outline",
            "word_backdrop_color": "#FF0000",
        },
        relative_values={
            "font_size": "40px",
            "outline_weight": "3px",
            "word_backdrop_size": "5px",
        },
        animation_values={"word_backdrop_mode": "active-word"},
    )
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("one", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("two", 1),
        ),
        durations=(40, 60),
        active_intervals=((10, 40), (50, 80)),
    )
    path = tmp_path / "word-outline.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "one two", "_karaoke_cue": cue}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    cue_outlines_for_one = [
        line
        for line in dialogue
        if line.startswith("Dialogue: 0,")
        and r"\3c&H000000&" in line
        and line.endswith("one")
    ]
    word_outlines_for_one = [
        line
        for line in dialogue
        if line.startswith("Dialogue: 1,")
        and r"\3c&H0000FF&" in line
        and line.endswith("one")
    ]
    assert len(cue_outlines_for_one) == 2
    assert any(",0:00:00.00,0:00:00.10," in line for line in cue_outlines_for_one)
    assert any(",0:00:00.40,0:00:01.00," in line for line in cue_outlines_for_one)
    assert len(word_outlines_for_one) == 1
    assert ",0:00:00.10,0:00:00.40," in word_outlines_for_one[0]
    assert all(r"{\b900\1a&HFF&" in line for line in cue_outlines_for_one)
    assert r"{\b900\1a&HFF&" in word_outlines_for_one[0]


def test_cue_outline_reuses_word_fragment_positions(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": "DejaVu Sans",
            "font_weight": "black",
            "backdrop": "outline",
            "backdrop_color": "#000000",
        },
        relative_values={
            "font_size": "40px",
            "outline_weight": "4px",
            "shadow_weight": "0px",
        },
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "progressive",
        },
    )
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("Ele", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("tem...", 1),
        ),
        durations=(50, 50),
        active_intervals=((10, 40), (50, 80)),
    )
    path = tmp_path / "fragmented-cue-outline.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "Ele tem...", "_karaoke_cue": cue}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert not any(
        line.startswith("Dialogue: 0,") and line.endswith("Ele tem...")
        for line in dialogue
    )
    for word in ("Ele", "tem..."):
        outline = next(
            line
            for line in dialogue
            if line.startswith("Dialogue: 0,") and line.endswith(word)
        )
        text_events = [
            line
            for line in dialogue
            if line.startswith("Dialogue: 2,") and line.endswith(word)
        ]
        outline_position = re.search(r"\\pos\((\d+),(\d+)\)", outline)
        assert outline_position is not None
        assert r"{\b900\1a&HFF&" in outline
        assert text_events
        for event in text_events:
            text_position = re.search(r"\\pos\((\d+),(\d+)\)", event)
            assert text_position is not None
            assert text_position.groups() == outline_position.groups()


def test_cue_outline_follows_cue_and_word_text_motion(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": "DejaVu Sans",
            "font_weight": "bold",
            "backdrop": "outline",
            "backdrop_color": "#000000",
        },
        relative_values={
            "font_size": "40px",
            "outline_weight": "4px",
            "shadow_weight": "0px",
        },
        animation_values={
            "cue_text_entrance": "pop",
            "cue_backdrop_entrance": "slide-right",
            "word_text_emphasis": "bounce",
        },
    )
    cue = KaraokeCue(
        fragments=(SubtitleDisplayFragment("Example", 0),),
        durations=(100,),
        active_intervals=((0, 100),),
    )
    path = tmp_path / "animated-outline.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "Example", "_karaoke_cue": cue}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    outline_events = [line for line in dialogue if line.startswith("Dialogue: 0,")]
    text_events = [line for line in dialogue if line.startswith("Dialogue: 2,")]

    def timing(line: str) -> tuple[str, str]:
        fields = line.split(",", 3)
        return fields[1], fields[2]

    def motion(line: str) -> tuple[str, ...]:
        return tuple(
            re.findall(
                r"\\(?:an\d|pos\([^)]*\)|move\([^)]*\)|fsc[xy]\d+|"
                r"t\([^}]*\)|fade\([^)]*\))",
                line,
            )
        )

    assert outline_events
    assert text_events
    outlines_by_timing = {timing(line): motion(line) for line in outline_events}
    for event in text_events:
        assert timing(event) in outlines_by_timing
        assert motion(event) == outlines_by_timing[timing(event)]


def test_positioned_words_follow_the_cue_global_scale_origin(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        animation_values={
            "cue_text_entrance": "pop",
            "word_text_emphasis": "bounce",
        },
    )
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("left", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("right", 1),
        ),
        durations=(50, 50),
        active_intervals=((0, 40), (50, 100)),
    )
    path = tmp_path / "cue-origin.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "left right", "_karaoke_cue": cue}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    for word in ("left", "right"):
        initial = next(
            line for line in dialogue if line.endswith(word) and ",0:00:00.00," in line
        )
        stable = next(
            line
            for line in dialogue
            if line.endswith(word) and r"\pos(" in line and r"\fscx" not in line
        )
        initial_match = re.search(r"\\(?:move|pos)\((\d+)", initial)
        stable_match = re.search(r"\\pos\((\d+)", stable)
        assert initial_match is not None
        assert stable_match is not None
        initial_x = int(initial_match.group(1))
        stable_x = int(stable_match.group(1))

        assert abs(initial_x - 960) < abs(stable_x - 960)


@pytest.mark.parametrize(
    "text",
    [
        r"literal {\\an7} and \\ path",
        "comma, newline\nsecond line",
        "ação العربية हिन्दी 日本語 👩🏽‍💻 e\u0301",
    ],
)
def test_animated_ass_keeps_transcript_content_escaped(tmp_path: Path, text: str):
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        animation_values={"cue_text_entrance": "pop", "cue_text_exit": "fade"},
    )
    path = tmp_path / "escaped.ass"

    write_ass(path, [{"start": 0.0, "end": 1.0, "text": text}], config, GEOMETRY)

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert dialogue
    assert all(escape_ass_text(text) in line for line in dialogue)


@pytest.mark.parametrize("word_mode", ["progressive", "active-word"])
def test_word_intervals_sample_cue_animation_without_restarting(
    tmp_path: Path,
    word_mode: str,
):
    fragments = (
        SubtitleDisplayFragment("one", 0),
        SubtitleDisplayFragment(" "),
        SubtitleDisplayFragment("two", 1),
    )
    karaoke_cue = KaraokeCue(
        fragments=fragments,
        durations=(50, 50),
        active_intervals=((0, 40), (50, 90)),
    )
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        animation_values={
            "cue_text_entrance": "pop",
            "word_text_emphasis": "highlight",
            "word_text_mode": word_mode,
        },
    )
    path = tmp_path / f"{word_mode}.ass"

    write_ass(
        path,
        [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "one two",
                "_karaoke_cue": karaoke_cue,
            }
        ],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    initial_scale_events = [line for line in dialogue if r"\fscx76\fscy76" in line]
    assert len(initial_scale_events) == 2
    assert all(",0:00:00.00," in line for line in initial_scale_events)
    assert all(
        r"\fscx76\fscy76" not in line for line in dialogue if ",0:00:00.00," not in line
    )


def test_animation_event_count_is_bounded_by_words_and_phase_boundaries(
    tmp_path: Path,
):
    word_count = 10
    fragments = tuple(
        fragment
        for index in range(word_count)
        for fragment in (
            SubtitleDisplayFragment(f"word{index}", index),
            SubtitleDisplayFragment(" " if index < word_count - 1 else ""),
        )
    )
    karaoke_cue = KaraokeCue(
        fragments=fragments,
        durations=(10,) * word_count,
        active_intervals=tuple(
            (index * 10, (index + 1) * 10) for index in range(word_count)
        ),
    )
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        animation_values={
            "cue_text_entrance": "pop",
            "cue_text_exit": "fade",
            "word_text_emphasis": "highlight",
            "word_text_mode": "active-word",
        },
    )
    path = tmp_path / "bounded.ass"

    write_ass(
        path,
        [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "".join(fragment.text for fragment in fragments),
                "_karaoke_cue": karaoke_cue,
            }
        ],
        config,
        GEOMETRY,
    )

    dialogue_count = sum(
        line.startswith("Dialogue:")
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    assert dialogue_count <= word_count * 6


def test_slide_events_have_at_most_one_positioning_tag(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        animation_values={
            "cue_text_entrance": "slide-up",
            "cue_text_exit": "slide-left",
        },
    )
    path = tmp_path / "slide.ass"
    write_ass(path, [{"start": 0.0, "end": 1.0, "text": "moving"}], config, GEOMETRY)

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert any(r"\move(" in line for line in dialogue)
    assert all(line.count(r"\move(") + line.count(r"\pos(") == 1 for line in dialogue)


@pytest.mark.parametrize("position", list(SubtitlePosition))
def test_slide_animation_centers_boxed_text_in_each_native_anchor(
    tmp_path: Path,
    position: SubtitlePosition,
):
    relative_values = {
        "margin_left": "10px",
        "margin_right": "10px",
    }
    if position.value.startswith("top-"):
        relative_values["margin_top"] = "10px"
    elif position.value.startswith("bottom-"):
        relative_values["margin_bottom"] = "10px"
    config = validate_subtitle_config(
        None,
        position=position,
        relative_values=relative_values,
        animation_values={"cue_text_entrance": "slide-up"},
    )
    path = tmp_path / f"{position.value}.ass"

    write_ass(path, [{"start": 0.0, "end": 1.0, "text": "anchor"}], config, GEOMETRY)

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert dialogue
    assert all(line.count(r"\move(") + line.count(r"\pos(") == 1 for line in dialogue)
    text_events = [line for line in dialogue if r"\p1" not in line]
    assert all(r"\an5" in line for line in text_events)


def test_shared_box_and_visual_lines_use_the_same_pop_state(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        position="bottom-left",
        appearance_values={"font": "DejaVu Sans", "backdrop": "box"},
        relative_values={
            "font_size": "40px",
            "line_height": "50px",
            "outline_weight": "5px",
            "shadow_weight": "0px",
            "margin_left": "20px",
            "margin_right": "20px",
            "margin_bottom": "20px",
            "max_width": "300px",
            "max_height": "160px",
        },
        animation_values={
            "cue_text_entrance": "pop",
            "cue_backdrop_entrance": "pop",
        },
    )
    path = tmp_path / "box-pop.ass"

    write_ass(
        path,
        [{"start": 0.0, "end": 1.0, "text": "First line\nSecond line"}],
        config,
        GEOMETRY,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    first_interval = [line for line in dialogue if ",0:00:00.00,0:00:00.13," in line]
    assert len(first_interval) == 3
    assert (
        sum(
            ",Positioned," in line and line.startswith("Dialogue: 0,")
            for line in first_interval
        )
        == 1
    )
    assert sum(line.startswith("Dialogue: 2,") for line in first_interval) == 2
    assert all(r"\fscx76\fscy76" in line for line in first_interval)
    assert all(r"\fscx112\fscy112" in line for line in first_interval)
    backdrop = next(line for line in first_interval if line.startswith("Dialogue: 0,"))
    assert r"\an7\pos(" in backdrop
    assert "m 0 0 l " in backdrop


def test_focus_marker_animated_box_uses_local_top_left_geometry(tmp_path: Path):
    config = get_subtitle_template("focus-marker").config
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("Ele", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("tem...", 1),
        ),
        durations=(40, 60),
        active_intervals=((0, 40), (40, 100)),
    )
    path = tmp_path / "focus-marker.ass"

    write_ass(
        path,
        [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Ele tem...",
                "_karaoke_cue": cue,
            }
        ],
        config,
        GEOMETRY,
    )

    backdrops = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: 1,") and r"\p1" in line
    ]
    assert backdrops
    assert all(r"\an7\pos(" in line for line in backdrops)
    assert all("m 0 0 l " in line for line in backdrops)
    assert all(r"\an2" not in line for line in backdrops)


def test_preview_suppresses_cue_motion_but_keeps_template_identity(tmp_path: Path):
    config = get_subtitle_template("bold-headline").config
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    request = PreviewRequest(
        input_path=input_path,
        output_dir=tmp_path,
        subtitle_config=config,
        preview_at=0.0,
        preview_text="Static preview",
        guides=False,
        subtitle_template_requested="bold-headline",
        subtitle_template_resolved="bold-headline",
    )
    path = tmp_path / "preview.ass"

    build_preview_ass(path, request, GEOMETRY, 0.0)

    content = path.read_text(encoding="utf-8")
    assert r"\move(" not in content
    assert r"\fade(" not in content
    assert r"\fscx76" not in content


def test_json_records_unified_animation_metadata_and_shortened_cues(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source,
        language="pt",
        task="transcribe",
        model_name="turbo",
        full_text="Curto",
        segments=({"start": 0.0, "end": 0.1, "text": "Curto", "words": []},),
    )
    config = validate_subtitle_config(
        None,
        animation_values={"cue_text_entrance": "fade", "cue_text_exit": "fade"},
    )

    json_path, _, _ = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        config,
        geometry=GEOMETRY,
    )

    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    rendering = payload["metadata"]["rendering"]
    assert payload["schema_version"] == 3
    assert "effects" not in rendering
    assert rendering["animation"] == {
        "cue": {
            "text": {
                "active": True,
                "entrance": {"type": "fade", "duration_ms": 160},
                "emphasis": {"type": "none"},
                "exit": {"type": "fade", "duration_ms": 120},
            },
            "backdrop": {
                "active": True,
                "entrance": {"type": "none"},
                "emphasis": {"type": "none"},
                "exit": {"type": "none"},
            },
            "shortened_cues": {"text": 1, "backdrop": 0},
        },
        "word": {
            "text": {
                "active": False,
                "mode": "active-word",
                "entrance": {"type": "none"},
                "emphasis": {"type": "none"},
                "exit": {"type": "none"},
            },
            "backdrop": {
                "active": False,
                "mode": "active-word",
                "entrance": {"type": "none"},
                "emphasis": {"type": "none"},
                "exit": {"type": "none"},
            },
            "normal_color": "#FFFFFF",
            "highlight_color": None,
            "shortened_words": {"text": 0, "backdrop": 0},
            "fallback_cues": 0,
        },
    }


def test_json_records_word_box_behavior_and_style_separately(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source,
        language="pt",
        task="transcribe",
        model_name="turbo",
        full_text="Caixa ativa",
        segments=(
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Caixa ativa",
                "words": [
                    {"word": "Caixa", "start": 0.0, "end": 0.4},
                    {"word": "ativa", "start": 0.5, "end": 1.0},
                ],
            },
        ),
    )
    config = validate_subtitle_config(
        None,
        appearance_values={
            "word_backdrop": "box",
            "word_backdrop_color": "#FEDCBA80",
        },
        relative_values={"word_backdrop_size": "10%"},
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "progressive",
            "word_backdrop_mode": "progressive",
            "word_text_highlight_color": "#102030",
        },
    )

    json_path, _, _ = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        config,
        geometry=GEOMETRY,
    )

    rendering = json.loads(Path(json_path).read_text(encoding="utf-8"))["metadata"][
        "rendering"
    ]
    assert rendering["animation"]["word"]["text"] == {
        "active": True,
        "mode": "progressive",
        "entrance": {"type": "none"},
        "emphasis": {"type": "highlight"},
        "exit": {"type": "none"},
    }
    assert rendering["animation"]["word"]["backdrop"]["active"] is True
    assert rendering["animation"]["word"]["backdrop"]["mode"] == "progressive"
    assert rendering["animation"]["word"]["normal_color"] == "#FFFFFF"
    assert rendering["animation"]["word"]["highlight_color"] == "#102030"
    assert rendering["requested"]["word_backdrop_type"] == "box"
    assert rendering["requested"]["word_backdrop_size"] == "10%"
    assert rendering["resolved"]["word_backdrop_size"] == 4
    assert rendering["opacity"]["base_colors"]["word_backdrop"] == "#FEDCBA80"
    assert "word_backdrop" not in rendering["animation"]["word"]


def test_json_records_word_phases_shortening_and_fallback(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source,
        language="pt",
        task="transcribe",
        model_name="turbo",
        full_text="Short fallback",
        segments=(
            {
                "start": 0.0,
                "end": 0.1,
                "text": "Short",
                "words": [{"word": "Short", "start": 0.0, "end": 0.1}],
            },
            {
                "start": 0.2,
                "end": 0.8,
                "text": "fallback",
                "words": [],
            },
        ),
    )
    config = validate_subtitle_config(
        None,
        animation_values={
            "word_text_entrance": "pop",
            "word_text_emphasis": "bounce",
            "word_text_exit": "fade",
        },
    )

    json_path, srt_path, _ = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        config,
        geometry=GEOMETRY,
    )

    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    word = payload["metadata"]["rendering"]["animation"]["word"]
    assert word == {
        "text": {
            "active": True,
            "mode": "active-word",
            "entrance": {"type": "pop", "duration_ms": 160},
            "emphasis": {"type": "bounce", "duration_ms": 240},
            "exit": {"type": "fade", "duration_ms": 100},
        },
        "backdrop": {
            "active": False,
            "mode": "active-word",
            "entrance": {"type": "none"},
            "emphasis": {"type": "none"},
            "exit": {"type": "none"},
        },
        "normal_color": "#FFFFFF",
        "highlight_color": None,
        "shortened_words": {"text": 1, "backdrop": 0},
        "fallback_cues": 1,
    }
    assert "\\fsc" not in Path(srt_path).read_text(encoding="utf-8")


@pytest.mark.integration
@pytest.mark.parametrize("canvas", [(320, 180), (180, 320)])
def test_ffmpeg_libass_renders_every_cue_animation_in_both_orientations(
    tmp_path: Path,
    canvas: tuple[int, int],
):
    if shutil.which("ffmpeg") is None or shutil.which("fc-match") is None:
        pytest.skip("FFmpeg and fontconfig are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))
    font_match = subprocess.run(
        ["fc-match", "-f", "%{family}", "DejaVu Sans"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if "DejaVu Sans" not in font_match:
        pytest.skip("The controlled DejaVu Sans font is not available")

    width, height = canvas
    geometry = VideoGeometry(
        stream_index=0,
        coded_width=width,
        coded_height=height,
        render_width=width,
        render_height=height,
        rotation_degrees=0,
        sample_aspect_ratio=Fraction(1, 1),
        display_aspect_ratio=Fraction(width, height),
        duration_seconds=1.0,
    )
    cases = (
        [
            ("cue_text_entrance", animation_type)
            for animation_type in CUE_ENTRANCE_ANIMATION_CHOICES
            if animation_type != "none"
        ]
        + [
            ("cue_text_emphasis", animation_type)
            for animation_type in CUE_EMPHASIS_ANIMATION_CHOICES
            if animation_type != "none"
        ]
        + [
            ("cue_text_exit", animation_type)
            for animation_type in CUE_EXIT_ANIMATION_CHOICES
            if animation_type != "none"
        ]
    )
    frame_size = width * height

    for phase, animation_type in cases:
        config = validate_subtitle_config(
            None,
            appearance_values={
                "font": "DejaVu Sans",
                "backdrop": "outline",
                "backdrop_color": "#FFFFFF",
                "text_color": "#FFFFFF",
            },
            relative_values={
                "font_size": "28px",
                "outline_weight": "8%",
                "shadow_weight": "0px",
                "margin_left": "5px",
                "margin_right": "5px",
                "margin_bottom": "10px",
                "max_width": "100%",
                "max_height": "40%",
            },
            animation_values={phase: animation_type},
        )
        ass_path = tmp_path / f"{width}x{height}-{phase}-{animation_type}.ass"
        write_ass(
            ass_path,
            [{"start": 0.0, "end": 1.0, "text": "ANIMATION"}],
            config,
            geometry,
        )

        raw = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={width}x{height}:d=1:r=25",
                "-vf",
                f"subtitles={ass_path}",
                "-frames:v",
                "25",
                "-pix_fmt",
                "gray",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        ).stdout
        assert len(raw) == frame_size * 25
        early = raw[frame_size : frame_size * 2]
        stable = raw[frame_size * 9 : frame_size * 10]
        late = raw[frame_size * 24 : frame_size * 25]
        if phase == "cue_text_entrance":
            assert early != stable, animation_type
        elif phase == "cue_text_exit":
            assert late != stable, animation_type
        else:
            frames = {
                raw[offset : offset + frame_size]
                for offset in range(0, len(raw), frame_size)
            }
            assert len(frames) > 1, animation_type


@pytest.mark.integration
@pytest.mark.parametrize("canvas", [(320, 180), (180, 320)])
def test_ffmpeg_libass_renders_every_word_motion_in_both_orientations(
    tmp_path: Path,
    canvas: tuple[int, int],
):
    if shutil.which("ffmpeg") is None or shutil.which("fc-match") is None:
        pytest.skip("FFmpeg and fontconfig are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))
    font_match = subprocess.run(
        ["fc-match", "-f", "%{family}", "DejaVu Sans"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if "DejaVu Sans" not in font_match:
        pytest.skip("The controlled DejaVu Sans font is not available")

    width, height = canvas
    geometry = VideoGeometry(
        stream_index=0,
        coded_width=width,
        coded_height=height,
        render_width=width,
        render_height=height,
        rotation_degrees=0,
        sample_aspect_ratio=Fraction(1, 1),
        display_aspect_ratio=Fraction(width, height),
        duration_seconds=1.0,
    )
    cases = (
        [
            ("word_text_entrance", animation_type)
            for animation_type in WORD_ENTRANCE_ANIMATION_CHOICES
            if animation_type != "none"
        ]
        + [
            ("word_text_emphasis", animation_type)
            for animation_type in WORD_EMPHASIS_ANIMATION_CHOICES
            if animation_type not in {"none", "highlight"}
        ]
        + [
            ("word_text_exit", animation_type)
            for animation_type in WORD_EXIT_ANIMATION_CHOICES
            if animation_type != "none"
        ]
    )
    cue = KaraokeCue(
        fragments=(SubtitleDisplayFragment("WORD", 0),),
        durations=(100,),
        active_intervals=((10, 90),),
    )
    frame_size = width * height

    for phase, animation_type in cases:
        config = validate_subtitle_config(
            None,
            appearance_values={
                "font": "DejaVu Sans",
                "backdrop": "none",
                "text_color": "#FFFFFF",
            },
            relative_values={
                "font_size": "28px",
                "shadow_weight": "0px",
                "margin_left": "5px",
                "margin_right": "5px",
                "margin_bottom": "10px",
                "max_width": "100%",
                "max_height": "40%",
            },
            animation_values={phase: animation_type},
        )
        ass_path = tmp_path / f"{width}x{height}-{phase}-{animation_type}.ass"
        write_ass(
            ass_path,
            [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": "WORD",
                    "_karaoke_cue": cue,
                }
            ],
            config,
            geometry,
        )

        raw = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={width}x{height}:d=1:r=25",
                "-vf",
                f"subtitles={ass_path}",
                "-frames:v",
                "25",
                "-pix_fmt",
                "gray",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        ).stdout
        assert len(raw) == frame_size * 25
        assert max(raw) > 0
        frames = {
            raw[offset : offset + frame_size]
            for offset in range(0, len(raw), frame_size)
        }
        assert len(frames) > 1, animation_type


@pytest.mark.integration
@pytest.mark.parametrize("canvas", [(320, 180), (180, 320)])
@pytest.mark.parametrize("mode", ["active-word", "progressive"])
def test_word_focus_box_contains_animated_words_in_both_orientations(
    tmp_path: Path,
    canvas: tuple[int, int],
    mode: str,
):
    if shutil.which("ffmpeg") is None or shutil.which("fc-match") is None:
        pytest.skip("FFmpeg and fontconfig are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))
    font_match = subprocess.run(
        ["fc-match", "-f", "%{family}", "DejaVu Sans"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if "DejaVu Sans" not in font_match:
        pytest.skip("The controlled DejaVu Sans font is not available")

    width, height = canvas
    geometry = VideoGeometry(
        stream_index=0,
        coded_width=width,
        coded_height=height,
        render_width=width,
        render_height=height,
        rotation_degrees=0,
        sample_aspect_ratio=Fraction(1, 1),
        display_aspect_ratio=Fraction(width, height),
        duration_seconds=1.0,
    )
    config = validate_subtitle_config(
        None,
        defaults=get_subtitle_template("focus-marker").config,
        appearance_values={
            "font": "DejaVu Sans",
            "backdrop": "box",
            "backdrop_color": "#FF0000",
            "text_color": "#FFFFFF",
        },
        relative_values={
            "font_size": "28px",
            "outline_weight": "6px",
            "margin_left": "5px",
            "margin_right": "5px",
            "margin_bottom": "10px",
            "max_width": "100%",
            "max_height": "40%",
        },
        animation_values={
            "word_text_mode": mode,
            "word_backdrop_mode": mode,
        },
    )
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("Ele", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("tem...", 1),
        ),
        durations=(40, 60),
        active_intervals=((0, 40), (40, 100)),
    )
    ass_path = tmp_path / f"focus-marker-{width}x{height}.ass"
    write_ass(
        ass_path,
        [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Ele tem...",
                "_karaoke_cue": cue,
            }
        ],
        config,
        geometry,
    )

    raw = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d=1:r=25",
            "-vf",
            f"subtitles={ass_path}",
            "-frames:v",
            "25",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    ).stdout
    frame_size = width * height * 3
    early_frame = raw[5 * frame_size : 6 * frame_size]
    frame = raw[17 * frame_size : 18 * frame_size]
    red_pixels: list[tuple[int, int]] = []
    text_pixels: list[tuple[int, int]] = []
    for pixel_index in range(width * height):
        red, green, blue = frame[pixel_index * 3 : pixel_index * 3 + 3]
        coordinate = (pixel_index % width, pixel_index // width)
        if red > 100 and red > green * 2 and red > blue * 2:
            red_pixels.append(coordinate)
        if red > 150 and green > 130 and blue > 40:
            text_pixels.append(coordinate)

    assert red_pixels
    assert text_pixels
    box_bounds = (
        min(x for x, _ in red_pixels),
        min(y for _, y in red_pixels),
        max(x for x, _ in red_pixels),
        max(y for _, y in red_pixels),
    )
    text_bounds = (
        min(x for x, _ in text_pixels),
        min(y for _, y in text_pixels),
        max(x for x, _ in text_pixels),
        max(y for _, y in text_pixels),
    )
    assert box_bounds[0] <= text_bounds[0] <= text_bounds[2] <= box_bounds[2]
    assert box_bounds[1] <= text_bounds[1] <= text_bounds[3] <= box_bounds[3]

    def yellow_coordinates(data: bytes) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for pixel_index in range(width * height):
            red, green, blue = data[pixel_index * 3 : pixel_index * 3 + 3]
            if red > 150 and green > 120 and blue < 130:
                result.append((pixel_index % width, pixel_index // width))
        return result

    early_word_box = yellow_coordinates(early_frame)
    late_word_box = yellow_coordinates(frame)
    assert early_word_box
    assert late_word_box
    early_left = min(x for x, _ in early_word_box)
    early_right = max(x for x, _ in early_word_box)
    late_left = min(x for x, _ in late_word_box)
    late_right = max(x for x, _ in late_word_box)
    if mode == "active-word":
        assert late_left > early_left
        assert late_right > early_right
    else:
        assert late_left <= early_left + 1
        assert late_right > early_right


# Word-highlight timing, output, and renderer contracts.
def test_word_highlight_config_resolves_default_and_custom_colors():
    default = validate_subtitle_config(
        None, animation_values={"word_text_emphasis": "highlight"}
    )
    custom = validate_subtitle_config(
        None,
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "active-word",
            "word_text_highlight_color": "#abcdef80",
        },
    )

    assert default.animation.word.uses_timed_highlight is True
    assert (
        default.style.typography.highlight_color
        == DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR
    )
    assert default.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD
    assert custom.animation.word.text.mode is WordAnimationMode.ACTIVE_WORD
    assert custom.style.typography.highlight_color == "#ABCDEF80"


@pytest.mark.parametrize(
    "animation",
    [
        {"word_text_highlight_color": "#FFD54F"},
        {"word_text_emphasis": "highlight", "word_text_highlight_color": "white"},
        {"word_text_emphasis": "highlight", "word_text_mode": "unknown"},
    ],
)
def test_word_animation_validation_rejects_meaningless_or_invalid_colors(animation):
    with pytest.raises(ValidationError):
        validate_subtitle_config(None, animation_values=animation)


def test_word_animation_cli_request_is_typed(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--animation-word-text-emphasis",
            "highlight",
            "--animation-word-text-mode",
            "active-word",
            "--animation-word-text-highlight-color",
            "#abcdef80",
        ]
    )

    request = cli._build_request(args, parser)

    assert request.subtitle_config.animation.word.uses_timed_highlight is True
    assert (
        request.subtitle_config.animation.word.text.mode
        is WordAnimationMode.ACTIVE_WORD
    )
    assert request.subtitle_config.style.typography.highlight_color == "#ABCDEF80"


@pytest.mark.parametrize(
    "animation_options",
    [
        ["--animation-word-text-highlight-color", "#FFD54F"],
    ],
)
def test_cli_rejects_highlight_color_without_highlight(
    tmp_path: Path,
    animation_options: list[str],
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        cli._build_request(
            parser.parse_args(["-i", str(input_path), *animation_options]),
            parser,
        )

    assert error.value.code == 2


def test_word_animation_cli_accepts_transcription_free_preview(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    request = cli._build_request(
        parser.parse_args(
            [
                "-i",
                str(input_path),
                "--preview-layout",
                "--animation-word-text-emphasis",
                "highlight",
            ]
        ),
        parser,
    )

    assert isinstance(request, PreviewRequest)
    assert request.subtitle_config.animation.word.uses_timed_highlight is True


def test_word_timing_allocation_conserves_quantized_cue_duration():
    words = [
        _word_animation_record("one", 0.001, 0.4),
        _word_animation_record("two", 0.505, 1.0),
    ]

    assert allocate_karaoke_durations(0.001, 1.0, words) == (50, 50)


def test_active_word_intervals_use_word_ends_and_leave_pause_gaps():
    words = [
        _word_animation_record("one", 0.0, 0.25),
        _word_animation_record("two", 0.4, 0.7),
        _word_animation_record("three", 0.6, 1.0),
    ]

    assert allocate_active_word_intervals(0.0, 1.0, words) == (
        (0, 25),
        (40, 60),
        (60, 100),
    )


@pytest.mark.parametrize(
    "cue_start, words",
    [
        (0.0, [_word_animation_record("one", 0.5, 1.0)]),
        (
            0.0,
            [
                _word_animation_record("one", 0.0, 0.4),
                _word_animation_record("two", -0.1, 1.0),
            ],
        ),
        (
            0.0,
            [
                _word_animation_record("one", 0.0, 0.4),
                _word_animation_record("two", 0.5, 0.4),
            ],
        ),
    ],
)
def test_word_timing_allocation_rejects_invalid_boundaries(cue_start, words):
    with pytest.raises(ArtifactError):
        allocate_karaoke_durations(cue_start, 1.0, words)


def test_layout_preserves_lossless_word_fragments_and_line_breaks():
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            relative_values={"max_width": "300px", "max_height": "200px"},
        ),
        WORD_GEOMETRY,
    )
    words = [
        _word_animation_record("one", 0.0, 0.4),
        _word_animation_record("two", 0.5, 1.0),
    ]

    display, _ = transcriber.layout_subtitle_cues(
        [{"start": 0.0, "end": 1.0, "text": "one two", "words": words}],
        config,
        WORD_GEOMETRY,
    )

    fragments = display[0]["display_fragments"]
    assert fragments is not None
    assert "".join(fragment.text for fragment in fragments) == display[0]["text"]
    assert [
        fragment.word_index for fragment in fragments if fragment.word_index is not None
    ] == [0, 1]


@pytest.mark.parametrize("highlight_mode", ["progressive", "active-word"])
def test_text_case_preserves_word_identity_and_timing(
    tmp_path: Path, highlight_mode: str
):
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            appearance_values={"text_case": "uppercase"},
            animation_values={
                "word_text_emphasis": "highlight",
                "word_text_mode": highlight_mode,
            },
        ),
        WORD_GEOMETRY,
    )
    words = [
        _word_animation_record("Straße", 0.0, 0.4),
        _word_animation_record("groß", 0.5, 1.0),
    ]

    display, _ = transcriber.layout_subtitle_cues(
        [{"start": 0.0, "end": 1.0, "text": "Straße groß", "words": words}],
        config,
        WORD_GEOMETRY,
    )
    prepared, fallback_count = transcriber.prepare_karaoke_cues(display, config)

    assert fallback_count == 0
    assert display[0]["text"] == "STRASSE GROSS"
    assert [word["word"] for word in display[0]["words"]] == ["Straße", "groß"]
    cue = prepared[0]["_karaoke_cue"]
    assert "".join(fragment.text for fragment in cue.fragments) == "STRASSE GROSS"
    assert [
        fragment.word_index
        for fragment in cue.fragments
        if fragment.word_index is not None
    ] == [0, 1]
    assert sum(cue.durations) == 100

    path = tmp_path / f"{highlight_mode}-uppercase.ass"
    write_ass(path, prepared, config, WORD_GEOMETRY)
    content = path.read_text(encoding="utf-8")
    assert "STRASSE" in content
    assert "GROSS" in content
    assert "Straße" not in content


def test_write_ass_compiles_one_timing_block_per_word_and_escapes_text(
    tmp_path: Path,
):
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None, animation_values={"word_text_emphasis": "highlight"}
        ),
        WORD_GEOMETRY,
    )
    fragments = (
        SubtitleDisplayFragment("Hello", 0),
        SubtitleDisplayFragment(" "),
        SubtitleDisplayFragment(r"{world}", 1),
    )
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": r"Hello {world}",
        "_karaoke_cue": KaraokeCue(
            fragments,
            (50, 50),
            ((0, 40), (50, 100)),
        ),
    }
    path = tmp_path / "word-highlight.ass"

    write_ass(path, [segment], config, WORD_GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert content.count(r"{\1c&H4FD5FF&\1a&H00&}") == 2
    assert r"{\k" not in content
    assert r"\{world\}" in content


def test_active_word_mode_splits_stable_full_cue_events_across_pauses(
    tmp_path: Path,
):
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            animation_values={
                "word_text_emphasis": "highlight",
                "word_text_mode": "active-word",
            },
        ),
        WORD_GEOMETRY,
    )
    fragments = (
        SubtitleDisplayFragment("Hello", 0),
        SubtitleDisplayFragment(" "),
        SubtitleDisplayFragment("world", 1),
    )
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": "Hello world",
        "_karaoke_cue": KaraokeCue(
            fragments,
            (50, 50),
            ((0, 40), (50, 100)),
        ),
    }
    path = tmp_path / "active-word-highlight.ass"

    write_ass(path, [segment], config, WORD_GEOMETRY)

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    text_dialogue = [line for line in dialogue if line.startswith("Dialogue: 2,")]
    assert len(text_dialogue) == 4
    assert any("0:00:00.00,0:00:00.40" in line for line in text_dialogue)
    assert any("0:00:00.40,0:00:01.00" in line for line in text_dialogue)
    assert any("0:00:00.00,0:00:00.50" in line for line in text_dialogue)
    assert any("0:00:00.50,0:00:01.00" in line for line in text_dialogue)
    assert r"{\k" not in "\n".join(dialogue)
    assert any(
        r"{\1c&H4FD5FF&\1a&H00&}" in line and line.endswith("Hello")
        for line in text_dialogue
    )
    assert any(
        r"{\1c&H4FD5FF&\1a&H00&}" in line and line.endswith("world")
        for line in text_dialogue
    )


def test_word_color_overrides_preserve_color_and_alpha_channels():
    assert rgba_to_ass_color_override("#11223380", 1) == (r"\1c&H332211&\1a&H7F&")


@pytest.mark.parametrize("highlight_mode", ["progressive", "active-word"])
def test_word_colors_use_once_composed_global_opacity(
    tmp_path: Path,
    highlight_mode: str,
):
    path = tmp_path / f"{highlight_mode}-opacity.ass"
    config = validate_subtitle_config(
        None,
        appearance_values={"text_color": "#FFFFFF80", "opacity": "50%"},
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": highlight_mode,
            "word_text_highlight_color": "#112233C0",
        },
    )
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": "Hello",
        "_karaoke_cue": KaraokeCue(
            (SubtitleDisplayFragment("Hello", 0),),
            (100,),
            ((0, 100),),
        ),
    }

    write_ass(path, [segment], config, WORD_GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert r"\1c&H332211&\1a&H9F&" in content
    assert "&HBFFFFFFF" in content


def test_disabled_word_highlight_keeps_plain_ass_output_unchanged(tmp_path: Path):
    default_path = tmp_path / "default.ass"
    explicit_disabled_path = tmp_path / "explicit-disabled.ass"
    segment = {"start": 0.0, "end": 1.0, "text": "plain output", "words": []}
    write_ass(default_path, [segment], validate_subtitle_config(None), WORD_GEOMETRY)
    write_ass(
        explicit_disabled_path,
        [segment],
        validate_subtitle_config(None, animation_values={"word_text_emphasis": "none"}),
        WORD_GEOMETRY,
    )

    assert default_path.read_bytes() == explicit_disabled_path.read_bytes()


@pytest.mark.parametrize("highlight_mode", ["progressive", "active-word"])
def test_word_highlight_retains_exact_font_weight(tmp_path: Path, highlight_mode: str):
    path = tmp_path / f"{highlight_mode}-weight.ass"
    config = validate_subtitle_config(
        None,
        appearance_values={"font_weight": "800"},
        relative_values={"letter_spacing": "2px"},
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": highlight_mode,
        },
    )
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": "Hello",
        "_karaoke_cue": KaraokeCue(
            (SubtitleDisplayFragment("Hello", 0),),
            (100,),
            ((0, 100),),
        ),
    }

    write_ass(path, [segment], config, WORD_GEOMETRY)

    content = path.read_text(encoding="utf-8")
    style_fields = content.split("Style: Default,", 1)[1].split(",")
    assert style_fields[6] == "0"
    assert style_fields[12] == "2"
    dialogue = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    assert dialogue
    assert all(r"{\b800}" in line for line in dialogue if "Hello" in line)
    assert "Hello" in content


@pytest.mark.parametrize("highlight_mode", ["progressive", "active-word"])
def test_word_animation_artifacts_keep_srt_plain_and_record_fallback_metadata(
    tmp_path: Path,
    highlight_mode: str,
):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source,
        language="pt",
        task="transcribe",
        model_name="turbo",
        full_text="Hello world.",
        segments=(
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hello world.",
                "words": [
                    _word_animation_record("Hello", 0.0, 0.4),
                    _word_animation_record("world.", 0.5, 1.0),
                ],
            },
            {"start": 1.0, "end": 2.0, "text": "Fallback", "words": []},
        ),
    )
    progress: list[str] = []
    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            animation_values={
                "word_text_emphasis": "highlight",
                "word_text_mode": highlight_mode,
            },
        ),
        geometry=WORD_GEOMETRY,
        progress=progress.append,
    )

    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert "effects" not in payload["metadata"]["rendering"]
    word_animation = payload["metadata"]["rendering"]["animation"]["word"]
    assert word_animation == {
        "text": {
            "active": True,
            "mode": highlight_mode,
            "entrance": {"type": "none"},
            "emphasis": {"type": "highlight"},
            "exit": {"type": "none"},
        },
        "backdrop": {
            "active": False,
            "mode": "active-word",
            "entrance": {"type": "none"},
            "emphasis": {"type": "none"},
            "exit": {"type": "none"},
        },
        "normal_color": "#FFFFFF",
        "highlight_color": DEFAULT_WORD_ANIMATION_HIGHLIGHT_COLOR,
        "shortened_words": {"text": 0, "backdrop": 0},
        "fallback_cues": 1,
    }
    assert "Warning: 1 subtitle cue(s)" in "\n".join(progress)
    srt = Path(paths[1]).read_text(encoding="utf-8")
    assert "{\\k" not in srt
    assert "Hello world." in srt
    ass = Path(paths[2]).read_text(encoding="utf-8")
    assert r"{\k" not in ass
    assert ass.count("Dialogue:") >= 5
    assert "Fallback" in ass


@pytest.mark.integration
@pytest.mark.parametrize("canvas", [(320, 180), (180, 320)])
@pytest.mark.parametrize("highlight_mode", ["progressive", "active-word"])
def test_ffmpeg_libass_highlight_changes_word_colors_without_moving_layout(
    tmp_path: Path,
    canvas: tuple[int, int],
    highlight_mode: str,
):
    """Exercise the real ASS/libass color transition with a system font."""
    if shutil.which("ffmpeg") is None or shutil.which("fc-match") is None:
        pytest.skip("FFmpeg and fontconfig are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    font_match = subprocess.run(
        ["fc-match", "-f", "%{family}", "DejaVu Sans"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if "DejaVu Sans" not in font_match:
        pytest.skip("The controlled DejaVu Sans font is not available")

    width, height = canvas
    input_path = tmp_path / f"highlight-input-{highlight_mode}-{width}x{height}.mp4"
    highlight_ass = tmp_path / "word-highlight.ass"
    plain_ass = tmp_path / "plain.ass"
    highlight_video = tmp_path / "karaoke.mp4"
    plain_video = tmp_path / "plain.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d=1.3",
            "-t",
            "1.3",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    highlight_config = validate_subtitle_config(
        None,
        appearance_values={"font": "DejaVu Sans", "backdrop": "none"},
        relative_values={
            "font_size": "20px",
            "shadow_weight": "0px",
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "150px",
            "max_height": "80px",
        },
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": highlight_mode,
        },
    )
    resolved = resolve_subtitle_config(highlight_config, geometry)
    words = [
        _word_animation_record("one", 0.2, 0.3),
        _word_animation_record("two", 0.4, 0.5),
        _word_animation_record("three", 0.7, 0.8),
        _word_animation_record("four", 0.9, 1.0),
    ]
    display, _ = transcriber.layout_subtitle_cues(
        [{"start": 0.2, "end": 1.0, "text": "one two three four", "words": words}],
        resolved,
        geometry,
        language="en",
    )
    prepared, fallback_count = transcriber.prepare_karaoke_cues(display, resolved)
    assert fallback_count == 0
    write_ass(highlight_ass, prepared, highlight_config, geometry)
    plain_config = validate_subtitle_config(
        None,
        appearance_values={"font": "DejaVu Sans", "backdrop": "none"},
        relative_values={
            "font_size": "20px",
            "shadow_weight": "0px",
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "150px",
            "max_height": "80px",
        },
    )
    write_ass(plain_ass, display, plain_config, geometry)
    embed_subtitles(
        input_path,
        highlight_ass,
        tmp_path,
        output_path=highlight_video,
        geometry=geometry,
    )
    embed_subtitles(
        input_path,
        plain_ass,
        tmp_path,
        output_path=plain_video,
        geometry=geometry,
    )

    def frame(video_path: Path, timestamp: float) -> bytes:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-ss",
                str(timestamp),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        )
        assert len(result.stdout) == geometry.render_width * geometry.render_height * 3
        return result.stdout

    def highlight_pixels(raw: bytes) -> int:
        return sum(
            red > 180 and 130 < green < 245 and blue < 150
            for red, green, blue in zip(raw[::3], raw[1::3], raw[2::3], strict=True)
        )

    def highlight_mask(raw: bytes) -> set[int]:
        return {
            index
            for index, (red, green, blue) in enumerate(
                zip(raw[::3], raw[1::3], raw[2::3], strict=True)
            )
            if red > 180 and 130 < green < 245 and blue < 150
        }

    def foreground_bbox(raw: bytes) -> tuple[int, int, int, int]:
        points = [
            (index % geometry.render_width, index // geometry.render_width)
            for index, (red, green, blue) in enumerate(
                zip(raw[::3], raw[1::3], raw[2::3], strict=True)
            )
            if max(red, green, blue) > 50
        ]
        assert points
        xs, ys = zip(*points, strict=True)
        return min(xs), min(ys), max(xs), max(ys)

    before = frame(highlight_video, 0.1)
    first = frame(highlight_video, 0.25)
    second = frame(highlight_video, 0.45)
    pause = frame(highlight_video, 0.6)
    final = frame(highlight_video, 0.95)
    plain = frame(plain_video, 0.45)
    highlight_counts = [
        highlight_pixels(first),
        highlight_pixels(second),
        highlight_pixels(final),
    ]
    assert not highlight_pixels(before)
    if highlight_mode == "progressive":
        assert 0 < highlight_counts[0] < highlight_counts[1] < highlight_counts[2]
        assert highlight_pixels(pause) >= highlight_counts[1]
    else:
        assert all(highlight_counts)
        assert not highlight_pixels(pause)
        masks = [highlight_mask(frame) for frame in (first, second, final)]
        for left, right in zip(masks, masks[1:], strict=False):
            assert len(left & right) < min(len(left), len(right)) * 0.25
    assert not highlight_pixels(plain)
    assert (
        len({hashlib.sha256(frame).digest() for frame in (first, second, final)}) == 3
    )
    highlight_bbox = foreground_bbox(second)
    plain_bbox = foreground_bbox(plain)
    assert all(
        abs(left - right) <= 2
        for left, right in zip(highlight_bbox, plain_bbox, strict=True)
    )
