"""End-to-end hermetic CLI visual iteration without ASR runtimes or FFmpeg."""

import json
import re
from fractions import Fraction
from pathlib import Path

import pytest
from test_cli_helpers import TestParser
from typer.main import get_command
from typer.testing import CliRunner

from multisubs import cli, speech_cache, subtitler, transcriber
from multisubs.asr.base import ASRResult
from multisubs.errors import ArtifactError, RenderingError
from multisubs.models import RunRequest, VideoGeometry


@pytest.fixture
def run(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "output"
    cache = tmp_path / "cache"
    calls = []
    result = ASRResult(
        "pt",
        "Olá, mundo!",
        (
            {
                "start": 0.2,
                "end": 2.0,
                "text": "Olá, mundo!",
                "words": [
                    {"word": "Olá,", "start": 0.2, "end": 0.7},
                    {"word": " mundo!", "start": 0.8, "end": 1.8},
                ],
            },
        ),
    )

    class Adapter:
        def transcribe(self, request):
            calls.append(request)
            return result

    monkeypatch.setattr(transcriber, "create_adapter", lambda _: Adapter())
    monkeypatch.setattr(speech_cache, "_versions", lambda _: {})
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda: None)
    monkeypatch.setattr(subtitler, "validate_animation_preview_support", lambda: None)
    monkeypatch.setattr(subtitler, "validate_video_encoding_support", lambda _: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda _: cli_geometry())

    def render(*args, **kwargs):
        path = Path(kwargs["output_path"])
        path.write_bytes(b"rendered")
        return str(path)

    monkeypatch.setattr(subtitler, "embed_subtitles", render)

    def invoke(*options):
        return cli.main(["-i", str(source), "-o", str(output), *options])

    return source, output, cache, calls, invoke


def cli_geometry():
    return VideoGeometry(0, 1920, 1080, 1920, 1080, 0, Fraction(1), Fraction(16, 9), 10)


@pytest.mark.parametrize("custom_cache", [False, True])
def test_export_variants_reuse_speech_and_never_encode(run, monkeypatch, custom_cache):
    _source, output, cache, calls, invoke = run
    cache_options = ("--cache-dir", str(cache)) if custom_cache else ()

    def unexpected(*args, **kwargs):
        pytest.fail("subtitle-only mode must not preflight or render")

    monkeypatch.setattr(subtitler, "embed_subtitles", unexpected)
    monkeypatch.setattr(subtitler, "validate_video_encoding_support", unexpected)
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", unexpected)
    assert invoke("--subtitles-only", *cache_options) == 0
    first_ass = (output / "video-pt.ass").read_bytes()
    assert invoke("--subtitles-only", *cache_options, "--template", "yellow-pop") == 0
    assert len(calls) == 1
    assert first_ass != (output / "video-pt (1).ass").read_bytes()
    assert {p.suffix for p in output.iterdir() if p.is_file()} == {".srt", ".ass"}
    assert {p.name for p in output.iterdir() if p.is_dir()} == (
        set() if custom_cache else {".multisubs-cache"}
    )


def test_export_pair_uses_shared_collision_suffix(run):
    _source, output, _cache, _calls, invoke = run
    output.mkdir()
    existing = output / "video-pt.ass"
    existing.write_text("user subtitle")
    assert invoke("--subtitles-only") == 0
    assert existing.read_text() == "user subtitle"
    assert (output / "video-pt (1).srt").exists()
    assert (output / "video-pt (1).ass").exists()
    assert not (output / "video-pt.srt").exists()


def test_cache_survives_failed_render_and_works_with_keep(run, monkeypatch):
    _source, output, cache, calls, invoke = run
    original = subtitler.embed_subtitles

    def failed(*args, **kwargs):
        raise RenderingError("encoder failed")

    monkeypatch.setattr(subtitler, "embed_subtitles", failed)
    assert invoke("--cache-dir", str(cache)) == 1
    assert len(list(cache.rglob("*.json"))) == 1
    assert not list(output.glob("*.mp4"))
    monkeypatch.setattr(subtitler, "embed_subtitles", original)
    assert invoke("--cache-dir", str(cache), "-k") == 0
    assert len(calls) == 1
    assert (output / "video" / "subtitles" / "video-pt.json").exists()


@pytest.mark.parametrize("keep", [False, True])
def test_default_runs_reuse_output_local_cache_across_styles(run, keep):
    _source, output, cache, calls, invoke = run
    options = ("-k",) if keep else ()
    assert invoke(*options) == 0
    assert invoke(*options, "--template", "yellow-pop") == 0
    assert not cache.exists()
    assert len(calls) == 1
    default_cache = output / ".multisubs-cache"
    assert len(list((default_cache / "transcriptions" / "v1").glob("*.json"))) == 1
    assert {p.name for p in output.iterdir()} == (
        {".multisubs-cache", "video", "video (1)"}
        if keep
        else {".multisubs-cache", "video-pt.mp4", "video-pt (1).mp4"}
    )


@pytest.mark.parametrize("custom_cache", [False, True])
def test_refresh_cache_recognizes_again_and_updates_the_saved_speech(
    run, monkeypatch, custom_cache
):
    _source, output, cache, calls, invoke = run
    options = ("--subtitles-only",)
    if custom_cache:
        options += ("--cache-dir", str(cache))
    else:
        cache = output / ".multisubs-cache"
    assert invoke(*options) == 0

    class Updated:
        def transcribe(self, request):
            calls.append(request)
            return ASRResult(
                "pt",
                "Novo texto.",
                (
                    {
                        "text": "Novo texto.",
                        "start": 0.2,
                        "end": 2.0,
                    },
                ),
            )

    monkeypatch.setattr(transcriber, "create_adapter", lambda _: Updated())
    assert invoke(*options, "--refresh-cache") == 0
    assert invoke(*options) == 0
    assert len(calls) == 2
    payload = json.loads(next(cache.rglob("*.json")).read_text())
    assert payload["speech"]["full_text"] == "Novo texto."


def test_default_cache_uses_current_directory_when_output_is_omitted(
    tmp_path, monkeypatch
):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    monkeypatch.chdir(tmp_path)
    parser = TestParser()
    request = cli._build_request(parser.parse_args(["-i", str(source)]), parser)
    assert isinstance(request, RunRequest)
    assert request.cache_dir is not None
    assert request.cache_dir == tmp_path / ".multisubs-cache"
    assert not request.cache_dir.exists()


def test_default_cache_path_conflict_fails_before_recognition(run):
    _source, output, _cache, calls, invoke = run
    output.mkdir()
    conflicting = output / ".multisubs-cache"
    conflicting.write_text("user file")
    with pytest.raises(SystemExit) as error:
        invoke()
    assert error.value.code == 2
    assert not calls
    assert list(output.iterdir()) == [conflicting]
    assert conflicting.read_text() == "user file"


def test_translation_does_not_default_to_source_speech_cache(tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    parser = TestParser()
    request = cli._build_request(
        parser.parse_args(
            [
                "-i",
                str(source),
                "-o",
                str(tmp_path / "output"),
                "--task",
                "translate",
                "--model",
                "small",
            ]
        ),
        parser,
    )
    assert isinstance(request, RunRequest)
    assert request.cache_dir is None


def test_all_preview_options_share_one_help_panel_without_duplicate_flags():
    parameters = get_command(cli.app).params
    preview = {
        parameter.name: parameter
        for parameter in parameters
        if parameter.name
        in {
            "preview_layout",
            "preview_animation",
            "preview_clip",
            "preview_at",
            "preview_duration",
            "preview_text",
            "preview_guides",
        }
    }
    assert len(preview) == 7
    assert all(
        getattr(parameter, "rich_help_panel", None) == "Subtitle preview"
        for parameter in preview.values()
    )
    options = [option for parameter in parameters for option in parameter.opts]
    assert options.count("--preview-at") == 1
    assert options.count("--preview-duration") == 1


@pytest.mark.parametrize("color", [False, True])
@pytest.mark.parametrize(
    "option",
    [
        "--speech-cache",
        "--refresh-transcription",
        "--no-cache",
        "--clip-start",
        "--clip-duration",
    ],
)
def test_superseded_flags_are_not_exposed(option, color):
    result = CliRunner().invoke(cli.app, [option], color=color)
    assert result.exit_code == 2
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.output)
    assert f"No such option: {option}" in " ".join(output.split())


def test_empty_speech_and_unknown_language_remain_valid(run, monkeypatch):
    _source, output, cache, _calls, invoke = run

    class Empty:
        def transcribe(self, request):
            return ASRResult(None, "", ())

    monkeypatch.setattr(transcriber, "create_adapter", lambda _: Empty())
    assert invoke("--subtitles-only", "--cache-dir", str(cache)) == 0
    assert (output / "video.srt").read_text() == ""
    assert (output / "video.ass").exists()
    assert invoke("--subtitles-only", "--cache-dir", str(cache)) == 0


def test_failed_pair_publication_leaves_no_final_files(run, monkeypatch):
    _source, output, _cache, _calls, invoke = run

    from multisubs import utils

    original = utils._publish_one

    def failed(source, destination):
        if destination.suffix == ".ass":
            raise ArtifactError("second file publication failed")
        return original(source, destination)

    monkeypatch.setattr(utils, "_publish_one", failed)
    assert invoke("--subtitles-only") == 1
    assert not list(output.glob("*.srt"))
    assert not list(output.glob("*.ass"))


@pytest.mark.parametrize("custom_cache", [False, True])
def test_real_preview_uses_full_speech_clock_and_publishes_only_clip(
    run, monkeypatch, custom_cache
):
    source, output, cache, calls, invoke = run
    observed = []

    def render(video, ass, target, **kwargs):
        observed.append((video, Path(ass).read_text(), kwargs))
        target.write_bytes(b"real excerpt")
        return target

    monkeypatch.setattr(subtitler, "render_subtitle_clip", render)
    options = (
        "--preview-clip",
        "--preview-at",
        "00:00:01",
        "--preview-duration",
        "1500ms",
    )
    if custom_cache:
        options += ("--cache-dir", str(cache))
    assert invoke(*options) == 0
    assert invoke(*options) == 0
    assert len(calls) == 1
    assert observed[0][0] == source
    assert observed[0][2]["start"] == 1.0
    assert observed[0][2]["duration"] == 1.5
    assert "0:00:00.20" in observed[0][1]
    assert {p.name for p in output.iterdir() if p.is_file()} == {
        "video-subtitle-clip-preview.mp4",
        "video-subtitle-clip-preview (1).mp4",
    }
    assert {p.name for p in output.iterdir() if p.is_dir()} == (
        set() if custom_cache else {".multisubs-cache"}
    )


def test_out_of_range_clip_fails_before_asr(run):
    _source, _output, cache, calls, invoke = run
    assert (
        invoke(
            "--preview-clip",
            "--preview-at",
            "00:00:10",
            "--cache-dir",
            str(cache),
        )
        == 1
    )
    assert not calls
    assert not cache.exists()


@pytest.mark.parametrize(
    "options",
    [
        ["--refresh-cache", "--task", "translate"],
        ["--refresh-cache", "--preview-layout"],
        ["--refresh-cache", "--preview-animation"],
        ["--refresh-cache", "--subtitle-file", "captions.ass"],
        ["--subtitles-only", "--preview-clip"],
        ["--preview-at", "00:00:00"],
        ["--preview-duration", "2s"],
        ["--preview-clip"],
        ["--preview-clip", "--preview-at", "bad"],
        ["--preview-clip", "--preview-at", "00:00:00", "--preview-duration", "16s"],
        ["--subtitles-only", "-k"],
        ["--subtitles-only", "--video-encoder", "libx264"],
        ["--subtitles-only", "--preview-layout"],
        ["--cache-dir", "cache", "--preview-animation"],
        ["--subtitles-only", "--task", "translate"],
        ["--subtitle-file", "captions.ass", "--cache-dir", "cache"],
        ["--preview-clip", "--preview-at", "00:00:00", "--preview-text", "sample"],
    ],
)
def test_invalid_combinations_fail_before_processing(tmp_path, monkeypatch, options):
    def unexpected(*args, **kwargs):
        pytest.fail("invalid options must fail before probing or ASR")

    monkeypatch.setattr(subtitler, "probe_video_geometry", unexpected)
    monkeypatch.setattr(transcriber, "create_adapter", unexpected)
    result = CliRunner().invoke(
        cli.app, ["-i", str(tmp_path / "missing.mp4"), *options]
    )
    assert result.exit_code == 2


def test_real_clip_failure_removes_partial_media(tmp_path, monkeypatch):
    source, ass = tmp_path / "source.mp4", tmp_path / "source.ass"
    source.write_bytes(b"input")
    ass.write_text("placeholder")
    target = tmp_path / "excerpt.mp4"

    geometry = VideoGeometry(0, 640, 360, 640, 360, 0, Fraction(1), Fraction(16, 9), 4)

    class Failed:
        Error = RuntimeError

        def input(self, *a, **kw):
            return self

        def __getitem__(self, key):
            return self

        def filter(self, *a, **kw):
            return self

        def output(self, *a, **kw):
            Path(a[2]).write_bytes(b"partial")
            return self

        def global_args(self, *a):
            return self

        def run(self, **kwargs):
            raise RuntimeError("encoder failed")

    monkeypatch.setattr(subtitler, "_load_ffmpeg_python", lambda: Failed())
    with pytest.raises(RenderingError):
        subtitler.render_subtitle_clip(
            source, ass, target, geometry=geometry, start=1, duration=1
        )
    assert not target.exists()
    assert {path.name for path in tmp_path.iterdir()} == {source.name, ass.name}
