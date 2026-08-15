import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import ffmpeg
import pytest

from multisubs.errors import DependencyError, RenderingError, ValidationError
from multisubs.models import VideoGeometry
from multisubs.subtitler import (
    _build_output_stream,
    _parse_probe_payload,
    _short_output,
    embed_subtitles,
    probe_video_geometry,
    validate_ffmpeg_support,
)


def _geometry(**overrides):
    values = {
        "stream_index": 0,
        "coded_width": 1920,
        "coded_height": 1080,
        "render_width": 1920,
        "render_height": 1080,
        "rotation_degrees": 0,
        "sample_aspect_ratio": Fraction(1, 1),
        "display_aspect_ratio": Fraction(16, 9),
        "duration_seconds": 12.5,
    }
    values.update(overrides)
    return VideoGeometry(**values)


def _payload(streams, duration: str | None = "12.5"):
    format_data = {} if duration is None else {"duration": duration}
    return json.dumps({"streams": streams, "format": format_data})


def _video_stream(**overrides):
    values = {
        "index": 0,
        "codec_type": "video",
        "width": 1920,
        "height": 1080,
        "sample_aspect_ratio": "1:1",
    }
    values.update(overrides)
    return values


def test_subtitle_filter_is_structured_and_escapes_special_paths(tmp_path: Path):
    source = tmp_path / "video source.mp4"
    subtitle = tmp_path / "odd:comma,quote'back\\slash.ass"
    output = tmp_path / "output.mp4"

    command = ffmpeg.compile(
        _build_output_stream(ffmpeg, source, subtitle, output, _geometry())
    )
    command_text = " ".join(command)

    assert "subtitles=filename=" in command_text
    assert "0:a?" in command
    assert "\\:" in command_text
    assert "\\," in command_text
    assert "\\'" in command_text
    assert "\\\\slash.ass" in command_text
    assert "original_size=1920x1080" in command_text
    assert "-autorotate" in command


def test_probe_parser_normalizes_landscape_geometry_and_duration():
    geometry = _parse_probe_payload(_payload([_video_stream()]))

    assert geometry == _geometry()


def test_probe_parser_keeps_stored_portrait_dimensions():
    geometry = _parse_probe_payload(
        _payload([_video_stream(width=1080, height=1920)], duration=None)
    )

    assert geometry.render_width == 1080
    assert geometry.render_height == 1920
    assert geometry.display_aspect_ratio == Fraction(9, 16)
    assert geometry.duration_seconds is None


@pytest.mark.parametrize("rotation", [90, 270, -90])
def test_probe_parser_swaps_dimensions_for_right_angle_rotation(rotation):
    geometry = _parse_probe_payload(
        _payload([_video_stream(side_data_list=[{"rotation": rotation}])])
    )

    assert geometry.render_width == 1080
    assert geometry.render_height == 1920
    assert geometry.rotation_degrees == rotation % 360
    assert geometry.display_aspect_ratio == Fraction(9, 16)


def test_probe_parser_keeps_dimensions_for_180_rotation():
    geometry = _parse_probe_payload(_payload([_video_stream(tags={"rotate": "180"})]))

    assert geometry.render_width == 1920
    assert geometry.render_height == 1080
    assert geometry.rotation_degrees == 180


def test_probe_parser_accepts_equivalent_tag_and_display_matrix_rotation():
    geometry = _parse_probe_payload(
        _payload(
            [
                _video_stream(
                    tags={"rotate": "270"},
                    side_data_list=[{"rotation": 90}],
                )
            ]
        )
    )

    assert geometry.rotation_degrees == 90


def test_probe_parser_accounts_for_non_square_pixels_after_rotation():
    geometry = _parse_probe_payload(
        _payload(
            [
                _video_stream(
                    width=720,
                    height=480,
                    sample_aspect_ratio="8:9",
                    side_data_list=[{"rotation": 90}],
                )
            ]
        )
    )

    assert geometry.sample_aspect_ratio == Fraction(8, 9)
    assert geometry.display_aspect_ratio == Fraction(3, 4)


@pytest.mark.parametrize("sample_aspect_ratio", ["0:1", "1:0", "-1:1", "x:y"])
def test_probe_parser_rejects_invalid_sample_aspect_ratio(sample_aspect_ratio):
    with pytest.raises(ValidationError, match="sample aspect ratio"):
        _parse_probe_payload(
            _payload([_video_stream(sample_aspect_ratio=sample_aspect_ratio)])
        )


def test_probe_parser_selects_lowest_usable_video_stream_index():
    geometry = _parse_probe_payload(
        _payload(
            [
                _video_stream(index=4, width=640, height=360),
                _video_stream(index=1, width=1280, height=720),
                _video_stream(
                    index=0,
                    width=300,
                    height=300,
                    disposition={"attached_pic": 1},
                ),
            ]
        )
    )

    assert geometry.stream_index == 1
    assert geometry.render_width == 1280


def test_probe_parser_rejects_missing_video_and_contradictory_rotation():
    with pytest.raises(ValidationError, match="usable video stream"):
        _parse_probe_payload(_payload([{"index": 0, "codec_type": "audio"}]))

    with pytest.raises(ValidationError, match="contradictory rotation"):
        _parse_probe_payload(
            _payload(
                [
                    _video_stream(
                        tags={"rotate": "90"},
                        side_data_list=[{"rotation": 180}],
                    )
                ]
            )
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"width": 0},
        {"height": -1},
        {"width": "1920"},
        {"height": 32769},
    ],
)
def test_probe_parser_rejects_invalid_dimensions(overrides):
    with pytest.raises(ValidationError, match="video (width|height)"):
        _parse_probe_payload(_payload([_video_stream(**overrides)]))


def test_probe_reports_malformed_json_and_nonzero_exit(tmp_path: Path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr("multisubs.subtitler.shutil.which", lambda name: name)
    monkeypatch.setattr(
        "multisubs.subtitler.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="not-json", stderr=""
        ),
    )

    with pytest.raises(ValidationError, match="invalid JSON"):
        probe_video_geometry(source)

    monkeypatch.setattr(
        "multisubs.subtitler.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="bad\n" + "x" * 2_000
        ),
    )
    with pytest.raises(RenderingError) as error:
        probe_video_geometry(source)
    assert len(str(error.value)) < 1_200


def test_ffmpeg_validation_requires_ffprobe(monkeypatch):
    monkeypatch.setattr(
        "multisubs.subtitler.shutil.which",
        lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
    )

    with pytest.raises(DependencyError, match="ffprobe"):
        validate_ffmpeg_support()


def test_render_failure_removes_temporary_media(tmp_path: Path, monkeypatch):
    source = tmp_path / "video.mp4"
    subtitle = tmp_path / "subtitle.ass"
    output_dir = tmp_path / "output"
    source.write_bytes(b"input")
    subtitle.write_text("ASS", encoding="utf-8")

    class FakeFfmpegError(Exception):
        stderr = "render failed"

    class FakeOutput:
        def run(self, **kwargs):
            raise FakeFfmpegError()

    fake_ffmpeg = SimpleNamespace(Error=FakeFfmpegError)
    monkeypatch.setattr("multisubs.subtitler._load_ffmpeg_python", lambda: fake_ffmpeg)
    monkeypatch.setattr(
        "multisubs.subtitler._build_output_stream",
        lambda *args: FakeOutput(),
    )

    with pytest.raises(RenderingError):
        embed_subtitles(source, subtitle, output_dir, geometry=_geometry())

    assert list(output_dir.glob(".*.mp4")) == []
    assert not (output_dir / "video-en.mp4").exists()


def test_short_output_compacts_and_limits_ffmpeg_diagnostics():
    assert _short_output("first\nsecond", limit=20) == "first second"
    shortened = _short_output("start " + "x" * 100 + " final error", limit=30)
    assert len(shortened) == 30
    assert shortened.startswith("start")
    assert shortened.endswith("final error")
