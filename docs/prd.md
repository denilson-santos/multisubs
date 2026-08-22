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
| FR-7 | Subtitle cues should use word-level alignment when available, favor readable boundaries such as sentence punctuation and meaningful pauses, and adapt visual wrapping to the resolved layout width, resolved-font metrics when available, and line limit without losing transcript content or creating avoidable orphan lines. |
| FR-8 | The tool must render the ASS subtitles into a new video with FFmpeg. |
| FR-9 | The user must be able to select a complete subtitle layout preset (`auto`, `landscape`, `portrait`, `square`, `vertical-social`, `upper-third`, or `centered`) and override its appearance and layout through explicit CLI options, including unit-bearing font, backdrop, shadow, margin, and maximum-width values, nine named subtitle positions, or a safe-area-local custom X/Y coordinate paired with one of the nine anchors. Margins define the safe containing rectangle; percentage maximum width and custom coordinates resolve inside it. |
| FR-10 | With --keep-transcriptions, the tool must retain JSON, SRT, and ASS files in a subtitles subdirectory next to the rendered video. |
| FR-11 | Without --keep-transcriptions, a successful run must retain the JSON transcript and remove the temporary SRT and ASS files after rendering. |
| FR-12 | Generated files and output directories must receive a numeric suffix when a collision would otherwise occur. |
| FR-13 | Invalid arguments and paths must exit with a non-zero status before model loading; processing and rendering failures must also exit non-zero with an actionable diagnostic. |
| FR-14 | Transient connection failures while loading WhisperX model, VAD, or alignment assets must be retried automatically before the processing run is reported as failed. |
| FR-15 | Before model loading, the tool must probe a deterministic video stream and use its autorotated render dimensions consistently for the ASS canvas and FFmpeg subtitle rendering. |

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Runtime | Run locally through a Python CLI. Use CUDA when available; otherwise support CPU inference. |
| Compatibility | Require Python 3.10 through 3.13 and a system FFmpeg installation that provides ffprobe and subtitle rendering support. Python 3.14 is excluded while WhisperX 3.8.6 declares an upper bound below 3.14. |
| Traceability | Include a schema version, source path, selected language, task, model, creation time, duration, segment count, and resolved video geometry in the JSON output. |
| Usability | Show progress for geometry detection, model loading, transcription, alignment, artifact generation, subtitle rendering, and model-load retries. |
| Safety | Do not overwrite existing output files or directories. |
| Caption readability | Aim for at most two subtitle lines using resolved-font metrics with a visible Unicode-estimate fallback, keep a complete fitting cue unbroken, avoid unnecessary one-word final lines, split timed cues when required, and never mutate transcript content when shaping differs. |

## Out of scope

- A graphical or web interface.
- Batch orchestration for multiple input videos in one command.
- An interactive subtitle editor or human review workflow.
- Selectable translation target languages; English is the only translation target.
- Soft subtitle tracks that can be enabled or disabled in a video player.
- Speaker diarization, speaker labels, or subtitle speaker styling.

## Acceptance criteria

1. A user can install the package, run multisubs --help, and see the supported options.
2. A valid transcription command generates a subtitle-burned video without overwriting existing output.
3. A retained run creates JSON, SRT, and ASS assets under an output subtitles directory.
4. A non-retained successful run leaves the rendered video and JSON transcript while removing its intermediate SRT and ASS files.
5. A translation request using turbo or an English-only model is rejected before transcription begins.
6. The JSON output contains metadata and timed subtitle segments.
7. A user can change an exposed semantic appearance option or choose a named position and see it reflected in the generated ASS style definition and rendered video without providing ASS field names, numeric codes, or ASS color syntax.
8. Invalid input exits non-zero without loading a model, and a failed render does not publish a partial final video.
9. A transient model or alignment connection failure is retried automatically, while a deterministic loading failure is surfaced without unnecessary retries.
10. Landscape, portrait, square, rotated, and non-square-pixel inputs use an ASS canvas matching the dimensions seen by the autorotated FFmpeg render graph.
11. Equivalent percentage-based font and margin values produce equivalent normalized subtitle bounds across supported video resolutions, while pixel values remain fixed in the PlayRes canvas.
12. `--layout auto` classifies the autorotated render canvas using the documented aspect-ratio bands, and explicit position or margin options override only their corresponding preset fields before safe-area validation.
13. A custom X/Y coordinate is resolved locally inside the selected safe rectangle and then converted to the autorotated PlayRes canvas; the anchor stays inside that rectangle and both coordinate spaces appear clearly in generated metadata without changing SRT text or timing.
14. A cue that fits the width budget with its resolved font remains on one line; when a break is required, equivalent semantic candidates avoid an unnecessary one-word final line, and JSON identifies the resolved font or estimate used.
15. A `100%` maximum width means the complete width remaining after horizontal margins; the effective wrapping budget is then limited only by that ceiling and the space available from the selected anchor to the safe-area edges.

## Constraints and risks

- Model quality, alignment quality, and processing time depend on source audio, selected language, selected model, and available hardware.
- Source-language selection is limited to languages with a default WhisperX word-alignment model.
- Initial use may require model downloads; temporary connection failures during those downloads are retried, but a stable network connection is still required when assets are not cached.
- FFmpeg installations without ffprobe or subtitle rendering support, or hosts without the requested font, can prevent expected rendering.
- Generated hard subtitles cannot be turned off after the video is created.

## Product decisions

- Favor a local, command-line workflow over hosted processing.
- Favor hard subtitles for a straightforward, portable final-video result.
- Retain JSON by default because it is a compact, machine-readable record of the transcription; make SRT and ASS retention opt-in to avoid clutter.
- Prefer semantic cue boundaries over rigid splitting when the two conflict.
