import builtins
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from multisubs import cli
from multisubs.ass import write_ass
from multisubs.config import validate_subtitle_config
from multisubs.errors import ValidationError
from multisubs.layout import resolve_subtitle_config, resolve_wrapping_metrics
from multisubs.models import (
    PreviewRequest,
    SubtitlePosition,
    VideoGeometry,
)
from multisubs.preview import (
    DEFAULT_PREVIEW_TEXT,
    build_preview_ass,
    build_preview_guide_events,
    normalise_preview_text,
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


def test_preview_renders_only_the_first_segment_that_fits_the_envelope(
    tmp_path: Path,
):
    text = (
        "Example subtitle preview text that demonstrates a readable two-line "
        "caption on your selected video layout before final rendering"
    )
    compact_config = validate_subtitle_config(
        None,
        relative_values={"max_width": "300px", "max_height": "54px"},
    )
    spacious_config = validate_subtitle_config(
        None,
        relative_values={"max_width": "1600px", "max_height": "500px"},
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
            },
            anchor="bottom-center",
        )
    else:
        config = validate_subtitle_config(None, position="top-right")
    resolved = resolve_subtitle_config(config, GEOMETRY)
    metrics = resolve_wrapping_metrics(resolved, GEOMETRY)
    events = build_preview_guide_events(resolved, GEOMETRY, metrics, 1.0)

    assert events
    assert any("\\p1" in event.text for event in events)
    assert any("Preview guides" in event.text for event in events)
    assert any(r"\fs40" in event.text for event in events)
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
    events = build_preview_guide_events(resolved, GEOMETRY, metrics, 0.0)
    assert any("m 24 684" in event.text for event in events)


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
