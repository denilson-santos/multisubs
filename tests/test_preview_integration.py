import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from multisubs.config import validate_subtitle_config
from multisubs.models import PreviewRequest
from multisubs.preview import build_preview_ass
from multisubs.subtitler import (
    probe_video_geometry,
    render_subtitle_preview,
    validate_ffmpeg_support,
)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("config", "text", "guides"),
    [
        (validate_subtitle_config(None, position="top-right"), "One line", False),
        (
            validate_subtitle_config(
                None,
                relative_values={
                    "position_x": "50%",
                    "position_y": "80%",
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
