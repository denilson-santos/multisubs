from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import cli
from multisubs.config import parse_relative_length, validate_subtitle_config
from multisubs.errors import ArtifactError, TranscriptionError, ValidationError
from multisubs.models import (
    RelativeLength,
    RunArtifacts,
    RunRequest,
    SubtitleBackdrop,
    SubtitleLayoutPreset,
    TranscriptDocument,
    TranscriptionPaths,
    VideoGeometry,
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


def _request(input_path: Path, output_dir: Path, keep: bool = False) -> RunRequest:
    return RunRequest(
        input_path=input_path,
        output_dir=output_dir,
        language="pt",
        task="transcribe",
        model_name="turbo",
        subtitle_config=validate_subtitle_config(None),
        keep_transcriptions=keep,
    )


def _artifacts(tmp_path: Path, input_path: Path) -> RunArtifacts:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    transcripts = TranscriptionPaths(
        work_dir / "video-pt.json",
        work_dir / "video-pt.srt",
        work_dir / "video-pt.ass",
    )
    for path in (*transcripts.as_tuple(),):
        Path(path).write_text(path, encoding="utf-8")
    video = work_dir / "video-pt.mp4"
    video.write_bytes(b"video")
    return RunArtifacts(work_dir, transcripts, video)


def test_missing_input_is_argparse_error(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        cli.main(["-i", str(tmp_path / "missing.mp4")])

    assert error.value.code == 2


def test_language_without_default_alignment_model_is_rejected(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")

    with pytest.raises(SystemExit) as error:
        cli.main(["-i", str(input_path), "--lang", "af"])

    assert error.value.code == 2


def test_translation_restriction_is_rejected_before_processing(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")

    with pytest.raises(SystemExit) as error:
        cli.main(["-i", str(input_path), "-t", "translate", "-m", "turbo"])

    assert error.value.code == 2


def test_invalid_semantic_color_is_argparse_error(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")

    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "-i",
                str(input_path),
                "--text-color",
                "white",
            ]
        )

    assert error.value.code == 2


def test_build_request_accepts_semantic_appearance_and_named_position(
    tmp_path: Path,
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--font",
            "Inter",
            "--font-size",
            "22px",
            "--text-color",
            "#abcdef80",
            "--bold",
            "--italic",
            "--backdrop",
            "box",
            "--position",
            "top-right",
        ]
    )

    request = cli._build_request(args, parser)

    assert request.subtitle_config.appearance.font == "Inter"
    assert request.subtitle_config.appearance.font_size == parse_relative_length("22px")
    assert request.subtitle_config.appearance.text_color == "#ABCDEF80"
    assert request.subtitle_config.appearance.bold is True
    assert request.subtitle_config.appearance.italic is True
    assert request.subtitle_config.appearance.backdrop is SubtitleBackdrop.BOX
    assert request.subtitle_config.layout.position.value == "top-right"
    assert request.subtitle_config.layout_preset is SubtitleLayoutPreset.AUTO


def test_build_request_accepts_layout_preset_and_position_override(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--layout",
            "portrait",
            "--position",
            "top-right",
        ]
    )

    request = cli._build_request(args, parser)

    assert request.subtitle_config.layout_preset is SubtitleLayoutPreset.PORTRAIT
    assert request.subtitle_config.layout.position.value == "top-right"
    assert "position" in request.subtitle_config.layout_overrides


def test_build_request_accepts_relative_layout_values(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--font-size",
            "4.5%",
            "--backdrop-size",
            "6%",
            "--shadow-size",
            "4%",
            "--margin-left",
            "8%",
            "--margin-right",
            "72px",
        ]
    )

    request = cli._build_request(args, parser)

    font_size = request.subtitle_config.appearance.font_size
    assert isinstance(font_size, RelativeLength)
    assert font_size.original == "4.5%"
    assert str(font_size.value) == "4.5"
    margin_left = request.subtitle_config.layout.margin_left
    margin_right = request.subtitle_config.layout.margin_right
    assert isinstance(margin_left, RelativeLength)
    assert isinstance(margin_right, RelativeLength)
    assert margin_left.unit == "%"
    assert margin_right.original == "72px"


def test_build_request_accepts_custom_coordinates_and_default_anchor(
    tmp_path: Path,
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--position-x",
            "50%",
            "--position-y",
            "86%",
        ]
    )

    request = cli._build_request(args, parser)

    position_x = request.subtitle_config.layout.position_x
    assert isinstance(position_x, RelativeLength)
    assert position_x == parse_relative_length("50%")
    anchor = request.subtitle_config.layout.anchor
    assert anchor is not None
    assert anchor.value == "bottom-center"


@pytest.mark.parametrize(
    "arguments",
    [
        ["--position-x", "50%"],
        ["--position-y", "86%"],
        ["--anchor", "top-left"],
        [
            "--position",
            "top-left",
            "--position-x",
            "50%",
            "--position-y",
            "86%",
        ],
    ],
)
def test_custom_coordinate_conflicts_fail_before_runtime(tmp_path: Path, arguments):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        cli._build_request(
            parser.parse_args(["-i", str(input_path), *arguments]), parser
        )

    assert error.value.code == 2


def test_removed_style_options_are_rejected(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["-i", str(input_path), "--style-font-size", "22"])

    assert error.value.code == 2


def test_help_exposes_semantic_options_without_ass_style_flags():
    help_text = cli.build_parser().format_help()

    assert "--font NAME" in help_text
    assert "--text-color COLOR" in help_text
    assert "--bold, --no-bold" in help_text
    assert "--backdrop {none,outline,box}" in help_text
    assert "--style-" not in help_text


@pytest.mark.parametrize("value", ["14", "-1px", "1e2px"])
def test_relative_layout_options_require_explicit_units(tmp_path: Path, value: str):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["-i", str(input_path), "--font-size", value])

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("option", "value"),
    [("--style-alignment", "8"), ("--position", "5")],
)
def test_numeric_alignment_and_position_values_are_rejected(
    tmp_path: Path, option: str, value: str
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["-i", str(input_path), option, value])

    assert error.value.code == 2


def test_unknown_layout_preset_is_argparse_error(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["-i", str(input_path), "--layout", "5"])

    assert error.value.code == 2


def test_default_publication_keeps_json_and_video_only(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    output_dir = tmp_path / "output"
    artifacts = _artifacts(tmp_path, input_path)

    result = cli._publish_default_artifacts(artifacts, _request(input_path, output_dir))

    assert result == output_dir / "video-pt.mp4"
    assert (output_dir / "video-pt.mp4").read_bytes() == b"video"
    assert (output_dir / "video-pt.json").exists()
    assert not (output_dir / "video-pt.srt").exists()
    assert not (output_dir / "video-pt.ass").exists()


def test_default_publication_suffixes_dangling_output_links(
    tmp_path: Path,
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "video-pt.json").symlink_to(output_dir / "missing.json")
    artifacts = _artifacts(tmp_path, input_path)

    result = cli._publish_default_artifacts(artifacts, _request(input_path, output_dir))

    assert result == output_dir / "video-pt (1).mp4"
    assert (output_dir / "video-pt (1).json").exists()


def test_retained_publication_uses_subtitles_directory_and_collision_suffix(
    tmp_path: Path,
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    output_dir = tmp_path / "output"
    (output_dir / "video").mkdir(parents=True)
    artifacts = _artifacts(tmp_path, input_path)

    result = cli._publish_retained_artifacts(
        artifacts, _request(input_path, output_dir, keep=True)
    )

    assert result == output_dir / "video (1)"
    assert (result / "video-pt.mp4").exists()
    assert sorted(path.name for path in (result / "subtitles").iterdir()) == [
        "video-pt.ass",
        "video-pt.json",
        "video-pt.srt",
    ]


def test_run_request_cleans_private_work_dir_after_default_success(
    tmp_path: Path, monkeypatch
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    output_dir = tmp_path / "output"
    request = _request(input_path, output_dir)

    def fake_transcription(source, language, task, model_name, *, progress):
        return TranscriptDocument(
            source_path=Path(source),
            language=language,
            task=task,
            model_name=model_name,
            full_text="artifact",
            segments=(),
        )

    def fake_artifact_writer(
        document,
        destination,
        config,
        *,
        geometry,
        resolved_subtitle_config,
        progress,
    ):
        assert geometry is GEOMETRY
        assert resolved_subtitle_config is not None
        paths = TranscriptionPaths(
            Path(destination) / "video-pt.json",
            Path(destination) / "video-pt.srt",
            Path(destination) / "video-pt.ass",
        )
        for path in paths.as_tuple():
            Path(path).write_text("artifact", encoding="utf-8")
        return paths.as_tuple()

    def fake_render(
        source,
        subtitle,
        destination,
        lang,
        *,
        output_path,
        geometry,
        fonts_dir,
        progress,
    ):
        assert geometry is GEOMETRY
        assert fonts_dir is None
        Path(output_path).write_bytes(b"video")
        return str(output_path)

    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry", lambda path: GEOMETRY
    )
    monkeypatch.setattr("multisubs.transcriber.transcribe_video", fake_transcription)
    monkeypatch.setattr(
        "multisubs.transcriber.write_transcription_artifacts",
        fake_artifact_writer,
    )
    monkeypatch.setattr("multisubs.subtitler.embed_subtitles", fake_render)

    result = cli._run_request(request, lambda message: None)

    assert result == output_dir / "video-pt.mp4"
    assert not list(output_dir.glob(".multisubs-*"))
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "video-pt.json",
        "video-pt.mp4",
    ]


def test_run_request_retains_private_work_dir_after_processing_failure(
    tmp_path: Path, monkeypatch
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    output_dir = tmp_path / "output"

    def failed_transcription(*args, **kwargs):
        raise TranscriptionError("model failed")

    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry", lambda path: GEOMETRY
    )
    monkeypatch.setattr("multisubs.transcriber.transcribe_video", failed_transcription)

    with pytest.raises(ArtifactError, match="Working artifacts"):
        cli._run_request(_request(input_path, output_dir), lambda message: None)

    assert len(list(output_dir.glob(".multisubs-*"))) == 1


def test_run_request_rejects_probe_failure_before_transcription(
    tmp_path: Path, monkeypatch
):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    output_dir = tmp_path / "output"

    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry",
        lambda path: (_ for _ in ()).throw(ValidationError("invalid geometry")),
    )
    monkeypatch.setattr(
        "multisubs.transcriber.transcribe_video",
        lambda *args, **kwargs: pytest.fail("transcription must not start"),
    )

    with pytest.raises(ValidationError, match="invalid geometry"):
        cli._run_request(_request(input_path, output_dir), lambda message: None)

    assert not output_dir.exists()
