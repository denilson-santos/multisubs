import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import cli
from multisubs.ass import (
    allocate_active_word_intervals,
    allocate_karaoke_durations,
    rgba_to_ass_color_override,
    write_ass,
)
from multisubs.config import (
    DEFAULT_KARAOKE_HIGHLIGHT_COLOR,
    validate_subtitle_config,
)
from multisubs.errors import ArtifactError, ValidationError
from multisubs.layout import resolve_subtitle_config
from multisubs.models import (
    KaraokeCue,
    KaraokeMode,
    SubtitleDisplayFragment,
    TranscriptDocument,
    VideoGeometry,
)
from multisubs.subtitler import (
    embed_subtitles,
    probe_video_geometry,
    validate_ffmpeg_support,
)
from multisubs.transcriber import (
    layout_subtitle_cues,
    prepare_karaoke_cues,
    write_transcription_artifacts,
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
    duration_seconds=12.5,
)


def _word(text: str, start: float, end: float):
    return {"word": text, "start": start, "end": end}


def test_karaoke_config_resolves_default_and_custom_highlight_colors():
    default = validate_subtitle_config(None, effects_values={"karaoke": True})
    custom = validate_subtitle_config(
        None,
        effects_values={
            "karaoke": True,
            "karaoke_mode": "active-word",
            "highlight_color": "#abcdef80",
        },
    )

    assert default.effects.karaoke is True
    assert default.effects.highlight_color == DEFAULT_KARAOKE_HIGHLIGHT_COLOR
    assert default.effects.mode is KaraokeMode.PROGRESSIVE
    assert custom.effects.mode is KaraokeMode.ACTIVE_WORD
    assert custom.effects.highlight_color == "#ABCDEF80"


@pytest.mark.parametrize(
    "effects",
    [
        {"highlight_color": "#FFD54F"},
        {"karaoke_mode": "active-word"},
        {"karaoke": True, "highlight_color": "white"},
        {"karaoke": True, "karaoke_mode": "unknown"},
    ],
)
def test_karaoke_effect_validation_rejects_meaningless_or_invalid_colors(effects):
    with pytest.raises(ValidationError):
        validate_subtitle_config(None, effects_values=effects)


def test_karaoke_cli_request_is_typed_and_translation_is_rejected(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--karaoke",
            "--karaoke-mode",
            "active-word",
            "--karaoke-highlight-color",
            "#abcdef80",
        ]
    )

    request = cli._build_request(args, parser)

    assert request.subtitle_config.effects.karaoke is True
    assert request.subtitle_config.effects.mode is KaraokeMode.ACTIVE_WORD
    assert request.subtitle_config.effects.highlight_color == "#ABCDEF80"

    with pytest.raises(SystemExit) as error:
        cli._build_request(
            parser.parse_args(
                [
                    "-i",
                    str(input_path),
                    "--karaoke",
                    "--task",
                    "translate",
                    "--model",
                    "medium",
                ]
            ),
            parser,
        )
    assert error.value.code == 2


@pytest.mark.parametrize(
    "effect_options",
    [
        ["--karaoke-highlight-color", "#FFD54F"],
        ["--karaoke-mode", "active-word"],
    ],
)
def test_karaoke_cli_rejects_effect_options_without_karaoke(
    tmp_path: Path,
    effect_options: list[str],
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        cli._build_request(
            parser.parse_args(["-i", str(input_path), *effect_options]),
            parser,
        )

    assert error.value.code == 2


def test_karaoke_cli_rejects_transcription_free_preview(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        cli._build_request(
            parser.parse_args(["-i", str(input_path), "--preview-layout", "--karaoke"]),
            parser,
        )

    assert error.value.code == 2


def test_karaoke_duration_allocation_conserves_quantized_cue_duration():
    words = [_word("one", 0.001, 0.4), _word("two", 0.505, 1.0)]

    assert allocate_karaoke_durations(0.001, 1.0, words) == (50, 50)


def test_active_word_intervals_use_word_ends_and_leave_pause_gaps():
    words = [
        _word("one", 0.0, 0.25),
        _word("two", 0.4, 0.7),
        _word("three", 0.6, 1.0),
    ]

    assert allocate_active_word_intervals(0.0, 1.0, words) == (
        (0, 25),
        (40, 60),
        (60, 100),
    )


@pytest.mark.parametrize(
    "cue_start, words",
    [
        (0.0, [_word("one", 0.5, 1.0)]),
        (0.0, [_word("one", 0.0, 0.4), _word("two", -0.1, 1.0)]),
        (0.0, [_word("one", 0.0, 0.4), _word("two", 0.5, 0.4)]),
    ],
)
def test_karaoke_duration_allocation_rejects_invalid_boundaries(cue_start, words):
    with pytest.raises(ArtifactError):
        allocate_karaoke_durations(cue_start, 1.0, words)


def test_layout_preserves_lossless_word_fragments_and_line_breaks():
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            relative_values={"max_width": "300px", "max_height": "200px"},
        ),
        GEOMETRY,
    )
    words = [_word("one", 0.0, 0.4), _word("two", 0.5, 1.0)]

    display, _ = layout_subtitle_cues(
        [{"start": 0.0, "end": 1.0, "text": "one two", "words": words}],
        config,
        GEOMETRY,
    )

    fragments = display[0]["display_fragments"]
    assert fragments is not None
    assert "".join(fragment.text for fragment in fragments) == display[0]["text"]
    assert [
        fragment.word_index for fragment in fragments if fragment.word_index is not None
    ] == [0, 1]


def test_prepare_karaoke_cues_falls_back_without_word_timings():
    config = resolve_subtitle_config(
        validate_subtitle_config(None, effects_values={"karaoke": True}),
        GEOMETRY,
    )
    segments = [{"start": 0.0, "end": 1.0, "text": "ordinary fallback", "words": []}]

    prepared, fallback_count = prepare_karaoke_cues(segments, config)

    assert fallback_count == 1
    assert "_karaoke_cue" not in prepared[0]


def test_write_ass_compiles_one_timing_block_per_word_and_escapes_text(
    tmp_path: Path,
):
    config = resolve_subtitle_config(
        validate_subtitle_config(None, effects_values={"karaoke": True}),
        GEOMETRY,
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
    path = tmp_path / "karaoke.ass"

    write_ass(path, [segment], config, GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert r"{\1c&H4FD5FF&\1a&H00&\2c&HFFFFFF&\2a&H00&}" in content
    assert content.count(r"{\k50}") == 2
    assert r"\{world\}" in content


def test_active_word_mode_splits_stable_full_cue_events_across_pauses(
    tmp_path: Path,
):
    config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            effects_values={"karaoke": True, "karaoke_mode": "active-word"},
        ),
        GEOMETRY,
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
    path = tmp_path / "active-word.ass"

    write_ass(path, [segment], config, GEOMETRY)

    dialogue = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert len(dialogue) == 3
    assert "0:00:00.00,0:00:00.40" in dialogue[0]
    assert "0:00:00.40,0:00:00.50" in dialogue[1]
    assert "0:00:00.50,0:00:01.00" in dialogue[2]
    assert r"{\k" not in "\n".join(dialogue)
    assert (
        r"{\1c&H4FD5FF&\1a&H00&}Hello"
        r"{\1c&HFFFFFF&\1a&H00&} world" in dialogue[0]
    )
    assert dialogue[1].endswith("Hello world")
    assert (
        r"Hello {\1c&H4FD5FF&\1a&H00&}world"
        r"{\1c&HFFFFFF&\1a&H00&}" in dialogue[2]
    )


def test_karaoke_color_overrides_preserve_color_and_alpha_channels():
    assert rgba_to_ass_color_override("#11223380", 1) == (r"\1c&H332211&\1a&H7F&")


@pytest.mark.parametrize("karaoke_mode", ["progressive", "active-word"])
def test_karaoke_colors_use_once_composed_global_opacity(
    tmp_path: Path,
    karaoke_mode: str,
):
    path = tmp_path / f"{karaoke_mode}-opacity.ass"
    config = validate_subtitle_config(
        None,
        appearance_values={"text_color": "#FFFFFF80", "opacity": "50%"},
        effects_values={
            "karaoke": True,
            "karaoke_mode": karaoke_mode,
            "highlight_color": "#112233C0",
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

    write_ass(path, [segment], config, GEOMETRY)

    content = path.read_text(encoding="utf-8")
    assert r"\1c&H332211&\1a&H9F&" in content
    if karaoke_mode == "progressive":
        assert r"\2c&HFFFFFF&\2a&HBF&" in content
    else:
        assert r"\1c&HFFFFFF&\1a&HBF&" in content


def test_disabled_karaoke_keeps_plain_ass_output_unchanged(tmp_path: Path):
    default_path = tmp_path / "default.ass"
    explicit_disabled_path = tmp_path / "explicit-disabled.ass"
    segment = {"start": 0.0, "end": 1.0, "text": "plain output", "words": []}
    write_ass(default_path, [segment], validate_subtitle_config(None), GEOMETRY)
    write_ass(
        explicit_disabled_path,
        [segment],
        validate_subtitle_config(None, effects_values={"karaoke": False}),
        GEOMETRY,
    )

    assert default_path.read_bytes() == explicit_disabled_path.read_bytes()


@pytest.mark.parametrize("karaoke_mode", ["progressive", "active-word"])
def test_karaoke_retains_exact_font_weight(tmp_path: Path, karaoke_mode: str):
    path = tmp_path / f"{karaoke_mode}-weight.ass"
    config = validate_subtitle_config(
        None,
        appearance_values={"font_weight": "800"},
        relative_values={"letter_spacing": "2px"},
        effects_values={"karaoke": True, "karaoke_mode": karaoke_mode},
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

    write_ass(path, [segment], config, GEOMETRY)

    content = path.read_text(encoding="utf-8")
    style_fields = content.split("Style: Default,", 1)[1].split(",")
    assert style_fields[6] == "0"
    assert style_fields[12] == "2"
    dialogue = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    assert dialogue
    assert all(r"{\b800}" in line for line in dialogue)
    assert "Hello" in content


@pytest.mark.parametrize("karaoke_mode", ["progressive", "active-word"])
def test_karaoke_artifacts_keep_srt_plain_and_record_fallback_metadata(
    tmp_path: Path,
    karaoke_mode: str,
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
                "words": [_word("Hello", 0.0, 0.4), _word("world.", 0.5, 1.0)],
            },
            {"start": 1.0, "end": 2.0, "text": "Fallback", "words": []},
        ),
    )
    progress: list[str] = []
    paths = write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            effects_values={"karaoke": True, "karaoke_mode": karaoke_mode},
        ),
        geometry=GEOMETRY,
        progress=progress.append,
    )

    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    karaoke = payload["metadata"]["rendering"]["effects"]["karaoke"]
    assert karaoke == {
        "enabled": True,
        "mode": karaoke_mode,
        "normal_color": "#FFFFFF",
        "highlight_color": DEFAULT_KARAOKE_HIGHLIGHT_COLOR,
        "fallback_cues": 1,
    }
    assert "Warning: 1 subtitle cue(s)" in "\n".join(progress)
    srt = Path(paths[1]).read_text(encoding="utf-8")
    assert "{\\k" not in srt
    assert "Hello world." in srt
    ass = Path(paths[2]).read_text(encoding="utf-8")
    if karaoke_mode == "progressive":
        assert ass.count(r"{\k") == 2
    else:
        assert r"{\k" not in ass
        assert ass.count("Dialogue:") == 4
    assert "Fallback" in ass


@pytest.mark.integration
@pytest.mark.parametrize("canvas", [(320, 180), (180, 320)])
@pytest.mark.parametrize("karaoke_mode", ["progressive", "active-word"])
def test_ffmpeg_libass_karaoke_changes_word_colors_without_moving_layout(
    tmp_path: Path,
    canvas: tuple[int, int],
    karaoke_mode: str,
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
    input_path = tmp_path / f"karaoke-input-{karaoke_mode}-{width}x{height}.mp4"
    karaoke_ass = tmp_path / "karaoke.ass"
    plain_ass = tmp_path / "plain.ass"
    karaoke_video = tmp_path / "karaoke.mp4"
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
    karaoke_config = validate_subtitle_config(
        None,
        appearance_values={"font": "DejaVu Sans", "backdrop": "none"},
        relative_values={
            "font_size": "20px",
            "shadow_weight": "0px",
            "max_width": "150px",
            "max_height": "80px",
        },
        effects_values={"karaoke": True, "karaoke_mode": karaoke_mode},
    )
    resolved = resolve_subtitle_config(karaoke_config, geometry)
    words = [
        _word("one", 0.2, 0.3),
        _word("two", 0.4, 0.5),
        _word("three", 0.7, 0.8),
        _word("four", 0.9, 1.0),
    ]
    display, _ = layout_subtitle_cues(
        [{"start": 0.2, "end": 1.0, "text": "one two three four", "words": words}],
        resolved,
        geometry,
        language="en",
    )
    prepared, fallback_count = prepare_karaoke_cues(display, resolved)
    assert fallback_count == 0
    write_ass(karaoke_ass, prepared, karaoke_config, geometry)
    plain_config = validate_subtitle_config(
        None,
        appearance_values={"font": "DejaVu Sans", "backdrop": "none"},
        relative_values={
            "font_size": "20px",
            "shadow_weight": "0px",
            "max_width": "150px",
            "max_height": "80px",
        },
    )
    write_ass(plain_ass, display, plain_config, geometry)
    embed_subtitles(
        input_path,
        karaoke_ass,
        tmp_path,
        output_path=karaoke_video,
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

    before = frame(karaoke_video, 0.1)
    first = frame(karaoke_video, 0.25)
    second = frame(karaoke_video, 0.45)
    pause = frame(karaoke_video, 0.6)
    final = frame(karaoke_video, 0.95)
    plain = frame(plain_video, 0.45)
    highlight_counts = [
        highlight_pixels(first),
        highlight_pixels(second),
        highlight_pixels(final),
    ]
    assert not highlight_pixels(before)
    if karaoke_mode == "progressive":
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
    karaoke_bbox = foreground_bbox(second)
    plain_bbox = foreground_bbox(plain)
    assert all(
        abs(left - right) <= 2
        for left, right in zip(karaoke_bbox, plain_bbox, strict=True)
    )
