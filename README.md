# multisubs

multisubs is a command-line tool that transcribes a local video, creates timed subtitle files, and burns those subtitles into a new video.

It uses WhisperX for transcription and word alignment, then produces JSON, SRT, and ASS artifacts. FFmpeg renders the ASS subtitles into the final video.

## Requirements

- Python 3.10 or newer
- FFmpeg available on your PATH. Its build must support the subtitles filter; builds with libass support are recommended.
- Enough CPU or GPU memory for the selected Whisper model

CUDA is used automatically when PyTorch reports that it is available. CPU runs use int8 inference and can take substantially longer.

## Installation

Create and activate a virtual environment, then install the project:

~~~
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
~~~

Confirm that FFmpeg and the CLI are available:

~~~
ffmpeg -version
multisubs --help
~~~

The first transcription can download model assets required by WhisperX.

## Quick start

Transcribe a Portuguese video, burn the subtitles into a copy, and retain all subtitle artifacts:

~~~
multisubs \
  --input-path ./video.mp4 \
  --lang pt \
  --output-dir ./output \
  --keep-transcriptions
~~~

Translate speech to English with a multilingual non-Turbo Whisper model:

~~~
multisubs \
  --input-path ./interview.mp4 \
  --lang pt \
  --task translate \
  --model medium \
  --output-dir ./output
~~~

Customize subtitle styling:

~~~
multisubs \
  -i ./video.mp4 \
  -l pt \
  -o ./output \
  --style-font "Roboto" \
  --style-font-size 18 \
  --style-bold 1 \
  --style-margin-v 30
~~~

## Command reference

| Option | Default | Description |
| --- | --- | --- |
| -i, --input-path PATH | required | Path to one input video file. |
| -o, --output-dir DIR | current directory | Directory for generated files. |
| -l, --lang CODE | en | Source-language code accepted by Whisper. |
| -t, --task TASK | transcribe | Either transcribe or translate. Translation output is always English. |
| -m, --model MODEL | turbo | Whisper model: tiny.en, tiny, base.en, base, small.en, small, medium.en, medium, large, or turbo. |
| -k, --keep-transcriptions | off | Retain JSON, SRT, and ASS files in a structured output directory. |
| -v, --version | — | Print the package version. |
| -h, --help | — | Show every CLI option and accepted language code. |

Translation cannot use turbo or an English-only model ending in .en. Use a multilingual model such as medium or large instead.

### Style options

Every default ASS style value can be overridden with a --style-* flag. The defaults live in [multisubs/config.py](multisubs/config.py).

| Area | Options |
| --- | --- |
| Font and colors | --style-font, --style-font-size, --style-primary-color, --style-secondary-color, --style-outline-color, --style-back-color |
| Text treatment | --style-bold, --style-italic, --style-underline, --style-strikeout |
| Size and position | --style-scale-x, --style-scale-y, --style-spacing, --style-angle, --style-alignment, --style-margin-l, --style-margin-r, --style-margin-v |
| Border and shadow | --style-border-style, --style-outline-weight, --style-shadow-weight |

Color values are passed through to ASS. Quote values containing shell-significant characters, for example:

~~~
--style-primary-color '&H00FFFFFF'
~~~

## Generated files

For an input named video.mp4 and language pt:

- Without --keep-transcriptions, a successful run leaves output/video-pt.mp4 and output/video-pt.json. The intermediate SRT and ASS files are removed after the video is rendered.
- With --keep-transcriptions, files are organized as output/video/video-pt.mp4 and output/video/subtitles/video-pt.{json,srt,ass}.

If a target file or directory already exists, multisubs adds a numeric suffix such as (1) instead of overwriting it.

The rendered subtitle video contains hard subtitles: they are part of the image and cannot be toggled off in a player. The audio stream is copied during rendering.

See [docs/prd.md](docs/prd.md) for product scope and [docs/architecture.md](docs/architecture.md) for implementation details.

## Current limitations

- The CLI processes one local input video per invocation.
- Translation has a fixed English target.
- There is no interactive subtitle editor or graphical interface.
- FFmpeg, a compatible font, and the selected model must be available on the host system.
