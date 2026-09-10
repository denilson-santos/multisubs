"""Opt-in real renderer evidence for the multilingual regression foundation."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from multisubs.config import validate_subtitle_config
from multisubs.models import TranscriptDocument
from multisubs.subtitler import probe_video_geometry
from multisubs.templates import get_subtitle_template
from multisubs.transcriber import write_transcription_artifacts
from scripts.replay_subtitle_layout import _geometry, replay

pytestmark = pytest.mark.integration
WQY = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
WQY_SHA256 = "79c18ebe7b811951e8311bad7103ebeae8c337ed9988ea69e8a78a66cfe029b9"
DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_SHA256 = "690243adfefe0ce154b547db6205794bd30ac4277275179517a90994f4980648"
FREE_SANS = Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf")
FREE_SANS_SHA256 = "b59dd5eeab73f77897ae0144a6b443a004efa6a90a5e1a5b550ea28978cd38e8"
NIRMALA = Path("/mnt/c/Windows/Fonts/Nirmala.ttc")
NIRMALA_SHA256 = "ad02cdfc06e144ac45f318e8e5a64cbe04c7479d4beb91d25f5a319a466b1767"


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
        appearance_values={"fonts_dir": WQY.parent},
        position="center",
    )
    paths = write_transcription_artifacts(
        document,
        tmp_path,
        config,
        geometry=geometry,
        verify_font_coverage=True,
    )
    metadata = json.loads(Path(paths[0]).read_text())["metadata"]["rendering"]
    measurement = metadata["text_measurement"]
    assert measurement["requested_font"] == "Inter"
    assert measurement["resolved_font"] == "WenQuanYi Zen Hei"
    assert measurement["coverage"] == "verified"
    assert measurement["fallback_reason"] == "requested face lacks glyph coverage"
    ass = Path(paths[2]).read_text()
    assert "Style: Default,WenQuanYi Zen Hei," in ass
    centers = sorted({int(x) for x in re.findall(r"\\pos\((\d+),\d+\)", ass)})
    if len(centers) < 2:
        pytest.fail("Fixture did not produce positioned glyphs")
    header = ass.split("Dialogue:", 1)[0]
    single = tmp_path / "single.ass"
    single.write_text(
        header + "Dialogue: 0,0:00:00.00,0:00:00.80,Positioned,,0,0,0,,"
        r"{\an5\pos(540,960)\b600\bord0}ナ" + "\n"
    )
    frame, log = _frame(single, WQY.parent)

    def threshold(value: float) -> float:
        return 255.0 if value > 32 else 0.0

    bounds = frame.point(threshold).getbbox()
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


@pytest.mark.parametrize(
    ("language", "sample", "family", "font_path", "font_sha256"),
    [
        ("ar", "العربية", "DejaVu Sans", DEJAVU, DEJAVU_SHA256),
        ("fa", "فارسی", "DejaVu Sans", DEJAVU, DEJAVU_SHA256),
        ("ur", "اردو", "DejaVu Sans", DEJAVU, DEJAVU_SHA256),
        ("he", "עברית", "DejaVu Sans", DEJAVU, DEJAVU_SHA256),
        ("hi", "हिन्दी", "FreeSans", FREE_SANS, FREE_SANS_SHA256),
        ("te", "తెలుగు", "Nirmala UI", NIRMALA, NIRMALA_SHA256),
        ("ml", "മലയാളം", "FreeSans", FREE_SANS, FREE_SANS_SHA256),
    ],
)
def test_shaping_fallback_matches_full_line_libass_geometry(
    tmp_path, language, sample, family, font_path, font_sha256
):
    _require_renderer()
    if not font_path.is_file() or hashlib.sha256(
        font_path.read_bytes()
    ).hexdigest() != (font_sha256):
        pytest.skip(f"Pinned shaping font fixture for {language} is unavailable")
    text = f"{sample} 123 (test)"
    words = [
        {"word": sample, "start": 0.0, "end": 0.4},
        {"word": "123", "start": 0.4, "end": 0.7},
        {"word": "(test)", "start": 0.7, "end": 1.0},
    ]
    document = TranscriptDocument(
        Path("synthetic.mp4"),
        language,
        "transcribe",
        "synthetic",
        text,
        ({"text": text, "start": 0.0, "end": 1.0, "words": words},),
    )
    geometry = _geometry(
        {"rendering": {"render_width": 1080, "render_height": 1920}}, document
    )
    common = {
        "font": family,
        "fonts_dir": font_path.parent,
        "backdrop": "none",
    }
    plain_config = validate_subtitle_config(None, appearance_values=common)
    effect_config = validate_subtitle_config(
        None,
        appearance_values=common,
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "active-word",
        },
    )

    plain_paths = write_transcription_artifacts(
        document,
        tmp_path / "plain",
        plain_config,
        geometry=geometry,
        verify_font_coverage=True,
    )
    effect_paths = write_transcription_artifacts(
        document,
        tmp_path / "effect",
        effect_config,
        geometry=geometry,
        verify_font_coverage=True,
    )

    plain_frame, _ = _frame(Path(plain_paths[2]), font_path.parent)
    effect_frame, _ = _frame(Path(effect_paths[2]), font_path.parent)
    assert ImageChops.difference(plain_frame, effect_frame).getbbox() is None
    metadata = json.loads(Path(effect_paths[0]).read_text())["metadata"]["rendering"]
    assert metadata["word_effects"] == {
        "units": "alignment-records",
        "cues": 1,
        "fallback_cues": 1,
        "reasons": {"unsupported-word-shaping": 1},
        "renderer_strategies": {"full-line": 1},
    }
