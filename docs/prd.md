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

## User journey

1. The user installs the package and FFmpeg.
2. The user invokes multisubs with an input video and optional language, task, model, output directory, appearance, and layout options.
3. The tool transcribes and aligns speech, constructs subtitle cues, and creates JSON, SRT, and ASS files.
4. FFmpeg burns the ASS file into a copy of the input video.
5. The user receives the rendered video and, when requested, the subtitle artifacts in a predictable directory layout.

## Functional requirements

| ID | Requirement |
| --- | --- |
| FR-1 | The CLI must require one input video path and must reject a missing input file. |
| FR-2 | The user must be able to choose an output directory; the current directory is the default. |
| FR-3 | The user must be able to specify a source-language code for which the installed WhisperX release provides a default word-alignment model. |
| FR-4 | The tool must support transcription and translation tasks. Translation output is English. |
| FR-5 | The tool must reject translation with turbo and English-only Whisper models. |
| FR-6 | The tool must generate a JSON transcript with metadata, an SRT subtitle file, and an ASS subtitle file before rendering. |
| FR-7 | Subtitle cues should use word-level alignment when available, favor readable boundaries such as sentence punctuation and meaningful pauses, apply the selected Unicode display casing before measurement, and adapt visual wrapping to the resolved maximum width, maximum height, font metrics, configured letter spacing, and resolved line height when available, without losing transcript content, word timing identity, or creating avoidable orphan lines. When multiple fitting cue boundaries have the same semantic priority, the shared layout should retain the longest fitting prefix. |
| FR-8 | The tool must render the ASS subtitles into a new video with FFmpeg. |
| FR-9 | The user must receive one complete fixed native subtitle presentation by default, be able to select any of sixteen built-in typed presentation templates (`default` plus fifteen curated styles for social video, podcasts, tutorials, and editorial clips), and be able to override each template's appearance, layout, and animation through explicit CLI options, including font family, named or 100-step numeric font weight, unit-bearing font size, non-negative letter spacing, automatic or explicit line height, complete-composition opacity, original/uppercase/lowercase display text, cue backdrop, timed word decoration type/color/size, shadow, margins, maximum width, maximum height, nine named subtitle positions, a global PlayRes X/Y coordinate paired with one of the nine anchors, and independent entrance/emphasis/exit phases for cue text, cue backdrop, word text, and word backdrop. Built-in templates must share default placement and margins, calibrate visible font size against the default bundled Roboto, and provide per-template maximum heights targeting two lines at common video geometries. Explicit overrides may change line capacity. Omitted template selection and explicit `default` must produce the same semantic configuration. Explicit fields must override only their corresponding template fields. Roboto, Inter, Montserrat, Oswald, Lora, and Atkinson Hyperlegible Next must be available from the packaged offline catalog, with explicit custom faces taking precedence over bundled faces and bundled faces taking precedence over fontconfig. Percentage font size must use autorotated render height so horizontal and vertical outputs with the same height resolve to the same size. Opacity must preserve the relative alpha of every visual component. Case conversion must preserve original transcription and aligned-word data in JSON. Named positions must use native ASS alignment and margins. Template fields must behave as baselines rather than explicit option presence for placement conflicts. Explicit inactive vertical margins and every explicitly supplied margin in coordinate mode must fail before probing. Explicit coordinates must require explicit maximum dimensions and reject any complete subtitle envelope that would leave the canvas. |
| FR-9A | The user must be able to provide one flat local directory with --template-dir and select a version-1 custom JSON template by its name through --template. Custom files are validated before probing, inherit only from the packaged built-in catalog through optional base, and may override the same semantic style, layout, and animation fields as built-in baselines. Custom names take precedence within that invocation, including default; the directory is never installed into the package catalog. |
| FR-10 | With --keep-transcriptions, the tool must retain JSON, SRT, and ASS files in a subtitles subdirectory next to the rendered video. |
| FR-11 | Without --keep-transcriptions, a successful run must retain only the rendered video and remove the temporary JSON, SRT, and ASS files after rendering. |
| FR-12 | Generated files and output directories must receive a numeric suffix when a collision would otherwise occur. |
| FR-13 | Invalid arguments and paths must exit with a non-zero status before model loading; processing and rendering failures must also exit non-zero with an actionable diagnostic. |
| FR-14 | Transient connection failures while loading WhisperX model, VAD, or alignment assets must be retried automatically before the processing run is reported as failed. |
| FR-15 | Before model loading, the tool must probe a deterministic video stream and use its autorotated render dimensions consistently for the ASS canvas and FFmpeg subtitle rendering. |
| FR-16 | The user must be able to request a transcription-free layout preview that probes the video, resolves the same appearance, opacity, text case, placement, wrapping, line height, animation configuration, and ASS canvas, renders exactly one collision-safe PNG frame at a validated timestamp, and never creates transcription artifacts or imports WhisperX/PyTorch. The preview must suppress every cue and word motion phase at its stable state. Each progressive word track affects the first half of the displayed cue, while each active-word track affects only its first word, without invented timing. Optional guides must show the relevant native margin region or explicit envelope, anchor or position, resolved line height, opacity, text case, and PlayRes dimensions. |
| FR-17 | The user must be able to select entrance, emphasis, and exit independently for cue text, cue backdrop, word text, and word backdrop, directly or through a template. Cue entrances support `none`, `fade`, four directional slides, `pop`, and `zoom`; cue emphasis supports `none`, `pulse`, `bounce`, `float`, `shake`, `flash`, and `breathe`; cue exits support entrances except `pop`. Word entrances support `none`, `fade`, vertical slides, `pop`, and `zoom`; word text emphasis supports `none`, `highlight`, `pulse`, `bounce`, `float`, and `breathe`; word backdrop emphasis supports the same set except `highlight`; word exits support `none`, `fade`, vertical slides, and `zoom`. Omitted options inherit their template leaves, while explicit `none` disables only the selected phase. Each applicable phase accepts a public duration from 10 through 5000 milliseconds, with explicit CLI duration taking precedence over template and effect defaults. Phases remain relative to their logical cue or aligned-word interval, repeat emphasis deterministically, and shrink when too short without changing timestamps. Word text and backdrop have independent `active-word` or `progressive` timing. A glyph-shaped cue outline remains geometrically attached to its text through cue and word motion. A word decoration becomes visible when its style type is `outline` or `box`, even when all its motion phases are `none`. SRT remains plain; retained schema-version-3 JSON reports all four tracks plus fallback and shortening counts; incomplete word mappings fall back without invented timestamps. Translation is excluded while word text animation or a word decoration is active. |
| FR-18 | The user must be able to request `--preview-animation` instead of `--preview-layout` to export one collision-safe silent MP4 without transcription or speech synthesis. It must reuse the first fitting transformed preview cue, selected template, layout, font metrics, ASS geometry, and production animation compiler. A single uncaptioned frame selected by `--preview-at` is frozen as the background; the timestamp does not affect the animation clock. The cue runs after a 500 ms lead-in and before a 500 ms tail, with a configurable `--preview-duration` from 1 through 15 seconds (default `4s`) accepted as whole milliseconds or seconds. Simulated word units preserve whitespace fragments, punctuation attachment, CJK graphemes, combining marks, and ZWJ clusters; sentence/clause/default gaps are deterministic and capped at 20% of the cue, and weighted integer timing conserves the ASS centisecond interval with positive ordered units. The MP4 contains one 30 fps H.264 video stream, no audio, preserves autorotated geometry, uses a compatible pixel format for odd dimensions, and publishes no JSON, SRT, or ASS. Progress and optional guides must identify timings as simulated rather than speech-synchronized. Language, model, and task do not trigger speech validation in this mode, and `--keep-transcriptions` is rejected. |

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Runtime | Run locally through a Python CLI. Use CUDA when available; otherwise support CPU inference. |
| Compatibility | Require Python 3.10 through 3.13 and a system FFmpeg installation that provides ffprobe and subtitle rendering support; animated preview clips additionally require the `libx264` encoder. Python 3.14 is excluded while WhisperX 3.8.6 declares an upper bound below 3.14. |
| Traceability | Include a schema version, source path, selected language, task, model, creation time, duration, segment count, and resolved video geometry in the JSON output. |
| Usability | Show progress for geometry detection, model loading, transcription, alignment, artifact generation, subtitle rendering, and model-load retries. |
| Safety | Do not overwrite existing output files or directories. |
| Caption readability | Derive line capacity from the fixed maximum-height default or its explicit override, natural/resolved line-height metrics, and decorations with a visible Unicode-estimate fallback; capacity may vary with geometry, but a complete fitting cue remains unbroken, unnecessary one-word final lines are avoided, timed cues split when required, and transcript content is never mutated when shaping differs. |

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

1. A user can install the package, run multisubs --help, and see the supported options.
2. A valid transcription command generates a subtitle-burned video without overwriting existing output.
3. A retained run creates JSON, SRT, and ASS assets under an output subtitles directory.
4. A non-retained successful run leaves only the rendered video and removes its intermediate JSON, SRT, and ASS files.
5. A translation request using turbo or an English-only model is rejected before transcription begins.
6. The JSON output contains metadata and timed subtitle segments.
7. A user can change an exposed semantic appearance option, including letter spacing, or choose a named position and see it reflected in the generated ASS style definition and rendered video without providing raw ASS field names, ASS alignment codes, or ASS color syntax.
8. Invalid input exits non-zero without loading a model, and a failed render does not publish a partial final video.
9. A transient model or alignment connection failure is retried automatically, while a deterministic loading failure is surfaced without unnecessary retries.
10. Landscape, portrait, square, rotated, and non-square-pixel inputs use an ASS canvas matching the dimensions seen by the autorotated FFmpeg render graph.
11. Equivalent percentage-based font and margin values produce equivalent normalized subtitle bounds across supported video resolutions, while pixel values remain fixed in the PlayRes canvas.
12. The default native presentation starts from `bottom-center`, `18%` left/right margins, `0%` top margin, `3%` bottom margin, `100%` maximum width, and `12%` maximum height without classifying the video shape. Each effective explicit named-position, margin, or maximum-dimension option overrides only its corresponding default before native layout validation; explicitly supplied inactive vertical margins fail with an actionable alternative.
13. A custom X/Y coordinate is resolved globally on the autorotated PlayRes canvas; explicitly supplied margins are rejected, retained native defaults do not affect it, the complete maximum-width/maximum-height envelope must fit for the selected anchor, and generated metadata identifies explicit placement without changing SRT text or timing.
14. A cue that fits the width budget with its resolved font and letter spacing remains on one line; when a break is required, equivalent semantic candidates avoid an unnecessary one-word final line, and JSON identifies the resolved font or estimate used.
15. In native mode, a `100%` maximum width means the complete width remaining after horizontal margins. In explicit mode, maximum width and height are required, percentages use the full canvas axes, and invalid anchor coordinates are rejected rather than clamped or moved.
16. Maximum height accounts for measured line height plus backdrop and shadow allowances and produces an internal line capacity of at least one line; increasing the height can increase that capacity without introducing a public maximum-lines option. The same capacity is used by ordinary cue wrapping and transcription-free preview selection.
17. `--preview-layout` accepts the documented timestamp, sample text, appearance, placement, template, and animation options, defaults to the video midpoint or first frame, produces a valid PNG with the probed dimensions, applies collision-safe naming, and cleans temporary ASS/PNG files on success or failure without loading WhisperX/PyTorch. When the sample exceeds the resolved envelope, the PNG contains only the first lexical group that fits the normal cue-layout calculation; among equivalent fitting boundaries it retains the longest prefix, while sentence, clause, pause, and orphan-avoidance priorities remain authoritative. Backdrop and shadow allowances are counted once in the width budget. Text representing later timed cues is omitted from that frame. Motion is suppressed at stable position, scale, and opacity. Each progressive word track statically affects the first half of that cue; each active-word track affects only its first word. No timing tags are generated. `--keep-transcriptions` is rejected in this mode, and optional guides are visibly present only when requested.
18. `--animation-word-text-emphasis highlight` and the `amber-word`, `mint-progress`, `focus-marker`, `kinetic-lime`, `coral-marker`, `yellow-pop`, `yellow-trace`, and `neon-lime-marker` templates enable text highlighting. `--word-backdrop outline|box` and the `focus-marker`, `emerald-word`, `coral-marker`, or `neon-lime-marker` templates enable a measured timed decoration independently of its motion phases. The separate text and backdrop modes control whether prior affected words remain visible (`progressive`) or only the validated current interval is affected (`active-word`). Explicit `none` disables only the selected inherited phase. These combinations preserve line breaks and placement in real ASS/libass renders and leave equivalent untimed output unchanged.
19. Active word text animation or a non-`none` word backdrop rejects translation before probing or model loading in the normal transcription path. Durations are accepted only for duration-bearing effects, must be 10–5000 ms, and follow CLI, template, then effect-default precedence. Incomplete or lossy word mappings render plainly, produce one aggregate warning without transcript text, and record the exact fallback count in JSON.
20. Timed text highlight uses trusted generated color overrides around independently escaped fragments. Word outline or box decoration emits bounded measured ASS events on a layer between the cue backdrop and text; active decorations end with the word, while progressive decorations persist through the cue. Cue text, cue backdrop, word text, and word backdrop sample independent animation tracks without restarting at derived boundaries or duplicating visible glyphs. SRT and JSON contain no generated ASS markup.
21. Named font weights, documented aliases, and numeric ranks from 100 through 900 resolve to the same canonical weight contract. Missing exact faces use the nearest deterministic measured weight, preview and final ASS request the same rank, JSON records requested and resolved weight diagnostics without local paths, and the existing bold shorthands remain compatible but conflict with an explicit weight.
22. A non-negative pixel or percentage letter-spacing value resolves deterministically from PlayRes pixels or the resolved font size, is reflected in ASS `Spacing`, and is included in the width budget before wrapping and cue splitting. Zero spacing preserves existing output and invalid values fail before model loading.
23. Percentage font size resolves against autorotated render height, so 16:9 and 9:16 inputs with the same output height produce the same resolved font size; pixel values remain absolute PlayRes pixels.
24. `--line-height auto` preserves the measured natural line height. One-line cues without a box retain the single-event ASS path; every nonempty box cue, including one-line cues, uses positioned text lines around one shared measured vector rectangle. Visible font bounds center the text vertically so baseline space does not produce unequal top or bottom padding, and single-line cue text is centered horizontally inside the box while the box retains its requested screen anchor. Explicit `%` and `px` values resolve deterministically, reject values below the natural metric, drive maximum-height capacity, and render multi-line cues with the documented baseline spacing in preview and final video without changing logical SRT/JSON cues.
25. `--opacity` accepts only an explicit percentage from `0%` through `100%`, multiplies every component's existing conventional alpha once with half-up rounding, and produces the same effective text, timed highlight, cue/word backdrop, shadow, and line-height-box palette in preview, retained ASS, and final rendering. `100%` preserves existing output, while opacity never changes SRT text, cue timing, wrapping, placement, or artifact lifecycle.
26. `--text-case` accepts `original`, `uppercase`, or `lowercase` case-insensitively and defaults to `original`. Unicode conversion occurs before measurement and wrapping in preview, ordinary cues, and both timed-word modes; length-changing conversions may alter line/cue breaks without changing source timestamps or word identity. SRT, ASS, preview, and final video use transformed display text, while JSON retains original full/cue text and aligned words and records `display_text` plus requested/resolved mode. Locale-specific casing is not inferred.
27. A clean installation can measure and render every one of the 82 manifest-declared static faces from the six bundled OFL families without network access or system font installation. Roboto, Inter, and Montserrat expose weights 100-900; Oswald exposes 200-700 upright; Lora exposes 400-700; and Atkinson Hyperlegible Next exposes 200-800, with upright and italic faces where the family provides them. An explicit flat `--fonts-dir` matching the requested internal family wins over a bundled face, the bundled catalog wins over fontconfig, Pillow/RAQM and libass receive the same selected provider directory, and retained JSON records only the provider kind rather than a local resource path.
28. `--template` accepts exactly `default`, `bold-headline`, `amber-word`, `mint-progress`, `focus-marker`, `golden-title`, `emerald-word`, `kinetic-lime`, `coral-marker`, `editorial-reveal`, `headline-bounce`, `yellow-pop`, `yellow-trace`, `neon-lime-marker`, `neon-cyan-reveal`, and `neon-magenta-pulse`. Omitted selection equals explicit `default`; every template uses its documented bundled face and typed baseline; explicit flags override one field at a time; preview and final rendering resolve the same presentation on 16:9 and 9:16 inputs, with animation represented by the static state from criterion 17; and JSON records requested/resolved template identity without exposing registry data or asset paths. The removed legacy names are rejected with an actionable invalid-choice diagnostic, and visual parity with the replacements is not promised.
29. Every documented cue and word entrance, emphasis, and exit can be selected without a template and compiles to bounded trusted ASS color, fade, movement, or scale tags. Cue-global and word-relative state remain continuous across aligned-word intervals, positioned visual lines, and shared vector boxes; short phases remain ordered inside their original cue or word interval; independently positioned word fragments retain stable measured advances without duplicate glyphs; and static configurations retain their existing ASS event structure for non-box cues while every nonempty box uses one shared measured vector backdrop.
30. `--preview-animation` accepts the same layout/template/text inputs, defaults to a 4-second cue, freezes one uncaptioned frame selected by the validated timestamp, emits a silent H.264 MP4 with a 500 ms lead-in and tail at 30 fps, and publishes it collision-safely without JSON, SRT, ASS, or transcription artifacts. The simulated timeline uses the selected first fitting cue, preserves typed display fragments and Unicode units, allocates positive ordered intervals with exact ASS-centisecond conservation, applies deterministic punctuation gaps capped at 20%, and labels optional guides and progress as simulated rather than speech-synchronized. The total duration is the requested cue plus one second within one output frame; even geometry uses `yuv420p`, odd geometry uses `yuv444p`, and unavailable `libx264` fails with actionable guidance. `--preview-animation` does not load WhisperX/PyTorch or apply normal translation restrictions, while `--keep-transcriptions` and `--preview-layout` conflicts fail before probing.
31. The packaged template index and resources use schema version 5, contain exactly sixteen indexed JSON resources including `default`, and accept sparse recognized fields whose omitted values inherit `config.py` semantic defaults. Unknown fields, duplicate keys, unsupported versions, malformed types, invalid animation phases, and index/resource drift fail with contextual `TemplateError`. Sparse resources compile to the same complete immutable runtime configuration as their expanded equivalents; retained transcription JSON remains schema version 3.

32. A user can point \`--template-dir\` at a flat local directory and select a
custom schema-1 JSON by name in both transcription and preview modes. The
reader validates every immediate JSON file, rejects duplicate or unknown
definitions, resolves \`base\` only through the built-in catalog, and records
custom source/base metadata without serializing local paths or raw JSON.

## Constraints and risks

- Model quality, alignment quality, and processing time depend on source audio, selected language, selected model, and available hardware.
- Source-language selection is limited to languages with a default WhisperX word-alignment model.
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
