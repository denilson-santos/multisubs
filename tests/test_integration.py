import re
import shutil
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs.ass import write_ass
from multisubs.config import validate_subtitle_config
from multisubs.layout import resolve_subtitle_config
from multisubs.models import SubtitlePosition
from multisubs.subtitler import (
    embed_subtitles,
    probe_video_geometry,
    validate_ffmpeg_support,
)
from multisubs.transcriber import layout_subtitle_cues


@pytest.mark.integration
@pytest.mark.parametrize(
    ("font", "font_weight", "requested_rank", "resolved_rank"),
    [
        ("Roboto", "regular", 400, 400),
        ("Roboto", "extra-light", 200, 200),
        ("Roboto", "semi-bold", 600, 600),
        ("Roboto", "extra-bold", 800, 800),
    ],
)
def test_resolved_font_measurement_tracks_libass_bounds(
    tmp_path: Path,
    font: str,
    font_weight: str,
    requested_rank: int,
    resolved_rank: int,
):
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "font-metrics-input.mp4"
    subtitle_path = tmp_path / "font-metrics.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1920x1080:d=0.2",
            "-t",
            "0.2",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(
        None,
        appearance_values={
            "font": font,
            "font_weight": font_weight,
            "backdrop": "none",
        },
        relative_values={
            "font_size": "43px",
            "shadow_weight": "0px",
            "margin_left": "0%",
            "margin_right": "0%",
            "max_width": "100%",
        },
    )
    resolved = resolve_subtitle_config(config, geometry)
    text = (
        "divulgou um vídeo nas redes sociais agradecendo o apoio recebido nos "
        "últimos dias."
    )
    display, metrics = layout_subtitle_cues(
        [{"id": 0, "start": 0.0, "end": 0.2, "text": text, "words": []}],
        resolved,
        geometry,
        language="pt",
    )
    if (
        metrics.text_measurer.info.mode != "font-metrics"
        or metrics.text_measurer.info.resolved_font != font
        or metrics.text_measurer.info.resolved_weight != resolved_rank
    ):
        pytest.fail(f"Bundled {font} {font_weight} did not resolve as expected")
    assert metrics.text_measurer.info.font_source == "bundled"
    assert metrics.text_measurer.info.requested_weight == requested_rank
    fonts_dir = metrics.text_measurer.info.renderer_fonts_dir
    assert fonts_dir is not None

    measured_width = metrics.text_measurer.measure(text)
    assert measured_width < metrics.width_budget
    assert display[0]["text"] == text

    write_ass(subtitle_path, display, config, geometry)
    output_path = Path(
        embed_subtitles(
            input_path,
            subtitle_path,
            tmp_path,
            geometry=geometry,
            fonts_dir=fonts_dir,
        )
    )
    bbox = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(output_path),
            "-vf",
            "bbox=min_val=32",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    matches = re.findall(r"x1:\d+ x2:\d+ y1:\d+ y2:\d+ w:(\d+)", bbox.stderr)
    assert matches, bbox.stderr
    rendered_width = int(matches[-1])
    tolerance = max(40.0, measured_width * 0.08)
    assert abs(rendered_width - measured_width) <= tolerance


@pytest.mark.integration
@pytest.mark.parametrize(
    ("canvas", "letter_spacing", "expected_spacing"),
    [
        ((1920, 1080), "0px", 0),
        ((1920, 1080), "2px", 2),
        ((1920, 1080), "4%", 2),
        ((1080, 1920), "0px", 0),
        ((1080, 1920), "2px", 2),
        ((1080, 1920), "4%", 2),
    ],
)
def test_resolved_font_letter_spacing_tracks_libass_bounds(
    tmp_path: Path,
    canvas: tuple[int, int],
    letter_spacing: str,
    expected_spacing: int,
):
    """Keep measured tracking and the native ASS spacing field aligned."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    width, height = canvas
    input_path = tmp_path / "letter-spacing-input.mp4"
    subtitle_path = tmp_path / "letter-spacing.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d=0.2",
            "-t",
            "0.2",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(
        None,
        appearance_values={"font": "Roboto", "backdrop": "none"},
        relative_values={
            "font_size": "43px",
            "letter_spacing": letter_spacing,
            "shadow_weight": "0px",
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "100%",
        },
    )
    resolved = resolve_subtitle_config(config, geometry)
    text = "Spacing changes measured subtitle width"
    display, metrics = layout_subtitle_cues(
        [{"id": 0, "start": 0.0, "end": 0.2, "text": text, "words": []}],
        resolved,
        geometry,
    )
    if (
        metrics.text_measurer.info.mode != "font-metrics"
        or metrics.text_measurer.info.resolved_font != "Roboto"
    ):
        pytest.fail("Bundled Roboto did not resolve as expected")
    assert metrics.text_measurer.info.font_source == "bundled"
    fonts_dir = metrics.text_measurer.info.renderer_fonts_dir
    assert fonts_dir is not None

    assert metrics.letter_spacing == expected_spacing
    assert display[0]["text"] == text
    write_ass(subtitle_path, display, config, geometry)
    style_fields = (
        subtitle_path.read_text(encoding="utf-8")
        .split("Style: Default,", 1)[1]
        .split(",")
    )
    assert style_fields[12] == str(expected_spacing)
    assert r"{\fsp" not in subtitle_path.read_text(encoding="utf-8")

    output_path = Path(
        embed_subtitles(
            input_path,
            subtitle_path,
            tmp_path,
            geometry=geometry,
            fonts_dir=fonts_dir,
        )
    )
    bbox = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(output_path),
            "-vf",
            "bbox=min_val=32",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    matches = re.findall(r"x1:\d+ x2:\d+ y1:\d+ y2:\d+ w:(\d+)", bbox.stderr)
    assert matches, bbox.stderr
    rendered_width = int(matches[-1])
    measured_width = metrics.text_measurer.measure(text)
    tolerance = max(40.0, measured_width * 0.08)
    assert abs(rendered_width - measured_width) <= tolerance


@pytest.mark.integration
def test_ffmpeg_libass_render_round_trip(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is not installed")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "input.mp4"
    subtitle_path = tmp_path / "subtitle.ass"
    subtitle_path.write_text(
        "\n".join(
            (
                "[Script Info]",
                "ScriptType: v4.00+",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Arial,16,&H00FFFFFF,&H00FFFFFF,&H00000000,"
                "&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
                "MarginV, Effect, Text",
                "Dialogue: 0,0:00:00.00,0:00:00.20,Default,,0,0,0,,Test",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:d=0.2",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=8000:cl=mono",
            "-t",
            "0.2",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-shortest",
            str(input_path),
        ],
        check=True,
    )

    output_path = Path(embed_subtitles(input_path, subtitle_path, tmp_path, "en"))

    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.integration
def test_subtitle_opacity_changes_intensity_without_moving_libass_bounds(
    tmp_path: Path,
):
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is not installed")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    width, height = 320, 180
    input_path = tmp_path / "opacity-input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d=0.3",
            "-t",
            "0.3",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)

    frames: dict[str, bytes] = {}
    for opacity in ("100%", "50%", "0%"):
        subtitle_path = tmp_path / f"opacity-{opacity[:-1]}.ass"
        config = validate_subtitle_config(
            None,
            appearance_values={
                "font": "DejaVu Sans",
                "backdrop": "none",
                "text_color": "#FFFFFFFF",
                "opacity": opacity,
            },
            relative_values={
                "font_size": "40px",
                "shadow_weight": "0px",
            },
        )
        write_ass(
            subtitle_path,
            [{"start": 0.0, "end": 0.3, "text": "Opacity"}],
            config,
            geometry,
        )
        frames[opacity] = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "0.1",
                "-i",
                str(input_path),
                "-vf",
                f"ass={subtitle_path}",
                "-frames:v",
                "1",
                "-pix_fmt",
                "gray",
                "-f",
                "rawvideo",
                "-",
            ],
            capture_output=True,
            check=True,
        ).stdout

    assert all(len(frame) == width * height for frame in frames.values())
    intensities = {opacity: sum(frame) for opacity, frame in frames.items()}
    assert intensities["100%"] > intensities["50%"] > intensities["0%"]
    assert intensities["0%"] == 0
    ratio = intensities["50%"] / intensities["100%"]
    assert 0.4 <= ratio <= 0.6

    def bounds(frame: bytes) -> tuple[int, int, int, int]:
        foreground = [index for index, value in enumerate(frame) if value > 10]
        assert foreground
        x_values = [index % width for index in foreground]
        y_values = [index // width for index in foreground]
        return min(x_values), max(x_values), min(y_values), max(y_values)

    assert bounds(frames["100%"]) == bounds(frames["50%"])


@pytest.mark.integration
def test_subtitle_text_case_reaches_real_libass_rendering(tmp_path: Path):
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

    width, height = 320, 180
    input_path = tmp_path / "text-case-input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d=0.3",
            "-t",
            "0.3",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    frames: dict[str, bytes] = {}

    for text_case, expected in (("original", "Straße"), ("uppercase", "STRASSE")):
        subtitle_path = tmp_path / f"text-case-{text_case}.ass"
        config = validate_subtitle_config(
            None,
            appearance_values={
                "font": "DejaVu Sans",
                "backdrop": "none",
                "text_case": text_case,
            },
            relative_values={
                "font_size": "40px",
                "shadow_weight": "0px",
                "margin_left": "0px",
                "margin_right": "0px",
                "max_width": "260px",
                "max_height": "80px",
            },
        )
        resolved = resolve_subtitle_config(config, geometry)
        display, _ = layout_subtitle_cues(
            [{"start": 0.0, "end": 0.3, "text": "Straße", "words": []}],
            resolved,
            geometry,
        )
        assert display[0]["text"] == expected
        write_ass(subtitle_path, display, config, geometry)
        frames[text_case] = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "0.1",
                "-i",
                str(input_path),
                "-vf",
                f"ass={subtitle_path}",
                "-frames:v",
                "1",
                "-pix_fmt",
                "gray",
                "-f",
                "rawvideo",
                "-",
            ],
            capture_output=True,
            check=True,
        ).stdout

    assert all(len(frame) == width * height for frame in frames.values())
    assert sum(frames["original"]) > 0
    assert sum(frames["uppercase"]) > 0
    assert frames["original"] != frames["uppercase"]


@pytest.mark.integration
def test_adaptive_wrapping_renders_the_resolved_display_cue(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is not installed")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "adaptive-input.mp4"
    subtitle_path = tmp_path / "adaptive.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=0.4",
            "-t",
            "0.4",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(
        None,
        relative_values={"max_width": "40%", "font_size": "8px"},
    )
    resolved = resolve_subtitle_config(config, geometry)
    semantic = [
        {
            "id": 0,
            "start": 0.0,
            "end": 0.4,
            "text": "A long subtitle cue follows the resolved width budget",
            "words": [],
        }
    ]
    display, metrics = layout_subtitle_cues(semantic, resolved, geometry)

    assert metrics.width_budget == 82
    assert display[0]["text"].count("\n") <= metrics.line_capacity - 1
    write_ass(subtitle_path, display, config, geometry)
    output_path = Path(
        embed_subtitles(input_path, subtitle_path, tmp_path, geometry=geometry)
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.integration
def test_explicit_line_height_libass_uses_measured_baseline_spacing(
    tmp_path: Path,
):
    """Compile positioned lines and verify their PlayRes baseline delta."""
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

    input_path = tmp_path / "line-height-input.mp4"
    subtitle_path = tmp_path / "line-height.ass"
    output_path = tmp_path / "line-height-output.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=0.4",
            "-t",
            "0.4",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(
        None,
        appearance_values={"font": "DejaVu Sans", "backdrop": "none"},
        relative_values={
            "font_size": "20px",
            "line_height": "40px",
            "shadow_weight": "0px",
            "max_width": "80%",
            "max_height": "80%",
        },
    )
    write_ass(
        subtitle_path,
        [{"start": 0.0, "end": 0.4, "text": "FIRST\nSECOND"}],
        config,
        geometry,
        preserve_line_breaks=True,
    )
    ass_lines = [
        line
        for line in subtitle_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: 1,")
    ]
    assert len(ass_lines) == 2
    positions = [
        int(match.group("y"))
        for line in ass_lines
        if (match := re.search(r"\\pos\(160,(?P<y>\d+)\)", line))
    ]
    assert len(positions) == 2
    assert positions[1] - positions[0] == 40

    embed_subtitles(
        input_path,
        subtitle_path,
        tmp_path,
        output_path=output_path,
        geometry=geometry,
    )
    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.integration
def test_ffmpeg_libass_render_supports_video_without_audio(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is not installed")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "video-only.mp4"
    subtitle_path = tmp_path / "subtitle.ass"
    subtitle_path.write_text(
        "\n".join(
            (
                "[Script Info]",
                "ScriptType: v4.00+",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Arial,16,&H00FFFFFF,&H00FFFFFF,&H00000000,"
                "&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
                "MarginV, Effect, Text",
                "Dialogue: 0,0:00:00.00,0:00:00.20,Default,,0,0,0,,Test",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:d=0.2",
            "-t",
            "0.2",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )

    output_path = Path(embed_subtitles(input_path, subtitle_path, tmp_path, "en"))

    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("size", "sample_aspect_ratio", "expected_display_aspect_ratio"),
    [
        ("160x90", "1/1", Fraction(16, 9)),
        ("90x160", "1/1", Fraction(9, 16)),
        ("120x120", "1/1", Fraction(1, 1)),
        ("120x90", "4/3", Fraction(16, 9)),
    ],
)
def test_probe_generated_video_geometry(
    tmp_path: Path,
    size: str,
    sample_aspect_ratio: str,
    expected_display_aspect_ratio: Fraction,
):
    input_path = tmp_path / "geometry.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={size}:d=0.2",
            "-vf",
            f"setsar={sample_aspect_ratio}",
            "-t",
            "0.2",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )

    geometry = probe_video_geometry(input_path)

    width, height = (int(value) for value in size.split("x"))
    assert (geometry.render_width, geometry.render_height) == (width, height)
    assert geometry.display_aspect_ratio == expected_display_aspect_ratio


@pytest.mark.integration
def test_rotation_canvas_matches_autorotated_rendered_frame(tmp_path: Path):
    base_path = tmp_path / "base.mp4"
    input_path = tmp_path / "rotated.mp4"
    subtitle_path = tmp_path / "rotated.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:d=0.2",
            "-t",
            "0.2",
            "-c:v",
            "mpeg4",
            "-an",
            str(base_path),
        ],
        check=True,
    )
    ffmpeg_help = subprocess.run(
        ["ffmpeg", "-hide_banner", "-h", "full"],
        check=True,
        capture_output=True,
        text=True,
    )
    supports_display_rotation = "-display_rotation" in (
        f"{ffmpeg_help.stdout}\n{ffmpeg_help.stderr}"
    )
    # Newer FFmpeg builds use input-side display rotation. Keep the legacy
    # metadata fallback for older developer environments.
    rotation_input_args = (
        ["-display_rotation:v:0", "90"] if supports_display_rotation else []
    )
    rotation_output_args = (
        [] if supports_display_rotation else ["-metadata:s:v:0", "rotate=90"]
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            *rotation_input_args,
            "-i",
            str(base_path),
            "-c",
            "copy",
            *rotation_output_args,
            str(input_path),
        ],
        check=True,
    )

    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(None)
    config = replace(
        config,
        appearance=replace(config.appearance, font_size=16),
        layout=replace(config.layout, margin_top=12, margin_bottom=12),
    )
    write_ass(
        subtitle_path,
        [{"start": 0.0, "end": 0.2, "text": "Test"}],
        config,
        geometry,
    )
    output_path = Path(
        embed_subtitles(
            input_path,
            subtitle_path,
            tmp_path,
            geometry=geometry,
        )
    )
    rendered_geometry = probe_video_geometry(output_path)

    assert geometry.rotation_degrees == 90
    assert (geometry.render_width, geometry.render_height) == (90, 160)
    assert (rendered_geometry.render_width, rendered_geometry.render_height) == (
        geometry.render_width,
        geometry.render_height,
    )


@pytest.mark.integration
def test_relative_test_layout_has_consistent_rendered_bounds(tmp_path: Path):
    normalized_bounds: list[tuple[float, float, float]] = []
    fixed_glyph_heights: list[int] = []
    cases = (
        (320, 180, "1/1"),
        (640, 360, "1/1"),
        (180, 320, "1/1"),
        (240, 240, "1/1"),
        (240, 180, "4/3"),
    )
    for width, height, sample_aspect_ratio in cases:
        input_path = tmp_path / f"input-{width}x{height}.mp4"
        subtitle_path = tmp_path / f"subtitle-{width}x{height}.ass"
        output_path = tmp_path / f"rendered-{width}x{height}.mp4"
        fixed_subtitle_path = tmp_path / f"fixed-subtitle-{width}x{height}.ass"
        fixed_output_path = tmp_path / f"fixed-rendered-{width}x{height}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={width}x{height}:d=0.2",
                "-vf",
                f"setsar={sample_aspect_ratio}",
                "-t",
                "0.2",
                "-c:v",
                "mpeg4",
                "-an",
                str(input_path),
            ],
            check=True,
        )
        geometry = probe_video_geometry(input_path)
        config = validate_subtitle_config(
            None,
            relative_values={
                "font_size": "10%",
                "outline_weight": "0px",
                "shadow_weight": "0px",
                "margin_bottom": "10%",
            },
        )
        write_ass(
            subtitle_path,
            [{"start": 0.0, "end": 0.2, "text": "TEST"}],
            config,
            geometry,
        )
        embed_subtitles(
            input_path,
            subtitle_path,
            tmp_path,
            output_path=output_path,
            geometry=geometry,
        )

        def measure_foreground(
            video_path: Path, frame_width: int, frame_height: int
        ) -> tuple[float, float, float]:
            frame = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    "0.1",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-pix_fmt",
                    "gray",
                    "-f",
                    "rawvideo",
                    "pipe:1",
                ],
                check=True,
                capture_output=True,
            ).stdout
            foreground = [index for index, value in enumerate(frame) if value > 80]
            assert foreground
            x_values = [index % frame_width for index in foreground]
            y_values = [index // frame_width for index in foreground]
            return (
                (min(x_values) + max(x_values)) / 2 / frame_width,
                max(y_values) - min(y_values) + 1,
                (frame_height - 1 - max(y_values)) / frame_height,
            )

        center_x, rendered_glyph_height, bottom_gap = measure_foreground(
            output_path, width, height
        )
        normalized_bounds.append((center_x, rendered_glyph_height / height, bottom_gap))

        fixed_config = validate_subtitle_config(
            None,
            relative_values={
                "font_size": "18px",
                "outline_weight": "0px",
                "shadow_weight": "0px",
                "margin_bottom": "12px",
            },
        )
        write_ass(
            fixed_subtitle_path,
            [{"start": 0.0, "end": 0.2, "text": "TEST"}],
            fixed_config,
            geometry,
        )
        embed_subtitles(
            input_path,
            fixed_subtitle_path,
            tmp_path,
            output_path=fixed_output_path,
            geometry=geometry,
        )
        _, fixed_glyph_height, _ = measure_foreground(fixed_output_path, width, height)
        fixed_glyph_heights.append(round(fixed_glyph_height))

    for metric in zip(*normalized_bounds, strict=True):
        assert max(metric) - min(metric) < 0.035
    assert max(fixed_glyph_heights) - min(fixed_glyph_heights) <= 3


@pytest.mark.integration
@pytest.mark.parametrize(
    (
        "width",
        "height",
        "layout_id",
        "position",
        "values",
        "vertical_region",
        "margins",
    ),
    [
        (320, 180, "default", None, {}, "bottom", (58, 58, 0, 9)),
        (
            320,
            180,
            "historical-landscape",
            "bottom-center",
            {
                "margin_left": "6%",
                "margin_right": "6%",
                "margin_bottom": "6%",
                "max_width": "100%",
                "max_height": "10.5%",
            },
            "bottom",
            (19, 19, 0, 11),
        ),
        (
            180,
            320,
            "historical-portrait",
            "bottom-center",
            {
                "margin_left": "8%",
                "margin_right": "8%",
                "margin_bottom": "8%",
                "max_width": "100%",
                "max_height": "6%",
            },
            "bottom",
            (14, 14, 0, 26),
        ),
        (
            240,
            240,
            "historical-square",
            "bottom-center",
            {
                "margin_left": "7%",
                "margin_right": "7%",
                "margin_bottom": "7%",
                "max_width": "100%",
                "max_height": "10.6%",
            },
            "bottom",
            (17, 17, 0, 17),
        ),
        (
            320,
            180,
            "historical-vertical-social",
            "bottom-center",
            {
                "margin_left": "8%",
                "margin_right": "12%",
                "margin_bottom": "16%",
                "max_width": "100%",
                "max_height": "6.6%",
            },
            "bottom",
            (26, 38, 0, 29),
        ),
        (
            320,
            180,
            "historical-upper-third",
            "top-center",
            {
                "margin_left": "6%",
                "margin_right": "6%",
                "margin_top": "8%",
                "max_width": "100%",
                "max_height": "10.7%",
            },
            "top",
            (19, 19, 14, 9),
        ),
        (
            320,
            180,
            "historical-centered",
            "center",
            {
                "margin_left": "8%",
                "margin_right": "8%",
                "max_width": "100%",
                "max_height": "10%",
            },
            "middle",
            (26, 26, 0, 9),
        ),
    ],
)
def test_default_and_historical_layout_values_render_inside_expected_regions(
    tmp_path: Path,
    width: int,
    height: int,
    layout_id: str,
    position: str | None,
    values: dict[str, str],
    vertical_region: str,
    margins: tuple[int, int, int, int],
):
    input_path = tmp_path / f"layout-input-{layout_id}-{width}x{height}.mp4"
    subtitle_path = tmp_path / f"layout-{layout_id}-{width}x{height}.ass"
    output_path = tmp_path / f"layout-{layout_id}-{width}x{height}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d=0.3",
            "-t",
            "0.3",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )

    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(None, position=position, relative_values=values)
    resolved = resolve_subtitle_config(config, geometry)
    assert (
        resolved.layout.margin_left,
        resolved.layout.margin_right,
        resolved.layout.margin_top,
        resolved.layout.margin_bottom,
    ) == margins
    write_ass(
        subtitle_path,
        [{"start": 0.0, "end": 0.3, "text": "PRESET"}],
        config,
        geometry,
    )
    embed_subtitles(
        input_path,
        subtitle_path,
        tmp_path,
        output_path=output_path,
        geometry=geometry,
    )
    frame = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0.15",
            "-i",
            str(output_path),
            "-frames:v",
            "1",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    ).stdout
    foreground = [index for index, value in enumerate(frame) if value > 80]
    assert foreground
    x_values = [index % width for index in foreground]
    y_values = [index // width for index in foreground]
    center_x = (min(x_values) + max(x_values)) / 2 / width
    center_y = (min(y_values) + max(y_values)) / 2 / height
    assert 0.35 < center_x < 0.65
    if vertical_region == "top":
        assert center_y < 0.45
    elif vertical_region == "bottom":
        assert center_y > 0.55
    else:
        assert 0.35 < center_y < 0.65


@pytest.mark.integration
def test_named_positions_render_inside_expected_frame_thirds(tmp_path: Path):
    input_path = tmp_path / "positions-input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=0.3",
            "-t",
            "0.3",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )

    for position in SubtitlePosition:
        subtitle_path = tmp_path / f"{position.value}.ass"
        output_path = tmp_path / f"{position.value}.mp4"
        geometry = probe_video_geometry(input_path)
        relative_values = {
            "font_size": "18px",
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
        )
        write_ass(
            subtitle_path,
            [{"start": 0.0, "end": 0.3, "text": "TEST"}],
            config,
            geometry,
        )
        embed_subtitles(
            input_path,
            subtitle_path,
            tmp_path,
            output_path=output_path,
            geometry=geometry,
        )
        frame = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "0.15",
                "-i",
                str(output_path),
                "-frames:v",
                "1",
                "-pix_fmt",
                "gray",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        ).stdout
        foreground = [index for index, value in enumerate(frame) if value > 80]
        assert foreground
        x_values = [index % 320 for index in foreground]
        y_values = [index // 320 for index in foreground]
        center_x = (min(x_values) + max(x_values)) / 2 / 320
        center_y = (min(y_values) + max(y_values)) / 2 / 180

        if position.value.endswith("left"):
            assert center_x < 1 / 3
        elif position.value.endswith("right"):
            assert center_x > 2 / 3
        else:
            assert 1 / 3 < center_x < 2 / 3

        if position.value.startswith("top"):
            assert center_y < 1 / 3
        elif position.value.startswith("bottom"):
            assert center_y > 2 / 3
        else:
            assert 1 / 3 < center_y < 2 / 3


@pytest.mark.integration
@pytest.mark.parametrize(
    ("position_x", "position_y", "anchor", "expected"),
    [
        ("50%", "50%", "center", "center"),
        ("10%", "10%", "top-left", "top-left"),
        ("50%", "86%", "bottom-center", "bottom-center"),
    ],
)
def test_custom_coordinates_render_at_requested_anchor(
    tmp_path: Path,
    position_x: str,
    position_y: str,
    anchor: str,
    expected: str,
):
    input_path = tmp_path / f"custom-{expected}-input.mp4"
    subtitle_path = tmp_path / f"custom-{expected}.ass"
    output_path = tmp_path / f"custom-{expected}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=0.3",
            "-t",
            "0.3",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )

    geometry = probe_video_geometry(input_path)
    config = validate_subtitle_config(
        None,
        relative_values={
            "position_x": position_x,
            "position_y": position_y,
            "max_width": "40%",
            "max_height": "20%",
        },
        anchor=anchor,
    )
    write_ass(
        subtitle_path,
        [{"start": 0.0, "end": 0.3, "text": "ONE\nTWO"}],
        config,
        geometry,
    )
    embed_subtitles(
        input_path,
        subtitle_path,
        tmp_path,
        output_path=output_path,
        geometry=geometry,
    )

    frame = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0.15",
            "-i",
            str(output_path),
            "-frames:v",
            "1",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    ).stdout
    foreground = [index for index, value in enumerate(frame) if value > 80]
    assert foreground
    x_values = [index % 320 for index in foreground]
    y_values = [index // 320 for index in foreground]
    min_x, max_x = min(x_values), max(x_values)
    min_y, max_y = min(y_values), max(y_values)
    center_x = (min_x + max_x) / 2 / 320
    center_y = (min_y + max_y) / 2 / 180

    if expected == "center":
        assert abs(center_x - 0.5) < 0.08
        assert abs(center_y - 0.5) < 0.12
    elif expected == "top-left":
        assert min_x / 320 > 0.02
        assert min_x / 320 < 0.2
        assert min_y / 180 > 0.02
        assert min_y / 180 < 0.2
    else:
        assert abs(center_x - 0.5) < 0.08
        assert center_y > 0.55
        assert max_y / 180 > 0.75
