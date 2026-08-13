from pathlib import Path

import pytest

from multisubs import cli
from multisubs.errors import ArtifactError, TranscriptionError
from multisubs.models import RunArtifacts, RunRequest, TranscriptionPaths


def _request(input_path: Path, output_dir: Path, keep: bool = False) -> RunRequest:
    return RunRequest(
        input_path=input_path,
        output_dir=output_dir,
        language="pt",
        task="transcribe",
        model_name="turbo",
        style_options={},
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

    def fake_transcription(source, destination, *args, **kwargs):
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
        "multisubs.transcriber.generate_transcriptions", fake_transcription
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
        "multisubs.transcriber.generate_transcriptions", failed_transcription
    )

    with pytest.raises(ArtifactError, match="Working artifacts"):
        cli._run_request(_request(input_path, output_dir), lambda message: None)

    assert len(list(output_dir.glob(".multisubs-*"))) == 1
