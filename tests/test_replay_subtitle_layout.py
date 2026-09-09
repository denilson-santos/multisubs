import json
import subprocess
import sys

import pytest

from multisubs.errors import ValidationError
from scripts.replay_subtitle_layout import FIDELITY, load_transcript, main, replay


@pytest.fixture
def retained(tmp_path):
    path = tmp_path / "retained.json"
    payload = {
        "schema_version": 3,
        "metadata": {
            "language": "ja",
            "task": "transcribe",
            "model": "turbo",
            "original_path": "/do-not-open/private.mp4",
            "rendering": {"render_width": 320, "render_height": 240},
        },
        "transcription": {
            "text": "字幕。",
            "segments": [
                {"start": 0.0, "end": 0.2, "text": "字幕。", "words": []},
            ],
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False))
    return path


def test_replay_keeps_input_and_publishes_unique_artifacts(retained, tmp_path):
    original = retained.read_bytes()
    one = replay(retained, tmp_path / "outputs", template="default")
    two = replay(retained, tmp_path / "outputs", template="default")
    assert one != two
    assert retained.read_bytes() == original
    for output in (one, two):
        assert len(list(output.glob("*.srt"))) == 1
        assert len(list(output.glob("*.ass"))) == 1
        evidence = json.loads((output / "evidence.json").read_text())
        assert evidence["fidelity"] == FIDELITY
        assert evidence["render_status"] == "not-requested"
        assert "/do-not-open" not in (output / "evidence.json").read_text()
        assert evidence["bundled_font_sha256"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("metadata", None),
        ("transcription", []),
    ],
)
def test_replay_rejects_invalid_shape_before_output(retained, tmp_path, field, value):
    payload = json.loads(retained.read_text())
    payload[field] = value
    retained.write_text(json.dumps(payload))
    with pytest.raises(ValidationError):
        replay(retained, tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("end", [float("nan"), float("inf"), -1, 3601, "1", True])
def test_replay_rejects_invalid_times(retained, end):
    payload = json.loads(retained.read_text())
    payload["transcription"]["segments"][0]["end"] = end
    retained.write_text(json.dumps(payload))
    with pytest.raises(ValidationError):
        load_transcript(retained)


def test_replay_retains_missing_alignment_and_ignores_private_keys(retained):
    payload = json.loads(retained.read_text())
    payload["transcription"]["segments"][0].update(
        words=[{"word": "字幕。"}],
        _karaoke_cue="untrusted",
    )
    retained.write_text(json.dumps(payload))
    doc, _, _ = load_transcript(retained)
    assert doc.segments[0]["words"] == [{"word": "字幕。"}]
    assert "_karaoke_cue" not in doc.segments[0]


def test_replay_has_no_speech_imports(retained, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from scripts.replay_subtitle_layout import main; "
            "assert main(sys.argv[1:]) == 0; "
            "assert 'whisperx' not in sys.modules; assert 'torch' not in sys.modules",
            str(retained),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_replay_bounds_input_size(retained, monkeypatch):
    monkeypatch.setattr("scripts.replay_subtitle_layout.MAX_JSON_BYTES", 10)
    with pytest.raises(ValidationError, match="16 MiB"):
        load_transcript(retained)


@pytest.mark.parametrize("value", [None, [], {}, True, "translate-to-ja"])
def test_replay_rejects_invalid_task_without_type_errors(retained, value):
    payload = json.loads(retained.read_text())
    payload["metadata"]["task"] = value
    retained.write_text(json.dumps(payload))
    with pytest.raises(ValidationError, match="language or task"):
        load_transcript(retained)


@pytest.mark.parametrize("width", [None, "320", True, 0, 4097])
def test_replay_validates_canvas_before_creating_outputs(retained, tmp_path, width):
    payload = json.loads(retained.read_text())
    payload["metadata"]["rendering"]["render_width"] = width
    retained.write_text(json.dumps(payload))
    with pytest.raises(ValidationError, match="canvas"):
        replay(retained, tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


def test_replay_reports_invalid_input_without_transcript_text(retained, capsys):
    retained.write_text("private malformed transcript")
    assert main([str(retained), "--output-dir", str(retained.parent / "out")]) == 1
    assert "private malformed transcript" not in capsys.readouterr().out


def test_render_failure_preserves_input_and_diagnostic_artifacts(
    retained, tmp_path, monkeypatch
):
    original = retained.read_bytes()

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["ffmpeg"])

    monkeypatch.setattr("scripts.replay_subtitle_layout.subprocess.run", fail)
    # Version lookup also runs a subprocess; keep it independent of failure injection.
    monkeypatch.setattr(
        "scripts.replay_subtitle_layout._command_version", lambda args: None
    )
    with pytest.raises(subprocess.CalledProcessError):
        replay(retained, tmp_path / "outputs", render=True)
    assert retained.read_bytes() == original
    assert list((tmp_path / "outputs").glob("*/evidence.json"))
