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
| FR-7 | Subtitle cues should use word-level alignment when available, favor readable boundaries such as sentence punctuation and meaningful pauses, apply the selected Unicode display casing before measurement, and adapt visual wrapping to the resolved maximum width, maximum height, font metrics, configured letter spacing, and resolved line height when available, without losing transcript content, word timing identity, or creating avoidable orphan lines. |
| FR-8 | The tool must render the ASS subtitles into a new video with FFmpeg. |
| FR-9 | The user must receive one complete fixed native subtitle layout by default and be able to override its appearance and layout through explicit CLI options, including font family, named or 100-step numeric font weight, unit-bearing font size, non-negative letter spacing, automatic or explicit line height, complete-composition opacity, original/uppercase/lowercase display text, backdrop, shadow, margins, maximum width, maximum height, nine named subtitle positions, or a global PlayRes X/Y coordinate paired with one of the nine anchors. Opacity must preserve the relative alpha of every visual component. Case conversion must preserve original transcription and aligned-word data in JSON. Named positions must use native ASS alignment and margins. Position changes must not apply hidden margin or maximum-dimension values. Explicit coordinates must ignore margins, require explicit maximum dimensions, and reject any complete subtitle envelope that would leave the canvas. |
| FR-10 | With --keep-transcriptions, the tool must retain JSON, SRT, and ASS files in a subtitles subdirectory next to the rendered video. |
| FR-11 | Without --keep-transcriptions, a successful run must retain only the rendered video and remove the temporary JSON, SRT, and ASS files after rendering. |
| FR-12 | Generated files and output directories must receive a numeric suffix when a collision would otherwise occur. |
| FR-13 | Invalid arguments and paths must exit with a non-zero status before model loading; processing and rendering failures must also exit non-zero with an actionable diagnostic. |
| FR-14 | Transient connection failures while loading WhisperX model, VAD, or alignment assets must be retried automatically before the processing run is reported as failed. |
| FR-15 | Before model loading, the tool must probe a deterministic video stream and use its autorotated render dimensions consistently for the ASS canvas and FFmpeg subtitle rendering. |
| FR-16 | The user must be able to request a transcription-free layout preview that probes the video, resolves the same appearance, opacity, text case, placement, wrapping, line-height, and ASS canvas, renders exactly one collision-safe PNG frame at a validated timestamp, and never creates transcription artifacts or imports WhisperX/PyTorch. Optional guides must show the relevant native margin region or explicit envelope, anchor or position, resolved line-height, opacity, text case, and PlayRes dimensions. |
| FR-17 | The user must be able to opt into word-timed karaoke highlighting for source-language transcription and select progressive or active-word mode. Progressive mode must keep prior words highlighted after their validated starts; active-word mode must highlight only the current validated word interval and leave pauses normal. SRT must remain plain, JSON must report the resolved mode/effect and per-cue fallback count, and incomplete mappings must fall back without invented timestamps. Translation, preview-only samples, and richer animated karaoke styles are excluded. |

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Runtime | Run locally through a Python CLI. Use CUDA when available; otherwise support CPU inference. |
| Compatibility | Require Python 3.10 through 3.13 and a system FFmpeg installation that provides ffprobe and subtitle rendering support. Python 3.14 is excluded while WhisperX 3.8.6 declares an upper bound below 3.14. |
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
- Syllable-, phoneme-, character-, sweep-, fade-, bounce-, line-level, or other animated karaoke effects beyond progressive and active-word color highlighting.
- Karaoke on translated output or transcription-free previews, because neither path has a lossless source-word timing map.

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
12. Every native invocation starts from `bottom-center`, `6%` left/right/bottom margins, a `0%` top margin, `100%` maximum width, and `10.5%` maximum height without classifying the video shape. Each explicit named-position, margin, or maximum-dimension option overrides only its corresponding default before native layout validation.
13. A custom X/Y coordinate is resolved globally on the autorotated PlayRes canvas; margins do not affect it, the complete maximum-width/maximum-height envelope must fit for the selected anchor, and generated metadata identifies explicit placement without changing SRT text or timing.
14. A cue that fits the width budget with its resolved font and letter spacing remains on one line; when a break is required, equivalent semantic candidates avoid an unnecessary one-word final line, and JSON identifies the resolved font or estimate used.
15. In native mode, a `100%` maximum width means the complete width remaining after horizontal margins. In explicit mode, maximum width and height are required, percentages use the full canvas axes, and invalid anchor coordinates are rejected rather than clamped or moved.
16. Maximum height accounts for measured line height plus backdrop and shadow allowances and produces an internal line capacity of at least one line; increasing the height can increase that capacity without introducing a public maximum-lines option.
17. `--preview-layout` accepts the documented timestamp, sample text, appearance, and placement options, defaults to the video midpoint or first frame, produces a valid PNG with the probed dimensions, applies collision-safe naming, and cleans temporary ASS/PNG files on success or failure without loading WhisperX/PyTorch. When the sample exceeds the resolved envelope, the PNG contains only the first lexical group that fits the normal cue-layout calculation; text representing later timed cues is omitted from that frame. `--keep-transcriptions` is rejected in this mode, and optional guides are visibly present only when requested.
18. `--karaoke` is opt-in and defaults to progressive mode, which highlights eligible displayed words at quantized aligned starts and keeps prior words highlighted. `--karaoke-mode active-word` uses validated word ends, caps overlaps at the next word start, resets prior words, and leaves pauses in the normal color. Both modes preserve line breaks and placement in real ASS/libass renders and leave equivalent non-karaoke output unchanged.
19. Karaoke rejects translation and meaningless color-only combinations before probing or model loading; incomplete or lossy cues render plainly, produce one aggregate warning without transcript text, and record the exact fallback count in JSON.
20. Progressive karaoke ASS contains trusted generated color and `\k` overrides around independently escaped transcript fragments; active-word ASS uses trusted color overrides in adjacent, non-overlapping full-cue events. SRT and JSON contain no generated ASS markup in either mode.
21. Named font weights, documented aliases, and numeric ranks from 100 through 900 resolve to the same canonical weight contract. Missing exact faces use the nearest deterministic measured weight, preview and final ASS request the same rank, JSON records requested and resolved weight diagnostics without local paths, and the existing bold shorthands remain compatible but conflict with an explicit weight.
22. A non-negative pixel or percentage letter-spacing value resolves deterministically from PlayRes pixels or the resolved font size, is reflected in ASS `Spacing`, and is included in the width budget before wrapping and cue splitting. Zero spacing preserves existing output and invalid values fail before model loading.
23. `--line-height auto` preserves the measured natural line height and existing ASS event structure. Explicit `%` and `px` values resolve deterministically, reject values below the natural metric, drive maximum-height capacity, and render multi-line cues with the documented baseline spacing in preview and final video without changing logical SRT/JSON cues.
24. `--opacity` accepts only an explicit percentage from `0%` through `100%`, multiplies every component's existing conventional alpha once with half-up rounding, and produces the same effective text, karaoke, backdrop/outline, shadow, and line-height-box palette in preview, retained ASS, and final rendering. `100%` preserves existing output, while opacity never changes SRT text, cue timing, wrapping, placement, or artifact lifecycle.
25. `--text-case` accepts `original`, `uppercase`, or `lowercase` case-insensitively and defaults to `original`. Unicode conversion occurs before measurement and wrapping in preview, ordinary cues, and both karaoke modes; length-changing conversions may alter line/cue breaks without changing source timestamps or word identity. SRT, ASS, preview, and final video use transformed display text, while JSON retains original full/cue text and aligned words and records `display_text` plus requested/resolved mode. Locale-specific casing is not inferred.

## Constraints and risks

- Model quality, alignment quality, and processing time depend on source audio, selected language, selected model, and available hardware.
- Source-language selection is limited to languages with a default WhisperX word-alignment model.
- Initial use may require model downloads; temporary connection failures during those downloads are retried, but a stable network connection is still required when assets are not cached.
- FFmpeg installations without ffprobe or subtitle rendering support, or hosts without the requested font, can prevent expected rendering.
- Generated hard subtitles cannot be turned off after the video is created.

## Product decisions

- Favor a local, command-line workflow over hosted processing.
- Favor hard subtitles for a straightforward, portable final-video result.
- Keep generated subtitle artifacts out of the default output; retain JSON, SRT, and ASS together only when the user requests `--keep-transcriptions`.
- Prefer semantic cue boundaries over rigid splitting when the two conflict.
- Prefer one explicit, geometry-resolved native layout baseline over named or
  automatically selected layout profiles.
