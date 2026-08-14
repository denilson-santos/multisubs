from pathlib import Path

import pytest

from multisubs import cli
from multisubs.config import validate_subtitle_config
from multisubs.errors import ArtifactError, TranscriptionError
from multisubs.models import (
    RunArtifacts,
    RunRequest,
    TranscriptDocument,
    TranscriptionPaths,
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


def test_oversized_style_argument_is_argparse_error(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")

    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "-i",
                str(input_path),
                "--style-font-size",
                str(10**400),
            ]
        )

    assert error.value.code == 2


def test_build_request_adapts_legacy_style_flags_to_typed_config(tmp_path: Path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"input")
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "-i",
            str(input_path),
            "--style-font-size",
            "22",
            "--style-alignment",
            "8",
        ]
    )

    request = cli._build_request(args, parser)

    assert request.subtitle_config.appearance.font_size == 22
    assert request.subtitle_config.layout.alignment == 8


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

    def fake_artifact_writer(document, destination, config, *, progress):
        paths = TranscriptionPaths(
            Path(destination) / "video-pt.json",
            Path(destination) / "video-pt.srt",
            Path(destination) / "video-pt.ass",
        )
        for path in paths.as_tuple():
            Path(path).write_text("artifact", encoding="utf-8")
        return paths.as_tuple()

    def fake_render(source, subtitle, destination, lang, *, output_path, progress):
        Path(output_path).write_bytes(b"video")
        return str(output_path)

    monkeypatch.setattr("multisubs.subtitler.validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(
        "multisubs.transcriber.transcribe_video", fake_transcription
    )
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
        "multisubs.transcriber.transcribe_video", failed_transcription
    )

    with pytest.raises(ArtifactError, match="Working artifacts"):
        cli._run_request(_request(input_path, output_dir), lambda message: None)

    assert len(list(output_dir.glob(".multisubs-*"))) == 1
