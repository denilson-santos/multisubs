"""Public media-free preparation, resource leases, and invocation isolation."""

from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from threading import Barrier, Event
from typing import Any

import pytest

from multisubs import (
    CancelledError,
    MultisubsError,
    PreparedSubtitleArtifacts,
    SpeechTranscript,
    build_subtitle_config,
    font_catalog,
    prepare_subtitles,
    render_transcript,
    speech,
    subtitler,
    transcriber,
    utils,
)
from multisubs.asr.base import ASRResult
from multisubs.errors import ArtifactError, ValidationError
from multisubs.models import VideoGeometry


def _speech(case="aligned"):
    text = " Hello,  world!"
    words = [
        {"word": " Hello,", "start": 0.2, "end": 0.5},
        {"word": "  world!", "start": 0.6, "end": 1.0},
    ]
    segment = {"text": text, "start": 0.0, "end": 2.0, "words": words}
    if case == "partial":
        words[0].pop("end")
        words[1]["start"] = None
    elif case == "absent":
        segment.pop("words")
    elif case == "null":
        segment["words"] = None
    elif case == "point":
        words[0]["end"] = words[0]["start"]
    elif case == "all-points":
        for word in words:
            word["start"] = word["end"] = 0.5
    return SpeechTranscript(
        None if case == "unknown" else "en",
        "transcribe",
        "faster-whisper",
        "base",
        text,
        (segment,),
    )


def _unexpected(*args, **kwargs):
    pytest.fail("Preparation must not load an ASR, probe media, or start FFmpeg")


@pytest.fixture(autouse=True)
def _no_media_or_asr(monkeypatch):
    monkeypatch.setattr(transcriber, "create_adapter", _unexpected)
    monkeypatch.setattr(subtitler, "probe_video_geometry", _unexpected)
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", _unexpected)
    monkeypatch.setattr(subtitler, "validate_video_encoding_support", _unexpected)
    monkeypatch.setattr(subtitler, "embed_subtitles", _unexpected)


@pytest.mark.parametrize("size", [(1920, 1080), (1080, 1920), (1080, 1080)])
@pytest.mark.parametrize("template", ["default", "yellow-pop"])
@pytest.mark.parametrize(
    "case",
    ["aligned", "partial", "absent", "null", "point", "all-points", "unknown"],
)
def test_prepare_matches_native_pipeline(tmp_path, monkeypatch, size, template, case):
    source = _speech(case)
    payload = source.to_dict()
    before = deepcopy(payload)
    width, height = size
    geometry = VideoGeometry(
        0,
        width,
        height,
        width,
        height,
        0,
        Fraction(1),
        Fraction(width, height),
        2.0,
    )
    video = tmp_path / "source.mp4"
    video.write_bytes(b"mock media")

    class Adapter:
        def transcribe(self, request):
            return ASRResult(source.language, source.full_text, source.segments)

    with monkeypatch.context() as native:
        native.setattr(transcriber, "create_adapter", lambda _: Adapter())
        native.setattr(subtitler, "probe_video_geometry", lambda _: geometry)
        _, native_srt, native_ass = transcriber.generate_transcriptions(
            video,
            tmp_path / "native",
            build_subtitle_config(template=template),
        )
    messages = []
    output = tmp_path / "prepared"
    with prepare_subtitles(
        payload,
        output_dir=output,
        frame_width=width,
        frame_height=height,
        template=template,
        progress=messages.append,
    ) as prepared:
        assert isinstance(prepared, PreparedSubtitleArtifacts)
        assert prepared.srt_path.read_bytes() == Path(native_srt).read_bytes()
        assert prepared.ass_path.read_bytes() == Path(native_ass).read_bytes()
        ass = prepared.ass_path.read_text()
        assert f"PlayResX: {width}" in ass and f"PlayResY: {height}" in ass
        assert prepared.template_resolved == template
        assert prepared.template_source == "builtin"
    assert sorted(path.suffix for path in output.iterdir()) == [".ass", ".srt"]
    assert payload == before == source.to_dict()
    if case in {"partial", "absent", "null", "all-points"} and template == "yellow-pop":
        assert any("could not safely use" in message for message in messages)


def test_custom_templates_overrides_and_truthful_provenance(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "brand.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "brand",
                "description": "Brand captions",
                "base": "yellow-pop",
                "style": {"typography": {"italic": False}},
            }
        )
    )
    options: dict[str, Any] = dict(
        output_dir=tmp_path / "output",
        frame_width=1080,
        frame_height=1920,
    )
    config = build_subtitle_config(
        template="brand",
        template_dir=templates,
        overrides={"font_size": "5%"},
    )
    before = deepcopy(config)
    with prepare_subtitles(
        _speech(),
        template="brand",
        template_dir=templates,
        **options,
    ) as custom:
        assert custom.template_requested == custom.template_resolved == "brand"
        assert custom.template_source == "custom"
        assert custom.template_base == "yellow-pop"
    with prepare_subtitles(_speech(), subtitle_config=config, **options) as explicit:
        assert explicit.template_source == "config"
        assert explicit.template_resolved is None and explicit.template_base is None
        style = next(
            line
            for line in explicit.ass_path.read_text().splitlines()
            if line.startswith("Style:")
        )
        assert style.split(",")[2] == "96"
    assert config == before
    for selection in ({"template": "brand"}, {"template_dir": templates}):
        with pytest.raises(ValidationError, match="not both"):
            with prepare_subtitles(
                _speech(), subtitle_config=config, **selection, **options
            ):
                pytest.fail("Conflicting configuration must not be accepted")


@pytest.mark.parametrize(
    "width,height", [(True, 1080), (1080.0, 1920), (0, 1), (1, 32769)]
)
def test_geometry_validation_precedes_work(tmp_path, width, height):
    with pytest.raises(ValidationError, match="Frame dimensions"):
        with prepare_subtitles(
            _speech(),
            output_dir=tmp_path / "out",
            frame_width=width,
            frame_height=height,
        ):
            pytest.fail("Invalid geometry must not be accepted")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("exit_mode", ["success", "consumer-failure", "cancel"])
def test_materialized_fonts_are_leased_and_subtitles_persist(
    tmp_path, monkeypatch, exit_mode
):
    monkeypatch.setattr(font_catalog, "bundled_filesystem_directory", lambda _: None)
    cancelled = Event()
    fonts = None

    def consume():
        nonlocal fonts
        with prepare_subtitles(
            _speech(),
            output_dir=tmp_path,
            frame_width=1080,
            frame_height=1920,
            template="yellow-pop",
            should_cancel=cancelled.is_set,
        ) as prepared:
            fonts = prepared.fonts_dir
            assert fonts is not None and fonts.is_dir()
            assert list(fonts.glob("*.ttf")) or list(fonts.glob("*.otf"))
            if exit_mode == "consumer-failure":
                raise RuntimeError("consumer encode failed")
            if exit_mode == "cancel":
                cancelled.set()

    if exit_mode == "success":
        consume()
    else:
        with pytest.raises(CancelledError if exit_mode == "cancel" else RuntimeError):
            consume()
    assert fonts is not None and not fonts.exists()
    assert sorted(path.suffix for path in tmp_path.iterdir()) == [".ass", ".srt"]


@pytest.mark.parametrize(
    "stage", ["before", "Completed JSON", "Completed SRT", "Completed ASS"]
)
def test_cancelled_preparation_never_publishes_partial_files(
    tmp_path, monkeypatch, stage
):
    monkeypatch.setattr(font_catalog, "bundled_filesystem_directory", lambda _: None)
    cancelled = Event()
    if stage == "before":
        cancelled.set()

    def progress(message):
        if message.startswith(stage):
            cancelled.set()

    with pytest.raises(CancelledError):
        with prepare_subtitles(
            _speech(),
            output_dir=tmp_path,
            frame_width=1080,
            frame_height=1920,
            template="yellow-pop",
            progress=progress,
            should_cancel=cancelled.is_set,
        ):
            pytest.fail("Cancellation must not produce a successful result")
    assert not list(tmp_path.iterdir())


def test_failed_pair_publication_rolls_back_only_owned_files(tmp_path, monkeypatch):
    with prepare_subtitles(
        _speech(),
        output_dir=tmp_path,
        frame_width=1080,
        frame_height=1920,
    ) as first:
        original = {p: p.read_bytes() for p in (first.srt_path, first.ass_path)}
    publish = utils._publish_one

    def fail_ass(source, destination):
        if destination.suffix == ".ass":
            raise ArtifactError("disk failure")
        publish(source, destination)

    monkeypatch.setattr(utils, "_publish_one", fail_ass)
    with pytest.raises(ArtifactError, match="disk failure"):
        with prepare_subtitles(
            _speech(),
            output_dir=tmp_path,
            frame_width=1080,
            frame_height=1920,
        ):
            pytest.fail("Failed publication must not yield artifacts")
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == original


def test_caller_owned_fonts_survive_context_exit(tmp_path):
    fonts = tmp_path / "fonts"
    bundled = font_catalog.bundled_filesystem_directory("Inter")
    assert bundled is not None
    shutil.copytree(bundled, fonts)
    original = {p.name: p.read_bytes() for p in fonts.iterdir()}
    config = build_subtitle_config(overrides={"font": "Inter", "fonts_dir": fonts})
    with prepare_subtitles(
        _speech(),
        output_dir=tmp_path / "out",
        frame_width=1080,
        frame_height=1920,
        subtitle_config=config,
    ) as prepared:
        assert prepared.fonts_dir == fonts
    assert {p.name: p.read_bytes() for p in fonts.iterdir()} == original


@pytest.mark.parametrize("failure", ["cancel", "callback"])
def test_failed_preparation_does_not_interrupt_parallel_publication(tmp_path, failure):
    source = _speech()
    config = build_subtitle_config(template="yellow-pop")
    both_written = Barrier(2, timeout=20)
    cancelled = Event()

    def run(index):
        def report(message):
            if message.startswith("Completed SRT"):
                both_written.wait()
                if index == 0:
                    if failure == "callback":
                        raise RuntimeError("progress callback failed")
                    cancelled.set()

        with prepare_subtitles(
            source,
            output_dir=tmp_path / str(index),
            frame_width=1080,
            frame_height=1920,
            subtitle_config=config,
            progress=report,
            should_cancel=cancelled.is_set if index == 0 else None,
        ) as prepared:
            return prepared

    with ThreadPoolExecutor(max_workers=2) as pool:
        failed = pool.submit(run, 0)
        successful = pool.submit(run, 1)
        with pytest.raises(CancelledError if failure == "cancel" else RuntimeError):
            failed.result(timeout=30)
        prepared = successful.result(timeout=30)
    assert prepared.ass_path.is_file() and prepared.srt_path.is_file()
    assert not list((tmp_path / "0").iterdir())


@pytest.mark.parametrize("failure", ["none", "cancel", "consumer-failure"])
@pytest.mark.parametrize("shared_directory", [False, True])
def test_concurrent_resource_leases_and_cleanup(
    tmp_path, monkeypatch, failure, shared_directory
):
    monkeypatch.setattr(font_catalog, "bundled_filesystem_directory", lambda _: None)
    source = _speech()
    before = source.to_dict()
    config = build_subtitle_config(template="yellow-pop")
    both_ready = Barrier(2, timeout=20)
    first_done = Event()
    cancelled = Event()

    def run(index):
        output = tmp_path if shared_directory else tmp_path / str(index)
        try:
            with prepare_subtitles(
                source,
                output_dir=output,
                frame_width=1080,
                frame_height=1920,
                subtitle_config=config,
                should_cancel=cancelled.is_set if index == 0 else None,
            ) as prepared:
                fonts = prepared.fonts_dir
                assert fonts is not None and fonts.is_dir()
                both_ready.wait()
                if index == 0:
                    if failure == "cancel":
                        cancelled.set()
                    if failure == "consumer-failure":
                        raise RuntimeError("consumer failed")
                else:
                    assert first_done.wait(timeout=20)
                    assert fonts.is_dir() and prepared.ass_path.is_file()
            return prepared
        except (CancelledError, RuntimeError):
            if index != 0 or failure == "none":
                raise
            return None
        finally:
            if index == 0:
                first_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, index) for index in range(2)]
        first, second = [future.result(timeout=30) for future in futures]
    assert second is not None and second.ass_path.is_file()
    assert second.fonts_dir is not None and not second.fonts_dir.exists()
    if first is not None:
        assert first.ass_path != second.ass_path
        assert first.ass_path.read_bytes() == second.ass_path.read_bytes()
    assert len(list(tmp_path.rglob("*.srt"))) == len(list(tmp_path.rglob("*.ass"))) == 2
    assert not list(tmp_path.rglob(".multisubs-*"))
    assert source.to_dict() == before


def test_render_reuses_public_preparation_and_holds_fonts(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"input")
    geometry = VideoGeometry(
        0, 1080, 1920, 1080, 1920, 0, Fraction(1), Fraction(9, 16), 2.0
    )
    monkeypatch.setattr(font_catalog, "bundled_filesystem_directory", lambda _: None)
    monkeypatch.setattr(subtitler, "probe_video_geometry", lambda *a, **kw: geometry)
    monkeypatch.setattr(subtitler, "validate_ffmpeg_support", lambda **kw: None)
    monkeypatch.setattr(
        subtitler, "validate_video_encoding_support", lambda *a, **kw: None
    )
    calls = []
    original = speech.prepare_subtitles

    def prepare(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    def embed(*args, **kwargs):
        assert kwargs["fonts_dir"].is_dir()
        Path(kwargs["output_path"]).write_bytes(b"encoded")

    monkeypatch.setattr(speech, "prepare_subtitles", prepare)
    monkeypatch.setattr(subtitler, "embed_subtitles", embed)
    artifacts = render_transcript(
        _speech(), video, tmp_path / "out", template="yellow-pop"
    )
    assert len(calls) == 1 and calls[0]["frame_height"] == 1920
    assert artifacts.video_path.read_bytes() == b"encoded"
    assert sorted(p.suffix for p in artifacts.video_path.parent.iterdir()) == [
        ".ass",
        ".mp4",
        ".srt",
    ]
    assert issubclass(CancelledError, MultisubsError)
