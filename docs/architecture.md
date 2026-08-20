# Architecture

## Overview

multisubs is a small Python package with one CLI entry point. It orchestrates two external capabilities:

- WhisperX and PyTorch for transcription and word-level timing alignment.
- FFmpeg and ffprobe for normalized media geometry and ASS subtitle rendering.

~~~mermaid
flowchart LR
    user[User command] --> cli[cli.py]
    input[Input video] --> cli
    input --> probe[ffprobe geometry]
    probe --> cli
    config[config.py<br/>typed subtitle config] --> cli
    cli --> transcriber[transcriber.py]
    transcriber --> whisper[WhisperX + PyTorch]
    whisper --> cues[Timed subtitle cues]
    cues --> json[JSON]
    cues --> srt[SRT]
    cues --> asswriter[ass.py]
    asswriter --> ass[ASS]
    config --> asswriter
    probe --> asswriter
    cli --> subtitler[subtitler.py]
    input --> subtitler
    ass --> subtitler
    probe --> subtitler
    subtitler --> ffmpeg[FFmpeg subtitles filter]
    ffmpeg --> video[Rendered video]
    utils[utils.py] --> transcriber
    utils --> subtitler
    errors[errors.py] --> cli
    models[models.py] --> cli
~~~

## Components

| Component | Responsibility | Main interfaces |
| --- | --- | --- |
| multisubs/cli.py | Defines the console interface, validates direct user errors, chooses output layout, invokes the pipeline, and cleans up transient files. | main() |
| multisubs/transcriber.py | Loads WhisperX, transcribes audio, aligns words, builds readable cues, and coordinates JSON/SRT/ASS artifact writing. | transcribe_video(), write_transcription_artifacts(), generate_transcriptions() |
| multisubs/ass.py | Compiles semantic appearance into private ASS fields and serializes headers, timestamps, placement overrides, and safely escaped dialogue text. | write_ass(), rgba_to_ass_color() |
| multisubs/subtitler.py | Probes normalized video geometry and invokes FFmpeg to burn ASS into the selected video stream. | probe_video_geometry(), embed_subtitles() |
| multisubs/config.py | Defines supported choices, semantic appearance defaults, immutable layout preset sources, and validates typed subtitle configuration. | SUPPORTED_LANGUAGES, MODELS, LAYOUT_PRESETS, validate_subtitle_config() |
| multisubs/layout.py | Classifies autorotated geometry, merges preset and explicit layout fields, resolves unit-bearing lengths, and validates the subtitle-safe rectangle on the probed canvas. | classify_layout_preset(), resolve_relative_length(), resolve_subtitle_config(), resolve_safe_rectangle() |
| multisubs/utils.py | Produces non-conflicting file and directory paths. | get_unique_path(), get_unique_dir_path() |
| multisubs/errors.py | Defines user-actionable validation, dependency, artifact, transcription, and rendering errors. | MultisubsError subclasses |
| multisubs/models.py | Defines typed request, unit-bearing subtitle configuration, semantic backdrop and layout choices, immutable layout preset values, video geometry, per-cue placement, semantic transcript, and artifact value objects. | RelativeLength, CuePlacement, LayoutPreset, RunRequest, SubtitleBackdrop, SubtitleConfig, SubtitleLayoutPreset, VideoGeometry, TranscriptDocument, RunArtifacts, TranscriptionPaths |
| multisubs/__init__.py | Exposes the package version and lazily loads the primary package functions. | __version__ |

## Execution flow

1. The console script declared in pyproject.toml calls cli.main().
2. The CLI parses options and verifies that the selected source language has a default WhisperX alignment model, the input exists, the output path is not an existing file, semantic colors and appearance values are valid, every unit value has an explicit suffix, the layout preset is supported, and any named position or custom anchor is one of the nine supported screen anchors. Unit-bearing options are stored as RelativeLength values; raw ASS style mappings and `--style-*` options are not accepted. Custom X/Y coordinates must be supplied as a pair and cannot be combined with --position.
3. For a translation task, the CLI rejects turbo and English-only model names before model loading.
4. The CLI validates the FFmpeg and ffprobe executables and FFmpeg's subtitles filter. probe_video_geometry() then selects the lowest-index usable video stream and validates coded dimensions, rotation, sample aspect ratio, displayed aspect ratio, and container duration before a work directory or model is loaded. resolve_subtitle_config() classifies --layout auto from the autorotated render aspect ratio, merges the selected immutable preset with explicit field overrides, converts every known unit-bearing field once against that geometry, and validates the resulting safe rectangle. resolve_cue_placement() then resolves custom coordinates against the PlayRes canvas and rejects anchors that cannot fit inside the safe rectangle before WhisperX is loaded.
5. The geometry policy follows explicitly enabled FFmpeg autorotation: 0° and 180° retain the coded axes; 90° and 270° swap the render axes and invert the sample-aspect-ratio axes. Legacy rotate tags are normalized from their sign convention to the display-matrix convention. Contradictory metadata is rejected.
6. The CLI reports the resolved dimensions, semantic position, and concrete layout preset, then creates a private temporary work directory inside the output directory.
7. transcribe_video() selects CUDA with float16 when available, otherwise CPU with int8; WhisperX is imported only at the transcription boundary.
8. WhisperX loads the requested model with the Silero VAD method, extracts audio from the input, transcribes it, and aligns the result at word level. During Silero setup, the transcriber isolates WhisperX's unused optional Pyannote ONNX import so ONNX Runtime does not probe an incomplete Linux DRM sysfs tree. Model, VAD, and alignment asset loads retry transient connection failures up to three attempts with a short exponential backoff; deterministic loading errors are surfaced immediately.
9. The cue builder combines consecutive aligned segments, prefers sentence endings, clauses, and meaningful pauses, and applies duration and text-length limits as fallbacks.
10. write_transcription_artifacts() validates external timestamps and writes UTF-8 JSON and SRT files atomically. It delegates preset merging, unit resolution, custom-placement validation, and safe-rectangle validation to layout.py, then delegates ASS serialization to ass.py. The ASS compiler converts conventional RGBA colors to ASS BGR/inverted-alpha values, maps semantic backdrop and position choices to private ASS fields, emits generated per-cue \\an/\\pos tags for custom coordinates, and safely escapes dialogue text separately. The JSON artifact preserves only JSON-compatible aligned-word metadata plus requested and resolved preset names, requested unit strings, resolved PlayRes values, position or custom coordinates, and the safe rectangle used for rendering.
11. embed_subtitles() selects the same probed stream, explicitly enables autorotation, supplies the normalized canvas as original_size to the structured FFmpeg subtitles filter, and supplies fontsdir only when a validated custom fonts directory was requested. Available audio streams are copied into a temporary rendered output when present.
12. After rendering succeeds, the CLI publishes a collision-safe set of final artifacts and removes the private work directory. Failed runs retain transcription artifacts in that directory for diagnosis, while the renderer removes its partial temporary media.

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
  "schema_version": 1,
  "metadata": {
    "file_name": "video",
    "original_path": "/path/to/video.mp4",
    "language": "pt",
    "task": "transcribe",
    "created_at": "ISO-8601 timestamp",
    "model": "turbo",
    "duration": 123.45,
    "num_segments": 12,
    "rendering": {
      "video_stream_index": 0,
      "coded_width": 1920,
      "coded_height": 1080,
      "render_width": 1080,
      "render_height": 1920,
      "rotation_degrees": 90,
      "sample_aspect_ratio": "1:1",
      "display_aspect_ratio": "9:16",
      "container_duration": 123.45,
      "requested_preset": "auto",
      "resolved_preset": "portrait",
      "requested_position": "bottom-center",
      "resolved_position": "bottom-center",
      "margins": {
        "left": 86,
        "right": 86,
        "top": 96,
        "bottom": 154
      },
      "requested": {
        "font_size": "4%",
        "backdrop_size": "0px",
        "shadow_size": "4%",
        "margins": {
          "left": "8%",
          "right": "8%",
          "top": "5%",
          "bottom": "8%"
        }
      },
      "resolved": {
        "font_size": 43,
        "backdrop_size": 0,
        "shadow_size": 2,
        "margins": {
          "left": 86,
          "right": 86,
          "top": 96,
          "bottom": 154
        }
      },
      "safe_rectangle": {
        "left": 86,
        "top": 96,
        "right": 994,
        "bottom": 1766,
        "width": 908,
        "height": 1670
      }
    }
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

`schema_version` identifies the top-level JSON contract. The words array preserves the usable JSON-compatible aligned-word records supplied by WhisperX. Its exact optional fields are owned by that dependency. `created_at` is a timezone-aware UTC ISO-8601 timestamp. The rendering object records the geometry, requested and resolved layout presets, semantic position or custom coordinates, resolved margins, and safe rectangle used for both ASS generation and the FFmpeg filter; container_duration is null when ffprobe cannot report it. Unit-bearing fields add `rendering.requested` strings and `rendering.resolved` PlayRes values without storing generated ASS or raw command lines. Custom placement adds `requested_coordinates` with the original X/Y strings and anchor, plus `resolved_coordinates` with integer PlayRes coordinates and anchor.

### SRT and ASS

SRT is generated from cue start time, end time, and wrapped text. ASS contains a
Default style compiled from semantic `SubtitleConfig` values. Raw ASS style
mappings are rejected. The public `--layout` value is stored on SubtitleConfig and resolved to a concrete preset
in layout.py. The public `--position` value is stored on SubtitleLayout and
mapped to the private ASS alignment field only inside ass.py. Explicit position
and margin fields override only their matching preset fields. RelativeLength
values are resolved once in layout.py using render width, render height, or the
shorter edge according to their field. Custom `--position-x` and
`--position-y` values use render width and height respectively; their anchor is
converted to a private ASS alignment and serialized with `\\pos` per cue.
Percentages use Decimal half-up rounding; pixel values refer to the PlayRes
canvas. layout.py validates that all four resolved margins leave a positive safe
rectangle on the autorotated canvas, that custom anchors fit inside that
rectangle, and that resolved font, backdrop, and shadow values remain bounded.
ass.py converts `#RRGGBB[AA]` colors, backdrop kinds, boolean text treatments,
and semantic positions into the required private ASS fields. The `box` backdrop
uses libass `BorderStyle=4`, which draws one background box for the complete
cue. The required ASS `SecondaryColour` field follows the semantic text color
until a separate karaoke/highlight color is introduced. `OutlineColour` and
`BackColour` both follow the one semantic backdrop color. Underline and
strikeout remain disabled; scale stays at 100%, spacing and angle at zero, and
encoding at 1 because those ASS internals are outside the public appearance
model. ass.py converts line
breaks to ASS's \N syntax in dialogue events and escapes
subtitle-derived braces and backslashes separately from generated override tags
so they cannot become unintended controls. Every generated ASS declares
ScriptType, PlayResX, PlayResY, ScaledBorderAndShadow, and WrapStyle in a stable
order. PlayRes matches the autorotated render dimensions. SRT retains text and
timing only; it cannot represent custom positioning.

## Output layouts

For video.mp4, language pt, and an output directory named output:

| Mode | Rendered video | Subtitle artifacts |
| --- | --- | --- |
| Default | output/video-pt.mp4 | output/video-pt.json remains; temporary output/video-pt.srt and output/video-pt.ass are removed after a successful render. |
| --keep-transcriptions | output/video/video-pt.mp4 | output/video/subtitles/video-pt.json, video-pt.srt, and video-pt.ass |

get_unique_path() and get_unique_dir_path() append (1), (2), and so on when a target already exists. Related JSON/SRT/ASS/video outputs reserve one shared stem so a collision cannot split a run across different suffixes.

## External boundaries

### WhisperX and PyTorch

The transcriber owns all model interaction. It chooses the compute device, calls the transcription API, then requests an alignment model for the detected or requested language. The public CLI limits source-language choices to codes with a default alignment model in the installed WhisperX release. Silero VAD is explicitly selected to avoid the default Pyannote VAD dependency path and its compatibility constraints. Because the installed WhisperX release eagerly imports Pyannote's optional speaker-embedding support, Silero model setup temporarily blocks that unused ONNX Runtime import; this avoids a benign DRM discovery warning without changing PyTorch/CUDA inference.

### FFmpeg

subtitler.py owns ffprobe inspection and video rendering. It checks that both
executables and the subtitles filter are available, bounds probe time and
diagnostics, and parses only the geometry contract from JSON. The render graph
selects the recorded stream index, explicitly enables FFmpeg autorotation, uses
the render dimensions as libass original_size, and requests copying of any
available audio streams. Probe and FFmpeg failures preserve their original cause
behind an actionable project error.

## Design constraints

- The pipeline is synchronous and processes one video at a time.
- Subtitle rendering is a hard-subtitle operation, not muxing a selectable subtitle track.
- Translation has an English-only target and requires a multilingual non-Turbo Whisper model.
- Supported source languages must have a default word-alignment model in the installed WhisperX release.
- Completed transcription artifacts are cleaned only after subtitle rendering returns successfully; partial renderer media is cleaned on both success and failure.
- File collision avoidance is a required safety property, not merely a convenience.
- Final media is published only after FFmpeg succeeds; temporary output is never presented as a completed video.
- CLI diagnostics use non-zero exit statuses for validation and processing failures.
- ASS PlayRes, JSON rendering metadata, and the FFmpeg subtitles filter must use one VideoGeometry instance per run.
