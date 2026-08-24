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
| multisubs/layout.py | Classifies autorotated geometry, merges preset and explicit layout fields, resolves unit-bearing lengths, derives wrapping dimensions, and validates native regions or explicit subtitle envelopes on the probed canvas. | classify_layout_preset(), resolve_relative_length(), resolve_subtitle_config(), resolve_native_layout_region(), resolve_wrapping_metrics(), resolve_cue_placement() |
| multisubs/text_measurement.py | Resolves custom or fontconfig faces, measures glyph advances with Pillow/RAQM, caches per-run values, and owns the Unicode-aware fallback. | build_text_measurer(), TextMeasurer, TextMeasurementInfo |
| multisubs/utils.py | Produces non-conflicting file and directory paths. | get_unique_path(), get_unique_dir_path() |
| multisubs/errors.py | Defines user-actionable validation, dependency, artifact, transcription, and rendering errors. | MultisubsError subclasses |
| multisubs/models.py | Defines typed request, unit-bearing subtitle configuration, semantic backdrop and layout choices, immutable layout preset values, video geometry, per-cue placement, semantic transcript, and artifact value objects. | RelativeLength, CuePlacement, LayoutPreset, RunRequest, SubtitleBackdrop, SubtitleConfig, SubtitleLayoutPreset, VideoGeometry, TranscriptDocument, RunArtifacts, TranscriptionPaths |
| multisubs/__init__.py | Exposes the package version and lazily loads the primary package functions. | __version__ |

## Execution flow

1. The console script declared in pyproject.toml calls cli.main().
2. The CLI parses options and verifies that the selected source language has a default WhisperX alignment model, the input exists, the output path is not an existing file, semantic colors and appearance values are valid, every unit value has an explicit suffix, the layout preset is supported, and any named position or custom anchor is one of the nine supported screen anchors. Unit-bearing options are stored as RelativeLength values; raw ASS style mappings and `--style-*` options are not accepted. Custom X/Y coordinates must be supplied as a pair, cannot be combined with `--position`, and require explicit anchor, maximum width, and maximum height values.
3. For a translation task, the CLI rejects turbo and English-only model names before model loading.
4. The CLI validates the FFmpeg and ffprobe executables and FFmpeg's subtitles filter. probe_video_geometry() then selects the lowest-index usable video stream and validates coded dimensions, rotation, sample aspect ratio, displayed aspect ratio, and container duration before a work directory or model is loaded. resolve_subtitle_config() classifies `--layout auto` from the autorotated render aspect ratio, merges the selected immutable preset with explicit field overrides, and resolves all dimensions. Native placement resolves maximum width after horizontal ASS margins and maximum height after the active top or bottom margin; middle alignment uses the full height. Explicit placement resolves X/Y and both maximum dimensions against the full PlayRes canvas, ignores margins, and rejects a complete envelope that crosses an edge. resolve_wrapping_metrics() also validates that at least one decorated line fits before WhisperX is loaded.
5. The geometry policy follows explicitly enabled FFmpeg autorotation: 0° and 180° retain the coded axes; 90° and 270° swap the render axes and invert the sample-aspect-ratio axes. Legacy rotate tags are normalized from their sign convention to the display-matrix convention. Contradictory metadata is rejected.
6. The CLI reports the resolved dimensions, semantic position, and concrete layout preset, then creates a private temporary work directory inside the output directory.
7. transcribe_video() selects CUDA with float16 when available, otherwise CPU with int8; WhisperX is imported only at the transcription boundary.
8. WhisperX loads the requested model with the Silero VAD method, extracts audio from the input, transcribes it, and aligns the result at word level. During Silero setup, the transcriber isolates WhisperX's unused optional Pyannote ONNX import so ONNX Runtime does not probe an incomplete Linux DRM sysfs tree. Model, VAD, and alignment asset loads retry transient connection failures up to three attempts with a short exponential backoff; deterministic loading errors are surfaced immediately.
9. The cue builder combines consecutive aligned segments, prefers sentence endings, clauses, and meaningful pauses, and applies the duration ceiling as a fallback. The resolved layout then creates display cues using maximum width, maximum height, font line height, and backdrop/shadow allowances. The text-measurement boundary first searches the validated custom font directory, then queries fontconfig where available, measures a resolved face with Pillow/RAQM, and otherwise uses its explicit Unicode estimate. Complete cues that fit remain unbroken; required multi-line layouts use bounded global partition scoring rather than greedy first-line filling.
10. write_transcription_artifacts() validates external timestamps and writes UTF-8 JSON and SRT files atomically. It delegates preset merging, unit resolution, placement validation, and wrapping metrics to layout.py, then delegates ASS serialization to ass.py. The ASS compiler converts conventional RGBA colors to ASS BGR/inverted-alpha values. Native placement compiles semantic alignment and actual margins into the style without event positioning; explicit placement uses neutral style margins and generated per-cue `\\an`/`\\pos` tags. Dialogue text is escaped separately. JSON preserves JSON-compatible aligned-word metadata plus the placement mode, applicable margins, requested and resolved dimensions, wrapping metrics, native region or explicit PlayRes coordinates.
11. embed_subtitles() selects the same probed stream, explicitly enables autorotation, supplies the normalized canvas as original_size to the structured FFmpeg subtitles filter, and supplies fontsdir only when a validated custom fonts directory was requested. Available audio streams are copied into a temporary rendered output when present.
12. After rendering succeeds, the CLI publishes a collision-safe set of final artifacts and removes the private work directory. Failed runs retain transcription artifacts in that directory for diagnosis, while the renderer removes its partial temporary media.

## Subtitle-cue construction

The subtitle builder is intentionally separate from raw WhisperX segmentation:

- It joins adjacent WhisperX word streams so an ASR segment boundary does not force a poor subtitle break.
- It emits a cue at a sentence end or a pause of at least 0.45 seconds when possible.
- It targets no more than 6 seconds per semantic cue; width no longer uses a
  fixed character count.
- It calculates a PlayRes width budget from `max-width` after subtracting the
  horizontal backdrop/shadow allowance. In native mode, percentage width uses
  the region remaining after left/right margins; in explicit mode it uses the
  full canvas and the requested envelope must already fit its anchor.
- It derives line capacity from `max-height` after subtracting the vertical
  backdrop/shadow allowance, divided by the resolved font line height. Presets
  retain a calibrated two-line default, but there is no fixed max-lines input.
- It measures a concrete face with Pillow when `--fonts-dir` or fontconfig can
  resolve the family/style that libass will use. RAQM applies direction and
  language shaping when available. Otherwise it reports and records a
  Unicode-category estimate with calibrated proportional-width factors.
- It keeps a complete cue on one line whenever its measured width fits. A
  required multi-line break searches no more partitions than both the derived
  line capacity and the number of text units, then scores semantic class,
  overflow, avoidable orphan lines, raggedness, and deterministic source order.
- It prefers a new timed cue over exceeding the derived visual line capacity
  when aligned word boundaries are available. Semantic sentence, clause, and
  pause priorities remain higher than line balancing.
- It emits intentional visual line breaks to SRT and ASS. A coarse segment
  without word timestamps is wrapped lexically without inventing new timings.
- A long indivisible token remains intact and may overflow the approximate width
  budget; transcript content is never removed or mutated.
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
      "placement_mode": "native-style",
      "requested_position": "bottom-center",
      "resolved_position": "bottom-center",
      "margins": {
        "applied": true,
        "left": 86,
        "right": 86,
        "top": 0,
        "bottom": 154
      },
      "requested": {
        "font_size": "4%",
        "backdrop_size": "0px",
        "shadow_size": "4%",
        "margins": {
          "left": "0px",
          "right": "0px",
          "top": "0px",
          "bottom": "0px"
        },
        "max_width": null,
        "max_height": null
      },
      "resolved": {
        "font_size": 43,
        "backdrop_size": 0,
        "shadow_size": 2,
        "margins": {
          "left": 86,
          "right": 86,
          "top": 0,
          "bottom": 154
        },
        "max_width": 908,
        "max_height": 106,
        "line_capacity": 2
      },
      "wrapping": {
        "available_width": 908,
        "available_height": 1766,
        "max_width": 908,
        "max_height": 106,
        "width_budget": 906,
        "line_height": 43.0,
        "vertical_decoration": 2,
        "line_capacity": 2,
        "font_size": 43,
        "backdrop_size": 0,
        "shadow_size": 2
      },
      "percentage_bases": {
        "max_width": "native-width-after-horizontal-margins",
        "max_height": "native-height-after-active-margin",
        "position_x": null,
        "position_y": null
      },
      "text_measurement": {
        "mode": "font-metrics",
        "requested_font": "Roboto",
        "resolved_font": "Roboto",
        "resolved_style": "Regular",
        "font_source": "fontconfig",
        "shaping": "raqm",
        "metric_size": 36
      },
      "native_region": {
        "left": 86,
        "top": 0,
        "right": 994,
        "bottom": 1766,
        "width": 908,
        "height": 1766
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

`schema_version` identifies the top-level JSON contract. The words array preserves the usable JSON-compatible aligned-word records supplied by WhisperX; its exact optional fields are owned by that dependency. `created_at` is a timezone-aware UTC ISO-8601 timestamp. The rendering object records normalized geometry, requested and resolved presets, placement mode, whether margins apply, maximum dimensions, percentage bases, and the reproducibility inputs used by adaptive wrapping. The `wrapping` object records available and maximum dimensions, effective width budget, measured line height, vertical decoration allowance, and derived line capacity. `text_measurement` records `font-metrics` or `unicode-estimate`, requested and resolved family/style names, font source, and shaping mode. Unresolved values are null, font substitutions remain visible, and absolute local font paths are never serialized. Native mode adds `native_region` and deliberately omits synthetic coordinates. Explicit mode omits `native_region` and adds requested and resolved X/Y values with `coordinate_space: playres`. The metadata does not claim exact equivalence with final libass shaping or store generated ASS or raw command lines. `container_duration` is null when ffprobe cannot report it.

### SRT and ASS

SRT is generated from cue start time, end time, and layout-aware wrapped text.
ASS contains a Default style compiled from semantic `SubtitleConfig` values.
Raw ASS style mappings are rejected. The public `--layout` value is stored on
SubtitleConfig and resolved to a concrete preset in layout.py. Explicit fields
override only their matching preset fields in native mode.

RelativeLength margins use render width or height, font size uses the shorter
render edge, and decoration sizes use the resolved font size. Native percentage
`max-width` uses the width after left/right margins. Native percentage
`max-height` uses the height after the active top or bottom margin, while middle
alignment uses the full render height. The public `--position` compiles to the
corresponding ASS style Alignment; actual `MarginL`, `MarginR`, and active
`MarginV` values remain authoritative, and no event `\\pos` is emitted.

Explicit `--position-x` and `--position-y` percentages use the full render axes;
pixels are absolute PlayRes coordinates. Explicit maximum dimensions also use
the full axes, all margins compile to zero, and each cue receives the private
anchor plus `\\pos` event override. layout.py rejects an envelope whose maximum
width or height would cross the canvas for the selected anchor; it does not
clamp, move, or shrink it. Percentages use Decimal half-up rounding. All resolved
lengths use PlayRes pixels, and resolved font, backdrop, and shadow values remain
bounded.
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
timing only; it cannot represent named or custom positioning.

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

### Pillow and font providers

Pillow is a direct runtime dependency used only by the text-measurement
boundary. It loads a validated TrueType/OpenType face and returns advance widths
in PlayRes pixels; the standard library and existing dependencies do not expose
equivalent shaping-aware font metrics. Because libass asks FreeType for a
real-dimension size while Pillow starts from an EM-oriented size, the measurer
normalizes Pillow's ascent plus descent to the resolved ASS font size and records
the resulting `metric_size`. The package uses the MIT-CMU license, is
actively maintained, supports the project's Python 3.10-3.13 range, and
publishes platform wheels. Typical wheels add several megabytes to an
environment, but Pillow is already present transitively in common WhisperX
installations; declaring it directly makes the relied-upon API explicit.

Custom font resolution inspects only supported files directly inside
`--fonts-dir` and matches their internal family/style metadata. On hosts with
fontconfig, `fc-match` is invoked with a bounded argument-vector subprocess and
its returned regular file is validated. Other providers are not guessed. Font
objects and up to 4096 repeated text measurements are cached in memory for one
artifact-writing run; transcript strings are not persisted by the cache.
Pillow and libass can differ in shaping, hinting, and fallback, so libass remains
the render authority and integration tests use an explicit tolerance.

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
