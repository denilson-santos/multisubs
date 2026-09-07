import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from multisubs import cli
from multisubs.ass import write_ass
from multisubs.config import validate_subtitle_config
from multisubs.models import KaraokeCue, PreviewRequest, SubtitleDisplayFragment
from multisubs.preview import build_preview_ass
from multisubs.subtitler import (
    probe_video_geometry,
    render_subtitle_preview,
    validate_ffmpeg_support,
)
from multisubs.templates import TEMPLATE_CHOICES


@pytest.mark.integration
@pytest.mark.parametrize(
    ("config", "text", "guides"),
    [
        (
            validate_subtitle_config(
                None,
                position="top-right",
                appearance_values={"backdrop": "none"},
                relative_values={"outline_weight": "0px"},
            ),
            "One line",
            False,
        ),
        (
            validate_subtitle_config(
                None,
                appearance_values={"backdrop": "none"},
                relative_values={
                    "position_x": "50%",
                    "position_y": "80%",
                    "outline_weight": "0px",
                    "max_width": "60%",
                    "max_height": "30%",
                },
                anchor="bottom-center",
            ),
            "A two line preview with enough text to exercise wrapping",
            True,
        ),
    ],
)
def test_preview_png_matches_probe_geometry_for_named_and_custom_layouts(
    tmp_path: Path, config, text: str, guides: bool
):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "entrada com espaço-é.mp4"
    output_dir = tmp_path / "saída com espaço"
    ass_path = tmp_path / "preview fonte-é.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=320x180:d=1.2",
            "-frames:v",
            "36",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    geometry = probe_video_geometry(input_path)
    request = PreviewRequest(
        input_path=input_path,
        output_dir=output_dir,
        subtitle_config=config,
        preview_at=0.5,
        preview_text=text,
        guides=guides,
    )
    build_preview_ass(ass_path, request, geometry, 0.5)

    preview_path = Path(
        render_subtitle_preview(
            input_path,
            ass_path,
            output_dir,
            timestamp=0.5,
            geometry=geometry,
        )
    )

    assert preview_path.name == "entrada com espaço-é-subtitle-preview.png"
    assert preview_path.exists()
    with Image.open(preview_path) as image:
        assert image.size == (geometry.render_width, geometry.render_height)
        assert image.format == "PNG"
    assert not list(output_dir.glob(".*.png"))


@pytest.mark.integration
def test_animation_preview_clip_is_silent_h264_30fps_and_collision_safe(
    tmp_path: Path,
):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "animated input-é.mp4"
    output_dir = tmp_path / "animated output"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=#203040:s=320x180:d=1.2",
            "-frames:v",
            "36",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    parser = cli.build_parser()
    arguments = [
        "-i",
        str(input_path),
        "-o",
        str(output_dir),
        "--preview-animation",
        "--preview-at",
        "00:00:00.400",
        "--preview-duration",
        "2s",
        "--preview-text",
        "One, two, three four",
        "--template",
        "focus-marker",
    ]
    request = cli._build_request(parser.parse_args(arguments), parser)

    preview_path = cli._run_request(request, lambda _message: None)
    second_preview_path = cli._run_request(request, lambda _message: None)

    assert preview_path.name == "animated input-é-subtitle-animation-preview.mp4"
    assert second_preview_path.name == (
        "animated input-é-subtitle-animation-preview (1).mp4"
    )
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(preview_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(probe.stdout)
    streams = payload["streams"]
    assert len(streams) == 1
    assert streams[0]["codec_type"] == "video"
    assert streams[0]["codec_name"] == "h264"
    assert streams[0]["width"] == 320
    assert streams[0]["height"] == 180
    assert streams[0]["r_frame_rate"] == "30/1"
    assert streams[0]["pix_fmt"] == "yuv420p"
    assert abs(float(payload["format"]["duration"]) - 3.0) <= 1 / 30
    assert not list(output_dir.glob(".*"))


@pytest.mark.integration
def test_preview_and_timed_render_share_fragmented_outline_geometry(tmp_path: Path):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "outline-input.mp4"
    preview_ass = tmp_path / "preview-outline.ass"
    timed_ass = tmp_path / "timed-outline.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=#303030:s=640x360:d=1",
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
        position="center",
        appearance_values={
            "font": "DejaVu Sans",
            "backdrop": "outline",
            "backdrop_color": "#050505",
        },
        relative_values={
            "font_size": "40px",
            "outline_weight": "4px",
            "shadow_weight": "0px",
            "margin_left": "0px",
            "margin_right": "0px",
            "max_width": "400px",
            "max_height": "100px",
        },
        animation_values={
            "word_text_emphasis": "highlight",
            "word_text_mode": "progressive",
            "word_text_highlight_color": "#00F5D4",
        },
    )
    request = PreviewRequest(
        input_path=input_path,
        output_dir=tmp_path / "preview",
        subtitle_config=config,
        preview_at=0.45,
        preview_text="Ele tem...",
        guides=False,
    )
    build_preview_ass(preview_ass, request, geometry, 0.45)
    cue = KaraokeCue(
        fragments=(
            SubtitleDisplayFragment("Ele", 0),
            SubtitleDisplayFragment(" "),
            SubtitleDisplayFragment("tem...", 1),
        ),
        durations=(50, 50),
        active_intervals=((0, 40), (50, 80)),
    )
    write_ass(
        timed_ass,
        [{"start": 0.0, "end": 1.0, "text": "Ele tem...", "_karaoke_cue": cue}],
        config,
        geometry,
    )

    preview_path = Path(
        render_subtitle_preview(
            input_path,
            preview_ass,
            request.output_dir,
            timestamp=0.45,
            geometry=geometry,
        )
    )
    timed_path = Path(
        render_subtitle_preview(
            input_path,
            timed_ass,
            tmp_path / "timed",
            timestamp=0.45,
            geometry=geometry,
        )
    )

    with (
        Image.open(preview_path) as preview_image,
        Image.open(timed_path) as timed_image,
    ):
        assert (
            preview_image.convert("RGB").tobytes()
            == timed_image.convert("RGB").tobytes()
        )


@pytest.mark.integration
def test_fragmented_words_preserve_unfragmented_libass_spacing(tmp_path: Path):
    """Word positioning must not turn font-metric scale into visual tracking."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    input_path = tmp_path / "word-spacing-input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=#203040:s=640x360:d=1",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )
    parser = cli.build_parser()
    common = [
        "-i",
        str(input_path),
        "--preview-layout",
        "--preview-at",
        "00:00:00.100",
        "--preview-text",
        "Example subtitle",
        "--template",
        "golden-title",
    ]
    fragmented_request = cli._build_request(
        parser.parse_args([*common, "-o", str(tmp_path / "fragmented")]), parser
    )
    baseline_request = cli._build_request(
        parser.parse_args(
            [
                *common,
                "-o",
                str(tmp_path / "baseline"),
                "--animation-word-text-emphasis",
                "none",
            ]
        ),
        parser,
    )

    fragmented_path = cli._run_request(fragmented_request, lambda _message: None)
    baseline_path = cli._run_request(baseline_request, lambda _message: None)

    def yellow_geometry(path: Path) -> tuple[int, int, int]:
        with Image.open(path) as image:
            rgb = image.convert("RGB")

            def is_yellow(x: int, y: int) -> bool:
                pixel = rgb.getpixel((x, y))
                return (
                    isinstance(pixel, tuple)
                    and len(pixel) >= 3
                    and pixel[0] > 150
                    and pixel[1] > 100
                    and pixel[2] < 100
                )

            columns = sorted(
                {
                    x
                    for y in range(rgb.height)
                    for x in range(rgb.width)
                    if is_yellow(x, y)
                }
            )
        assert columns
        gaps = [
            following - current - 1
            for current, following in zip(columns, columns[1:], strict=False)
            if following - current > 1
        ]
        return min(columns), max(columns), max(gaps, default=0)

    fragmented_left, fragmented_right, fragmented_gap = yellow_geometry(fragmented_path)
    baseline_left, baseline_right, baseline_gap = yellow_geometry(baseline_path)

    assert abs(fragmented_left - baseline_left) <= 1
    assert abs(fragmented_right - baseline_right) <= 1
    assert fragmented_gap == baseline_gap


@pytest.mark.integration
@pytest.mark.parametrize("canvas", [(1920, 1080), (1080, 1920)])
def test_every_builtin_template_renders_with_bundled_fonts_on_common_geometries(
    tmp_path: Path, canvas: tuple[int, int]
):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    try:
        validate_ffmpeg_support()
    except Exception as exc:
        pytest.skip(str(exc))

    width, height = canvas
    input_path = tmp_path / f"template-{width}x{height}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=#203040:s={width}x{height}:d=0.4",
            "-frames:v",
            "12",
            "-c:v",
            "mpeg4",
            "-an",
            str(input_path),
        ],
        check=True,
    )

    for template_name in TEMPLATE_CHOICES:
        output_dir = tmp_path / template_name
        arguments = [
            "-i",
            str(input_path),
            "-o",
            str(output_dir),
            "--preview-layout",
            "--preview-at",
            "00:00:00.100",
            "--preview-text",
            "Ação, informação e útil: modelo 123!",
            "--template",
            template_name,
        ]
        parser = cli.build_parser()
        request = cli._build_request(parser.parse_args(arguments), parser)
        progress: list[str] = []

        preview_path = cli._run_request(request, progress.append)

        assert preview_path.exists()
        assert progress[0] == f"Using subtitle template: {template_name}."
        animation = request.subtitle_config.animation
        assert progress[1] == (
            "Resolved subtitle animations: "
            f"cue.text={cli._format_animation_track(animation.cue.text)}, "
            f"cue.backdrop={cli._format_animation_track(animation.cue.backdrop)}, "
            f"word.text={cli._format_animation_track(animation.word.text)}, "
            f"word.backdrop={cli._format_animation_track(animation.word.backdrop)}."
        )
        with Image.open(preview_path) as image:
            assert image.size == canvas
            assert image.format == "PNG"

    active_output_dir = tmp_path / "amber-word-active-word"
    active_arguments = [
        "-i",
        str(input_path),
        "-o",
        str(active_output_dir),
        "--preview-layout",
        "--preview-at",
        "00:00:00.100",
        "--preview-text",
        "Primeira palavra destacada no modo ativo",
        "--template",
        "amber-word",
        "--animation-word-text-mode",
        "active-word",
    ]
    parser = cli.build_parser()
    active_request = cli._build_request(parser.parse_args(active_arguments), parser)

    active_preview = cli._run_request(active_request, lambda _message: None)

    with Image.open(active_preview) as image:
        assert image.size == canvas
        assert image.format == "PNG"
