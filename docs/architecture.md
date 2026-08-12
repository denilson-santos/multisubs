# Architecture

## Overview

multisubs is a small Python package with one CLI entry point. It orchestrates two external capabilities:

- WhisperX and PyTorch for transcription and word-level timing alignment.
- FFmpeg, through ffmpeg-python, for rendering ASS subtitles into a video.

~~~mermaid
flowchart LR
    user[User command] --> cli[cli.py]
    input[Input video] --> cli
    config[config.py<br/>DEFAULT_STYLE] --> cli
    cli --> transcriber[transcriber.py]
    transcriber --> whisper[WhisperX + PyTorch]
    whisper --> cues[Timed subtitle cues]
    cues --> json[JSON]
    cues --> srt[SRT]
    cues --> ass[ASS]
    config --> transcriber
    cli --> subtitler[subtitler.py]
    input --> subtitler
    ass --> subtitler
    subtitler --> ffmpeg[FFmpeg subtitles filter]
    ffmpeg --> video[Rendered video]
    utils[utils.py] --> transcriber
    utils --> subtitler
~~~

## Components

| Component | Responsibility | Main interfaces |
| --- | --- | --- |
| multisubs/cli.py | Defines the console interface, validates direct user errors, chooses output layout, invokes the pipeline, and cleans up transient files. | main() |
| multisubs/transcriber.py | Loads WhisperX, transcribes audio, aligns words, builds readable cues, and writes JSON/SRT/ASS artifacts. | generate_transcriptions() |
| multisubs/subtitler.py | Invokes FFmpeg to burn the generated ASS file into a copy of the input video. | embed_subtitles() |
| multisubs/config.py | Defines the default ASS style dictionary used by the CLI and ASS writer. | DEFAULT_STYLE |
| multisubs/utils.py | Produces non-conflicting file and directory paths. | get_unique_path(), get_unique_dir_path() |
| multisubs/__init__.py | Exposes the package version and primary package functions. | __version__ |

## Execution flow

1. The console script declared in pyproject.toml calls cli.main().
2. The CLI parses options and verifies that the input exists and that the output path is not an existing file.
3. For a translation task, the CLI rejects turbo and English-only model names before model loading.
4. The CLI builds style overrides from --style-* flags and chooses either the flat or retained output layout.
5. generate_transcriptions() selects CUDA with float16 when available, otherwise CPU with int8.
6. WhisperX loads the requested model with the Silero VAD method, extracts audio from the input, transcribes it, and aligns the result at word level.
7. The cue builder combines consecutive aligned segments, prefers sentence endings, clauses, and meaningful pauses, and applies duration and text-length limits as fallbacks.
8. The transcriber writes JSON, SRT, and ASS files.
9. embed_subtitles() passes the input video and ASS path to FFmpeg's subtitles filter, copying the audio stream into the rendered output.
10. The CLI either retains all transcription files or removes the transient SRT and ASS files after a successful render.

## Subtitle-cue construction

The subtitle builder is intentionally separate from raw WhisperX segmentation:

- It joins adjacent WhisperX word streams so an ASR segment boundary does not force a poor subtitle break.
- It emits a cue at a sentence end or a pause of at least 0.45 seconds when possible.
- It targets no more than 6 seconds and 84 characters per cue.
- It wraps text to two lines with a preferred line length of 42 characters. A small overflow is allowed when it preserves a better phrase boundary.
- If word timestamps are unavailable for a WhisperX segment, it flushes pending aligned words and uses that segment's coarse start and end times as a safe fallback.

These rules reside in multisubs/transcriber.py and should be changed with focused tests once a test suite is introduced.

## Output data

### JSON

The JSON artifact has this high-level shape:

~~~
{
  "metadata": {
    "file_name": "video",
    "original_path": "/path/to/video.mp4",
    "language": "pt",
    "task": "transcribe",
    "created_at": "ISO-8601 timestamp",
    "model": "turbo",
    "duration": 123.45,
    "num_segments": 12
  },
  "transcription": {
    "text": "Complete transcription",
    "segments": [
      {
        "id": 0,
        "start": 0.0,
        "end": 2.4,
        "text": "One or two subtitle lines",
        "words": []
      }
    ]
  }
}
~~~

The words array preserves the usable aligned-word records supplied by WhisperX. Its exact optional fields are owned by that dependency.

### SRT and ASS

SRT is generated from cue start time, end time, and wrapped text. ASS contains a Default style built from DEFAULT_STYLE plus any CLI overrides; line breaks are converted to ASS's \N syntax in dialogue events.

## Output layouts

For video.mp4, language pt, and an output directory named output:

| Mode | Rendered video | Subtitle artifacts |
| --- | --- | --- |
| Default | output/video-pt.mp4 | output/video-pt.json remains; temporary output/video-pt.srt and output/video-pt.ass are removed after a successful render. |
| --keep-transcriptions | output/video/video-pt.mp4 | output/video/subtitles/video-pt.json, video-pt.srt, and video-pt.ass |

get_unique_path() and get_unique_dir_path() append (1), (2), and so on when a target already exists.

## External boundaries

### WhisperX and PyTorch

The transcriber owns all model interaction. It chooses the compute device, calls the transcription API, then requests an alignment model for the detected or requested language. Silero VAD is explicitly selected to avoid the default Pyannote VAD dependency path and its compatibility constraints.

### FFmpeg

subtitler.py owns video rendering. It uses the ASS subtitle file as the source for FFmpeg's subtitles video filter and requests audio stream copying. Errors from FFmpeg are currently allowed to propagate to the caller rather than being translated into a project-specific error type.

## Design constraints

- The pipeline is synchronous and processes one video at a time.
- Subtitle rendering is a hard-subtitle operation, not muxing a selectable subtitle track.
- Translation has an English-only target and requires a multilingual non-Turbo Whisper model.
- Artifact cleanup happens only after subtitle rendering returns successfully.
- File collision avoidance is a required safety property, not merely a convenience.
