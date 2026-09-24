# Architecture

## Overview

multisubs is a small Python package with one CLI entry point. It orchestrates
two external capabilities:

- A lazy local-ASR adapter layer for WhisperX, Faster-Whisper, NVIDIA Parakeet,
  and Qwen3-ASR. WhisperX is the default.
- FFmpeg and ffprobe for normalized media geometry and ASS subtitle rendering.
- A transcription-free preview path that reuses the same ASS and FFmpeg
  subtitle filter without importing an ASR runtime. It supports both a
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
    transcriber --> adapter[asr/<br/>selected adapter]
    adapter --> whisper[WhisperX]
    adapter --> faster[Faster-Whisper]
    adapter --> parakeet[Parakeet + NeMo]
    adapter --> qwen[Qwen3-ASR + forced aligner]
    adapter --> segmentation[text_segmentation.py<br/>Unicode boundaries + source map]
    segmentation --> cues[Timed subtitle cues]
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
| multisubs/cli.py | Defines the Typer console interface, validates direct user errors, chooses output layout, invokes the pipeline, and cleans up transient files. | app, main() |
| multisubs/asr/ | Defines backend capabilities and normalizes WhisperX, Faster-Whisper, Parakeet/NeMo, and Qwen3-ASR results into one language/text/segments contract without importing unselected runtimes. | ASRBackend, ASRRequest, ASRResult, create_adapter() |
| multisubs/transcriber.py | Selects an ASR adapter, builds readable display cues, prepares optional aligned-word timing, and coordinates JSON/SRT/ASS artifact writing. | transcribe_video(), write_transcription_artifacts(), generate_transcriptions() |
| multisubs/preview.py | Resolves a sample cue without transcription, applies adaptive wrapping, generates deterministic simulated word timing for animated previews, and generates optional native or explicit ASS guide events. | build_preview_ass(), build_animation_preview_ass(), build_simulated_karaoke_cue(), resolve_preview_timestamp() |
| multisubs/animation.py | Normalizes cue and aligned-word phases with configured durations inside quantized bounds and samples relative opacity, movement, and scale state without I/O. | normalize_cue_animation(), normalize_word_animation(), animation_boundaries(), word_animation_boundaries(), sample_cue_animation(), sample_word_animation() |
| multisubs/render_capabilities.py | Classifies actual display text for bidirectional/contextual shaping and selects positioned word fragments or complete logical-line fallback without using a language allowlist. | assess_renderer_capability(), RendererCapability |
| multisubs/ass.py | Compiles semantic appearance and cue/word animation into trusted private ASS fields and overrides around safely escaped dialogue text. | write_ass(), rgba_to_ass_color(), allocate_karaoke_durations(), allocate_active_word_intervals() |
| multisubs/subtitler.py | Probes normalized video geometry, extracts private 16 kHz mono audio for audio-only ASRs, and invokes FFmpeg to burn ASS into the selected video stream or render previews. | probe_video_geometry(), extract_audio_track(), embed_subtitles(), render_subtitle_preview(), render_subtitle_animation_preview() |
| multisubs/config.py | Defines supported choices and semantic defaults, composes CLI overrides, applies scoped animation/effect suppressions, and validates the typed style/layout/animation configuration. | SUPPORTED_LANGUAGES, MODELS, validate_subtitle_config(), apply_subtitle_feature_disables() |
| multisubs/templates.py | Strictly loads the deterministic packaged JSON index and sparse built-in style/layout/animation definitions, expands them from semantic defaults, and compiles complete baselines through the normal validator. | SubtitleTemplate, SUBTITLE_TEMPLATES, get_subtitle_template() |
| multisubs/custom_templates.py | Reads the bounded public schema-1 template directory, validates every discovered file, resolves custom names with built-in-only inheritance, and returns immutable source metadata for one request. | load_custom_template_directory(), resolve_subtitle_template(), ResolvedSubtitleTemplate |
| multisubs/layout.py | Resolves unit-bearing layout fields, derives wrapping dimensions, validates native or explicit envelopes, and positions measured visual-line fragments on the probed canvas. | resolve_relative_length(), resolve_subtitle_config(), resolve_native_layout_region(), resolve_wrapping_metrics(), resolve_cue_placement(), position_visual_lines() |
| multisubs/font_catalog.py | Loads the immutable bundled-font manifest, performs bounded family lookup, exposes unpacked package resources, and materializes only a selected family when required by the importer. | load_bundled_font_catalog(), bundled_font_directory(), verify_bundled_font_assets() |
| multisubs/text_measurement.py | Resolves the nearest custom, bundled, or fontconfig family/weight face, measures glyph advances and ascent/descent metrics with Pillow/RAQM, caches per-run values, and owns the Unicode-aware fallback. | build_text_measurer(), TextMeasurer, TextMeasurementInfo |
| multisubs/text_segmentation.py | Isolates pinned Unicode and offline linguistic adapters, maps aligned records monotonically onto source spans, and derives provenance-bearing Japanese/Chinese display groups, display units, and preview effect units. | build_source_text_map(), LinguisticSegmenter, linguistic_units(), simulated_effect_units(), display_units_for_records() |
| multisubs/wrapping.py | Applies typed Unicode display casing, shares font-aware bounded adaptive wrapping between transcription and preview without importing the model runtime, and partitions mapped display units into visual lines. | transform_display_text(), wrap_subtitle_text(), line_count(), build_visual_lines(), render_display_units() |
| multisubs/utils.py | Produces non-conflicting file and directory paths. | get_unique_path(), get_unique_dir_path() |
| multisubs/errors.py | Defines user-actionable validation, template-catalog, dependency, artifact, transcription, and rendering errors. | MultisubsError subclasses |
| multisubs/models.py | Defines typed request, preview mode, style/layout/animation configuration, typography, cue and word backdrops, shadow, global opacity, display casing, timed-word modes, immutable source spans/maps/display groups/units/fragments, visual lines and timed cues, video geometry, placement, guide, transcript, and artifact value objects. | RelativeLength, PreviewMode, SubtitleStyle, SubtitleTypography, SubtitleBackdropStyle, SubtitleWordBackdropStyle, SubtitleShadow, SubtitleLayout, SubtitleAnimation, SubtitleConfig, SubtitleSourceSpan, SubtitleSourceMap, SubtitleDisplayGroup, SubtitleDisplayUnit, RunRequest, PreviewRequest, TranscriptDocument, RunArtifacts |
| multisubs/__init__.py | Exposes the package version and lazily loads the primary package functions. | __version__ |

### Timed-cue JSON input

`timed_cues.py` handles a separate public schema-version-1 JSON contract.
It validates a required language tag, ordered cues and words, exact word-to-cue
source spans, finite times, resource bounds, and Unicode grapheme boundaries.
Unlike the retained schema-3 transcript, it carries no ASR metadata.
`subtitle_artifacts.py` writes the same SRT format used by transcription;
`ass.py` compiles the mapped display cues with the existing template, layout,
font, and animation contracts. Supplied cue and word times stay unchanged.
Visual line breaks may be inserted, but an unfit cue fails instead of being
split. Overlapping cues remain separate, simultaneous ASS dialogue events.

The JSON mode probes the required input video once for normalized geometry and
checks its known duration. It builds SRT and ASS in a private work directory,
renders the video from that private generated ASS through `subtitler.py`, and
publishes all three files under one collision-safe `<video>-<language>` stem.
A failed render or publication leaves no completed output files. The supplied
JSON and video are read-only. No transcript JSON or ASR runtime is involved.

## Execution flow

1. The console script calls `cli.main()`. Typer parses options and their custom values; the CLI validates combinations, paths, and built-in or custom template defaults plus explicit overrides before probing. Scoped disable flags are then applied to the resolved typed configuration: each scope-level animation flag removes every phase from text and backdrop tracks; cue suppression preserves its static backdrop, while word suppression also removes the dependent word decoration fields. During a default processing run, the CLI routes its own progress to standard output and discards external runtimes' Python and native stdout/stderr writes through the platform's null device. Exceptions still become multisubs errors after normal streams are restored. `--verbose` leaves runtime output visible and includes detailed progress. See [internal template resources](#internal-template-resources) and the [functional requirements](prd.md#functional-requirements).
2. Both paths validate FFmpeg/ffprobe and probe the lowest-index usable stream, checking coded dimensions, rotation, sample/display aspect ratios, and container duration in one `VideoGeometry`. Autorotation keeps coded axes at 0°/180° and swaps render and sample-aspect-ratio axes at 90°/270°; legacy rotate-tag signs are normalized, and contradictory metadata fails. This precedes normal work-directory creation and model loading. The normal path resolves layout and wrapping and validates a decorated line can fit before model loading. See [FFmpeg](#ffmpeg), [design constraints](#design-constraints), and [FR-15](prd.md#functional-requirements).
3. The normal path resolves `--asr` and a backend-specific default model before
   loading any runtime. The selected adapter owns device selection, inference,
   language resolution, and available word alignment, then returns normalized
   text and timed segments. WhisperX and Faster-Whisper support English
   translation with non-Turbo multilingual models; translated words are not
   aligned. Parakeet and Qwen3-ASR accept a private 16 kHz mono WAV extracted by
   FFmpeg and removed after inference. Model and aligner downloads retry
   transient connection failures up to three times. See [local ASR adapters](#local-asr-adapters)
   and [FR-3–FR-5, FR-14, FR-19](prd.md#functional-requirements).
4. `transcriber.py` maps aligned records to source text, constructs timed cues, and rebuilds wrapping metrics for the subtitle language and display-cased sample. Incomplete mappings retain complete source text at coarse segment timing instead of fabricated word times. Translation has a second, layout-level safeguard: after the six-second backend chunking stage, the artifact writer validates the measured ASS envelope and retries up to three times with the effective font size reduced by 4% per step when width or height still overflows. It then serializes JSON, SRT, and ASS from the same successful cue/config/metric set. See [subtitle-cue construction](#subtitle-cue-construction) and [Unicode segmentation and source mapping](#unicode-segmentation-and-source-mapping) for the detailed rules.
5. The artifact writer validates timestamps and atomically writes JSON/SRT; `ass.py` compiles the same resolved configuration and cues. Both preview modes bypass transcription and reuse layout, ASS, and FFmpeg without publishing subtitle artifacts. See [JSON](#json), [SRT and ASS](#srt-and-ass), and [FR-16–FR-18](prd.md#functional-requirements) for their contracts.
6. Normal rendering burns ASS into the selected stream with autorotation and copies available audio; preview rendering produces its still or clip without transcription artifacts. After a successful normal render, the CLI publishes collision-safe outputs and removes its private work directory; failed normal runs retain that directory for diagnosis. Preview runs remove temporary ASS/frame files and partial media. See [FFmpeg](#ffmpeg), [output layouts](#output-layouts), and [design constraints](#design-constraints).

## Subtitle-cue construction

The subtitle builder is intentionally separate from backend-specific ASR
segmentation:

- It joins adjacent aligned word streams so an ASR segment boundary does not
  force a poor subtitle break.
- It keeps alignment records, derived linguistic display groups, and legal
  visual line-break opportunities as separate units. Japanese uses Sudachi
  mode B with predicate-tail presentation joining; Chinese uses jieba with its
  packaged dictionary and HMM. Other languages retain aligned word boundaries.
- It emits a cue at a sentence end or a pause of at least 0.45 seconds when possible.
- It keeps zero-duration alignment records with their real timestamps but does
  not isolate them into zero-duration cues when an adjacent timed record can
  carry the complete source text.
- It targets no more than 6 seconds per semantic cue; width no longer uses a
  fixed character count.
- Translation is handled in two stages. WhisperX limits translation inference
  with `chunk_size=6`, and Faster-Whisper uses its equivalent
  `chunk_length=6`; this keeps translated source chunks bounded before cue
  layout. If the resulting translated display still exceeds the measured ASS
  width or height envelope, the artifact writer retries up to three times with
  a 4% smaller effective font per retry. Requested style values remain in JSON,
  while the resolved values describe the successful fallback layout.
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
- When a preview or aligned-group split must choose among fitting cue prefixes,
  it evaluates the bounded candidate set because shaped widths need not be
  monotonic. It preserves sentence, clause, and pause priorities, avoids a
  one-group tail when possible, and otherwise retains the longest fitting
  legal prefix. This lets a multi-line envelope consume its available visual
  capacity without changing source timing or record order.
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
- A long indivisible display group remains intact and may overflow the
  approximate width budget. It is subdivided only at a legal visual/grapheme
  boundary backed by an exact source-record timing boundary, and that emergency
  path is diagnosed rather than labeled as a lexical word. Original transcript
  content is never removed or replaced by its display transformation.
- If word timestamps are unavailable for an ASR segment, it flushes pending
  aligned words and uses that segment's coarse start and end times as a safe
  fallback.
- Karaoke never retokenizes the final display string. It animates original
  alignment records while preserving linguistic groups for boundary guidance.
  If a display cue cannot be mapped to every record in order, it remains plain
  and contributes to one aggregate effect fallback warning; a visual line
  break inside a group is not itself a fallback condition.
- Before ASS serialization, the shared renderer-capability boundary examines
  actual display characters. Bidirectional classes, contextual-shaping script
  ranges, and joining controls disable both word tracks because measured
  logical-prefix placement is not a visual-run algorithm. The cue remains one
  complete logical text event per visual line for libass shaping, while cue
  animation and shared backdrops remain active. Production and both preview
  modes use the same decision and report `unsupported-word-shaping` without
  logging subtitle contents.

Semantic cue rules reside in multisubs/transcriber.py, source mapping and pinned
Unicode boundaries reside in multisubs/text_segmentation.py, and shared visual
wrapping rules reside in multisubs/wrapping.py; all should be changed with
focused tests.

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
    "asr": "whisperx",
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
        "weight_substituted": false,
        "coverage": "verified",
        "fallback_reason": null
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

`schema_version` identifies the top-level JSON contract. Version 3 records the
selected `asr` and model, concrete requested/resolved layout, and unified
animation contract. The words array preserves usable JSON-compatible records
normalized from the selected backend; backend-only optional fields are not a
stable project contract. Each cue keeps source text, real available timestamps,
and wrapped/case-transformed `display_text`. The top-level text remains the ASR
output. Rendering metadata records geometry, placement, appearance, wrapping,
measurement, opacity, animation, template, and fallback diagnostics. Local
model paths, generated ASS, and raw command lines are not serialized.

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
after source mapping, measurement, and wrapping, then escapes each fragment
before generated overrides are assembled. Source separators are copied from the
map; no display tokenization invents them. Karaoke preparation does not
retokenize display text and refuses fallback-marked maps. JSON keeps original
full/cue text and every JSON-safe aligned record, adds each cue's
`display_text`, and records TextCase plus resolved cue/word animation metadata
without storing compiled tags. Incomplete maps add per-cue
`alignment_mapping` and aggregate `metadata.rendering.text_mapping` counts and
reasons; internal span objects and offset tables remain private.
Complete mapped cues add a `segmentation` object containing the linguistic
strategy, pinned backend version, alignment granularity, derived-group count,
emergency-subdivision count, and bounded fallback fields. Cues prepared for
word-dependent effects additionally expose `word_effect` with the explicit
`alignment-records` unit and bounded strategy/reason fields; the aggregate
`metadata.rendering.word_effects` count is separate from source-map diagnostics.
These additive objects do not replace or rewrite the original `words` array.

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
The positioned-fragment path is limited to display text classified as safe by
`render_capabilities.py`. Arabic-family, Hebrew, Indic, and other detected
bidirectional/contextual-shaping content uses complete logical-line events;
multisubs never reverses strings or approximates visual runs. The retained
per-cue `word_effect` object records `renderer_strategy`, bounded
`shaping_features`, and `unsupported-word-shaping` when requested word tracks
are suppressed. Aggregate diagnostics count each cue once and summarize both
fallback reasons and renderer strategies.
When aligned-word behavior positions text fragments independently, a cue glyph
outline is partitioned into the same fragments and reuses their exact measured
placements. Mixing a libass-shaped whole-line outline with positioned fragment
text is forbidden because their shaping advances can differ. Because an outline
is bound to the glyph rather than an independent rectangular surface, each
fragmented outline also samples the corresponding cue-text and word-text timing,
movement, and scale. Preview uses that same fragmented topology while
suppressing only its temporal motion. Static preview selection uses linguistic
boundaries for representative content, while simulated effect timing uses
script-appropriate units and is never reused as production speech timing.

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

Every `entrance`, `emphasis`, and `exit` phase is an animation. Therefore,
`--disable-cue-animations` and `--disable-word-animations` clear all text and
backdrop tracks in the selected scope. Cue suppression preserves the static cue
backdrop; word suppression also removes the word decoration and highlight color
because they depend on aligned-word timestamps. These transformations happen
after template and explicit-option resolution, so a selected template remains
the recorded template even when a scope is suppressed. Translation reports
remaining word animation or backdrop requirements and recommends the single
`--disable-word-animations` flag; cue-level animation and backdrop remain valid
for translation.

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

When neither the user nor the selected ASR provides a source-language code,
`metadata.language` is null and the same layouts use `video.mp4`, `video.json`,
`video.srt`, and `video.ass` without a language suffix.

## External boundaries

### Local ASR adapters

`multisubs/asr` owns model interaction and exposes one normalized result to the
transcriber. Static capability validation happens before runtime import. Each
adapter validates external fields and timestamps before subtitle construction;
no adapter imports another backend.

- WhisperX is the default adapter but an optional installation extra. It uses
  CUDA/float16 or CPU/int8, leaves VAD selection to WhisperX, and loads its
  source-language alignment model for transcription. Translation requests
  six-second chunks with WhisperX's `chunk_size` option.
- Faster-Whisper is optional, detects visible CUDA devices through CTranslate2,
  uses CUDA/float16 or CPU/int8 without importing PyTorch, enables Silero VAD
  with the runtime defaults for transcription and translation, requests
  `chunk_length=6` for translation, and requests native word timestamps for
  transcription. Its translation layout fallback is shared with WhisperX in
  the artifact writer.
- Parakeet is optional and uses NeMo with
  `nvidia/parakeet-tdt-0.6b-v3`. It receives a private 16 kHz mono WAV, returns
  native segment/word timestamps, and recognizes supported languages without a
  prompt. Its normal result does not expose that internal language decision, so
  an omitted `--lang` leaves language metadata null; an explicit code labels
  artifacts without conditioning inference. NeMo's transcription progress bar
  follows the CLI verbosity setting and is hidden by default.
- Qwen3-ASR is selected as `qwen`, uses the native Transformers checkpoint
  `Qwen/Qwen3-ASR-1.7B-hf`, and receives the same private WAV in chunks capped
  at 180 seconds. When more than one chunk is needed, the adapter searches for
  a low-energy boundary within five seconds of each limit and preserves complete
  source coverage and offsets. It exposes the detected language when `--lang`
  is omitted. After transcription, the ASR model is released before the
  independent forced aligner is loaded. CUDA uses BF16 when supported and
  otherwise falls back to FP16; CPU uses float32.
  Each explicit or detected language supported by the aligner is passed to
  `Qwen/Qwen3-ForcedAligner-0.6B-hf`; its word timestamps are offset back onto
  the source timeline. Because the HF aligner may omit punctuation from its
  timed units, the adapter monotonically restores punctuation-only source gaps
  onto the preceding record before common source mapping; lexical mismatches
  still use the safe coarse fallback. Languages outside the aligner's smaller
  catalog retain real chunk boundaries and use the existing no-word-effects
  coarse fallback.

All model and aligner loaders retry transient network failures. Every ASR
runtime is an installation extra; a core installation therefore does not
resolve PyTorch or CUDA packages. Model caches stay under runtime defaults,
outside project outputs.

PyTorch-backed ASRs use separately installed CPU or CUDA wheels. The documented
CUDA baseline is the PyTorch 2.8 CUDA 12.8 index matching the package pins.
Faster-Whisper instead requires the CUDA 12 cuBLAS and cuDNN 9 libraries
supported by its CTranslate2 runtime. Its NVIDIA driver and GPU libraries are
conditional system dependencies, installed through the operating system rather
than a Python extra. Standard system library locations require no per-shell
loader configuration. Runtime device visibility controls automatic CPU/GPU
selection; multisubs does not install GPU drivers.

### FFmpeg

subtitler.py owns ffprobe inspection, ASR audio extraction, and video rendering.
It checks that both
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

fontTools 4.63 is a direct runtime dependency used for bounded Unicode cmap
coverage checks. Pillow and fontTools have different responsibilities: Pillow
performs RAQM-aware shaping and measurement, while fontTools reads the selected
TrueType/OpenType face (including a bounded TTC index) to reject missing-glyph
advances before layout claims concrete metrics. Candidate files are limited by
size, collection-face count, and fontconfig candidate count; malformed tables
are rejected without serializing paths or transcript text. Non-rendering
controls and variation selectors do not require standalone cmap entries, while
combining marks remain covered characters. Cmap verification is necessary but
does not by itself claim complete shaping or libass identity, so the rendered
ASS family is set to the same effective face and integration tests remain the
render authority.

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
fontconfig. When the requested face lacks a displayed glyph, the resolver
searches covering custom faces and then a bounded `fc-match -s` list with the
language as a preference. Common face names are mapped to canonical OpenType
ranks, and candidates are ordered by absolute weight distance, requested italic
state, then stable path/index order within the selected provider. On hosts with
fontconfig, `fc-match` is invoked with a bounded argument-vector subprocess
using the corresponding weight, slant, and optional language; each returned
file's actual metadata and cmap are validated instead of assuming an exact
match. Other providers are not guessed. The resolved provider kind and
fallback reason are serialized, while its package, custom, system, or
temporary path remains private. Font objects and up to 4096 repeated text
measurements are cached in memory for one artifact-writing run; transcript
strings are not persisted by the cache.
Pillow and libass can differ in shaping, hinting, and fallback, so libass remains
the render authority and integration tests use an explicit tolerance.

### Unicode segmentation and source mapping

`text_segmentation.py` is the pure text boundary between normalized ASR data and
subtitle layout. It depends on `uniseg==0.10.1` (Unicode 16.0.0 data) for
extended grapheme, word, line, and sentence boundaries; it does not import
ASR runtimes, PyTorch, Pillow, or FFmpeg, so preview remains transcription-free.
It lazily loads SudachiPy 0.6.11 with SudachiDict-small 20260723 for Japanese
mode-B boundaries and jieba 0.42.1 with its packaged dictionary/HMM for Chinese.
These resources install as Python dependencies and never download transcript
data or dictionaries at runtime. Sudachi and jieba boundaries are intersected
with complete uniseg graphemes; Japanese auxiliary and non-independent
predicate tails and compatible numeric counters attach to their presentation
group unless whitespace, punctuation, or a significant source pause requires
a boundary. The jieba
tokenizer writes only to an invocation-local temporary cache, removed when the
segmenter closes. Preview text uses the same adapter with script inference when
no source language exists.
Offsets are Python code-point positions. The adapter normalizes only CRLF/CR to
LF and retains raw-to-logical and logical-to-raw offset tables. A cursor-based
source map assigns the next matching aligned record to its source span,
preserving repeated tokens, meaningful whitespace, NBSP, punctuation, joiners,
and unmatched ranges. Cues use mapped display units for casing, measurement,
wrapping, and fragments. Missing/invalid timing or unmatched text is a visible
fallback condition; the source remains at coarse segment timing and no word
effect receives fabricated bounds. The compatibility `words_to_text()` helper
may still provide conservative separators for direct callers that have no
source string, but the production mapped path does not use that heuristic.

## Design constraints

- The pipeline is synchronous and processes one video at a time.
- Subtitle rendering is a hard-subtitle operation, not muxing a selectable subtitle track.
- Translation has an English-only target and requires WhisperX or
  Faster-Whisper with a multilingual non-Turbo model.
- Source languages and word-timestamp availability follow the selected ASR;
  missing word timing uses the visible coarse-segment fallback.
- Completed transcription artifacts are cleaned only after subtitle rendering returns successfully; partial renderer media is cleaned on both success and failure.
- File collision avoidance is a required safety property, not merely a convenience.
- Final media is published only after FFmpeg succeeds; temporary output is never presented as a completed video.
- CLI diagnostics use non-zero exit statuses for validation and processing failures.
- ASS PlayRes, JSON rendering metadata, and the FFmpeg subtitles filter must use one VideoGeometry instance per run.
