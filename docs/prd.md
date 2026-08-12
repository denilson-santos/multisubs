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
5. Provide basic ASS style control from the command line.
6. Avoid overwriting a user's existing files.

## User journey

1. The user installs the package and FFmpeg.
2. The user invokes multisubs with an input video and optional language, task, model, output directory, and style options.
3. The tool transcribes and aligns speech, constructs subtitle cues, and creates JSON, SRT, and ASS files.
4. FFmpeg burns the ASS file into a copy of the input video.
5. The user receives the rendered video and, when requested, the subtitle artifacts in a predictable directory layout.

## Functional requirements

| ID | Requirement |
| --- | --- |
| FR-1 | The CLI must require one input video path and must reject a missing input file. |
| FR-2 | The user must be able to choose an output directory; the current directory is the default. |
| FR-3 | The user must be able to specify a supported source-language code. |
| FR-4 | The tool must support transcription and translation tasks. Translation output is English. |
| FR-5 | The tool must reject translation with turbo and English-only Whisper models. |
| FR-6 | The tool must generate a JSON transcript with metadata, an SRT subtitle file, and an ASS subtitle file before rendering. |
| FR-7 | Subtitle cues should use word-level alignment when available and favor readable boundaries such as sentence punctuation and meaningful pauses. |
| FR-8 | The tool must render the ASS subtitles into a new video with FFmpeg. |
| FR-9 | The user must be able to override the default ASS styling through CLI flags. |
| FR-10 | With --keep-transcriptions, the tool must retain JSON, SRT, and ASS files in a subtitles subdirectory next to the rendered video. |
| FR-11 | Without --keep-transcriptions, a successful run must retain the JSON transcript and remove the temporary SRT and ASS files after rendering. |
| FR-12 | Generated files and output directories must receive a numeric suffix when a collision would otherwise occur. |

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Runtime | Run locally through a Python CLI. Use CUDA when available; otherwise support CPU inference. |
| Compatibility | Require Python 3.10 or newer and a system FFmpeg installation with subtitle rendering support. |
| Traceability | Include source path, selected language, task, model, creation time, duration, and segment count in the JSON output. |
| Usability | Show progress for model loading, transcription, alignment, artifact generation, and subtitle rendering. |
| Safety | Do not overwrite existing output files or directories. |
| Caption readability | Aim for at most two subtitle lines, with a preferred line length of 42 characters and timing-aware cue splitting. |

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
7. A user can change an exposed style option and see it reflected in the generated ASS style definition and rendered video.

## Constraints and risks

- Model quality, alignment quality, and processing time depend on source audio, selected language, selected model, and available hardware.
- Initial use may require model downloads.
- FFmpeg builds without the required subtitle rendering support, or hosts without the requested font, can prevent expected rendering.
- Generated hard subtitles cannot be turned off after the video is created.

## Product decisions

- Favor a local, command-line workflow over hosted processing.
- Favor hard subtitles for a straightforward, portable final-video result.
- Retain JSON by default because it is a compact, machine-readable record of the transcription; make SRT and ASS retention opt-in to avoid clutter.
- Prefer semantic cue boundaries over rigid splitting when the two conflict.
