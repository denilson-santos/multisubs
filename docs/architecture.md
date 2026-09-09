# Architecture

## Overview

multisubs is a small Python package with one CLI entry point. It orchestrates two external capabilities:

- WhisperX and PyTorch for transcription and word-level timing alignment.
- FFmpeg and ffprobe for normalized media geometry and ASS subtitle rendering.
- A transcription-free preview path that reuses the same ASS and FFmpeg
  subtitle filter without importing WhisperX or PyTorch. It supports both a
  static PNG layout frame and a silent frozen-background MP4 whose word times
  are explicitly simulated.

~~~mermaid
flowchart LR
    user[User command] --> cli[cli.py]
    input[Input video] --> cli
    input --> probe[ffprobe geometry]
    probe --> cli
    config[config.py<br/>typed subtitle config] --> cli
    templates[templates.py + packaged JSON<br/>validated baselines] --> cli
    custom[custom_templates.py<br/>local JSON directory] --> cli
    cli --> preview[preview.py<br/>sample cue + guides]
    cli --> transcriber[transcriber.py]
    transcriber --> whisper[WhisperX + PyTorch]
    whisper --> cues[Timed subtitle cues]
    cues --> json[JSON]
    cues --> srt[SRT]
    cues --> animations[animation.py<br/>cue- and word-relative state]
    animations --> json
    animations --> asswriter
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
    ffmpeg --> clip[Silent animation preview MP4]
    utils[utils.py] --> transcriber
    utils --> subtitler
    errors[errors.py] --> cli
    models[models.py] --> cli
~~~

## Components

| Component | Responsibility | Main interfaces |
| --- | --- | --- |
| multisubs/cli.py | Defines the console interface, validates direct user errors, chooses output layout, invokes the pipeline, and cleans up transient files. | main() |
| multisubs/transcriber.py | Loads WhisperX, transcribes audio, aligns words, builds readable display cues, prepares optional aligned-word timing, and coordinates JSON/SRT/ASS artifact writing. | transcribe_video(), write_transcription_artifacts(), generate_transcriptions() |
| multisubs/preview.py | Resolves a sample cue without transcription, applies adaptive wrapping, generates deterministic simulated word timing for animated previews, and generates optional native or explicit ASS guide events. | build_preview_ass(), build_animation_preview_ass(), build_simulated_karaoke_cue(), resolve_preview_timestamp() |
| multisubs/animation.py | Normalizes cue and aligned-word phases with configured durations inside quantized bounds and samples relative opacity, movement, and scale state without I/O. | normalize_cue_animation(), normalize_word_animation(), animation_boundaries(), word_animation_boundaries(), sample_cue_animation(), sample_word_animation() |
| multisubs/ass.py | Compiles semantic appearance and cue/word animation into trusted private ASS fields and overrides around safely escaped dialogue text. | write_ass(), rgba_to_ass_color(), allocate_karaoke_durations(), allocate_active_word_intervals() |
| multisubs/subtitler.py | Probes normalized video geometry and invokes FFmpeg to burn ASS into the selected video stream, render one preview PNG, or encode a silent frozen-background animation preview. | probe_video_geometry(), embed_subtitles(), render_subtitle_preview(), render_subtitle_animation_preview() |
| multisubs/config.py | Defines supported choices and semantic defaults, composes CLI overrides, and validates the typed style/layout/animation configuration. | SUPPORTED_LANGUAGES, MODELS, validate_subtitle_config() |
| multisubs/templates.py | Strictly loads the deterministic packaged JSON index and sparse built-in style/layout/animation definitions, expands them from semantic defaults, and compiles complete baselines through the normal validator. | SubtitleTemplate, SUBTITLE_TEMPLATES, get_subtitle_template() |
| multisubs/custom_templates.py | Reads the bounded public schema-1 template directory, validates every discovered file, resolves custom names with built-in-only inheritance, and returns immutable source metadata for one request. | load_custom_template_directory(), resolve_subtitle_template(), ResolvedSubtitleTemplate |
| multisubs/layout.py | Resolves unit-bearing layout fields, derives wrapping dimensions, validates native or explicit envelopes, and positions measured visual-line fragments on the probed canvas. | resolve_relative_length(), resolve_subtitle_config(), resolve_native_layout_region(), resolve_wrapping_metrics(), resolve_cue_placement(), position_visual_lines() |
| multisubs/font_catalog.py | Loads the immutable bundled-font manifest, performs bounded family lookup, exposes unpacked package resources, and materializes only a selected family when required by the importer. | load_bundled_font_catalog(), bundled_font_directory(), verify_bundled_font_assets() |
| multisubs/text_measurement.py | Resolves the nearest custom, bundled, or fontconfig family/weight face, measures glyph advances and ascent/descent metrics with Pillow/RAQM, caches per-run values, and owns the Unicode-aware fallback. | build_text_measurer(), TextMeasurer, TextMeasurementInfo |
| multisubs/wrapping.py | Applies typed Unicode display casing, shares font-aware bounded adaptive wrapping between transcription and preview without importing the model runtime, and partitions mapped display fragments into visual lines. | transform_display_text(), wrap_subtitle_text(), line_count(), build_visual_lines() |
| multisubs/utils.py | Produces non-conflicting file and directory paths. | get_unique_path(), get_unique_dir_path() |
| multisubs/errors.py | Defines user-actionable validation, template-catalog, dependency, artifact, transcription, and rendering errors. | MultisubsError subclasses |
| multisubs/models.py | Defines typed request, preview mode, style/layout/animation configuration, typography, cue and word backdrops, shadow, global opacity, display casing, timed-word modes, immutable display fragments, visual lines and timed cues, video geometry, placement, guide, transcript, and artifact value objects. | RelativeLength, PreviewMode, SubtitleStyle, SubtitleTypography, SubtitleBackdropStyle, SubtitleWordBackdropStyle, SubtitleShadow, SubtitleLayout, SubtitleAnimation, SubtitleConfig, RunRequest, PreviewRequest, TranscriptDocument, RunArtifacts |
| multisubs/__init__.py | Exposes the package version and lazily loads the primary package functions. | __version__ |

## Execution flow

1. The console script declared in pyproject.toml calls cli.main().
2. The CLI parses options and, for the normal transcription path, verifies that the selected source language has a default WhisperX alignment model. Both paths load and validate an optional local template directory before resolving the omitted name to `default`; a custom name takes precedence over a built-in name, while custom bases resolve only through the packaged catalog. The selected complete immutable semantic baseline is then overlaid with only explicitly supplied style, layout, four independent animation-track phases, durations, word modes, and highlight color, and the final typed configuration is validated once. Template fields are defaults rather than explicit option presence. An explicit CLI duration overrides the selected template duration, which overrides the effect default; `none` and `highlight` are durationless. Both paths validate paths, semantic colors and options, explicit units, opacity, text case, and placement before probing. The normal transcription path validates the 10–5000 ms animation-phase range and rejects active word behavior for translation; preview modes skip speech-specific translation restrictions because they never load speech alignment.
3. When `--preview-layout` is present, the CLI validates FFmpeg and ffprobe, probes geometry and duration, resolves the layout, and creates a temporary ASS sample. preview.py suppresses every motion phase at its stable state. It maps displayed words into typed fragments so ass.py can show the first half for each progressive word track, rounding up, and the first word for each active-word track, independently for text and decoration and without timing tags. It then renders exactly one PNG and exits without importing transcriber.py, WhisperX, or PyTorch. When `--preview-animation` is present, the CLI additionally requires `libx264`, selects the same first fitting transformed display cue, builds a typed deterministic simulation in ASS centiseconds, and gives sentence/clause/default gaps capped at 20% of the cue before weighted largest-remainder allocation. The cue occupies [500ms, 500ms + duration), while a single uncaptioned frame captured at `--preview-at` is repeated at 30 fps as the background; the timestamp does not drive the animation clock. The MP4 is silent, lasts one second longer than the requested cue duration, uses `yuv420p` for even geometry or `yuv444p` for odd geometry, and reuses the production ASS compiler with motion enabled. Both preview modes avoid transcription imports, publish no subtitle artifacts, and remove temporary ASS/frame/partial-media files on success or failure. Animated guides identify the word timing as simulated.
4. For a normal translation task, the CLI rejects turbo and English-only model names before model loading.
5. The CLI validates the FFmpeg and ffprobe executables and FFmpeg's subtitles filter. probe_video_geometry() then selects the lowest-index usable video stream and validates coded dimensions, rotation, sample aspect ratio, displayed aspect ratio, and container duration before a work directory or model is loaded. resolve_subtitle_config() resolves the complete requested configuration without classifying the video shape, resolves all dimensions, resolves `--line-height` against measured natural font metrics, and rejects explicit leading below that metric. Native placement resolves maximum width after horizontal ASS margins and maximum height after the active top or bottom margin; middle alignment uses the full height. Explicit placement resolves X/Y and both user-supplied maximum dimensions against the full PlayRes canvas, compiles retained native defaults to zero, and rejects a complete envelope that crosses an edge. resolve_wrapping_metrics() also validates that at least one decorated line fits before WhisperX is loaded.
6. The geometry policy follows explicitly enabled FFmpeg autorotation: 0° and 180° retain the coded axes; 90° and 270° swap the render axes and invert the sample-aspect-ratio axes. Legacy rotate tags are normalized from their sign convention to the display-matrix convention. Contradictory metadata is rejected.
7. The normal transcription path reports the resolved dimensions and semantic position or explicit envelope, then creates a private temporary work directory inside the output directory.
8. transcribe_video() selects CUDA with float16 when available, otherwise CPU with int8; WhisperX is imported only at the transcription boundary.
9. WhisperX loads the requested model with the Silero VAD method, extracts audio from the input, transcribes it, and aligns the result at word level. During Silero setup, the transcriber isolates WhisperX's unused optional Pyannote ONNX import so ONNX Runtime does not probe an incomplete Linux DRM sysfs tree. Model, VAD, and alignment asset loads retry transient connection failures up to three attempts with a short exponential backoff; deterministic loading errors are surfaced immediately.
10. The cue builder combines consecutive aligned segments, prefers sentence endings, clauses, and meaningful pauses, and applies the duration ceiling as a fallback. It preserves source cue/word records, applies the selected locale-independent Unicode casing to separate display words, and retains their source indexes before measurement. The resolved layout then creates display cues using maximum width, maximum height, natural first-line metrics, configured baseline line height, letter spacing, and backdrop/shadow allowances. The text-measurement boundary normalizes named, aliased, or numeric font weights to an OpenType rank, first searches the validated custom font directory, then the selected bundled family, and finally fontconfig with the corresponding weight/slant where available. It measures the nearest resolved face with Pillow/RAQM and otherwise uses its explicit Unicode estimate. Both measurement modes add spacing between rendered grapheme clusters through one shared layer, resetting at explicit line breaks. Complete cues that fit remain unbroken; required multi-line layouts use bounded global partition scoring rather than greedy first-line filling. Length-changing casing can therefore change a line or timed-cue boundary without changing source timestamps. wrapping.py supplies the same case transform and layout algorithm to preview mode, where only the first fitting lexical group is rendered when the sample would require later timed cues. Explicit line-height percentages use the natural measured line height as their basis and explicit values below that natural metric are rejected after font resolution.
11. When active word behavior requires alignment, each display cue preserves a lossless sequence of `SubtitleDisplayFragment` values: transformed timed fragments retain indexes into the original aligned words, while separators and intentional line breaks remain untimed. The timing preparation validates identity and word boundaries without retokenizing transformed strings, quantizes cue/word bounds to ASS centiseconds, and prepares progressive and non-overlapping active-word intervals. Progressive intervals persist through the cue; active-word intervals end at the earlier of the aligned word end or next start. It records per-cue fallback instead of inventing timestamps and prepares the same immutable result before JSON, SRT, and ASS serialization.
12. write_transcription_artifacts() validates external timestamps and writes UTF-8 JSON and SRT files atomically. SRT consumes transformed display cues, while JSON keeps original full/cue text and aligned words and adds per-cue `display_text` plus requested/resolved TextCase metadata. It delegates unit resolution, placement validation, and wrapping metrics to layout.py, then delegates ASS serialization to ass.py. The ASS compiler resolves one base/effective palette, native or explicit placement, and exact font-weight overrides. Word fragments use the same measured advances as wrapping and render as independent positioned text layers so local movement, scale, highlighting, outline, or boxes do not reflow surrounding glyphs. Cue backdrop, word decoration, and text occupy layers 0, 1, and 2. A private typed dialogue-event contract retains logical and derived intervals. animation.py fits three phases inside each cue or word interval, repeats emphasis within the stable region, adds bounded phase/cycle boundaries, and samples each of the four tracks from its original timeline. ass.py composes the resulting trusted movement, opacity, and scale tags around separately escaped text. Preview uses the same compiler with motion suppressed. JSON preserves placement, dimensions, wrapping metrics, palette, and resolved four-track animation diagnostics.
13. embed_subtitles() selects the same probed stream, explicitly enables autorotation, supplies the normalized canvas as original_size to the structured FFmpeg subtitles filter, and supplies `fontsdir` when measurement selected a custom or bundled provider directory. The bundled resource context remains alive through preview or final rendering, so Pillow/RAQM and libass consume the same family directory. Available audio streams are copied into a temporary rendered output when present. render_subtitle_preview() uses the same subtitles filter options, seeks to the validated timestamp, requests one PNG frame, captures bounded diagnostics, and publishes it with get_unique_path(). render_subtitle_animation_preview() first extracts an uncaptioned frame, feeds it to a looped 30 fps input, applies the temporary ASS through the same filter options, encodes only video with H.264/faststart and the compatible pixel format, and publishes the complete MP4 collision-safely.
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
  `natural_line_height + (line_count - 1) * resolved_line_height`. The fixed
  `12%` native maximum-height default can derive different capacities from
  different video geometries; there is no fixed max-lines input.
- Wrapping compares measured text content with the already decoration-reduced
  width budget. Backdrop and shadow allowances are counted once while deriving
  that budget and are added only when the final visual envelope is positioned.
- It applies `original`, Unicode `upper()`, or Unicode `lower()` to plain-text
  display words before width measurement. Transformed word fragments retain
  their original ordered word indexes, timestamps, and metadata; locale-specific
  casing is not inferred.
- It measures a concrete face with Pillow when a custom directory, bundled
  family, or fontconfig can resolve the nearest family, weight, and italic
  style that libass will use.
  RAQM applies direction and language shaping when available. Otherwise it
  reports and records a Unicode-category estimate with calibrated
  proportional-width factors.
- It keeps a complete cue on one line whenever its measured width fits. A
  required multi-line break searches no more partitions than both the derived
  line capacity and the number of text units, then scores semantic class,
  overflow, avoidable orphan lines, raggedness, and deterministic source order.
- When a preview or aligned-word split must choose among fitting cue prefixes,
  it stops once the ordered prefix no longer fits, preserves sentence, clause,
  and pause priorities, avoids a one-word tail when possible, and otherwise
  retains the longest fitting prefix. This lets a multi-line envelope consume
  its available visual capacity without changing source timing or word order.
- It prefers a new timed cue over exceeding the derived visual line capacity
  when aligned word boundaries are available. Semantic sentence, clause, and
  pause priorities remain higher than line balancing.
- It emits intentional visual line breaks to SRT and ASS. A coarse segment
  without word timestamps is wrapped lexically without inventing new timings.
- With explicit `--line-height`, the wrapped display fragments are partitioned
  into immutable visual lines. ASS receives one synchronized event per line,
  positioned around the native margin anchor or explicit PlayRes coordinate.
  Every nonempty `backdrop=box` cue follows that measured path, including a
  one-line cue, and receives one lower-layer vector drawing for its complete
  text block. `auto` retains the native single dialogue event only for
  one-line cues without a cue box; a box always uses one shared vector
  rectangle regardless of line count. The block retains the requested semantic
  anchor, while each positioned line uses the corresponding middle-row ASS
  alignment plus one shared offset derived from its visible font bounds. This
  prevents baseline space from appearing as unequal top or bottom box padding.
  A single-line cue is centered horizontally inside the measured surface;
  multi-line cues retain the horizontal alignment selected by their block
  position.
- Preview models one frame of that sequence: it keeps only the first lexical
  group that fits the resolved width and line capacity, selecting the longest
  fitting prefix when semantic and orphan priorities are equivalent. It omits
  the groups that would appear in later cues and prevents libass from wrapping
  that first group again. Its guide and retained JSON report the same
  `positioned-lines` strategy that ASS uses for a nonempty box, positioned word
  behavior, or multiple visual lines.
- A long indivisible display token remains intact and may overflow the
  approximate width budget; original transcript content is never removed or
  replaced by its display transformation.
- If word timestamps are unavailable for a WhisperX segment, it flushes pending aligned words and uses that segment's coarse start and end times as a safe fallback.
- Karaoke never retokenizes the final display string. If a display cue cannot be mapped to every original word in order, it remains a plain cue and contributes to one aggregate fallback warning.

Semantic cue rules reside in multisubs/transcriber.py and shared visual wrapping
rules reside in multisubs/wrapping.py; both should be changed with focused tests.

## Output data

### JSON

The JSON artifact has this high-level shape:

~~~
{
  "schema_version": 3,
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
      "template": {
        "requested": null,
        "resolved": "default"
      },
      "placement_mode": "native-style",
      "requested_position": "bottom-center",
      "resolved_position": "bottom-center",
      "render_strategy": "positioned-lines",
      "margins": {
        "applied": true,
        "left": 194,
        "right": 194,
        "top": 0,
        "bottom": 58
      },
      "requested": {
        "backdrop_type": "box",
        "word_backdrop_type": "none",
        "font_size": "4%",
        "letter_spacing": "0px",
        "line_height": "auto",
        "backdrop_size": "25%",
        "word_backdrop_size": "25%",
        "shadow_size": "0px",
        "margins": {
          "left": "18%",
          "right": "18%",
          "top": "0%",
          "bottom": "3%"
        },
        "max_width": "100%",
        "max_height": "10%"
      },
      "resolved": {
        "backdrop_type": "box",
        "word_backdrop_type": "none",
        "font_size": 77,
        "letter_spacing": 0,
        "line_height": 76.0,
        "backdrop_size": 19,
        "word_backdrop_size": 19,
        "shadow_size": 0,
        "margins": {
          "left": 194,
          "right": 194,
          "top": 0,
          "bottom": 58
        },
        "max_width": 692,
        "max_height": 186,
        "line_capacity": 2
      },
      "wrapping": {
        "available_width": 692,
        "available_height": 1862,
        "max_width": 692,
        "max_height": 186,
        "width_budget": 672,
        "line_height": 76.0,
        "natural_line_height": 76.0,
        "resolved_line_height": 76.0,
        "ascent": 60.0,
        "descent": 16.0,
        "vertical_decoration": 20,
        "line_capacity": 2,
        "font_size": 77,
        "letter_spacing": 0,
        "backdrop_size": 11,
        "shadow_size": 0
      },
      "percentage_bases": {
        "font_size": "render-height",
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
        "font_source": "bundled",
        "shaping": "raqm",
        "metric_size": 64,
        "requested_weight_name": "regular",
        "requested_weight": 400,
        "requested_weight_input": "regular",
        "requested_weight_input_form": "default",
        "resolved_weight_name": "regular",
        "resolved_weight": 400,
        "weight_substituted": false
      },
      "text_case": {
        "requested": "original",
        "resolved": "original"
      },
      "opacity": {
        "requested": "100%",
        "percentage": 100,
        "normalized": 1,
        "base_colors": {
          "text": "#FFFFFFFF",
          "backdrop": "#00000099",
          "word_backdrop": "#111827E6",
          "shadow": "#00000099",
          "word_highlight": null
        },
        "effective_colors": {
          "text": "#FFFFFFFF",
          "backdrop": "#00000099",
          "word_backdrop": "#111827E6",
          "shadow": "#00000099",
          "word_highlight": null
        }
      },
      "animation": {
        "cue": {
          "text": {"active": true, "entrance": {"type": "none"}, "emphasis": {"type": "none"}, "exit": {"type": "none"}},
          "backdrop": {"active": true, "entrance": {"type": "none"}, "emphasis": {"type": "none"}, "exit": {"type": "none"}},
          "shortened_cues": {"text": 0, "backdrop": 0}
        },
        "word": {
          "text": {"active": false, "mode": "active-word", "entrance": {"type": "none"}, "emphasis": {"type": "none"}, "exit": {"type": "none"}},
          "backdrop": {"active": false, "mode": "active-word", "entrance": {"type": "none"}, "emphasis": {"type": "none"}, "exit": {"type": "none"}},
          "normal_color": "#FFFFFF",
          "highlight_color": null,
          "shortened_words": {"text": 0, "backdrop": 0},
          "fallback_cues": 0
        }
      },
      "native_region": {
        "left": 194,
        "top": 0,
        "right": 886,
        "bottom": 1862,
        "width": 692,
        "height": 1862
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
        "display_text": "One or two subtitle lines",
        "words": []
      }
    ]
  }
}
~~~

`schema_version` identifies the top-level JSON contract; version 3 records the concrete requested and resolved layout plus the unified animation contract. The words array preserves the usable JSON-compatible aligned-word records supplied by WhisperX; its exact optional fields are owned by that dependency. Each serialized cue keeps its original normalized semantic text in `text`, retains original aligned words and timestamps, and adds the wrapped/case-transformed `display_text` used by SRT and ASS. The top-level transcription text remains the original WhisperX output. `created_at` is a timezone-aware UTC ISO-8601 timestamp. The rendering object records normalized geometry, placement mode, whether margins apply, requested/resolved appearance and layout values, percentage bases, the render strategy, and the reproducibility inputs used by adaptive wrapping. The `wrapping` and `text_measurement` objects record the geometry and font diagnostics used by layout. `opacity` records canonical base and composed colors, including `word_highlight`. `animation.cue` and `animation.word` each contain independent `text` and `backdrop` tracks; every track records whether it is active plus its resolved entrance, emphasis, and exit, applicable duration, and—for word tracks—timing mode. Shortening is counted per element and the word section records exact plain-fallback cue count and text colors. Type `none` omits duration. Unresolved values are null, font-family and font-weight substitutions remain visible, and absolute local font paths are never serialized. Native mode adds `native_region`; explicit mode instead adds requested/resolved X/Y coordinates with `coordinate_space: playres`. The metadata does not store generated ASS strings or raw command lines. `container_duration` is null when ffprobe cannot report it.

The `template` object records requested and resolved template identity. Omitted
selection is stored as requested `null` and resolved `default`; only names are
serialized, never registry mappings or asset paths. A custom selection adds
`source: "custom"`, `schema_version: 1`, and its resolved built-in
`base`; directory paths, descriptions, and raw custom JSON are excluded.

### SRT and ASS

SRT is generated from cue start time, end time, and layout-aware wrapped text.
ASS contains a Default style compiled from semantic `SubtitleConfig` values.
The `style` branch owns typography, cue backdrop, timed word backdrop, shadow,
and global opacity;
`layout` owns placement and the wrapping envelope; and `animation` owns
independent cue and aligned-word entrance, emphasis, and exit phases. Typography
includes the resolved font size, non-negative letter spacing, resolved baseline
line height, display case, text color, and optional timed-highlight text color.
Raw ASS style mappings are rejected. `SubtitleConfig` stores a complete native
presentation assembled from one built-in or directory-provided template
baseline and explicit field-level overrides, or a complete explicit-coordinate
envelope. The
packaged `default.json` carries only identity metadata; the loader expands it
from config.py's authoritative fixed defaults and covers the result with exact
equivalence tests, so omitted selection and explicit `default` cannot drift
silently. templates.py contains no
hard-coded presentation registry; layout.py resolves the typed result without
template-aware branches or aspect-ratio-dependent selection.

SRT is always transformed plain display text and timing; it never contains
generated ASS override markup. ASS receives the same transformed fragments only
after measurement and wrapping, then escapes each fragment before generated
overrides are assembled. Karaoke preparation does not retokenize display text.
JSON keeps original full/cue text and aligned-word records, adds each cue's
`display_text`, and records TextCase plus resolved cue/word animation metadata
without storing compiled tags.

RelativeLength margins use render width or height, font size uses render height,
and letter spacing, line-height percentages, cue/word backdrop padding, and
shadow sizes use the resolved font size or natural line metric documented below.
Native percentage
`max-width` uses the width after left/right margins. Native percentage
`max-height` uses the height after the active top or bottom margin, while middle
alignment uses the full render height. The public `--position` compiles to the
corresponding ASS style Alignment; actual `MarginL`, `MarginR`, and active
`MarginV` values remain authoritative, and no event `\\pos` is emitted.

Explicit `--position-x` and `--position-y` percentages use the full render axes;
pixels are absolute PlayRes coordinates. Explicit maximum dimensions also use
the full axes, explicitly supplied margins are rejected before probing, retained
native margin defaults compile to zero, and each cue receives the private anchor
plus `\\pos` event override. layout.py rejects an envelope whose maximum
width or height would cross the canvas for the selected anchor; it does not
clamp, move, or shrink it. Percentages use Decimal half-up rounding. All resolved
lengths use PlayRes pixels, and resolved font, backdrop, and shadow values remain
bounded.

ass.py first canonicalizes `#RRGGBB[AA]` colors and resolves one effective
palette. For every component it computes
`round_half_up(base_alpha * opacity / 100)` in conventional alpha space exactly
once, then converts the effective color to ASS BGR/inverted-alpha notation.
Ordinary text, timed normal/highlight overrides, cue outline or box, timed word
boxes, shadow, explicit line-height vector boxes, retained ASS, preview, and
final video all consume this palette without altering geometry. It also converts backdrop
kinds, canonical 100-900 font weights, boolean italic treatment, and semantic
positions into the required private ASS fields and trusted event overrides. The
base ASS Bold style field
remains neutral because older libass style parsers coerce every positive value
to boolean bold. Each subtitle event instead receives an exact `\\b100` through
`\\b900` override, which keeps preview, ordinary cues, and both timed-word modes on
the same OpenType rank across supported libass versions. The semantic `box`
backdrop retains the standard ASS opaque-box `BorderStyle=3` in the Default
style contract; nonempty box cue events use a temporary neutral Positioned
style so libass does not draw a native box behind the measured vector surface.
`outline` uses `BorderStyle=1` with the configured weight, while `none` disables both. The
required ASS `SecondaryColour` field follows the semantic text color
for ordinary cues; timed highlight events override the normal and active
colors explicitly. `OutlineColour` and
`BackColour` both follow the one semantic backdrop color. Underline and
strikeout remain disabled; base style scale stays at 100%, angle stays at zero,
and the resolved semantic letter spacing is written to ASS `Spacing`. `auto`
line height does not add a custom baseline distance. A nonempty box cue or an
explicit line height on a multi-line ordinary cue emits one event per visual
line with trusted `\\an`/`\\pos` coordinates. For a cue or timed-word box,
each line uses a middle-row alignment, a shared visible-bounds vertical offset,
and the requested baseline advance, while the complete block keeps the selected
semantic anchor fixed. Single-line cue boxes center text horizontally within
their measured surface; other positioned lines retain their semantic alignment.
Progressive word text may use
synchronized interval events per visual line so word activation remains
cue-relative. For `backdrop=box`, the text style is temporarily neutralized and
one lower-layer `\\p1` rectangle uses the measured text bounds plus padding.
The outer layout envelope reserves the configured shadow allowance, and the
vector applies that shadow exactly once; it is never duplicated by the text
style. Encoding remains
1 because that ASS internal is outside the public appearance model. Timed word
text is partitioned at validated aligned-word boundaries and uses trusted
normal/highlight color overrides around independently escaped display
fragments. Word starts and ends are quantized with the existing ASS rule.
`progressive` keeps each affected fragment active through the cue;
`active-word` uses the validated end capped at the next start, leaves pauses
normal, and omits zero-length intervals. Word outline and measured box
decorations follow their own mode and animation track. Plain fallback cues use
the same style, placement, timing, and text as the ordinary path.
When aligned-word behavior positions text fragments independently, a cue glyph
outline is partitioned into the same fragments and reuses their exact measured
placements. Mixing a libass-shaped whole-line outline with positioned fragment
text is forbidden because their shaping advances can differ. Because an outline
is bound to the glyph rather than an independent rectangular surface, each
fragmented outline also samples the corresponding cue-text and word-text timing,
movement, and scale. Preview uses that same fragmented topology while
suppressing only its temporal motion.

Four animation tracks—cue text, cue backdrop, word text, and word backdrop—are
calculated independently in animation.py after ASS timestamp quantization.
Entrance and exit take priority and are fitted
proportionally inside short intervals; emphasis uses the remaining interval
without moving the logical start or end. Emphasis repeats within the stable
interval according to its validated duration, and a final partial cycle settles
before exit. Cue slides travel 75% of resolved font size, word slides travel
35%, and fixed pop, zoom, pulse, bounce, float, shake, flash, and breathe paths
settle to the stable state. A private typed dialogue event
retains its logical cue interval, derived event interval, and optional aligned
word interval. ass.py splits only at word, visual-line, and a fixed number of
phase boundaries, then samples cue-global and word-local state from their
original timelines. This keeps movement, scale, opacity, and highlight state
continuous instead of restarting them at derived boundaries. Generated
positioning contains at most one `\\pos` or `\\move` per event; transcript
fragments remain separately escaped. With all twelve phases set to `none`, the
ordinary static event structure is preserved unless a timed word decoration is
enabled by style. Preview suppresses every motion phase and renders the stable
state, selecting the first word for `active-word` and the first half of the cue
for `progressive` independently on both word tracks.

ass.py converts line breaks to ASS's \N syntax in dialogue events and escapes
subtitle-derived braces and backslashes separately from generated override tags
so they cannot become unintended controls. Every generated ASS declares
ScriptType, PlayResX, PlayResY, ScaledBorderAndShadow, and WrapStyle in a stable
order. PlayRes matches the autorotated render dimensions. SRT retains text and
timing only; it cannot represent named or custom positioning.

## Internal template resources

Built-in templates are package data under `multisubs/assets/templates`. One
schema-version-5 `index.json` is the sole ordering authority and names each of
the sixteen resources exactly once. Each indexed UTF-8 JSON file requires
`schema_version`, `name`, and `description`; `style`, `layout`, and `animation`
branches and their recognized nested fields are sparse. Omitted values inherit
the authoritative semantic defaults from `config.py`. Style separates
typography, cue backdrop, word backdrop, shadow, and opacity; layout stores
native position, four margins, and the width/height envelope. Animation stores
cue and word branches, each split into independent text and backdrop tracks;
word tracks also store their mode. A supplied phase object contains a type and,
for motion effects, an optional validated `duration_ms`. Text and highlight
colors belong to typography, while word decoration type, color, and size belong
to `style.word_backdrop`. The catalog contains `default` and fifteen curated
styles for social clips, podcasts, tutorials, and editorial work, including
restrained yellow, green, red, lime, cobalt, coral, cyan, and magenta palettes
plus coordinated cue and word animations. Packaged presets share default placement and margins, with authored font-size
and maximum-height overrides. Font calibration compares the average visible
height of `H` and `x` in each bundled weight/slant against Roboto Regular at
`4%`, using the Pillow boundary's libass-compatible sizing at a nominal 1000px
for stable ratios. This is a starting point for optical review of rendered
captions with each preset's actual casing, weight, outline, and highlighting.
The broad uppercase Montserrat ExtraBold presets use 4.8% (`bold-headline`)
and 4.9% (`yellow-pop`, compensating for its thinner outline). Uppercase
Roboto Bold (`neon-magenta-pulse`) uses
3.8% to temper their visual size against the mixed-case default. Condensed
Oswald presets retain their measured size. Authored percentages may therefore
be smaller than the default; equal values are omitted. Calibration approximates
perceived size, not equal glyph width, weight, or identical wrapping. Animation
scale remains an intentional temporary change to the calibrated resting size.

Maximum heights are rounded to tenths of a percent from 2.3 natural line heights
plus cue decoration allowance, measured at a 1000px render height with the
native 3% bottom margin. The extra 0.3 line provides rounding headroom above two
lines while remaining below three. The default retains its central 12% value.
All presets keep automatic line height. Calibration is checked at 720p, 1080p,
portrait 1080x1920, square 1080x1080, and 4K; it is not a fixed line-count contract
for arbitrary geometry, custom fonts, or explicit overrides.

The loader uses `importlib.resources`, rejects malformed UTF-8/JSON, duplicate
or unknown fields, unsupported schema versions, unsafe or duplicate filenames,
index/directory drift, name/file mismatches, invalid types, and semantically
invalid values. It retains a strict schema-4 reader for complete historical
fixtures while shipping only schema-5 sparse resources. It performs no writes,
network access, rendering, font loading, or model loading. Valid resources
normalize through `validate_subtitle_config()` into immutable complete runtime
objects and may then be cached for the process. A damaged packaged catalog
produces a concise `TemplateError` before probing or model loading; it never
falls back to a different template.

This template schema is private implementation data. It is not copied into
retained transcription JSON and is not a user template or discovery interface.
Retained transcription JSON uses its independent public schema version 3 and
records the resolved behavior under `metadata.rendering.animation`.

User templates use an independent public schema version 1 and are read by
custom_templates.py from one flat `--template-dir` for the current request.
The reader validates every immediate JSON file, applies bounded size/count/
depth limits, and resolves `base` only against the packaged built-in catalog.
It never modifies the package registry, follows JSON symlink entries, reads
recursively, or stores custom paths in retained artifacts.

## Output layouts

For video.mp4, language pt, and an output directory named output:

| Mode | Rendered video | Subtitle artifacts |
| --- | --- | --- |
| Default | output/video-pt.mp4 | None is published; temporary JSON, SRT, and ASS files are removed after a successful render. |
| --keep-transcriptions | output/video/video-pt.mp4 | output/video/subtitles/video-pt.json, video-pt.srt, and video-pt.ass |
| --preview-layout | output/video-subtitle-preview.png | No JSON, SRT, ASS, rendered video, or transcription directory is published; the temporary ASS is removed. |
| --preview-animation | output/video-subtitle-animation-preview.mp4 | No JSON, SRT, ASS, audio, rendered transcription video, or transcription directory is published; the temporary ASS and frozen frame are removed. |

get_unique_path() and get_unique_dir_path() append (1), (2), and so on when a target already exists. Retained JSON/SRT/ASS/video outputs reserve one shared stem so a collision cannot split a run across different suffixes; the default mode reserves only the published video name.

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
reads the selected SFNT face's OS/2 Windows ascent/descent and units-per-em to
derive the equivalent pixel size. It falls back to Pillow's ascent plus descent
when those tables are unavailable and records the resulting `metric_size`. The
package uses the MIT-CMU license, is
actively maintained, supports the project's Python 3.10-3.13 range, and
publishes platform wheels. Typical wheels add several megabytes to an
environment, but Pillow is already present transitively in common WhisperX
installations; declaring it directly makes the relied-upon API explicit.

The package contains 82 unmodified static TTF faces served by the official
Google Fonts API for Roboto, Inter, Montserrat, Oswald, Lora, and Atkinson
Hyperlegible Next under `multisubs/assets/fonts`. These static instances cover
every 100-step weight selectable by the CLI within each family's published
weight range, with upright and italic files where supported. Width and optical
size remain at the API defaults because those axes are not public CLI inputs.
One directory per family contains the `OFL.txt` from the same pinned Google
Fonts catalog revision; `manifest.json` records that revision, the family
stylesheet, and every face's exact versioned Google Fonts source URL, internal
family, style, weight, italic state, byte size, and SHA-256. Setuptools includes
the manifest, licenses, and binaries in both wheel and sdist. Integrity is
audited by tests and release preparation, not on every normal invocation.

`font_catalog.py` uses `importlib.resources` and performs bounded,
case-insensitive family lookup without Pillow, FFmpeg, or network access.
Unpacked wheels expose the selected family directory directly. For a non-file
resource importer, only that family is copied into an invocation-scoped
temporary directory which remains alive through measurement and rendering.

Custom font resolution inspects only supported files directly inside
`--fonts-dir` and matches their internal family/style metadata. A matching
custom face takes precedence over a bundled face; bundled faces precede
fontconfig. Common face names are mapped to canonical OpenType ranks, and
candidates are ordered by absolute weight distance, requested italic state,
then stable path/index order within the selected provider. On hosts with
fontconfig, `fc-match` is invoked with a bounded argument-vector subprocess
using the corresponding fontconfig weight and slant; the returned file's actual
metadata is still validated instead of assuming an exact match. Other providers
are not guessed. The resolved provider kind is serialized, while its package,
custom, system, or temporary path remains private. Font objects and up to 4096
repeated text measurements are cached in memory for one artifact-writing run;
transcript strings are not persisted by the cache.
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
