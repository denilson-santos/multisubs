import builtins
import re
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from multisubs import cli
from multisubs.ass import rgba_to_ass_color_override, write_ass
from multisubs.config import validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.layout import resolve_subtitle_config, resolve_wrapping_metrics
from multisubs.models import (
    PreviewMode,
    PreviewRequest,
    SubtitlePosition,
    VideoGeometry,
)
from multisubs.preview import (
    DEFAULT_PREVIEW_DURATION_MS,
    DEFAULT_PREVIEW_TEXT,
    build_animation_preview_ass,
    build_preview_ass,
    build_preview_guide_events,
    build_simulated_karaoke_cue,
    normalise_preview_text,
    parse_preview_duration,
    parse_preview_timestamp,
    resolve_preview_timestamp,
)

GEOMETRY = VideoGeometry(
    stream_index=0,
    coded_width=1920,
    coded_height=1080,
    render_width=1920,
    render_height=1080,
    rotation_degrees=0,
    sample_aspect_ratio=Fraction(1, 1),
    display_aspect_ratio=Fraction(16, 9),
    duration_seconds=10.0,
)


def _request(tmp_path: Path, **overrides) -> PreviewRequest:
    values = {
        "input_path": tmp_path / "video.mp4",
        "output_dir": tmp_path / "output",
        "subtitle_config": validate_subtitle_config(None),
        "preview_at": None,
        "preview_text": DEFAULT_PREVIEW_TEXT,
        "guides": False,
    }
    values.update(overrides)
    return PreviewRequest(**values)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00:00:00.000", 0.0),
        ("01:02:03.45", 3723.45),
        ("23:04:05.678", 83045.678),
    ],
)
def test_parse_preview_timestamp(value, expected):
    assert parse_preview_timestamp(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "-00:00:01.000",
        "00:60:00.000",
        "00:00:60.000",
        "00:00:00.1234",
        "00:00:00",
        "1.5",
    ],
)
def test_parse_preview_timestamp_rejects_ambiguous_values(value):
    with pytest.raises(ValidationError, match="preview-at"):
        parse_preview_timestamp(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1s", 1000), ("4s", 4000), ("1500ms", 1500), ("1.005s", 1005)],
)
def test_parse_preview_duration(value, expected):
    assert parse_preview_duration(value) == expected


@pytest.mark.parametrize(
    "value",
    ["0.5s", "15001ms", "4", "1.5", "nan", "-1s", "1.0015s"],
)
def test_parse_preview_duration_rejects_values_outside_whole_ms_bounds(value):
    with pytest.raises(ValidationError, match="preview-duration"):
        parse_preview_duration(value)


def test_simulated_karaoke_cue_is_exact_repeatable_and_reserves_punctuation_gaps():
    first = build_simulated_karaoke_cue("One, two. three", 50, 450)
    second = build_simulated_karaoke_cue("One, two. three", 50, 450)

    assert first == second
    assert sum(first.durations) == 400
    assert first.active_intervals[-1][1] == 450
    assert first.active_intervals[1][0] - first.active_intervals[0][1] == 8
    assert first.active_intervals[2][0] - first.active_intervals[1][1] == 15
    assert all(start < end for start, end in first.active_intervals)


@pytest.mark.parametrize("text", ["你好世界", "e\u0301lan", "👩‍💻 works"])
def test_simulated_karaoke_cue_preserves_unicode_fragment_reconstruction(text):
    cue = build_simulated_karaoke_cue(text, 0, 400)

    assert "".join(fragment.text for fragment in cue.fragments) == text
    assert len(cue.active_intervals) == len(cue.durations)


def test_preview_timestamp_defaults_to_midpoint_or_zero():
    assert resolve_preview_timestamp(None, GEOMETRY) == 5.0
    unknown_duration = replace(GEOMETRY, duration_seconds=None)
    assert resolve_preview_timestamp(None, unknown_duration) == 0.0


@pytest.mark.parametrize("timestamp", [-0.1, 10.001, float("nan"), float("inf")])
def test_preview_timestamp_rejects_out_of_range_values(timestamp):
    with pytest.raises(ValidationError, match="preview-at"):
        resolve_preview_timestamp(timestamp, GEOMETRY)


def test_preview_request_is_built_without_transcription_options(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--preview-layout",
            "--preview-at",
            "00:00:01.250",
            "--preview-guides",
        ]
    )

    request = cli._build_request(args, parser)

    assert isinstance(request, PreviewRequest)
    assert request.preview_at == 1.25
    assert request.preview_text == DEFAULT_PREVIEW_TEXT
    assert request.guides is True


def test_animation_preview_request_uses_typed_mode_and_default_duration(
    tmp_path: Path,
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--preview-animation",
            "--task",
            "translate",
            "--model",
            "turbo",
        ]
    )

    request = cli._build_request(args, parser)
    assert isinstance(request, PreviewRequest)

    assert request.preview_mode.value == "animation"
    assert request.preview_duration_ms == DEFAULT_PREVIEW_DURATION_MS


def test_preview_duration_requires_animation_mode(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--preview-layout",
            "--preview-duration",
            "2s",
        ]
    )

    with pytest.raises(SystemExit) as error:
        cli._build_request(args, parser)

    assert error.value.code == 2


def test_preview_rejects_retained_transcriptions_and_orphan_options(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    for arguments, message in (
        (
            ["-i", str(input_path), "--preview-layout", "--keep-transcriptions"],
            "keep-transcriptions",
        ),
        (["-i", str(input_path), "--preview-guides"], "require"),
    ):
        args = parser.parse_args(arguments)
        with pytest.raises(SystemExit) as error:
            cli._build_request(args, parser)
        assert error.value.code == 2
        assert message


def test_preview_text_normalization_and_ass_escaping():
    assert normalise_preview_text(" one\r\ntwo ") == "one two"
    with pytest.raises(ValidationError, match="preview-text"):
        normalise_preview_text("\r\n")


def test_build_preview_ass_reuses_resolved_height_and_wrapping(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        relative_values={"max_width": "30%", "max_height": "8%"},
    )
    request = _request(
        tmp_path,
        subtitle_config=config,
        preview_text="one two three four five six seven eight nine ten eleven twelve",
    )
    path = tmp_path / "preview.ass"

    resolved, display_text = build_preview_ass(path, request, GEOMETRY, 2.0)

    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)
    assert display_text.count("\n") + 1 <= metrics.line_capacity
    content = path.read_text(encoding="utf-8")
    assert "one two" in content
    assert "0:00:00.00,0:00:03.00" in content


def test_build_animation_preview_ass_uses_production_timeline_and_phases(
    tmp_path: Path,
):
    config = validate_subtitle_config(
        None,
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "active-word",
            "word_text_highlight_color": "#FFD54F",
        },
    )
    request = _request(
        tmp_path,
        subtitle_config=config,
        preview_duration_ms=2_000,
    )
    path = tmp_path / "animation-preview.ass"

    build_animation_preview_ass(path, request, GEOMETRY, 2.0)

    content = path.read_text(encoding="utf-8")
    assert "0:00:00.50" in content
    assert "0:00:02.50" in content
    assert "\\k" not in content
    assert "_karaoke_preview_cue" not in content


def test_preview_ass_uses_the_same_exact_font_weight_as_normal_output(
    tmp_path: Path,
):
    config = validate_subtitle_config(
        None,
        appearance_values={"font_weight": "600"},
    )
    path = tmp_path / "preview-weight.ass"

    build_preview_ass(
        path,
        _request(tmp_path, subtitle_config=config),
        GEOMETRY,
        0.0,
    )

    content = path.read_text(encoding="utf-8")
    style_fields = content.split("Style: Default,", 1)[1].split(",")
    assert style_fields[6] == "0"
    assert r"{\b600}" in content


def test_preview_ass_uses_global_opacity_for_the_effective_palette(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "text_color": "#FFFFFF80",
            "backdrop_color": "#00000099",
            "opacity": "50%",
        },
    )
    path = tmp_path / "preview-opacity.ass"

    build_preview_ass(
        path,
        _request(tmp_path, subtitle_config=config),
        GEOMETRY,
        0.0,
    )

    style_fields = (
        path.read_text(encoding="utf-8").split("Style: Default,", 1)[1].split(",")
    )
    assert style_fields[2:6] == [
        "&HBFFFFFFF",
        "&HBFFFFFFF",
        "&HB2000000",
        "&HB2000000",
    ]


@pytest.mark.parametrize(
    ("mode", "highlighted_word_count"),
    [("progressive", 2), ("active-word", 1)],
)
def test_preview_ass_shows_representative_static_karaoke_state(
    tmp_path: Path, mode: str, highlighted_word_count: int
):
    config = validate_subtitle_config(
        None,
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": mode,
            "word_text_highlight_color": "#00F5D4",
        },
    )
    path = tmp_path / f"preview-{mode}.ass"

    build_preview_ass(
        path,
        _request(
            tmp_path,
            subtitle_config=config,
            preview_at=0.0,
            preview_text="one two three four",
        ),
        GEOMETRY,
        0.0,
    )

    content = path.read_text(encoding="utf-8")
    highlight_override = "{" + rgba_to_ass_color_override("#00F5D4", 1) + "}"
    assert content.count(highlight_override) == highlighted_word_count
    assert r"\k" not in content
    assert all(word in content for word in ("one", "two", "three", "four"))


def test_preview_outline_reuses_word_fragment_positions(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": "DejaVu Sans",
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
    path = tmp_path / "preview-fragmented-outline.ass"

    build_preview_ass(
        path,
        _request(
            tmp_path,
            subtitle_config=config,
            preview_at=0.0,
            preview_text="Ele tem...",
        ),
        GEOMETRY,
        0.0,
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
        text = next(
            line
            for line in dialogue
            if line.startswith("Dialogue: 2,") and line.endswith(word)
        )
        outline_position = re.search(r"\\pos\((\d+),(\d+)\)", outline)
        text_position = re.search(r"\\pos\((\d+),(\d+)\)", text)
        assert outline_position is not None
        assert text_position is not None
        assert outline_position.groups() == text_position.groups()


@pytest.mark.parametrize(
    ("mode", "boxed_word_count"),
    [("progressive", 2), ("active-word", 1)],
)
def test_preview_ass_shows_representative_static_word_boxes(
    tmp_path: Path,
    mode: str,
    boxed_word_count: int,
):
    config = validate_subtitle_config(
        None,
        appearance_values={
            "backdrop": "none",
            "word_backdrop": "box",
            "word_backdrop_color": "#FF0000",
        },
        animation_values={
            "word_backdrop_mode": mode,
        },
    )
    path = tmp_path / f"preview-box-{mode}.ass"

    build_preview_ass(
        path,
        _request(
            tmp_path,
            subtitle_config=config,
            preview_at=0.0,
            preview_text="one two three four",
        ),
        GEOMETRY,
        0.0,
    )

    content = path.read_text(encoding="utf-8")
    assert content.count(r"\1c&H0000FF&") == boxed_word_count
    assert content.count(r"\p1") == boxed_word_count
    assert r"\1c&H000000&" not in content
    assert r"\move(" not in content
    assert r"\fade(" not in content
    assert r"\fsc" not in content
    assert all(word in content for word in ("one", "two", "three", "four"))


def test_karaoke_preview_preserves_escaping_and_explicit_line_height(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "line_height": "125%",
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "240px",
            "max_height": "30%",
        },
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "progressive",
        },
    )
    path = tmp_path / "preview-karaoke-lines.ass"

    _, display_text = build_preview_ass(
        path,
        _request(
            tmp_path,
            subtitle_config=config,
            preview_at=0.0,
            preview_text="{one} two three four five six",
        ),
        GEOMETRY,
        0.0,
    )

    content = path.read_text(encoding="utf-8")
    dialogue_lines = [
        line for line in content.splitlines() if line.startswith("Dialogue:")
    ]
    assert "\n" in display_text
    assert len(dialogue_lines) > 1
    assert r"\{one\}" in content
    assert r"\k" not in content


def test_preview_renders_only_the_first_segment_that_fits_the_envelope(
    tmp_path: Path,
):
    text = (
        "Example subtitle preview text that demonstrates a readable two-line "
        "caption on your selected video layout before final rendering"
    )
    compact_config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        relative_values={
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "300px",
            "max_height": "54px",
        },
    )
    spacious_config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        relative_values={
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "1600px",
            "max_height": "500px",
        },
    )
    compact_path = tmp_path / "compact.ass"
    spacious_path = tmp_path / "spacious.ass"

    _, compact_text = build_preview_ass(
        compact_path,
        _request(tmp_path, subtitle_config=compact_config, preview_text=text),
        GEOMETRY,
        0.5,
    )
    _, spacious_text = build_preview_ass(
        spacious_path,
        _request(tmp_path, subtitle_config=spacious_config, preview_text=text),
        GEOMETRY,
        0.5,
    )

    assert text.startswith(compact_text.replace("\n", " "))
    assert len(compact_text) < len(spacious_text)
    assert spacious_text.replace("\n", " ") == text
    compact_ass = compact_path.read_text(encoding="utf-8")
    assert "final rendering" not in compact_ass
    assert r"{\q2}" in compact_ass


def test_preview_segment_preserves_compact_text_without_inventing_spaces(
    tmp_path: Path,
):
    text = "这是一个没有空格的字幕句子"
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none"},
        relative_values={"max_width": "50px", "max_height": "54px"},
    )
    path = tmp_path / "compact-text.ass"

    _, display_text = build_preview_ass(
        path,
        _request(tmp_path, subtitle_config=config, preview_text=text),
        GEOMETRY,
        0.5,
    )

    assert display_text
    assert len(display_text) < len(text)
    assert text.startswith(display_text.replace("\n", ""))
    assert " " not in display_text


def test_preview_text_is_escaped_before_ass_serialization(tmp_path: Path):
    request = _request(tmp_path, preview_text=r"unsafe {\an9} text")
    path = tmp_path / "escaped.ass"

    build_preview_ass(path, request, GEOMETRY, 0.0)

    content = path.read_text(encoding="utf-8")
    assert r"unsafe \{\\an9\} text" in content
    assert r"Dialogue: 0,0:00:00.00,0:00:01.00" in content


def test_preview_applies_text_case_before_wrapping_and_ass_escaping(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={"text_case": "uppercase"},
        relative_values={"max_width": "1000px", "max_height": "100px"},
    )
    source_text = r"Olá Straße {\an9} novamente"
    path = tmp_path / "uppercase-preview.ass"

    _, display_text = build_preview_ass(
        path,
        _request(tmp_path, subtitle_config=config, preview_text=source_text),
        GEOMETRY,
        0.0,
    )

    assert display_text.replace("\n", " ") == r"OLÁ STRASSE {\AN9} NOVAMENTE"
    content = path.read_text(encoding="utf-8")
    assert "OLÁ STRASSE" in content
    assert r"\{\\AN9\}" in content


def test_preview_text_case_expansion_still_respects_cue_capacity(tmp_path: Path):
    config = validate_subtitle_config(
        None,
        appearance_values={"backdrop": "none", "text_case": "uppercase"},
        relative_values={"max_width": "180px", "max_height": "54px"},
    )
    source_text = "Straße erneut später"

    _, display_text = build_preview_ass(
        tmp_path / "uppercase-capacity.ass",
        _request(tmp_path, subtitle_config=config, preview_text=source_text),
        GEOMETRY,
        0.0,
    )

    assert display_text == "STRASSE"
    assert len(display_text) < len(source_text.upper())


def test_explicit_original_text_case_preserves_default_preview_ass(tmp_path: Path):
    default_path = tmp_path / "default-case.ass"
    explicit_path = tmp_path / "explicit-original-case.ass"
    request = _request(tmp_path, preview_text="Mixed Case preview")
    explicit_request = replace(
        request,
        subtitle_config=validate_subtitle_config(
            None, appearance_values={"text_case": "original"}
        ),
    )

    build_preview_ass(default_path, request, GEOMETRY, 0.0)
    build_preview_ass(explicit_path, explicit_request, GEOMETRY, 0.0)

    assert default_path.read_bytes() == explicit_path.read_bytes()


@pytest.mark.parametrize("explicit", [False, True])
def test_preview_guides_serialize_native_or_explicit_geometry(
    tmp_path: Path, explicit: bool
):
    if explicit:
        config = validate_subtitle_config(
            None,
            relative_values={
                "position_x": "50%",
                "position_y": "80%",
                "max_width": "60%",
                "max_height": "20%",
                "letter_spacing": "2px",
            },
            anchor="bottom-center",
        )
    else:
        config = validate_subtitle_config(
            None,
            position="top-right",
            relative_values={"letter_spacing": "2px"},
        )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)
    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        1.0,
        display_text="sample",
    )

    assert events
    assert any("\\p1" in event.text for event in events)
    assert any("Preview guides" in event.text for event in events)
    assert all("Preset:" not in event.text for event in events)
    assert any(r"\fs40" in event.text for event in events)
    assert any("Letter spacing: 2px" in event.text for event in events)
    path = tmp_path / ("explicit.ass" if explicit else "native.ass")
    write_ass(
        path,
        [{"start": 0.0, "end": 2.0, "text": "sample"}],
        config,
        GEOMETRY,
        guide_events=events,
    )
    content = path.read_text(encoding="utf-8")
    assert "Preview guides" in content
    assert "PlayRes: 1920x1080" in content


def test_preview_guide_explicit_anchor_is_custom_coordinate():
    config = validate_subtitle_config(
        None,
        relative_values={
            "position_x": "600px",
            "position_y": "900px",
            "max_width": "60%",
            "max_height": "20%",
        },
        anchor=SubtitlePosition.BOTTOM_CENTER.value,
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)
    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        0.0,
        display_text="sample",
    )
    assert any("m 24 684" in event.text for event in events)


def test_preview_guides_report_requested_and_resolved_letter_spacing():
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "letter_spacing": "4%",
        },
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)
    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        0.0,
        display_text="sample",
        requested_config=config,
    )

    assert any("Letter spacing: 4% (2px resolved)" in event.text for event in events)


def test_preview_guides_report_requested_and_resolved_line_height():
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "line_height": "125%",
        },
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)
    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        0.0,
        display_text="first\nsecond",
        requested_config=config,
    )

    assert any("Line height: 125%" in event.text for event in events)
    assert any("Line capacity:" in event.text for event in events)
    assert any("Render strategy: positioned-lines" in event.text for event in events)


def test_preview_guides_report_global_opacity():
    config = validate_subtitle_config(
        None,
        appearance_values={"opacity": "32.5%"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)

    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        0.0,
        display_text="sample",
        requested_config=config,
    )

    assert any("Opacity: 32.5%" in event.text for event in events)


def test_preview_guides_report_text_case():
    config = validate_subtitle_config(
        None,
        appearance_values={"text_case": "lowercase"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)

    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        0.0,
        display_text="sample",
        requested_config=config,
    )

    assert any("Text case: lowercase" in event.text for event in events)


def test_preview_guides_report_positioned_lines_for_one_line_box():
    config = validate_subtitle_config(
        None,
        relative_values={"line_height": "125%"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)

    events = build_preview_guide_events(
        resolved,
        GEOMETRY,
        metrics,
        0.0,
        display_text="one visual line",
        requested_config=config,
    )

    assert any("Render strategy: positioned-lines" in event.text for event in events)


def test_preview_one_line_box_uses_one_shared_surface(tmp_path: Path):
    path = tmp_path / "preview-box.ass"

    build_preview_ass(
        path,
        _request(tmp_path, preview_text="one visual line"),
        GEOMETRY,
        0.0,
    )

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert (
        sum(line.startswith("Dialogue: 0,") and r"\p1" in line for line in dialogue)
        == 1
    )
    assert sum(line.startswith("Dialogue: 2,") for line in dialogue) == 1


def test_preview_run_branches_before_whisper_runtime_import(
    tmp_path: Path, monkeypatch
):
    input_path = tmp_path / "video.mp4"
    output_dir = tmp_path / "output"
    input_path.write_bytes(b"input")
    request = _request(input_path.parent)
    request = replace(request, input_path=input_path, output_dir=output_dir)

    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry", lambda path: GEOMETRY
    )

    def fake_render(source, subtitle, destination, **kwargs):
        assert Path(subtitle).exists()
        preview = Path(destination) / "video-subtitle-preview.png"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(b"png")
        return str(preview)

    monkeypatch.setattr("multisubs.subtitler.render_subtitle_preview", fake_render)
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ):
        if name.split(".", 1)[0] in {"torch", "whisperx", "torchaudio", "torchvision"}:
            raise AssertionError(f"preview imported runtime dependency {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = cli._run_request(request, lambda message: None)

    assert result == output_dir / "video-subtitle-preview.png"
    assert not list(output_dir.glob(".multisubs-*"))


def test_animation_preview_branches_before_whisper_runtime_import(
    tmp_path: Path, monkeypatch
):
    input_path = tmp_path / "video.mp4"
    output_dir = tmp_path / "output"
    input_path.write_bytes(b"input")
    request = _request(input_path.parent)
    request = replace(
        request,
        input_path=input_path,
        output_dir=output_dir,
        preview_mode=PreviewMode.ANIMATION,
        preview_duration_ms=1_000,
    )

    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(
        "multisubs.subtitler.validate_animation_preview_support", lambda: None
    )
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry", lambda path: GEOMETRY
    )

    def fake_render(source, subtitle, destination, **kwargs):
        assert Path(subtitle).exists()
        preview = Path(destination) / "video-subtitle-animation-preview.mp4"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(b"mp4")
        return str(preview)

    monkeypatch.setattr(
        "multisubs.subtitler.render_subtitle_animation_preview", fake_render
    )
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ):
        if name.split(".", 1)[0] in {"torch", "whisperx", "torchaudio", "torchvision"}:
            raise AssertionError(f"preview imported runtime dependency {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    progress: list[str] = []
    result = cli._run_request(request, progress.append)

    assert result == output_dir / "video-subtitle-animation-preview.mp4"
    assert any("simulated word timings" in message for message in progress)
    assert not list(output_dir.glob(".multisubs-*"))
