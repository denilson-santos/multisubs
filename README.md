# multisubs

multisubs is a command-line tool that transcribes a local video, creates timed subtitle files, and burns those subtitles into a new video.

It uses WhisperX for transcription and word alignment, then produces JSON, SRT, and ASS artifacts. FFmpeg renders the ASS subtitles into the final video.

## Requirements

- Python 3.10 or newer
- FFmpeg and ffprobe available on your PATH. The FFmpeg build must support the subtitles filter; builds with libass support are recommended. Both executables normally come from the same FFmpeg installation.
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

To install the development and verification tools as well, use:

~~~
python -m pip install -e '.[dev]'
~~~

Confirm that FFmpeg and the CLI are available:

~~~
ffmpeg -version
ffprobe -version
multisubs --help
~~~

The first transcription can download model assets required by WhisperX. If a
model, VAD, or alignment download is interrupted by a temporary connection
failure, multisubs retries that load up to three times with a short
exponential backoff. A stable network connection is still required when the
assets are not already cached.

The default Silero VAD path does not require ONNX Runtime. WhisperX currently
imports an optional Pyannote speaker-embedding module during model setup; this
project isolates that unused import so hosts without a complete Linux DRM
sysfs tree do not show ONNX Runtime's harmless GPU-discovery warning. CUDA
selection remains controlled by PyTorch and is unaffected by this isolation.

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
| -l, --lang CODE | en | Source-language code with a default WhisperX alignment model. |
| -t, --task TASK | transcribe | Either transcribe or translate. Translation output is always English. |
| -m, --model MODEL | turbo | Whisper model: tiny.en, tiny, base.en, base, small.en, small, medium.en, medium, large, or turbo. |
| -k, --keep-transcriptions | off | Retain JSON, SRT, and ASS files in a structured output directory. |
| -v, --version | — | Print the package version. |
| -h, --help | — | Show every CLI option and accepted language code. |

Translation cannot use turbo or an English-only model ending in .en. Use a multilingual model such as medium or large instead.

Supported source-language codes are limited to languages with a default
word-alignment model in the installed WhisperX release:

~~~
ar, ca, cs, da, de, el, en, es, eu, fa, fi, fr, gl, he, hi, hr, hu, id,
it, ja, ka, ko, lv, ml, nl, nn, no, pl, pt, ro, ru, sk, sl, sv, te, tl,
tr, uk, ur, vi, zh
~~~

### Style options

Every exposed default ASS appearance value can be overridden with a --style-*
flag. The defaults live in [multisubs/config.py](multisubs/config.py).

| Area | Options |
| --- | --- |
| Font and colors | --style-font, --style-font-size, --style-primary-color, --style-secondary-color, --style-outline-color, --style-back-color |
| Text treatment | --style-bold, --style-italic, --style-underline, --style-strikeout |
| Size and position | --style-scale-x, --style-scale-y, --style-spacing, --style-angle, --style-margin-l, --style-margin-r, --style-margin-v |
| Border and shadow | --style-border-style, --style-outline-weight, --style-shadow-weight |

Color values are passed through to ASS. Quote values containing shell-significant characters, for example:

~~~
--style-primary-color '&H00FFFFFF'
~~~

Style values are validated before model loading. Colors must use ASS hexadecimal
notation (`&H` followed by 6 or 8 hexadecimal digits), numeric values must be
finite and in their supported ranges, and font names cannot contain commas or
line breaks.

### Relative layout units

The typed layout options accept an explicit unit suffix:

| Option | Percentage basis |
| --- | --- |
| `--font-size` | Shorter autorotated render edge |
| `--backdrop-size`, `--shadow-size` | Resolved font size |
| `--margin-left`, `--margin-right` | Render width |
| `--margin-top`, `--margin-bottom` | Render height |

Use `%` for resolution-independent values or `px` for fixed PlayRes pixels:

~~~
multisubs -i ./video.mp4 --font-size 4.5% --margin-left 8% \
  --margin-right 8% --margin-bottom 72px
~~~

Bare numbers, signs, exponent notation, and excessive precision are rejected.
Percentages are rounded deterministically to the nearest PlayRes pixel, with
half values rounded up. Geometry-dependent validation runs after ffprobe and
before WhisperX. During the transition to the final layout CLI, matching
semantic options take precedence over their temporary `--style-*` adapter
values.

### Subtitle positions

Use `--position` to choose a semantic screen anchor. The default is
`bottom-center`.

| `top-left` | `top-center` | `top-right` |
| --- | --- | --- |
| `middle-left` | `center` | `middle-right` |
| `bottom-left` | `bottom-center` | `bottom-right` |

Left and right are physical screen directions, not language-relative start and
end values. Numeric ASS alignment codes are private implementation details;
`--style-alignment` is not a supported option.

## Generated files

For an input named video.mp4 and language pt:

- Without --keep-transcriptions, a successful run leaves output/video-pt.mp4 and output/video-pt.json. The intermediate SRT and ASS files are removed after the video is rendered.
- With --keep-transcriptions, files are organized as output/video/video-pt.mp4 and output/video/subtitles/video-pt.{json,srt,ass}.

If a target file or directory already exists, multisubs adds a numeric suffix such as (1) instead of overwriting it.

Transcription and rendering first run in a private temporary directory inside
the requested output directory. Completed artifacts are published only after
FFmpeg succeeds. If processing fails, the temporary directory is retained so
the generated artifacts and the original error context remain available for
diagnosis.

The rendered subtitle video contains hard subtitles: they are part of the image and cannot be toggled off in a player. Available audio streams are copied during rendering; video-only inputs are supported.

Before loading WhisperX, multisubs uses ffprobe to select the first usable video
stream and determine the frame dimensions used by FFmpeg's autorotated render
graph. Generated ASS files declare those displayed dimensions as PlayResX and
PlayResY. Right-angle rotation swaps the canvas axes, while sample aspect ratio
is retained when calculating the displayed aspect ratio. The selected stream,
coded and render dimensions, rotation, aspect ratios, and container duration are
recorded under `metadata.rendering` in the versioned JSON transcript. Relative
layout options record both their requested strings and resolved PlayRes pixels.

See [docs/prd.md](docs/prd.md) for product scope and [docs/architecture.md](docs/architecture.md) for implementation details.

## Exit status and verification

The command exits with status `0` after a successful render, `2` for invalid
arguments or paths, and `1` for dependency, transcription, artifact, or FFmpeg
failures. Normal progress is written to standard output; diagnostics are sent
to standard error.

The default development checks are:

~~~
python -m compileall multisubs
ruff format --check .
ruff check .
pyright
python -m pytest
python -m build
twine check dist/*
~~~

## Current limitations

- The CLI processes one local input video per invocation.
- Translation has a fixed English target.
- There is no interactive subtitle editor or graphical interface.
- FFmpeg, ffprobe, a compatible font, and the selected model must be available on the host system.
