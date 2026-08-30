<div align="center">

# 🎬 multisubs

**Transcribe, style, preview, and burn subtitles into local videos from one CLI.**

[![Python 3.10–3.13](https://img.shields.io/badge/Python-3.10%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Latest release](https://img.shields.io/github/v/release/denilson-santos/multisubs?label=release)](https://github.com/denilson-santos/multisubs/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

multisubs turns a local video into a new video with hard subtitles. It uses
[WhisperX](https://github.com/m-bain/whisperX) for transcription and word-level
alignment, creates JSON, SRT, and ASS assets, and renders the final result with
FFmpeg.

Your media stays on your machine. A network connection is needed only when
WhisperX must download model assets that are not already cached.

## ✨ Highlights

| Feature | What it gives you |
| --- | --- |
| 🗣️ Transcription and translation | Word-aligned transcription in supported languages, or translation to English. |
| 🎨 Semantic styling | Font, weight, size, letter spacing, line height, colors, opacity, casing, backdrop, and shadow controls. |
| 📐 Responsive layouts | Presets for landscape, portrait, square, social, upper-third, and centered compositions. |
| 🎯 Precise placement | Nine semantic positions, relative units, margins, safe envelopes, and exact PlayRes coordinates. |
| 👀 Fast previews | Render one subtitle preview frame without loading WhisperX or transcribing the video. |
| 🎤 Karaoke | Progressive or active-word highlighting based on aligned word timestamps. |
| 🧠 Adaptive wrapping | Font-aware wrapping that favors readable language and timing boundaries. |
| 🛡️ Safe outputs | Collision-safe names and temporary rendering prevent existing or partial files from being overwritten. |

```text
video ──► WhisperX transcription ──► JSON + SRT + ASS ──► FFmpeg ──► subtitled video
  └──────────────────── preview layout without transcription ────────────────────┘
```

## 📋 Requirements

- Python 3.10 through 3.13. WhisperX 3.8.6 does not support Python 3.14.
- FFmpeg and ffprobe available on `PATH`.
- An FFmpeg build with the `subtitles` filter; libass support is recommended.
- Enough CPU or GPU memory for the selected Whisper model.

CUDA with float16 is selected automatically when PyTorch reports an available
GPU. CPU runs use int8 inference and can take substantially longer.

## 📦 Installation

Create an isolated environment and install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Install development tools with:

```bash
python -m pip install -e '.[dev]'
```

Confirm that the required commands are available:

```bash
ffmpeg -version
ffprobe -version
multisubs --help
```

The first run may download Whisper, voice-activity detection, and alignment
models. Temporary connection failures during those downloads are retried up to
three times.

## 🚀 Quick start

Transcribe a Portuguese video and keep every subtitle artifact:

```bash
multisubs \
  --input-path ./video.mp4 \
  --lang pt \
  --output-dir ./output \
  --keep-transcriptions
```

Short options are available for the most common arguments:

```bash
multisubs -i ./video.mp4 -l pt -o ./output -k
```

The result contains hard subtitles: they become part of the video image and
cannot be disabled in a player. Available audio streams are copied to the new
video.

## 🧰 Common recipes

### Translate speech to English

Translation requires a multilingual, non-Turbo Whisper model:

```bash
multisubs \
  -i ./interview.mp4 \
  -l pt \
  --task translate \
  --model medium \
  -o ./output
```

Translation output is always English. `turbo` and model names ending in `.en`
cannot be used with `--task translate`.

### Preview a layout before transcribing

Generate one PNG from a real video frame without loading WhisperX:

```bash
multisubs -i ./video.mp4 -o ./previews \
  --preview-layout \
  --preview-at 00:00:10.500 \
  --preview-text "This is how my subtitle will look" \
  --preview-guides \
  --layout landscape \
  --position bottom-center
```

Without `--preview-at`, the video midpoint is used. Preview styling, wrapping,
placement, coordinates, and custom fonts match the final render path. Output is
saved as `<video-stem>-subtitle-preview.png` with a numeric suffix when needed.

### Add word-timed karaoke

Progressively keep spoken words highlighted:

```bash
multisubs -i ./video.mp4 -l pt \
  --karaoke \
  --karaoke-highlight-color '#FFD54F'
```

Highlight only the currently spoken word:

```bash
multisubs -i ./video.mp4 -l pt \
  --karaoke \
  --karaoke-mode active-word
```

Karaoke works only with source-language transcription. It cannot be combined
with translation or layout preview because those paths do not provide a
lossless source-word timing map. Cues with incomplete timing data fall back to
normal subtitles instead of receiving invented timestamps.

### Customize typography

```bash
multisubs -i ./video.mp4 -l pt \
  --font "Roboto" \
  --font-weight semi-bold \
  --font-size 4.5% \
  --letter-spacing 1px \
  --line-height 125% \
  --text-case uppercase \
  --text-color '#F8FAFC' \
  --opacity 90% \
  --backdrop outline \
  --backdrop-color '#0F172AB3' \
  --margin-bottom 8%
```

Colors use `#RRGGBB` or `#RRGGBBAA`, where `00` is transparent and `FF` is
opaque. Quote colors in the shell because `#` may start a comment.

The typography controls added in 2.2.0 include:

- `--font-weight`: named weights or numeric ranks from 100 through 900.
- `--letter-spacing`: non-negative tracking in `%` or PlayRes `px`.
- `--line-height`: `auto`, a percentage of the natural line height, or PlayRes
  pixels.
- `--opacity`: multiplies the alpha of text, backdrop, shadow, and karaoke
  highlighting without changing layout.
- `--text-case`: `original`, `uppercase`, or `lowercase`, applied before
  measurement and wrapping.

JSON keeps the original transcript and aligned words even when the displayed
case changes.

## ⚙️ Command reference

Run `multisubs --help` for the parser's complete, authoritative help text.

### Input and processing

| Option | Default | Description |
| --- | --- | --- |
| `-i`, `--input-path PATH` | required | Path to one local input video. |
| `-o`, `--output-dir DIR` | current directory | Directory for generated files. |
| `-l`, `--lang CODE` | `en` | Source-language code with a WhisperX alignment model. |
| `-t`, `--task TASK` | `transcribe` | `transcribe` or translate speech to English. |
| `-m`, `--model MODEL` | `turbo` | Whisper model used for processing. |
| `-k`, `--keep-transcriptions` | off | Keep JSON, SRT, and ASS in a `subtitles` directory. |
| `-v`, `--version` | — | Print the package version. |
| `-h`, `--help` | — | Show CLI help and supported language codes. |

Supported models: `tiny.en`, `tiny`, `base.en`, `base`, `small.en`, `small`,
`medium.en`, `medium`, `large`, and `turbo`.

### Preview and effects

| Option | Default | Description |
| --- | --- | --- |
| `--preview-layout` | off | Render one layout preview PNG without transcription. |
| `--preview-at HH:MM:SS.mmm` | video midpoint | Select the frame used by the preview. |
| `--preview-text TEXT` | sample text | Replace the preview subtitle text. |
| `--preview-guides` | off | Draw placement, envelope, and canvas guides. |
| `--karaoke` | off | Enable aligned word highlighting. |
| `--karaoke-mode MODE` | `progressive` when enabled | Use `progressive` or `active-word`. |
| `--karaoke-highlight-color COLOR` | `#FFD54F` | Set the karaoke highlight color. |

### Appearance

| Option | Default | Description |
| --- | --- | --- |
| `--font NAME` | `Roboto` | Subtitle font family. |
| `--font-size LENGTH` | `4%` | Size relative to the shorter render edge, or PlayRes pixels. |
| `--font-weight WEIGHT` | `regular` (`400`) | Named or numeric weight from 100 through 900. |
| `--bold`, `--no-bold` | off | Compatibility shorthand for weight 700 or 400. |
| `--italic`, `--no-italic` | off | Enable or disable italic text. |
| `--letter-spacing LENGTH` | `0px` | Extra spacing between rendered grapheme clusters. |
| `--line-height auto\|LENGTH` | `auto` | Baseline distance for multi-line subtitles. |
| `--text-color COLOR` | `#FFFFFF` | Subtitle text color. |
| `--opacity PERCENT` | `100%` | Opacity multiplier for the complete composition. |
| `--text-case MODE` | `original` | `original`, `uppercase`, or `lowercase`. |
| `--backdrop KIND` | `box` | `none`, `outline`, or `box`. |
| `--backdrop-color COLOR` | `#00000099` | Outline, box, and shadow color. |
| `--backdrop-size LENGTH` | `0px` | Outline thickness or box padding. |
| `--shadow-size LENGTH` | `4%` | Shadow size relative to the resolved font size or in pixels. |
| `--fonts-dir DIR` | — | Additional `.ttf`, `.otf`, or `.ttc` fonts for this run. |

Font-weight names are `thin`, `extra-light`, `light`, `regular`, `medium`,
`semi-bold`, `bold`, `extra-bold`, and `black`. Their numeric equivalents are
100 through 900 in steps of 100. The closest available face is selected when a
font family does not contain the exact requested weight.

`--fonts-dir` does not install fonts on the host. It gives both font measurement
and FFmpeg/libass access to the same controlled directory, which improves
wrapping consistency across machines.

### Layout and positioning

| Option | Default | Description |
| --- | --- | --- |
| `--layout PRESET` | `auto` | Complete layout preset. |
| `--position POSITION` | preset value | Override the preset's semantic position. |
| `--margin-left LENGTH` | preset value | Native ASS left margin. |
| `--margin-right LENGTH` | preset value | Native ASS right margin. |
| `--margin-top LENGTH` | preset value | Native ASS top margin. |
| `--margin-bottom LENGTH` | preset value | Native ASS bottom margin. |
| `--max-width LENGTH` | preset value | Maximum subtitle width. |
| `--max-height LENGTH` | preset value | Maximum height used to derive line capacity. |
| `--position-x LENGTH` | — | Explicit global PlayRes X coordinate. |
| `--position-y LENGTH` | — | Explicit global PlayRes Y coordinate. |
| `--anchor POSITION` | — | Subtitle-box anchor for explicit coordinates. |

Available presets:

| Preset | Default placement |
| --- | --- |
| `auto` | Chooses landscape, portrait, or square from the rendered video shape. |
| `landscape` | Bottom center with 6% side and bottom insets. |
| `portrait` | Bottom center with 8% side and bottom insets. |
| `square` | Bottom center with 7% side and bottom insets. |
| `vertical-social` | Bottom center with asymmetric social-video-safe insets. |
| `upper-third` | Top center with 6% side and 8% top insets. |
| `centered` | Center with 8% insets. |

Available semantic positions:

| `top-left` | `top-center` | `top-right` |
| --- | --- | --- |
| `middle-left` | `center` | `middle-right` |
| `bottom-left` | `bottom-center` | `bottom-right` |

All layout lengths require an explicit `%` or `px` suffix. Percentages remain
resolution-aware; pixels refer to the generated ASS PlayRes canvas.

| Option | Percentage basis |
| --- | --- |
| `--font-size` | Shorter autorotated render edge. |
| `--letter-spacing` | Resolved font size. |
| `--line-height` | Natural measured font line height. |
| `--backdrop-size`, `--shadow-size` | Resolved font size. |
| `--margin-left`, `--margin-right` | Render width. |
| `--margin-top`, `--margin-bottom` | Render height. |
| `--max-width` | Native: width after side margins; explicit: render width. |
| `--max-height` | Native: height after the active vertical margin; explicit: render height. |
| `--position-x`, `--position-y` | Render width and height, respectively. |

### Exact coordinates

Use X and Y together to attach an anchor on the subtitle box to a global point:

```bash
multisubs -i ./video.mp4 \
  --position-x 50% \
  --position-y 86% \
  --anchor bottom-center \
  --max-width 60% \
  --max-height 20%
```

Explicit coordinates require `--position-x`, `--position-y`, `--anchor`,
`--max-width`, and `--max-height`. They cannot be combined with `--position`,
and margins are ignored. The complete anchored envelope must fit inside the
canvas; invalid coordinates are rejected instead of being moved or clipped.

### Adaptive wrapping

multisubs measures the selected font with Pillow and RAQM when a concrete face
is available. Otherwise, it uses a Unicode-aware width estimate. Wrapping takes
font size, weight, letter spacing, line height, maximum dimensions, backdrop,
and shadow into account.

Readable punctuation and timing boundaries are preferred. Text is never
truncated, and long indivisible tokens remain intact even when they exceed the
estimated width. SRT and ASS receive the same intentional line breaks; JSON
keeps both original cue text and its rendered `display_text`.

## 🌍 Supported languages

Source languages are limited to those with a default word-alignment model in
the installed WhisperX release:

```text
ar, ca, cs, da, de, el, en, es, eu, fa, fi, fr, gl, he, hi, hr, hu, id,
it, ja, ka, ko, lv, ml, nl, nn, no, pl, pt, ro, ru, sk, sl, sv, te, tl,
tr, uk, ur, vi, zh
```

## 📁 Generated files

For `video.mp4` with language `pt`:

```text
# Default: JSON is kept; transient SRT and ASS are removed after success
output/
├── video-pt.mp4
└── video-pt.json

# With --keep-transcriptions
output/
└── video/
    ├── video-pt.mp4
    └── subtitles/
        ├── video-pt.json
        ├── video-pt.srt
        └── video-pt.ass
```

Existing paths are never overwritten. multisubs adds suffixes such as `(1)` to
new files or directories when a name already exists.

Work happens in a private temporary directory inside the requested output
directory. Completed artifacts are published only after FFmpeg succeeds. If
processing fails, transcription artifacts are retained there for diagnosis;
partial final media is not published.

The versioned JSON transcript includes source and processing metadata, original
and displayed cue text, render geometry, resolved layout and typography,
wrapping diagnostics, and optional karaoke metadata.

## 🧪 Development

Install the `dev` extra, then run the local checks:

```bash
python -m compileall multisubs
ruff format --check .
ruff check .
pyright
python -m pytest
python -m build
twine check dist/*
```

The default test suite is hermetic and excludes tests marked `integration`.
Avoid a full transcription as a routine smoke test because model loading can
download large assets and consume significant CPU, GPU, memory, and time.

The CLI exits with status `0` on success, `2` for invalid arguments or paths,
and `1` for dependency, transcription, artifact, or FFmpeg failures.

## 📚 Project documentation

- [Product requirements](docs/prd.md) — product scope, requirements, and
  acceptance criteria.
- [Architecture](docs/architecture.md) — pipeline, data contracts, cue rules,
  and external boundaries.
- [Engineering conventions](docs/conventions.md) — code, tests, dependencies,
  privacy, and release standards.
- [Delivery guide](docs/delivery.md) — GitHub Flow, CI environments, artifact
  promotion, and recovery.

Contributions follow GitHub Flow: branch from `main`, open a pull request back
to `main`, and pass `Development / development-gate`. See the delivery guide for
the complete process.

## 📄 License

multisubs is available under the [MIT License](LICENSE). Third-party libraries,
models, and system tools retain their own licenses.

## ⚠️ Current limitations

- One local input video is processed per invocation.
- Translation output is fixed to English.
- Karaoke is unavailable for translation and preview-only samples.
- There is no interactive subtitle editor or graphical interface.
- Speaker diarization and speaker-specific styling are not supported.
- The output uses hard subtitles; selectable soft subtitle tracks are not
  created.
- FFmpeg, ffprobe, a compatible font, and the selected model must be available
  on the host.
