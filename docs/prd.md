# Product Requirements Document

## Product

- **Name:** multisubs
- **Status:** Current implementation baseline
- **Type:** Local command-line video subtitling tool

## Problem

Creating usable subtitles from a video normally requires transcription, timestamp alignment, subtitle formatting, styling, and video rendering as separate steps. This is repetitive for creators and editors who want a local, scriptable workflow.

multisubs reduces that workflow to one command while retaining subtitle files when they are needed for review or later reuse.

## Target users

- Video creators who need captions burned into a local video.
- Editors who need SRT or ASS files alongside a rendered preview.
- Technical users who want a scriptable transcription and translation workflow.

## Product goals

1. Accept one local video and generate subtitles with useful timing.
2. Produce a new video with hard subtitles rendered into its image.
3. Preserve machine-readable and editable subtitle artifacts on request.
4. Support source-language selection, transcription, and translation to English.
5. Provide format-independent subtitle appearance and layout control from the command line.
6. Avoid overwriting a user's existing files.
7. Let users choose among the primary supported local ASR runtimes without
   coupling subtitle generation to one result format.

## User journey

1. The user installs the package and FFmpeg.
2. The user invokes multisubs with an input video and optional ASR, language,
   task, model, output directory, appearance, and layout options.
3. The tool transcribes and aligns speech, constructs subtitle cues, and creates JSON, SRT, and ASS files.
4. FFmpeg burns the ASS file into a copy of the input video.
5. The user receives the rendered video and, when requested, the subtitle artifacts in a predictable directory layout.

## Functional requirements

| ID | Requirement |
| --- | --- |
| FR-1 | The CLI must require one input video path and must reject a missing input file. |
| FR-2 | The user must be able to choose an output directory; the current directory is the default. |
| FR-3 | WhisperX, Faster-Whisper, and Qwen3-ASR must detect one source language when `--lang` is omitted. Parakeet must transcribe automatically without requiring `--lang`; because its normal NeMo result does not expose the internally recognized code, an omitted language produces null JSON language metadata and artifact names without a language suffix. An explicit Parakeet language labels artifacts but does not condition inference. English-only Whisper models must use `en`, unsupported explicit or detected languages must fail with actionable guidance, and known language codes must remain in artifact names and JSON metadata. |
| FR-4 | WhisperX and Faster-Whisper must support transcription and translation to English. Parakeet and Qwen3-ASR support transcription only. |
| FR-5 | The tool must reject translation for Parakeet, Qwen3-ASR, Turbo, and English-only Whisper models before model loading. |
| FR-6 | The tool must generate a JSON transcript with metadata, an SRT subtitle file, and an ASS subtitle file before rendering. |
| FR-7 | Subtitle cues must treat aligned segment text as the source of truth for separators, adjacency, punctuation, and Unicode sequences, while using alignment records only for validated timing and stable source identity. Complete Japanese and Chinese maps must derive linguistic display groups from pinned offline dictionaries, while other languages retain available aligned-word boundaries; original records, derived groups, and legal Unicode visual breaks remain distinct. Cue selection must prefer sentence, clause, pause, then linguistic boundaries, including unpunctuated CJK, and evaluate bounded candidates without assuming shaped prefix widths are monotonic. Korean spaces, CJK/Latin adjacency, NBSP, combining sequences, and emoji joiners must not be reconstructed by heuristic whitespace insertion. An oversized group may be subdivided only at a legal grapheme/line boundary backed by an exact source timing boundary and must be diagnosed; otherwise it remains intact. Incomplete or lossy maps must render the complete source at coarse segment times, suppress timing-dependent effects, and expose bounded fallback diagnostics without fabricated timestamps. Display casing, verified covering-font measurement, maximum dimensions, letter spacing, line height, orphan handling, and longest-equivalent-prefix selection must not lose source content or original record metadata. Translation must first use six-second backend chunks in WhisperX and Faster-Whisper, then retry translated layout up to three times with a 4% smaller effective font when the measured width or height envelope overflows, without changing requested style metadata or source timing. |
| FR-8 | The tool must render the ASS subtitles into a new video with FFmpeg. |
| FR-9 | The user must receive one complete fixed native subtitle presentation by default, be able to select any of twenty-one built-in typed presentation templates (`default` plus twenty curated styles for social video, podcasts, tutorials, gaming, and editorial clips), and be able to override each template's appearance, layout, and animation through explicit CLI options, including font family, named or 100-step numeric font weight, unit-bearing font size, non-negative letter spacing, automatic or explicit line height, complete-composition opacity, original/uppercase/lowercase display text, cue backdrop, timed word decoration type/color/size, shadow, margins, maximum width, maximum height, nine named subtitle positions, a global PlayRes X/Y coordinate paired with one of the nine anchors, and independent entrance/emphasis/exit phases for cue text, cue backdrop, word text, and word backdrop. The user must also be able to remove all animation phases independently with `--disable-cue-animations` and `--disable-word-animations`; cue suppression preserves the static cue backdrop, while word suppression also removes dependent word decoration and highlight fields. Built-in templates must share default placement and margins, calibrate visible font size against the default bundled Roboto, and provide per-template maximum heights targeting two lines at common video geometries. Explicit overrides may change line capacity. Omitted template selection and explicit `default` must produce the same semantic configuration. Explicit fields must override only their corresponding template fields. Roboto, Inter, Montserrat, Oswald, Lora, Atkinson Hyperlegible Next, Anton, Bangers, Press Start 2P, Quantico, and Russo One must be available from the packaged offline catalog, with explicit custom faces taking precedence over bundled faces and bundled faces taking precedence over fontconfig. Percentage font size must use autorotated render height so horizontal and vertical outputs with the same height resolve to the same size. Opacity must preserve the relative alpha of every visual component. Case conversion must preserve original transcription and aligned-word data in JSON. Named positions must use native ASS alignment and margins. Template fields must behave as baselines rather than explicit option presence for placement conflicts. Explicit inactive vertical margins and every explicitly supplied margin in coordinate mode must fail before probing. Supplying any coordinate or anchor must enable custom placement and fill omitted fields from the selected template: the anchor inherits its native position, missing coordinates use the effective anchor's native margin point, omitted width preserves the template's effective native width, and omitted height inherits the template's full-render-height value. Maximum-height percentages must always use full render height; changing vertical margins must preserve height and line capacity wherever the complete envelope fits. Side margins must continue to change native width and wrapping without changing height-derived capacity. Explicit maximum-dimension overrides must use the full canvas axes without deducting margins again. Every complete subtitle envelope must fit inside the canvas. The retained JSON must identify requested and effective font families, coverage verification, provider, weight substitution, and any fallback reason without serializing local font paths. |
| FR-9A | The user must be able to provide one flat local directory with --template-dir and select a version-1 custom JSON template by its name through --template. Custom files are validated before probing, inherit only from the packaged built-in catalog through optional base, and may override the same semantic style, layout, and animation fields as built-in baselines. Custom names take precedence within that invocation, including default; the directory is never installed into the package catalog. |
| FR-10 | With --keep-transcriptions, the tool must retain JSON, SRT, and ASS files in a subtitles subdirectory next to the rendered video. |
| FR-11 | Without --keep-transcriptions, a successful normal full-video run must publish only the rendered video and remove the temporary JSON, SRT, and ASS files after rendering. Reusable source-speech persistence is independent; subtitle-only and real-preview outputs follow FR-24 and FR-25. |
| FR-12 | Generated files and output directories must receive a numeric suffix when a collision would otherwise occur. |
| FR-13 | Invalid arguments and paths must exit with a non-zero status before model loading; processing and rendering failures must also exit non-zero with an actionable diagnostic. |
| FR-14 | Transient connection failures while loading selected ASR, VAD, or alignment assets must be retried automatically before the processing run is reported as failed. |
| FR-15 | Before model loading, the tool must probe a deterministic video stream and use its autorotated render dimensions consistently for the ASS canvas and FFmpeg subtitle rendering. |
| FR-16 | The user must be able to request a transcription-free layout preview that probes the video, resolves the same appearance, opacity, text case, placement, wrapping, line height, animation configuration, shaping capability, and ASS canvas, renders exactly one collision-safe PNG frame at a validated timestamp, and never creates transcription artifacts or imports an ASR runtime. The preview must suppress every cue and word motion phase at its stable state. For content safe for positioned fragments, each progressive word track affects the first half of the displayed cue and each active-word track affects only its first word, without invented timing. Shaping-sensitive content must use the same complete-logical-line word-effect fallback as production and report it outside the image. Optional guides must show the relevant native margin region or explicit envelope, anchor or position, resolved line height, opacity, text case, and PlayRes dimensions. |
| FR-17 | The user must be able to select entrance, emphasis, and exit independently for cue text, cue backdrop, word text, and word backdrop, directly or through a template. Cue entrances support `none`, `fade`, four directional slides, `pop`, and `zoom`; cue emphasis supports `none`, `pulse`, `bounce`, `float`, `shake`, `flash`, and `breathe`; cue exits support entrances except `pop`. Word entrances support `none`, `fade`, vertical slides, `pop`, and `zoom`; word text emphasis supports `none`, `highlight`, `pulse`, `bounce`, `float`, and `breathe`; word backdrop emphasis supports the same set except `highlight`; word exits support `none`, `fade`, vertical slides, and `zoom`. Omitted options inherit their template leaves, while explicit `none` disables only the selected phase. Each applicable phase accepts a public duration from 10 through 5000 milliseconds, with explicit CLI duration taking precedence over template and effect defaults. Phases remain relative to their logical cue or derived word-effect presentation interval, repeat emphasis deterministically, and shrink when too short without changing source timestamps. Linguistic group timing is used only to prefer readable cue/line boundaries; active-word end is capped by the next alignment-record start, and positive effective intervals remain unchanged. Empty effect intervals after ASS quantization must use an adjacent free gap accommodating configured entrance, exit, and 100 ms of stable display, or share a nearest positive neighbor's animation/highlight interval when no gap fits. These estimates must remain inside the cue, preserve original source timestamps, keep text and its glyph outline synchronized, and expose bounded per-cue/aggregate timing-recovery diagnostics. Text and backdrop recover independently, usable progressive intervals remain unchanged, and unavailable recovery suppresses word effects for the complete cue while retaining source text and cue effects. Word text and backdrop have independent `active-word` or `progressive` timing and may consume only a complete source-to-alignment map. Positioned fragments may be used only when the actual display text is safe for their logical prefix-width placement. Bidirectional or contextual-shaping cues must suppress both word tracks, retain complete logical lines for libass shaping, and report `unsupported-word-shaping`; cue-level effects remain available. A glyph-shaped cue outline remains geometrically attached to its text through cue and word motion. A word decoration becomes visible when its style type is `outline` or `box`, even when all its motion phases are `none`. Every entrance, emphasis, and exit phase is an animation. The two scope-level animation flags clear all text and backdrop tracks; cue suppression preserves the static cue backdrop, while word suppression also removes dependent word decoration and highlight fields. The selected template identity remains unchanged. SRT remains plain; retained schema-version-3 JSON reports all four tracks plus fallback and shortening counts, original aligned records, bounded text-mapping and word-effect diagnostics, renderer strategies, shaping features, and additive segmentation strategy/group/subdivision metadata. Incomplete source or record mappings fall back to the complete static cue without invented timestamps. Translation is excluded while any visible word animation or word backdrop remains, and the validation message names the active category, recommends `--disable-word-animations`, and lists compatible built-in templates. |
| FR-18 | The user must be able to request `--preview-animation` instead of `--preview-layout` to export one collision-safe silent MP4 without transcription or speech synthesis. It must reuse the first fitting transformed preview cue, selected template, layout, font metrics, ASS geometry, production animation compiler, and shaping-capability decision. A single uncaptioned frame selected by optional `--preview-at` (the first frame when omitted) is frozen as the background; the timestamp does not affect the animation clock. The cue runs after a 500 ms lead-in and before a 500 ms tail, with a configurable `--preview-duration` from 1 through 15 seconds (default `4s`) accepted as whole milliseconds or seconds. Simulated word units preserve whitespace fragments, punctuation attachment, CJK graphemes, combining marks, and ZWJ clusters; sentence/clause/default gaps are deterministic and capped at 20% of the cue, and weighted integer timing conserves the ASS centisecond interval with positive ordered units. Unsafe per-word shaping uses complete logical lines and a warning rather than presenting simulated motion as supported. The MP4 contains one 30 fps H.264 video stream, no audio, preserves autorotated geometry, uses a compatible pixel format for odd dimensions, and publishes no JSON, SRT, or ASS. Progress and optional guides must identify timings as simulated rather than speech-synchronized. Language, model, and task do not trigger speech validation in this mode, and `--keep-transcriptions` is rejected. |
| FR-19 | The CLI must expose `--asr` with `whisperx`, `faster-whisper`, `parakeet`, and `qwen`; WhisperX remains the default. Omitted `--model` must resolve per backend while preserving `whisperx` plus `turbo` for existing commands and selecting `Qwen/Qwen3-ASR-1.7B-hf` for Qwen. Every ASR runtime must be an optional lazy import so the core package and Faster-Whisper CPU path do not require PyTorch or CUDA packages. Every adapter must normalize text, an optional reported language, segments, and real available word timestamps into one internal contract; unavailable word timing must use the existing visible coarse-segment fallback and must never be fabricated. WhisperX and Faster-Whisper translation must use equivalent six-second inference chunks, followed by the shared measured-font fallback when translated layout exceeds its envelope. Qwen must split long audio at nearby low-energy boundaries with source offsets intact, release its ASR model before loading the aligner, select BF16 when supported with an FP16 CUDA fallback, and pass an automatically detected aligner-supported language to its forced aligner. Retained JSON must identify the selected ASR and model. |
| FR-20 | Library callers must be able to transcribe once into source speech data, cache it losslessly, and generate SRT, ASS, and a hard-subtitled video for a final template and geometry without another ASR call. `transcribe_speech()` and `render_transcript()` share the normal transcription pipeline and use one version-1 source-speech interchange contract, preserving source segment/word association, text, available times, unknown language, and backend/model metadata. Only transcription is supported by these APIs; unavailable word alignment retains normal coarse timing and reports suppressed word effects. All three outputs use one collision-safe stem and are published only after successful rendering. |
| FR-21 | A caller may provide a readable, nonempty local SRT or ASS file and video to render one hard-subtitled copy without ASR or rewriting the subtitle file. ASS is passed through with authored styling; SRT receives FFmpeg/libass default styling. Optional local fonts may be supplied. The CLI rejects transcription, template, appearance, animation, and preview options in this mode; failures publish no video, and collisions add a suffix. |
| FR-22 | Users may explicitly select `libx264` or `h264_nvenc`, a compatible preset, and integer quality from 0 through 51 for normal rendering, external SRT/ASS rendering, animated previews, and real excerpts. Omission preserves existing encoder selection and flags. Explicit defaults are medium/CRF 23 for x264 and p4/VBR/CQ 28 without a target bitrate for NVENC. Preset and quality require an explicit encoder; PNG previews accept valid encoding options but ignore them without initializing that encoder. Typed Python `VideoEncodingConfig` is independent of subtitle templates and is accepted by the public rendering APIs. In video-producing modes, explicit encoders receive a bounded synthetic initialization check before ASR or deferred artifact generation; failures are actionable and never silently fall back to a different encoder. Existing audio-copy, geometry, collision, and publication behavior remains intact. |

### Visual iteration without repeated recognition

- **FR-23:** Transcription runs must automatically reuse original source speech
  under `<output-dir>/.multisubs-cache`, including subtitle exports and real
  clips. `--cache-dir DIR` overrides that location. Resolve the default from the
  requested output root, independently of collision-safe retained-run folders;
  without `-o`, use the current directory. Translation, sample previews, and
  external-subtitle rendering must not create or access this cache. Persist
  before semantic cue/layout decisions. Key by complete media content and the
  normalized recognition request/compatibility; detect installed runtime-version
  changes without importing model runtimes. A valid hit must skip inference and
  alignment, including when optional runtimes are absent. Save atomically before
  rendering, preserve source text and observed times, bound and validate stored
  JSON, report reuse, and retain entries independently of artifact cleanup until
  users remove the dedicated directory. `--refresh-cache` must work with the
  default or custom location and replace the matching entry only after
  recognition succeeds. Entries use `transcriptions/v1/<hash>.json` beneath the
  cache directory. Valid legacy `speech-v1` entries remain reusable when the
  current entry is absent; new writes and refreshes use the current location
  without modifying legacy entries.
- **FR-24:** `--subtitles-only` must publish one collision-safe, shared-stem
  SRT/ASS pair using normal styles, timing, and final video geometry without
  video rendering, encoder initialization, or published transcript JSON. It may
  reuse FR-23; a miss recognizes the full source. Reject incompatible retention,
  encoding, external-subtitle, and preview modes before expensive work.
- **FR-25:** `--preview-clip` must render moving source video and available
  source audio with real transcript timing. Require `--preview-at` earlier than
  a known video end; accept `--preview-duration` from 1 to 15 seconds in whole
  milliseconds, default 10 seconds, clamping the end to the media end. Reuse
  full-source speech and production layout/animation, including cues crossing
  the cut. Publish one collision-safe H.264 MP4, re-encode available audio as
  AAC, preserve autorotation, and publish no subtitle/JSON files. Silent input
  and intervals without speech remain valid. Existing sample previews stay
  transcription-free and simulated timing never enters this workflow.

The three preview selectors and their controls share one CLI help panel.
`--preview-at` must use `HH:MM:SS` with two ASCII digits per field and whole
seconds; fractional seconds and malformed fields must fail before processing.
`--preview-at` is optional for PNG and simulated animation, defaulting to the
first source frame; real clips require it. `--preview-duration` controls the
simulated cue or real excerpt, with defaults of 4 and 10 seconds respectively.
PNG rejects a duration; sample text and guides apply only to PNG/animation.

These CLI workflows initially support transcription only. Ordinary
translation and the existing Python speech schema remain unchanged. Batch
variants, cached layout, and retaining loaded models between processes are
outside this increment.

### Public composition integration

- **FR-26:** Public `prepare_subtitles()` must accept a source `SpeechTranscript`
  or its version-1 dictionary and explicit final width/height, without video,
  probing, ASR, encoding, or access to the CLI speech cache. It must use native
  grouping, layout, fonts, wrapping, animations, timing fallbacks, and template
  exclusivity. Its context-managed `PreparedSubtitleArtifacts` exposes SRT/ASS,
  optional renderer fonts, and truthful template provenance. ASS PlayRes matches
  the final canvas. Successful subtitle pairs persist without overwrites;
  temporary resources remain available throughout consumption and are then
  cleaned on success, failure, or cancellation. Caller objects are not mutated.
- **FR-27:** Preparation and public `render_transcript()`,
  `render_subtitle_file()`, and `embed_subtitles()` must accept optional
  cooperative cancellation, raise public `CancelledError` under `MultisubsError`,
  check between stages and during owned FFmpeg/ffprobe execution, terminate and
  reap owned processes, and remove incomplete invocation-owned outputs.
  `render_transcript()` must reuse preparation and preserve its existing return
  type and three-file publication after successful encoding. Published files and
  independent calls must survive another call's failure or cancellation.
- **FR-28:** The four synchronous operations must support concurrent independent
  output directories and shared read-only speech/config objects. Scheduling and
  externally launched FFmpeg remain the consumer's responsibility. Document
  resource ownership, callback requirements, and the scope of verified support;
  no concurrent-ASR or CLI-wide thread-safety guarantee is implied.

### Reusable source transcription API

Library consumers must be able to compose a selected built-in/custom template
with sparse presentation overrides through public `build_subtitle_config()`,
without copying private resources or importing private validation helpers.
It returns the immutable public `SubtitleConfig` accepted by
`render_transcript()`, supports all 57 native presentation options with the same
validation and suppression precedence as the CLI, and preserves unspecified
template fields. Missing keys and `None` inherit; explicit `False` and valid
zero values remain explicit. Unknown keys and invalid inputs raise public
`ValidationError`; invalid template resources/directories raise public
`TemplateError`, both under public `MultisubsError`. Composition is shared with
the CLI and requires no media, models, loaded fonts, network, or materialized
assets. Geometry-dependent validation remains in rendering. Configuration
requests do not mutate caller data, templates, or other requests.

Library consumers such as multicuts must be able to call `transcribe_speech()`
once, retain source segment/word association, text, whitespace, punctuation,
observed equal timestamps, missing/null word timing, unknown language, and
backend/model provenance, then call `render_transcript()` for a final video's
geometry, template, and placement without another ASR call. The supported
`SpeechTranscript` result must feed rendering directly or through its public,
lossless version-1 dictionary conversion. Consumers may select source content and
shift supplied times to a cut's timeline without private APIs or token cleanup.

The speech APIs support only transcription and validate the task restriction
before expensive work. Normal CLI transcription, retained schema-3 artifacts,
translation, and collision/retention behavior retain their established behavior.
Deferred SRT and ASS must match normal generation from the same ASR data,
configuration, and geometry in portrait and landscape, including source spaces,
point groups, missing/partial alignment, and unknown language. Missing alignment
keeps normal coarse timing and explicitly warns when word effects are unavailable.
Point words retain their source times, must not cancel unrelated visual partitions, and
must never cause silently overflowing output or fabricated word timestamps.

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Runtime | Run locally through a Python CLI. Use CUDA when available; otherwise support CPU inference where the selected ASR runtime permits it. |
| Compatibility | Require Python 3.10 through 3.13 and a system FFmpeg installation that provides ffprobe and subtitle rendering support; animated preview clips additionally require the `libx264` encoder. Python 3.14 is excluded while WhisperX 3.8.6 declares an upper bound below 3.14. |
| Traceability | Include a schema version, source path, known source language or null, task, ASR, model, creation time, duration, segment count, and resolved video geometry in the JSON output. |
| Usability | Show only multisubs progress, relevant subtitle warnings, actionable errors, and result paths by default. Suppress raw runtime output, including backend warnings and native diagnostics, during processing. `--verbose` shows detailed artifact progress and raw backend output for diagnosis. |
| Safety | Do not overwrite existing output files or directories. |
| Caption readability | Derive line capacity from the fixed maximum-height default or its explicit override, natural/resolved line-height metrics, and decorations with a visible Unicode-estimate fallback; verify glyph coverage before claiming concrete metrics and keep the measured face equal to the ASS face; capacity may vary with geometry, but a complete fitting cue remains unbroken, unnecessary one-word final lines are avoided, timed cues split when required, translated envelope overflow receives the bounded smaller-font fallback, and transcript content is never mutated when shaping differs. |

## Out of scope

- A graphical or web interface.
- Batch orchestration for multiple input videos in one command.
- An interactive subtitle editor or human review workflow.
- Selectable translation target languages; English is the only translation target.
- Soft subtitle tracks that can be enabled or disabled in a video player.
- Speaker diarization, speaker labels, or subtitle speaker styling.
- Syllable-, phoneme-, character-, sweep-, typewriter-, rotation-, blur-, color-cycle-, per-line, audio-reactive, or model-generated animation.
- Public animation travel distance, scale, overshoot, easing, chains, arbitrary expressions, or raw ASS tags.
- Aligned-word animation on translated output, because it has no lossless source-word timing map. The static PNG preview remains motion-suppressed; the animated MP4 preview is a synthetic demonstration and is not speech synchronization.

## Acceptance criteria

For FR-23–FR-25, style changes against one cache perform no additional ASR calls;
commands without `--cache-dir` share the output-local cache, including retained
runs, subtitle exports, and real clips. A custom cache overrides that default.
Changed source/configuration and forced refresh recognize again. A later media
failure preserves complete cached speech, and a failed refresh preserves the
previous entry. Subtitle-only published artifacts contain just the SRT/ASS pair,
with source speech stored in its separate cache. Real clips
match source-time subtitle behavior across cuts and expose source audio at the
selected time. Invalid combinations/ranges fail before model loading.

1. A user can install the package, run multisubs --help, and see the supported options.
2. A valid transcription command generates a subtitle-burned video without overwriting existing output.
3. A retained run creates JSON, SRT, and ASS assets under an output subtitles directory.
4. A non-retained successful normal full-video run publishes only the rendered video and removes its intermediate JSON, SRT, and ASS files; transcription retains reusable source speech in its separate cache.
5. Translation with Parakeet, Qwen3-ASR, Turbo, or an English-only Whisper
   model is rejected before transcription begins.
6. The JSON output contains metadata and timed subtitle segments.
7. A user can change an exposed semantic appearance option, including letter spacing, or choose a named position and see it reflected in the generated ASS style definition and rendered video without providing raw ASS field names, ASS alignment codes, or ASS color syntax.
8. Invalid input exits non-zero without loading a model, and a failed render does not publish a partial final video.
9. A transient model or alignment connection failure is retried automatically, while a deterministic loading failure is surfaced without unnecessary retries.
10. Landscape, portrait, square, rotated, and non-square-pixel inputs use an ASS canvas matching the dimensions seen by the autorotated FFmpeg render graph.
11. Equivalent percentage-based font and margin values produce equivalent normalized subtitle bounds across supported video resolutions, while pixel values remain fixed in the PlayRes canvas.
12. The default native presentation starts from `bottom-center`, `18%` left/right margins, `0%` top margin, `3%` bottom margin, `100%` maximum width, and `11.64%` maximum height without classifying the video shape. Each effective explicit named-position, margin, or maximum-dimension option overrides only its corresponding default before native layout validation; explicitly supplied inactive vertical margins fail with an actionable alternative.
13. A custom X/Y coordinate is resolved globally on the autorotated PlayRes canvas; explicitly supplied margins and named-position overrides are rejected, omitted coordinates use the effective anchor's native margin point, the anchor defaults to the template position, omitted width preserves the template's effective native limit after side margins, omitted height inherits the template's full-render-height value, and the complete maximum-width/maximum-height envelope must fit for the selected anchor. Generated metadata identifies explicit placement without changing SRT text or timing.
14. A cue that fits the width budget with its resolved font and letter spacing remains on one line; when a break is required, equivalent semantic candidates avoid an unnecessary one-word final line, and JSON identifies the resolved font or estimate used.
15. In native mode, a `100%` maximum width means the complete width remaining after horizontal margins. In explicit mode, omitted maximum dimensions preserve the selected template's native limits; the default template's inherited width is equivalent to `100% - 18% - 18% = 64%` of the video before pixel rounding. Explicit maximum-dimension overrides use the full canvas axes, and invalid anchor coordinates are rejected rather than clamped, moved, or given smaller envelopes. Supplying only `--position-y 86%` must inherit the template anchor, X coordinate, and dimensions. Mixed-unit side margins must resolve before deriving inherited width, preserving native pixel rounding. In all placement modes, maximum-height percentages use full render height, independent of vertical margins. Built-in height defaults are recalibrated to preserve their existing two-line capacity at common geometries. Native envelopes that cannot fit after a vertical-margin change are rejected without reducing dimensions, font size, or capacity.
16. Maximum height accounts for measured line height plus backdrop and shadow allowances and produces an internal line capacity of at least one line; increasing the height can increase that capacity without introducing a public maximum-lines option. The same capacity is used by ordinary cue wrapping and transcription-free preview selection.
17. `--preview-layout` accepts the documented timestamp, sample text, appearance, placement, template, and animation options, defaults to the first video frame, produces a valid PNG with the probed dimensions, applies collision-safe naming, and cleans temporary ASS/PNG files on success or failure without loading any ASR runtime. When the sample exceeds the resolved envelope, the PNG contains only the first lexical group that fits the normal cue-layout calculation; among equivalent fitting boundaries it retains the longest prefix, while sentence, clause, pause, and orphan-avoidance priorities remain authoritative. Backdrop and shadow allowances are counted once in the width budget. Text representing later timed cues is omitted from that frame. Motion is suppressed at stable position, scale, and opacity. Each progressive word track statically affects the first half of that cue; each active-word track affects only its first word. No timing tags are generated. `--keep-transcriptions` is rejected in this mode, and optional guides are visibly present only when requested.
18. `--animation-word-text-emphasis highlight` and the `amber-word`, `mint-progress`, `focus-marker`, `kinetic-lime`, `coral-marker`, `yellow-pop`, `yellow-trace`, `neon-lime-marker`, `anton-impact`, `press-start-arcade`, `quantico-tech`, and `russo-punch` templates enable text highlighting. `--word-backdrop outline|box` and the `focus-marker`, `emerald-word`, `coral-marker`, or `neon-lime-marker` templates enable a measured timed decoration independently of its motion phases. The separate text and backdrop modes control whether prior affected words remain visible (`progressive`) or only the validated current interval is affected (`active-word`). Explicit `none` disables only the selected inherited phase. These combinations preserve line breaks and placement in real ASS/libass renders and leave equivalent untimed output unchanged.
19. Any visible word animation or a non-`none` word backdrop rejects translation before probing or model loading in the normal transcription path. The diagnostic identifies whether word animations (entrance/emphasis/exit), word backdrop decoration (outline/box), or both are active, recommends `--disable-word-animations`, and lists compatible built-in templates. Durations are accepted only for duration-bearing phases, must be 10–5000 ms, and follow CLI, template, then phase-default precedence. Incomplete or lossy word mappings render plainly, produce one aggregate warning without transcript text, and record the exact fallback count in JSON.
20. Timed text highlight uses trusted generated color overrides around independently escaped fragments. Word outline or box decoration emits bounded measured ASS events on a layer between the cue backdrop and text; active decorations end with the word, while progressive decorations persist through the cue. Cue text, cue backdrop, word text, and word backdrop sample independent animation tracks without restarting at derived boundaries or duplicating visible glyphs. SRT and JSON contain no generated ASS markup. An empty word-effect interval uses a free gap containing the full entrance/exit plus 100 ms of stable display, or shares a timed neighbor's effect if no gap fits. Text and its cue outline move together; source timestamps, positive effect intervals, and cue boundaries remain unchanged. Retained JSON reports these presentation estimates separately from aligned records. The same rule covers zero durations received from ASR and positive durations collapsed by ASS quantization; a cue without recoverable timing retains its complete text with word effects suppressed.
21. Named font weights, documented aliases, and numeric ranks from 100 through 900 resolve to the same canonical weight contract. Missing exact faces use the nearest deterministic measured weight, preview and final ASS request the same rank, JSON records requested and resolved weight diagnostics without local paths, and the existing bold shorthands remain compatible but conflict with an explicit weight.
22. A non-negative pixel or percentage letter-spacing value resolves deterministically from PlayRes pixels or the resolved font size, is reflected in ASS `Spacing`, and is included in the width budget before wrapping and cue splitting. Zero spacing preserves existing output and invalid values fail before model loading.
23. Percentage font size resolves against autorotated render height, so 16:9 and 9:16 inputs with the same output height produce the same resolved font size; pixel values remain absolute PlayRes pixels.
24. `--line-height auto` preserves the measured natural line height. One-line cues without a box retain the single-event ASS path; every nonempty box cue, including one-line cues, uses positioned text lines around one shared measured vector rectangle. Visible font bounds center the text vertically so baseline space does not produce unequal top or bottom padding, and single-line cue text is centered horizontally inside the box while the box retains its requested screen anchor. Explicit `%` and `px` values resolve deterministically, reject values below the natural metric, drive maximum-height capacity, and render multi-line cues with the documented baseline spacing in preview and final video without changing logical SRT/JSON cues.
25. `--opacity` accepts only an explicit percentage from `0%` through `100%`, multiplies every component's existing conventional alpha once with half-up rounding, and produces the same effective text, timed highlight, cue/word backdrop, shadow, and line-height-box palette in preview, retained ASS, and final rendering. `100%` preserves existing output, while opacity never changes SRT text, cue timing, wrapping, placement, or artifact lifecycle.
26. `--text-case` accepts `original`, `uppercase`, or `lowercase` case-insensitively and defaults to `original`. Unicode conversion occurs before measurement and wrapping in preview, ordinary cues, and both timed-word modes; length-changing conversions may alter line/cue breaks without changing source timestamps or word identity. SRT, ASS, preview, and final video use transformed display text, while JSON retains original full/cue text and aligned words and records `display_text` plus requested/resolved mode. Locale-specific casing is not inferred.
27. A clean installation can measure and render every one of the 90 manifest-declared static faces from the eleven bundled OFL families without network access or system font installation. Roboto, Inter, and Montserrat expose weights 100-900; Oswald exposes 200-700 upright; Lora exposes 400-700; and Atkinson Hyperlegible Next exposes 200-800, with upright and italic faces where the family provides them. Anton, Bangers, Press Start 2P, and Russo One each provide Regular 400; Quantico provides 400 and 700 with upright and italic faces. An explicit flat `--fonts-dir` matching the requested internal family wins over a bundled face, the bundled catalog wins over fontconfig, Pillow/RAQM and libass receive the same selected provider directory, and retained JSON records only the provider kind rather than a local resource path.
28. `--template` accepts exactly `default`, `bold-headline`, `amber-word`, `mint-progress`, `focus-marker`, `golden-title`, `emerald-word`, `kinetic-lime`, `coral-marker`, `editorial-reveal`, `headline-bounce`, `yellow-pop`, `yellow-trace`, `neon-lime-marker`, `neon-cyan-reveal`, `neon-magenta-pulse`, `anton-impact`, `bangers-comic`, `press-start-arcade`, `quantico-tech`, and `russo-punch`. Omitted selection equals explicit `default`; every template uses its documented bundled face and typed baseline; explicit flags override one field at a time; preview and final rendering resolve the same presentation on 16:9 and 9:16 inputs, with animation represented by the static state from criterion 17; and JSON records requested/resolved template identity without exposing registry data or asset paths. The removed legacy names are rejected with an actionable invalid-choice diagnostic, and visual parity with the replacements is not promised.
29. Every documented cue and word entrance, emphasis, and exit can be selected without a template and compiles to bounded trusted ASS color, fade, movement, or scale tags. Cue-global and word-relative state remain continuous across aligned-word intervals, positioned visual lines, and shared vector boxes; short phases remain ordered inside their cue or word-effect presentation interval; independently positioned word fragments retain stable measured advances without duplicate glyphs; and static configurations retain their existing ASS event structure for non-box cues while every nonempty box uses one shared measured vector backdrop.
30. `--preview-animation` accepts the same layout/template/text inputs, defaults to a 4-second cue, freezes one uncaptioned frame selected by the optional validated timestamp (default: first frame), emits a silent H.264 MP4 with a 500 ms lead-in and tail at 30 fps, and publishes it collision-safely without JSON, SRT, ASS, or transcription artifacts. The simulated timeline uses the selected first fitting cue, preserves typed display fragments and Unicode units, allocates positive ordered intervals with exact ASS-centisecond conservation, applies deterministic punctuation gaps capped at 20%, and labels optional guides and progress as simulated rather than speech-synchronized. The total duration is the requested cue plus one second within one output frame; even geometry uses `yuv420p`, odd geometry uses `yuv444p`, and unavailable `libx264` fails with actionable guidance. `--preview-animation` does not load an ASR runtime or apply normal translation restrictions, while `--keep-transcriptions` and `--preview-layout` conflicts fail before probing.
31. The packaged template index and resources use schema version 5, contain exactly twenty-one indexed JSON resources including `default`, and accept sparse recognized fields whose omitted values inherit `config.py` semantic defaults. Unknown fields, duplicate keys, unsupported versions, malformed types, invalid animation phases, and index/resource drift fail with contextual `TemplateError`. Sparse resources compile to the same complete immutable runtime configuration as their expanded equivalents; retained transcription JSON remains schema version 3.

    The five display-font templates must pair their real bundled face with a
    coherent palette and motion: an impact entrance and amber accents for Anton,
    ink outline/shadow and word bounce for Bangers, a steady pixel face and
    progressive lime highlighting, 140% line height, and 30% solid black panel
    padding for Press Start 2P, a navy technical panel with coordinated cue
    movement and active-word cyan highlighting over other visible white words
    for Quantico, and 160ms/140ms vertical cue entrance/exit with 100ms coral word
    pops for Russo One. They must retain default margins and two-line capacity
    at common geometries, including after
    vertical-margin changes. Weight names must reflect published font metadata.

32. A user can point \`--template-dir\` at a flat local directory and select a
custom schema-1 JSON by name in both transcription and preview modes. The
reader validates every immediate JSON file, rejects duplicate or unknown
definitions, resolves \`base\` only through the built-in catalog, and records
custom source/base metadata without serializing local paths or raw JSON.

33. Complete Japanese and Chinese character alignments produce deterministic
offline linguistic display groups without changing any original record or
timestamp. Sentence/clause punctuation and 0.45-second pauses provide readable
cue candidates; `なかった`, `デフォルト`, `使用`, simplified `学习`, and
traditional `學習` remain whole when the envelope permits. Progressive and
active-word effects use validated alignment-record intervals with diagnosed
presentation recovery for empty intervals; linguistic groups guide cue/line boundaries but do not merge effect units. A
legal intra-group visual line break preserves every record mapping, while an
exactly timed emergency cue subdivision is diagnosed in retained JSON. Preview
selection may use linguistic groups, but simulated effect units remain a
separate script-appropriate contract, and incomplete mappings retain the
existing static fallback.

34. `--asr` selects WhisperX, Faster-Whisper, Parakeet, or Qwen without
importing unselected runtimes. Existing commands resolve to WhisperX `turbo`.
Each backend validates its model, language, and task before avoidable model
loading, produces the same JSON/SRT/ASS/render pipeline, and records its ASR and
model in retained metadata. WhisperX and Faster-Whisper translations first use
six-second inference chunks and then share a bounded measured-font fallback of
up to three 4% reductions when the translated subtitle envelope overflows.
Parakeet and Qwen3-ASR temporary WAV input is removed after success or failure;
missing native or forced-alignment timestamps produce coarse static cues instead
of invented word timing.

35. `transcribe_speech()` returns source segments and available word records
without selecting subtitle blocks or writing artifacts. Its `SpeechTranscript`
result and lossless version-1 dictionary both feed `render_transcript()` without
another ASR call. SRT and ASS match normal generation for the same source data,
template, and geometry in portrait and landscape, including source whitespace,
point times, missing or partial alignment, and unknown language. Rendering
publishes SRT, ASS, and video together with collision-safe names, reports
unavailable word effects, and leaves no completed files after failure.

36. `--subtitle-file` accepts a local SRT or ASS, renders it unchanged
through FFmpeg/libass into a new collision-safe video, and copies the available
audio. The source video and subtitle file remain unchanged, no transcript
artifacts are created, and invalid or malformed input publishes nothing.

37. Public `build_subtitle_config()` reproduces each built-in/custom baseline
with empty overrides, preserves unrelated fields with sparse overrides, supports
all 57 presentation options with CLI parity, rejects unknown keys and invalid
combinations before media work, and preserves explicit false/valid zero values.
Scoped suppression clears inherited highlight and word decoration when required.
Its immutable result renders through `render_transcript()` for different final
geometries without ASR, transcript mutation, or changes to missing-alignment
fallbacks. Package-root imports and composition remain lazy and perform no
expensive external work.

38. Rendering controls are available from the CLI and Python APIs without
changing existing default FFmpeg graphs. Encoder-specific validation rejects
unsupported presets and invalid quality values before processing, including
in PNG mode. PNG previews accept valid video encoding settings, produce the
same image as without those settings, and never initialize the video encoder.
In video-producing modes, a failed explicit encoder initialization prevents
ASR and artifact generation. Real encodes preserve audio streams, canvas
dimensions, timing, and collision-safe publication in CPU and opt-in NVIDIA
checks. Layout reuses already mapped units at cue subdivision, preserving
source offsets, Unicode break rules, casing transformations, and multilingual
layout results without retaining transcript data in a global cache.

## Constraints and risks

- Model quality, alignment quality, and processing time depend on source audio, selected language, selected model, and available hardware.
- Source-language and timestamp coverage depend on the selected ASR. Automatic
  detection selects one language per run and can be inaccurate for short or
  ambiguous audio. Parakeet does not expose its internal language decision, so
  its language metadata remains null unless the user supplies a label.
- Initial use may require model downloads; temporary connection failures during those downloads are retried, but a stable network connection is still required when assets are not cached.
- FFmpeg installations without ffprobe or subtitle rendering support can prevent expected rendering. Unbundled font families still require an explicit custom directory or a compatible system provider.
- Generated hard subtitles cannot be turned off after the video is created.
- Animation geometry is intentionally fixed; custom phase duration changes its
  speed, and temporary motion or scale may clip at a canvas edge even though the stable
  subtitle envelope remains valid.

## Product decisions

- Favor a local, command-line workflow over hosted processing.
- Favor hard subtitles for a straightforward, portable final-video result.
- Keep generated subtitle artifacts out of the default output; retain JSON, SRT, and ASS together only when the user requests `--keep-transcriptions`.
- Prefer semantic cue boundaries over rigid splitting when the two conflict.
- Prefer one explicit, geometry-resolved native layout baseline over named or
  automatically selected layout profiles.
