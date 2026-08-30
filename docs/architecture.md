# Architecture

## Overview

multisubs is a small Python package with one CLI entry point. It orchestrates two external capabilities:

- WhisperX and PyTorch for transcription and word-level timing alignment.
- FFmpeg and ffprobe for normalized media geometry and ASS subtitle rendering.
- A transcription-free preview path that reuses the same ASS and FFmpeg
  subtitle filter without importing WhisperX or PyTorch.

~~~mermaid
flowchart LR
    user[User command] --> cli[cli.py]
    input[Input video] --> cli
    input --> probe[ffprobe geometry]
    probe --> cli
    config[config.py<br/>typed subtitle config] --> cli
    cli --> preview[preview.py<br/>sample cue + guides]
    cli --> transcriber[transcriber.py]
    transcriber --> whisper[WhisperX + PyTorch]
    whisper --> cues[Timed subtitle cues]
    cues --> json[JSON]
    cues --> srt[SRT]
    cues --> effects[Word-timed effects]
    effects --> json
    effects --> asswriter
    cues --> asswriter[ass.py]
    asswriter --> ass[ASS]
    preview --> asswriter
    config --> asswriter
    probe --> asswriter
    cli --> subtitler[subtitler.py]
    preview --> subtitler
    input --> subtitler
    ass --> subtitler
    probe --> subtitler
    subtitler --> ffmpeg[FFmpeg subtitles filter]
    ffmpeg --> video[Rendered video]
    ffmpeg --> png[One preview PNG]
    utils[utils.py] --> transcriber
    utils --> subtitler
    errors[errors.py] --> cli
    models[models.py] --> cli
~~~

## Components

| Component | Responsibility | Main interfaces |
| --- | --- | --- |
| multisubs/cli.py | Defines the console interface, validates direct user errors, chooses output layout, invokes the pipeline, and cleans up transient files. | main() |
| multisubs/transcriber.py | Loads WhisperX, transcribes audio, aligns words, builds readable display cues, prepares optional word-timed effects, and coordinates JSON/SRT/ASS artifact writing. | transcribe_video(), write_transcription_artifacts(), generate_transcriptions() |
| multisubs/preview.py | Resolves a sample cue without transcription, applies adaptive wrapping, and generates optional native or explicit ASS guide events. | build_preview_ass(), resolve_preview_timestamp() |
| multisubs/ass.py | Compiles semantic appearance into private ASS fields and serializes headers, timestamps, placement overrides, optional karaoke color/timing overrides, and safely escaped dialogue text. | write_ass(), rgba_to_ass_color(), allocate_karaoke_durations(), allocate_active_word_intervals() |
| multisubs/subtitler.py | Probes normalized video geometry and invokes FFmpeg to burn ASS into the selected video stream or render one preview PNG. | probe_video_geometry(), embed_subtitles(), render_subtitle_preview() |
| multisubs/config.py | Defines supported choices, semantic appearance/effect defaults, immutable layout preset sources, and validates typed subtitle configuration. | SUPPORTED_LANGUAGES, MODELS, LAYOUT_PRESETS, validate_subtitle_config() |
| multisubs/layout.py | Classifies autorotated geometry, merges preset and explicit layout fields, resolves unit-bearing lengths, derives wrapping dimensions, and validates native regions or explicit subtitle envelopes on the probed canvas. | classify_layout_preset(), resolve_relative_length(), resolve_subtitle_config(), resolve_native_layout_region(), resolve_wrapping_metrics(), resolve_cue_placement() |
| multisubs/text_measurement.py | Resolves the nearest custom or fontconfig family/weight face, measures glyph advances and ascent/descent metrics with Pillow/RAQM, caches per-run values, and owns the Unicode-aware fallback. | build_text_measurer(), TextMeasurer, TextMeasurementInfo |
| multisubs/wrapping.py | Shares font-aware, bounded adaptive wrapping between transcription and preview without importing the model runtime, and partitions mapped display fragments into visual lines. | wrap_subtitle_text(), line_count(), build_visual_lines() |
| multisubs/utils.py | Produces non-conflicting file and directory paths. | get_unique_path(), get_unique_dir_path() |
| multisubs/errors.py | Defines user-actionable validation, dependency, artifact, transcription, and rendering errors. | MultisubsError subclasses |
| multisubs/models.py | Defines typed request, unit-bearing subtitle configuration, global opacity, semantic backdrop/layout/effect choices, karaoke modes, immutable display fragments, visual lines and karaoke cues, immutable layout preset values, video geometry, per-cue placement, generated guide events, semantic transcript, and artifact value objects. | RelativeLength, SubtitleOpacity, SubtitleEffects, KaraokeMode, SubtitleDisplayFragment, SubtitleVisualLine, KaraokeCue, AssDrawingEvent, CuePlacement, LayoutPreset, RunRequest, PreviewRequest, SubtitleBackdrop, SubtitleConfig, SubtitleLayoutPreset, VideoGeometry, TranscriptDocument, RunArtifacts, TranscriptionPaths |
| multisubs/__init__.py | Exposes the package version and lazily loads the primary package functions. | __version__ |

## Execution flow

1. The console script declared in pyproject.toml calls cli.main().
2. The CLI parses options and, for the normal transcription path, verifies that the selected source language has a default WhisperX alignment model. Both paths verify that the input exists, the output path is not an existing file, semantic colors, appearance values, and effect options are valid, every unit value has an explicit suffix (except the `auto` line-height keyword), global opacity is an explicit finite percentage from 0 through 100, the layout preset is supported, and any named position or custom anchor is one of the nine supported screen anchors. Unit-bearing options are stored as RelativeLength values and opacity as SubtitleOpacity; raw ASS style mappings and `--style-*` options are not accepted. Custom X/Y coordinates must be supplied as a pair, cannot be combined with `--position`, and require explicit anchor, maximum width, and maximum height values. Karaoke is rejected for translation and preview before probing or model loading.
3. When `--preview-layout` is present, the CLI rejects only misleading conflicts, skips translation/model validation, validates FFmpeg and ffprobe, probes geometry and duration, resolves the layout, and creates a temporary ASS sample. It then calls `render_subtitle_preview()` for exactly one PNG and exits without importing transcriber.py, WhisperX, or PyTorch. Preview temporary files are removed on both success and failure.
4. For a normal translation task, the CLI rejects turbo and English-only model names before model loading.
5. The CLI validates the FFmpeg and ffprobe executables and FFmpeg's subtitles filter. probe_video_geometry() then selects the lowest-index usable video stream and validates coded dimensions, rotation, sample aspect ratio, displayed aspect ratio, and container duration before a work directory or model is loaded. resolve_subtitle_config() classifies `--layout auto` from the autorotated render aspect ratio, merges the selected immutable preset with explicit field overrides, resolves all dimensions, resolves `--line-height` against measured natural font metrics, and rejects explicit leading below that metric. Native placement resolves maximum width after horizontal ASS margins and maximum height after the active top or bottom margin; middle alignment uses the full height. Explicit placement resolves X/Y and both maximum dimensions against the full PlayRes canvas, ignores margins, and rejects a complete envelope that crosses an edge. resolve_wrapping_metrics() also validates that at least one decorated line fits before WhisperX is loaded.
6. The geometry policy follows explicitly enabled FFmpeg autorotation: 0° and 180° retain the coded axes; 90° and 270° swap the render axes and invert the sample-aspect-ratio axes. Legacy rotate tags are normalized from their sign convention to the display-matrix convention. Contradictory metadata is rejected.
7. The normal transcription path reports the resolved dimensions, semantic position, and concrete layout preset, then creates a private temporary work directory inside the output directory.
8. transcribe_video() selects CUDA with float16 when available, otherwise CPU with int8; WhisperX is imported only at the transcription boundary.
9. WhisperX loads the requested model with the Silero VAD method, extracts audio from the input, transcribes it, and aligns the result at word level. During Silero setup, the transcriber isolates WhisperX's unused optional Pyannote ONNX import so ONNX Runtime does not probe an incomplete Linux DRM sysfs tree. Model, VAD, and alignment asset loads retry transient connection failures up to three attempts with a short exponential backoff; deterministic loading errors are surfaced immediately.
10. The cue builder combines consecutive aligned segments, prefers sentence endings, clauses, and meaningful pauses, and applies the duration ceiling as a fallback. The resolved layout then creates display cues using maximum width, maximum height, natural first-line metrics, configured baseline line height, letter spacing, and backdrop/shadow allowances. The text-measurement boundary normalizes named, aliased, or numeric font weights to an OpenType rank, first searches the validated custom font directory, then queries fontconfig with the corresponding weight/slant where available, measures the nearest resolved face with Pillow/RAQM, and otherwise uses its explicit Unicode estimate. Both measurement modes add spacing between rendered grapheme clusters through one shared layer, resetting at explicit line breaks. Complete cues that fit remain unbroken; required multi-line layouts use bounded global partition scoring rather than greedy first-line filling. wrapping.py supplies the same algorithm to preview mode, where only the first fitting lexical group is rendered when the sample would require later timed cues. Explicit line-height percentages use the natural measured line height as their basis and explicit values below that natural metric are rejected after font resolution.
11. When karaoke is enabled, each display cue preserves a lossless sequence of `SubtitleDisplayFragment` values: timed fragments point to original aligned words, while separators and intentional line breaks remain untimed. `prepare_karaoke_cues()` validates the mapping and word boundaries, quantizes cue/word starts, word ends, and cue ends to ASS centiseconds, then prepares both progressive durations and non-overlapping active-word intervals. Progressive intervals end at the next start; active-word intervals end at the earlier of the aligned word end or next start. It records per-cue fallback instead of inventing timestamps and prepares the same immutable outcome before JSON, SRT, and ASS serialization.
12. write_transcription_artifacts() validates external timestamps and writes UTF-8 JSON and SRT files atomically. It delegates preset merging, unit resolution, placement validation, and wrapping metrics to layout.py, then delegates ASS serialization to ass.py. The ASS compiler resolves one base/effective palette by multiplying each conventional RGBA alpha by global opacity with Decimal half-up rounding, then converts the result to ASS BGR/inverted-alpha values and emits the canonical 100-900 OpenType rank through a trusted event-level override. Native placement compiles semantic alignment and actual margins into the style without event positioning; explicit placement uses neutral style margins and generated per-cue `\\an`/`\\pos` tags. With explicit line height, wrapped lines become a typed visual-line model and receive synchronized per-line `\\an`/`\\pos` events around one stable anchor; a box backdrop is one lower-layer vector event for the full measured block. Progressive karaoke adds one trusted color setup and one `\\k` duration for each displayed timed word, partitioned by visual line in this path. Active-word karaoke emits interval events on every visible line. Each transcript fragment is escaped separately. Preview uses this same compiler and palette. JSON preserves JSON-compatible aligned-word metadata plus the placement mode, applicable margins, requested and resolved dimensions, requested/resolved letter spacing and line-height diagnostics, wrapping metrics, render strategy, native region or explicit PlayRes coordinates, base/effective opacity palette, and additive karaoke metadata.
13. embed_subtitles() selects the same probed stream, explicitly enables autorotation, supplies the normalized canvas as original_size to the structured FFmpeg subtitles filter, and supplies fontsdir only when a validated custom fonts directory was requested. Available audio streams are copied into a temporary rendered output when present. render_subtitle_preview() uses the same subtitles filter options, seeks to the validated timestamp, requests one PNG frame, captures bounded diagnostics, and publishes it with get_unique_path().
14. After normal rendering succeeds, the CLI publishes a collision-safe set of final artifacts and removes the private work directory. Failed normal runs retain transcription artifacts in that directory for diagnosis; preview runs remove their temporary ASS directory, while the renderer removes partial media in either mode.

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
  backdrop/shadow allowance. The first line uses the natural ascent-plus-descent
  metric and each additional line consumes the resolved baseline advance:
  `natural_line_height + (line_count - 1) * resolved_line_height`. Presets retain
  a calibrated two-line default, but there is no fixed max-lines input.
- It measures a concrete face with Pillow when `--fonts-dir` or fontconfig can
  resolve the nearest family, weight, and italic style that libass will use.
  RAQM applies direction and language shaping when available. Otherwise it
  reports and records a Unicode-category estimate with calibrated
  proportional-width factors.
- It keeps a complete cue on one line whenever its measured width fits. A
  required multi-line break searches no more partitions than both the derived
  line capacity and the number of text units, then scores semantic class,
  overflow, avoidable orphan lines, raggedness, and deterministic source order.
- It prefers a new timed cue over exceeding the derived visual line capacity
  when aligned word boundaries are available. Semantic sentence, clause, and
  pause priorities remain higher than line balancing.
- It emits intentional visual line breaks to SRT and ASS. A coarse segment
  without word timestamps is wrapped lexically without inventing new timings.
- With explicit `--line-height`, the wrapped display fragments are partitioned
  into immutable visual lines. ASS receives one synchronized event per line,
  positioned around the native margin anchor or explicit PlayRes coordinate;
  `backdrop=box` receives one lower-layer vector drawing for the measured block.
  `auto` keeps the historical single dialogue event and native style box.
- Preview models one frame of that sequence: it keeps only the first lexical
  group that fits the resolved width and line capacity, omits the groups that
  would appear in later cues, and prevents libass from wrapping that first
  group again. Its guide and retained JSON report `positioned-lines` only when
  the final display text actually contains multiple visual lines.
- A long indivisible token remains intact and may overflow the approximate width
  budget; transcript content is never removed or mutated.
- If word timestamps are unavailable for a WhisperX segment, it flushes pending aligned words and uses that segment's coarse start and end times as a safe fallback.
- Karaoke never retokenizes the final display string. If a display cue cannot be mapped to every original word in order, it remains a plain cue and contributes to one aggregate fallback warning.

Semantic cue rules reside in multisubs/transcriber.py and shared visual wrapping
rules reside in multisubs/wrapping.py; both should be changed with focused tests.

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
      "render_strategy": "single-event",
      "margins": {
        "applied": true,
        "left": 86,
        "right": 86,
        "top": 0,
        "bottom": 154
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
          "bottom": "0px"
        },
        "max_width": null,
        "max_height": null
      },
      "resolved": {
        "font_size": 43,
        "letter_spacing": 0,
        "line_height": 43.0,
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
        "natural_line_height": 43.0,
        "resolved_line_height": 43.0,
        "ascent": 35.0,
        "descent": 8.0,
        "vertical_decoration": 2,
        "line_capacity": 2,
        "font_size": 43,
        "letter_spacing": 0,
        "backdrop_size": 0,
        "shadow_size": 2
      },
      "percentage_bases": {
        "letter_spacing": "resolved-font-size",
        "line_height": "natural-line-height",
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
        "metric_size": 36,
        "requested_weight_name": "regular",
        "requested_weight": 400,
        "requested_weight_input": "regular",
        "requested_weight_input_form": "default",
        "resolved_weight_name": "regular",
        "resolved_weight": 400,
        "weight_substituted": false
      },
      "opacity": {
        "requested": "100%",
        "percentage": 100,
        "normalized": 1,
        "base_colors": {
          "text": "#FFFFFFFF",
          "backdrop": "#00000099",
          "shadow": "#00000099",
          "karaoke_highlight": null
        },
        "effective_colors": {
          "text": "#FFFFFFFF",
          "backdrop": "#00000099",
          "shadow": "#00000099",
          "karaoke_highlight": null
        }
      },
      "effects": {
        "karaoke": {
          "enabled": false,
          "mode": null,
          "normal_color": "#FFFFFF",
          "highlight_color": null,
          "fallback_cues": 0
        }
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

`schema_version` identifies the top-level JSON contract. The words array preserves the usable JSON-compatible aligned-word records supplied by WhisperX; its exact optional fields are owned by that dependency. `created_at` is a timezone-aware UTC ISO-8601 timestamp. The rendering object records normalized geometry, requested and resolved presets, placement mode, whether margins apply, requested/resolved font size, letter spacing, and line height, maximum dimensions, percentage bases, the render strategy, and the reproducibility inputs used by adaptive wrapping. The `wrapping` object records available and maximum dimensions, effective width budget after decorations and measured tracking, natural and resolved line heights, ascent/descent metrics, vertical decoration allowance, derived line capacity, and resolved typography values. `text_measurement` records `font-metrics` or `unicode-estimate`, requested and resolved family/style names, the original weight token and input form, canonical requested and inferred resolved weight names/ranks, substitution state, font source, and shaping mode. Letter spacing is measured as one gap between consecutive rendered grapheme clusters on each visual line; combining marks and zero-width joiner sequences remain attached to their base cluster. Explicit line-height percentages use the natural measured line height as their basis, while pixels are PlayRes baseline advances; `auto` preserves that natural metric. The `opacity` object records the requested token, percentage and normalized multiplier, and canonical eight-digit conventional RGBA colors before and after composition. `effects.karaoke` records whether word highlighting is enabled, the resolved `progressive` or `active-word` mode, normal/highlight semantic colors, and the exact number of plain fallback cues. Unresolved values are null, font-family and font-weight substitutions remain visible, and absolute local font paths are never serialized. Native mode adds `native_region` and deliberately omits synthetic coordinates. Explicit mode omits `native_region` and adds requested and resolved X/Y values with `coordinate_space: playres`. The metadata does not claim exact equivalence with final libass shaping or store generated ASS strings or raw command lines. `container_duration` is null when ffprobe cannot report it.

### SRT and ASS

SRT is generated from cue start time, end time, and layout-aware wrapped text.
ASS contains a Default style compiled from semantic `SubtitleConfig` values.
The appearance contract includes the resolved font size, non-negative letter
spacing, resolved baseline line height, and global opacity in addition to font
family, weight, colors, backdrop, and shadow.
Raw ASS style mappings are rejected. The public `--layout` value is stored on
SubtitleConfig and resolved to a concrete preset in layout.py. Explicit fields
override only their matching preset fields in native mode.

SRT is always plain display text and timing; it never contains generated ASS
override markup. Karaoke preparation does not alter SRT or JSON text. JSON keeps
the original aligned-word records and adds the resolved `effects.karaoke`
metadata object without storing compiled tags.

RelativeLength margins use render width or height, font size uses the shorter
render edge, and letter spacing, line-height percentages, and decoration sizes
use the resolved font size or natural line metric documented below.
Native percentage
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

ass.py first canonicalizes `#RRGGBB[AA]` colors and resolves one effective
palette. For every component it computes
`round_half_up(base_alpha * opacity / 100)` in conventional alpha space exactly
once, then converts the effective color to ASS BGR/inverted-alpha notation.
Ordinary text, karaoke normal/highlight overrides, outline or box, shadow,
explicit line-height vector boxes, retained ASS, preview, and final video all
consume this palette without altering geometry. It also converts backdrop
kinds, canonical 100-900 font weights, boolean italic treatment, and semantic
positions into the required private ASS fields and trusted event overrides. The
base ASS Bold style field
remains neutral because older libass style parsers coerce every positive value
to boolean bold. Each subtitle event instead receives an exact `\\b100` through
`\\b900` override, which keeps preview, ordinary cues, and both karaoke modes on
the same OpenType rank across supported libass versions. The `box` backdrop
uses libass `BorderStyle=4`, which draws one background box for the complete
cue. The required ASS `SecondaryColour` field follows the semantic text color
for ordinary cues; enabled karaoke events override the inactive and active
colors explicitly. `OutlineColour` and
`BackColour` both follow the one semantic backdrop color. Underline and
strikeout remain disabled; scale stays at 100%, angle stays at zero, and the
resolved semantic letter spacing is written to ASS `Spacing`. `auto` line height
does not add generated tags. An explicit line height on a multi-line ordinary
cue emits one event per visual line with trusted `\\an`/`\\pos` coordinates; the
line positions use the natural first-line box and the requested baseline
advance so the selected anchor remains fixed. Progressive karaoke may use
synchronized interval events per visual line so word activation remains
cue-relative. For `backdrop=box`, the text style is temporarily neutralized and
one lower-layer `\\p1` rectangle uses the full measured block bounds, padding,
configured color, and shadow allowance. Encoding remains
1 because that ASS internal is outside the public appearance model. In
progressive karaoke mode, ass.py emits one Dialogue event per cue in the
automatic path, with trusted highlight/normal color overrides followed by
`\\k` durations around independently escaped display fragments. Explicit line
height partitions those timings into synchronized per-line intervals. Word
starts are quantized to centiseconds with the existing ASS rounding rule;
durations conserve the full quantized cue duration and do not use word ends as
activation times. In
active-word mode, the writer partitions the cue into adjacent, non-overlapping
Dialogue events that all retain the complete cue text and placement. An active
interval recolors exactly one word, while gaps render the complete cue in the
normal color. A word end that overlaps the next start is capped at that start,
and a zero-length active interval emits no highlight event. Plain fallback cues
use the same style, placement, timing, and text as the non-karaoke path. ass.py
converts line breaks to ASS's \N syntax in dialogue events and escapes
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
| --preview-layout | output/video-subtitle-preview.png | No JSON, SRT, ASS, rendered video, or transcription directory is published; the temporary ASS is removed. |

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
`--fonts-dir` and matches their internal family/style metadata. Common face
names are mapped to canonical OpenType ranks, and candidates are ordered by
absolute weight distance, requested italic state, then stable path/index order.
On hosts with fontconfig, `fc-match` is invoked with a bounded argument-vector
subprocess using the corresponding fontconfig weight and slant; the returned
file's actual metadata is still validated instead of assuming an exact match.
Other providers are not guessed. Font objects and up to 4096 repeated text
measurements are cached in memory for one artifact-writing run; transcript
strings are not persisted by the cache.
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
