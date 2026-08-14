import shutil
import subprocess
from pathlib import Path

import pytest

from multisubs.subtitler import embed_subtitles, validate_ffmpeg_support


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
