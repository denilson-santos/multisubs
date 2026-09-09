"""Opt-in real renderer evidence for the multilingual regression foundation."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from multisubs.config import validate_subtitle_config
from multisubs.font_catalog import bundled_font_directory
from multisubs.models import TranscriptDocument
from multisubs.subtitler import probe_video_geometry
from multisubs.templates import get_subtitle_template
from multisubs.transcriber import write_transcription_artifacts
from scripts.replay_subtitle_layout import _geometry, replay

pytestmark = pytest.mark.integration
WQY = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
WQY_SHA256 = "79c18ebe7b811951e8311bad7103ebeae8c337ed9988ea69e8a78a66cfe029b9"


def _require_renderer():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg/ffprobe are required")


def _frame(ass: Path, fonts: Path) -> tuple[Image.Image, str]:
    # Both paths are pytest-owned and the bundled trusted fixture directory.
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "info",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=1080x1920:r=30",
            "-vf",
            f"subtitles=filename='{ass}':fontsdir='{fonts}'",
            "-frames:v",
            "1",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    return Image.frombytes("L", (1080, 1920), result.stdout), result.stderr.decode()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Multilingual Plan 1: Inter missing-glyph advances collide in real libass",
)
def test_japanese_fragment_advances_fit_rendered_glyphs(tmp_path, record_property):
    _require_renderer()
    if not WQY.is_file() or hashlib.sha256(WQY.read_bytes()).hexdigest() != WQY_SHA256:
        pytest.skip("Pinned fonts-wqy-zenhei 0.9.45-8 fixture is unavailable")
    words = [{"word": "ナ", "start": i * 0.2, "end": (i + 1) * 0.2} for i in range(4)]
    document = TranscriptDocument(
        Path("synthetic.mp4"),
        "ja",
        "transcribe",
        "synthetic",
        "ナナナナ",
        ({"text": "ナナナナ", "start": 0.0, "end": 0.8, "words": words},),
    )
    geometry = _geometry(
        {"rendering": {"render_width": 1080, "render_height": 1920}}, document
    )
    config = validate_subtitle_config(
        None,
        defaults=get_subtitle_template("amber-word").config,
        position="center",
    )
    paths = write_transcription_artifacts(document, tmp_path, config, geometry=geometry)
    ass = Path(paths[2]).read_text()
    centers = sorted({int(x) for x in re.findall(r"\\pos\((\d+),\d+\)", ass)})
    if len(centers) < 2:
        pytest.fail("Fixture did not produce positioned glyphs")
    header = ass.split("Dialogue:", 1)[0]
    single = tmp_path / "single.ass"
    single.write_text(
        header + "Dialogue: 0,0:00:00.00,0:00:00.80,Positioned,,0,0,0,,"
        r"{\an5\pos(540,960)\b600\bord0}ナ" + "\n"
    )
    with bundled_font_directory("Inter") as fonts:
        if fonts is None:
            raise RuntimeError("Bundled Inter fixture is unavailable")
        frame, log = _frame(single, fonts)
    bounds = frame.point(lambda value: 255 if value > 32 else 0).getbbox()
    if bounds is None:
        raise RuntimeError("Reference glyph did not render")
    advance = min(b - a for a, b in zip(centers, centers[1:], strict=False))
    width = bounds[2] - bounds[0]
    record_property("glyph_ink_width", width)
    record_property("fragment_advance", advance)
    record_property(
        "font_selection",
        "\n".join(
            line
            for line in log.splitlines()
            if "fontselect" in line or "libass" in line
        ),
    )
    assert advance >= width, f"Only {advance}px reserved for a {width}px rendered glyph"


def test_synthetic_replay_renders_without_speech_or_user_media(tmp_path):
    _require_renderer()
    source = tmp_path / "retained.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "metadata": {
                    "language": "pt",
                    "task": "transcribe",
                    "model": "synthetic",
                    "rendering": {"render_width": 320, "render_height": 240},
                },
                "transcription": {
                    "text": "Olá!",
                    "segments": [
                        {"text": "Olá!", "start": 0.0, "end": 0.2, "words": []},
                    ],
                },
            }
        )
    )
    destination = replay(source, tmp_path / "outputs", render=True, template="default")
    output = next(destination.glob("synthetic-background-pt.mp4"))
    geometry = probe_video_geometry(output)
    assert (geometry.render_width, geometry.render_height) == (320, 240)
    manifest = json.loads((destination / "evidence.json").read_text())
    assert manifest["render_status"] == "complete"
    assert manifest["video_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
