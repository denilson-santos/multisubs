import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from multisubs import transcriber
from multisubs.config import validate_subtitle_config
from multisubs.errors import TranscriptionError
from multisubs.layout import resolve_subtitle_config
from multisubs.models import TranscriptDocument, VideoGeometry
from multisubs.text_measurement import (
    TextMeasurementInfo,
    TextMeasurer,
    build_unicode_text_measurer,
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


@pytest.fixture(autouse=True)
def _use_hermetic_text_measurement(monkeypatch):
    def build(appearance, *, language=None):
        del language
        return build_unicode_text_measurer(
            appearance.font,
            appearance.font_size,
            font_weight=appearance.font_weight,
            font_weight_input=appearance.font_weight_input,
            font_weight_input_form=appearance.font_weight_input_form,
            letter_spacing=appearance.letter_spacing,
        )

    monkeypatch.setattr("multisubs.layout.build_text_measurer", build)


def _word(text: str, start: float, end: float, **extra):
    return {"word": text, "start": start, "end": end, **extra}


def test_build_subtitle_segments_prefers_sentence_and_pause_boundaries():
    segments = transcriber._build_subtitle_segments(
        [
            {
                "start": 0,
                "end": 2,
                "words": [
                    _word("Hello", 0, 0.5),
                    _word("world.", 0.6, 1.2),
                    _word("Next", 1.8, 2.2),
                ],
            }
        ]
    )

    assert [segment["text"] for segment in segments] == ["Hello world.", "Next"]
    assert [segment["id"] for segment in segments] == [0, 1]


def test_build_subtitle_segments_uses_coarse_fallback_without_word_timestamps():
    segments = transcriber._build_subtitle_segments(
        [{"start": 1, "end": 2.5, "text": "Fallback text"}]
    )

    assert segments == [
        {"id": 0, "start": 1.0, "end": 2.5, "text": "Fallback text", "words": []}
    ]


def test_adaptive_wrapping_uses_resolved_width_and_preserves_timed_words():
    words = [
        _word(word, index * 0.25, index * 0.25 + 0.2)
        for index, word in enumerate(
            "This is a deliberately long subtitle sentence that needs layout aware "
            "wrapping for the selected video geometry".split()
        )
    ]
    semantic = transcriber._build_subtitle_segments([{"words": words}])
    resolved = resolve_subtitle_config(validate_subtitle_config(None), GEOMETRY)

    display, metrics = transcriber.layout_subtitle_cues(semantic, resolved, GEOMETRY)

    assert metrics.width_budget == 1688
    assert len(display) == 1
    assert display[0]["text"].count("\n") == 1
    assert display[0]["semantic_text"].replace(" ", "") == "".join(
        word["word"] for word in words
    ).replace(" ", "")
    assert [word["word"] for word in display[0]["words"]] == [
        word["word"] for word in words
    ]


def test_adaptive_wrapping_changes_with_portrait_geometry_and_font_size():
    portrait_geometry = VideoGeometry(
        stream_index=0,
        coded_width=1080,
        coded_height=1920,
        render_width=1080,
        render_height=1920,
        rotation_degrees=90,
        sample_aspect_ratio=Fraction(1, 1),
        display_aspect_ratio=Fraction(9, 16),
        duration_seconds=12.5,
    )
    semantic = [
        {
            "id": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "A long subtitle line changes its visual break with geometry",
            "words": [],
        }
    ]
    landscape_config = resolve_subtitle_config(validate_subtitle_config(None), GEOMETRY)
    portrait_config = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            relative_values={"font_size": "8%", "max_height": "20%"},
        ),
        portrait_geometry,
    )

    landscape_display, landscape_metrics = transcriber.layout_subtitle_cues(
        semantic, landscape_config, GEOMETRY
    )
    portrait_display, portrait_metrics = transcriber.layout_subtitle_cues(
        semantic, portrait_config, portrait_geometry
    )

    assert landscape_metrics.width_budget == 1688
    assert portrait_metrics.width_budget == 905
    assert landscape_display[0]["text"] != portrait_display[0]["text"]


@pytest.mark.parametrize(
    ("max_height", "line_capacity"),
    [("54px", 1), ("106px", 2), ("157px", 3)],
)
def test_adaptive_wrapping_honors_height_derived_line_capacity(
    max_height, line_capacity
):
    text = "one two three four five six seven eight nine ten eleven twelve"
    config = validate_subtitle_config(
        None,
        relative_values={"max_width": "40%", "max_height": max_height},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    semantic = [{"id": 0, "start": 0.0, "end": 1.0, "text": text, "words": []}]

    display, _ = transcriber.layout_subtitle_cues(semantic, resolved, GEOMETRY)

    assert len(display) == 1
    assert display[0]["text"].count("\n") + 1 <= line_capacity


def test_adaptive_wrapping_splits_aligned_words_into_timed_cues_when_needed():
    words = [
        _word(word, index * 0.4, index * 0.4 + 0.3)
        for index, word in enumerate("one two three four five six seven eight".split())
    ]
    semantic = transcriber._build_subtitle_segments([{"words": words}])
    config = validate_subtitle_config(
        None,
        relative_values={"max_width": "30%", "max_height": "54px"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)

    display, metrics = transcriber.layout_subtitle_cues(semantic, resolved, GEOMETRY)

    assert len(display) > 1
    assert all("\n" not in cue["text"] for cue in display)
    assert all(cue["start"] <= cue["end"] for cue in display)
    assert [word["word"] for cue in display for word in cue["words"]] == [
        word["word"] for word in words
    ]
    assert metrics.line_capacity == 1


def test_adaptive_wrapping_keeps_long_unbroken_tokens_intact():
    config = validate_subtitle_config(
        None,
        relative_values={"max_width": "3px"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    semantic = [
        {
            "id": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "supercalifragilisticexpialidocious",
            "words": [],
        }
    ]

    display, _ = transcriber.layout_subtitle_cues(semantic, resolved, GEOMETRY)

    assert display[0]["text"] == semantic[0]["text"]


def test_adaptive_wrapping_handles_cjk_without_inventing_spaces():
    config = validate_subtitle_config(
        None,
        relative_values={"max_width": "20px"},
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    semantic = [
        {
            "id": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "这是一个没有空格的字幕句子",
            "words": [],
        }
    ]

    display, _ = transcriber.layout_subtitle_cues(semantic, resolved, GEOMETRY)

    assert " " not in display[0]["text"]
    assert display[0]["text"].replace("\n", "") == semantic[0]["text"]


def test_font_metrics_prevent_the_reported_premature_portuguese_break():
    text = (
        "divulgou um vídeo nas redes sociais agradecendo o apoio recebido nos "
        "últimos dias."
    )
    config = validate_subtitle_config(
        None,
        relative_values={
            "margin_left": "0%",
            "margin_right": "0%",
            "max_width": "100%",
        },
    )
    resolved = resolve_subtitle_config(config, GEOMETRY)
    measurer = TextMeasurer(
        TextMeasurementInfo(
            mode="font-metrics",
            requested_font="Roboto",
            resolved_font="Roboto",
            resolved_style="Regular",
            font_source="fonts-dir",
            shaping="raqm",
            metric_size=43,
        ),
        lambda value: 1800.0 if value == text else len(value) * 20.0,
    )

    display, metrics = transcriber.layout_subtitle_cues(
        [{"id": 0, "start": 0.0, "end": 4.0, "text": text, "words": []}],
        resolved,
        GEOMETRY,
        language="pt",
        text_measurer=measurer,
    )

    assert metrics.width_budget == 1918
    assert display[0]["text"] == text


def test_global_partition_avoids_an_avoidable_one_word_final_line():
    words = [
        _word(word, index * 0.2, index * 0.2 + 0.15)
        for index, word in enumerate(
            "one two three four five six seven eight nine".split()
        )
    ]
    resolved = resolve_subtitle_config(
        validate_subtitle_config(
            None,
            relative_values={"max_width": "800px"},
        ),
        GEOMETRY,
    )
    measurer = TextMeasurer(
        TextMeasurementInfo(
            mode="font-metrics",
            requested_font="Roboto",
            resolved_font="Roboto",
            resolved_style="Regular",
            font_source="fonts-dir",
            shaping="raqm",
            metric_size=43,
        ),
        lambda value: len(value.split()) * 90.0,
    )

    display, _ = transcriber.layout_subtitle_cues(
        [
            {
                "id": 0,
                "start": 0.0,
                "end": 1.8,
                "text": "one two three four five six seven eight nine",
                "words": words,
            }
        ],
        resolved,
        GEOMETRY,
        text_measurer=measurer,
    )

    line_lengths = [len(line.split()) for line in display[0]["text"].splitlines()]
    assert len(display) == 1
    assert line_lengths in ([4, 5], [5, 4])


def test_build_subtitle_segments_rejects_invalid_coarse_timestamps():
    with pytest.raises(TranscriptionError):
        transcriber._build_subtitle_segments(
            [{"start": 3, "end": 2, "text": "invalid"}]
        )


def test_subtitle_writers_preserve_unicode_and_escape_ass_text(tmp_path: Path):
    segments = [
        {
            "id": 0,
            "start": 0.001,
            "end": 61.239,
            "text": "Olá {mundo}\\\n字幕",
            "words": [],
        }
    ]
    srt_path = tmp_path / "captions.srt"
    transcriber._write_srt(srt_path, segments)

    srt = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,001 --> 00:01:01,239" in srt
    assert "Olá" in srt and "字幕" in srt


def test_model_loading_retries_transient_connection_failures(monkeypatch):
    calls = 0
    delays = []
    progress = []

    def flaky_loader():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("remote end closed connection without response")
        return "loaded-model"

    monkeypatch.setattr(transcriber.time, "sleep", delays.append)

    result = transcriber._load_model_with_retries(
        flaky_loader,
        operation="Loading model",
        progress=progress.append,
    )

    assert result == "loaded-model"
    assert calls == 3
    assert delays == [1.0, 2.0]
    assert progress == [
        "Loading model encountered a temporary connection error; "
        "retrying (2/3) in 1s...",
        "Loading model encountered a temporary connection error; "
        "retrying (3/3) in 2s...",
    ]


def test_model_loading_does_not_retry_deterministic_failures(monkeypatch):
    calls = 0

    def invalid_loader():
        nonlocal calls
        calls += 1
        raise ValueError("unknown model")

    monkeypatch.setattr(
        transcriber.time,
        "sleep",
        lambda _: pytest.fail("deterministic failures must not sleep"),
    )

    with pytest.raises(ValueError, match="unknown model"):
        transcriber._load_model_with_retries(
            invalid_loader,
            operation="Loading model",
            progress=None,
        )

    assert calls == 1


def test_silero_model_load_blocks_unused_onnxruntime_probe(monkeypatch):
    monkeypatch.delitem(sys.modules, "onnxruntime", raising=False)
    observed = {}

    class FakeWhisper:
        @staticmethod
        def load_model(*args, **kwargs):
            observed["module_entry"] = sys.modules.get("onnxruntime")
            observed["vad_method"] = kwargs["vad_method"]
            return "loaded-model"

    result = transcriber._load_silero_whisperx_model(
        FakeWhisper,
        model_name="turbo",
        device="cuda",
        compute_type="float16",
        language="pt",
        task="transcribe",
    )

    assert result == "loaded-model"
    assert observed == {"module_entry": None, "vad_method": "silero"}
    assert "onnxruntime" not in sys.modules


def test_generate_transcriptions_uses_fake_whisper_runtime(tmp_path: Path, monkeypatch):
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"not real media")
    output_dir = tmp_path / "output"
    load_calls = {"count": 0}

    class FakeCuda:
        @staticmethod
        def is_available():
            return False

    class FakeTorch:
        cuda = FakeCuda()

    class FakeModel:
        def transcribe(self, audio):
            assert audio == "audio"
            return {
                "text": "Hello world.",
                "language": "en",
                "segments": [{"start": 0, "end": 1, "text": "Hello world."}],
            }

    class FakeWhisper:
        @staticmethod
        def load_model(*args, **kwargs):
            load_calls["count"] += 1
            if load_calls["count"] == 1:
                raise ConnectionError("remote end closed connection")
            assert kwargs["task"] == "transcribe"
            assert kwargs["vad_method"] == "silero"
            return FakeModel()

        @staticmethod
        def load_audio(path):
            assert path == str(input_path.resolve())
            return "audio"

        @staticmethod
        def load_align_model(**kwargs):
            return "align", "metadata"

        @staticmethod
        def align(segments, model, metadata, audio, device, **kwargs):
            return {
                "segments": [
                    {
                        "start": 0,
                        "end": 1,
                        "text": "Hello world.",
                        "words": [_word("Hello", 0, 0.4), _word("world.", 0.5, 1)],
                    }
                ]
            }

    monkeypatch.setattr(
        transcriber, "_load_runtime_dependencies", lambda: (FakeTorch, FakeWhisper)
    )
    monkeypatch.setattr(
        "multisubs.subtitler.probe_video_geometry", lambda path: GEOMETRY
    )
    monkeypatch.setattr(transcriber.time, "sleep", lambda _: None)
    paths = transcriber.generate_transcriptions(input_path, output_dir)

    json_path, srt_path, ass_path = map(Path, paths)
    assert load_calls["count"] == 2
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["language"] == "en"
    assert payload["schema_version"] == 1
    assert payload["metadata"]["created_at"].endswith("+00:00")
    assert payload["metadata"]["rendering"] == {
        "video_stream_index": 0,
        "coded_width": 1920,
        "coded_height": 1080,
        "render_width": 1920,
        "render_height": 1080,
        "rotation_degrees": 0,
        "sample_aspect_ratio": "1:1",
        "display_aspect_ratio": "16:9",
        "container_duration": 12.5,
        "requested_preset": "auto",
        "resolved_preset": "landscape",
        "placement_mode": "native-style",
        "requested_position": "bottom-center",
        "resolved_position": "bottom-center",
        "render_strategy": "single-event",
        "margins": {
            "applied": True,
            "left": 115,
            "right": 115,
            "top": 0,
            "bottom": 65,
        },
        "requested": {
            "font_size": "4%",
            "letter_spacing": "0px",
            "line_height": "auto",
            "backdrop_size": "0px",
            "shadow_size": "4%",
            "margins": {
                "left": "0px",
                "right": "0px",
                "top": "0px",
                "bottom": "0px",
            },
            "max_width": None,
            "max_height": None,
        },
        "resolved": {
            "font_size": 43,
            "letter_spacing": 0,
            "line_height": 51.6,
            "backdrop_size": 0,
            "shadow_size": 2,
            "margins": {
                "left": 115,
                "right": 115,
                "top": 0,
                "bottom": 65,
            },
            "max_width": 1690,
            "max_height": 107,
            "line_capacity": 2,
        },
        "wrapping": {
            "available_width": 1690,
            "available_height": 1015,
            "max_width": 1690,
            "max_height": 107,
            "width_budget": 1688,
            "line_height": 51.6,
            "natural_line_height": 51.6,
            "resolved_line_height": 51.6,
            "ascent": 43.0,
            "descent": 8.6,
            "vertical_decoration": 2,
            "line_capacity": 2,
            "font_size": 43,
            "letter_spacing": 0,
            "backdrop_size": 0,
            "shadow_size": 2,
        },
        "percentage_bases": {
            "letter_spacing": "resolved-font-size",
            "line_height": "natural-line-height",
            "max_width": "native-width-after-horizontal-margins",
            "max_height": "native-height-after-active-margin",
            "position_x": None,
            "position_y": None,
        },
        "text_measurement": {
            "mode": "unicode-estimate",
            "requested_font": "Roboto",
            "resolved_font": None,
            "resolved_style": None,
            "font_source": "unresolved",
            "shaping": None,
            "metric_size": None,
            "requested_weight_name": "regular",
            "requested_weight": 400,
            "requested_weight_input": "regular",
            "requested_weight_input_form": "default",
            "resolved_weight_name": None,
            "resolved_weight": None,
            "weight_substituted": None,
        },
        "opacity": {
            "requested": "100%",
            "percentage": 100,
            "normalized": 1,
            "base_colors": {
                "text": "#FFFFFFFF",
                "backdrop": "#00000099",
                "shadow": "#00000099",
                "karaoke_highlight": None,
            },
            "effective_colors": {
                "text": "#FFFFFFFF",
                "backdrop": "#00000099",
                "shadow": "#00000099",
                "karaoke_highlight": None,
            },
        },
        "effects": {
            "karaoke": {
                "enabled": False,
                "mode": None,
                "normal_color": "#FFFFFF",
                "highlight_color": None,
                "fallback_cues": 0,
            }
        },
        "native_region": {
            "left": 115,
            "top": 0,
            "right": 1805,
            "bottom": 1015,
            "width": 1690,
            "height": 1015,
        },
    }
    assert srt_path.exists() and ass_path.exists()


def test_line_height_json_and_ass_strategy_are_explicit(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="one two three four",
        segments=(
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "one two three four",
                "words": [],
            },
        ),
    )
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "line_height": "125%",
            "max_width": "180px",
            "max_height": "220px",
        },
    )

    json_path, srt_path, ass_path = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        config,
        geometry=GEOMETRY,
    )

    rendering = json.loads(Path(json_path).read_text(encoding="utf-8"))["metadata"][
        "rendering"
    ]
    assert rendering["requested"]["line_height"] == "125%"
    assert rendering["resolved"]["line_height"] == 60
    assert rendering["render_strategy"] == "positioned-lines"
    assert rendering["wrapping"]["resolved_line_height"] == 60
    assert rendering["percentage_bases"]["line_height"] == "natural-line-height"
    assert (
        len(
            [
                line
                for line in Path(ass_path).read_text(encoding="utf-8").splitlines()
                if line.startswith("Dialogue:")
            ]
        )
        >= 2
    )
    assert Path(srt_path).read_text(encoding="utf-8").count("\n\n") == 1


def test_explicit_line_height_reports_single_event_for_one_line(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="one-unbreakable-long-token",
        segments=(
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "one-unbreakable-long-token",
                "words": [],
            },
        ),
    )
    config = validate_subtitle_config(
        None,
        relative_values={
            "font_size": "40px",
            "line_height": "125%",
            "max_width": "100px",
            "max_height": "220px",
        },
    )

    json_path, _, ass_path = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        config,
        geometry=GEOMETRY,
    )

    rendering = json.loads(Path(json_path).read_text(encoding="utf-8"))["metadata"][
        "rendering"
    ]
    dialogue = [
        line
        for line in Path(ass_path).read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert rendering["render_strategy"] == "single-event"
    assert len(dialogue) == 1
    assert r"\pos(" not in dialogue[0]


def test_opacity_json_records_base_and_effective_component_colors(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello",
        segments=(
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "Hello",
                "words": [_word("Hello", 0.0, 1.0)],
            },
        ),
    )
    config = validate_subtitle_config(
        None,
        appearance_values={
            "text_color": "#11223380",
            "backdrop_color": "#44556699",
            "opacity": "32.5%",
        },
        effects_values={
            "karaoke": True,
            "highlight_color": "#778899C0",
        },
    )

    json_path, _, ass_path = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        config,
        geometry=GEOMETRY,
    )

    rendering = json.loads(Path(json_path).read_text(encoding="utf-8"))["metadata"][
        "rendering"
    ]
    assert rendering["opacity"] == {
        "requested": "32.5%",
        "percentage": 32.5,
        "normalized": 0.325,
        "base_colors": {
            "text": "#11223380",
            "backdrop": "#44556699",
            "shadow": "#44556699",
            "karaoke_highlight": "#778899C0",
        },
        "effective_colors": {
            "text": "#1122332A",
            "backdrop": "#44556632",
            "shadow": "#44556632",
            "karaoke_highlight": "#7788993E",
        },
    }
    ass = Path(ass_path).read_text(encoding="utf-8")
    assert "&HD5332211" in ass
    assert "&HCD665544" in ass
    assert r"\1c&H998877&\1a&HC1&" in ass


def test_write_transcription_artifacts_does_not_load_model_runtime(
    tmp_path: Path, monkeypatch
):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello.",
        segments=(
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "Hello.",
                "words": [],
            },
        ),
    )
    monkeypatch.setattr(
        transcriber,
        "_load_runtime_dependencies",
        lambda: pytest.fail("artifact writing must not load WhisperX or PyTorch"),
    )

    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            relative_values={
                "font_size": "4.5%",
                "margin_left": "8%",
                "margin_right": "8%",
            },
        ),
        geometry=GEOMETRY,
    )

    assert all(Path(path).exists() for path in paths)
    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    rendering = payload["metadata"]["rendering"]
    assert rendering["requested"]["font_size"] == "4.5%"
    assert rendering["requested"]["margins"] == {
        "left": "8%",
        "right": "8%",
        "top": "0px",
        "bottom": "0px",
    }
    assert rendering["resolved"]["font_size"] == 49
    assert rendering["resolved"]["margins"] == {
        "left": 154,
        "right": 154,
        "top": 0,
        "bottom": 65,
    }
    assert rendering["requested_preset"] == "auto"
    assert rendering["resolved_preset"] == "landscape"


def test_json_records_requested_font_weight_without_machine_path(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello.",
        segments=(
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "Hello.",
                "words": [],
            },
        ),
    )

    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            appearance_values={"font_weight": "300"},
            relative_values={"font_size": "40px", "letter_spacing": "50%"},
        ),
        geometry=GEOMETRY,
    )

    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    measurement = payload["metadata"]["rendering"]["text_measurement"]
    assert measurement["requested_weight_name"] == "light"
    assert measurement["requested_weight"] == 300
    assert measurement["requested_weight_input"] == "300"
    assert measurement["requested_weight_input_form"] == "numeric"
    assert measurement["resolved_weight_name"] is None
    assert measurement["resolved_weight"] is None
    assert measurement["weight_substituted"] is None
    assert "font_path" not in measurement
    rendering = payload["metadata"]["rendering"]
    assert rendering["requested"]["letter_spacing"] == "50%"
    assert rendering["resolved"]["letter_spacing"] == 20
    assert rendering["percentage_bases"]["letter_spacing"] == "resolved-font-size"


def test_custom_coordinates_are_recorded_in_rendering_metadata(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello.",
        segments=({"id": 0, "start": 0.0, "end": 1.0, "text": "Hello.", "words": []},),
    )

    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            relative_values={
                "position_x": "50%",
                "position_y": "86%",
                "max_width": "60%",
                "max_height": "20%",
            },
            anchor="bottom-center",
        ),
        geometry=GEOMETRY,
    )

    payload = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    rendering = payload["metadata"]["rendering"]
    assert rendering["placement_mode"] == "explicit"
    assert rendering["margins"]["applied"] is False
    assert rendering["requested_position"] is None
    assert rendering["resolved_position"] is None
    assert rendering["requested_coordinates"] == {
        "x": "50%",
        "y": "86%",
        "anchor": "bottom-center",
        "coordinate_space": "playres",
    }
    assert rendering["resolved_coordinates"] == {
        "x": 960,
        "y": 929,
        "anchor": "bottom-center",
        "coordinate_space": "playres",
    }


def test_centered_native_metadata_uses_the_full_canvas_height(tmp_path: Path):
    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"input")
    document = TranscriptDocument(
        source_path=source_path,
        language="en",
        task="transcribe",
        model_name="turbo",
        full_text="Hello.",
        segments=({"id": 0, "start": 0.0, "end": 1.0, "text": "Hello."},),
    )

    paths = transcriber.write_transcription_artifacts(
        document,
        tmp_path / "output",
        validate_subtitle_config(
            None,
            position="center",
            relative_values={"max_height": "50%"},
        ),
        geometry=GEOMETRY,
    )

    rendering = json.loads(Path(paths[0]).read_text(encoding="utf-8"))["metadata"][
        "rendering"
    ]
    assert rendering["placement_mode"] == "native-style"
    assert rendering["resolved"]["max_height"] == 540
    assert rendering["percentage_bases"]["max_height"] == "render-height"
    assert rendering["native_region"]["top"] == 0
    assert rendering["native_region"]["bottom"] == 1080
    assert "requested_coordinates" not in rendering
    assert "resolved_coordinates" not in rendering
