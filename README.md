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
| 🧩 Ready-made templates | Eight built-in presentations for interviews, social video, news, editorial work, high contrast, and karaoke. |
| 🎨 Semantic styling | Font, weight, size, letter spacing, line height, colors, opacity, casing, backdrop, and shadow controls. |
| 🔤 Bundled fonts | 82 static faces from six OFL families render offline without system installation. |
| 📐 Responsive layout | Fixed resolution-aware defaults with explicit position, margin, width, and height controls. |
| 🎯 Precise placement | Nine semantic positions, relative units, margins, safe envelopes, and exact PlayRes coordinates. |
| 👀 Fast previews | Render one subtitle preview frame without loading WhisperX or transcribing the video. |
| 🎤 Karaoke | Progressive or active-word highlighting based on aligned word timestamps. |
| 🧠 Adaptive wrapping | Font-aware wrapping that favors readable language and timing boundaries. |
| 🛡️ Safe outputs | Collision-safe names and temporary rendering prevent existing or partial files from being overwritten. |

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

### Choose a built-in subtitle template

Select a complete presentation with one option:

```bash
multisubs -i ./video.mp4 -l pt \
  --template classic-yellow
```

The current Roboto Regular, white-on-translucent-black presentation remains the
`default`. Every explicit appearance, layout, or effect option overrides only
its corresponding template field:

```bash
multisubs -i ./video.mp4 -l pt \
  --template social-bold \
  --text-color '#B8FF5A' \
  --margin-bottom 10%
```

| Template | Good for | Font | Main presentation |
| --- | --- | --- | --- |
| `default` | General use | Roboto Regular | White, original case, translucent black box, bottom-center. |
| `clean-outline` | Interviews, courses, demos | Inter Medium | White with a clean dark outline and no shadow. |
| `social-bold` | Reels, Shorts, social clips | Montserrat ExtraBold | Large uppercase white text, strong outline, wider vertical envelope. |
| `classic-yellow` | Interviews, archives, documentaries | Roboto Bold | Yellow text with a strong dark outline. |
| `newsroom` | Reports, explainers, updates | Oswald SemiBold | Compact uppercase box, bottom-left. |
| `editorial` | Documentary and cultural material | Lora SemiBold Italic | Warm off-white serif text with a subtle outline. |
| `high-contrast` | Maximum visual differentiation | Atkinson Hyperlegible Next Bold | Black text on an opaque yellow box. |
| `neon-karaoke` | Energetic word-timed captions | Montserrat Bold | Large outlined text with progressive turquoise highlighting. |

The exact template baselines are:

| Template | Size and text | Backdrop | Native layout |
| --- | --- | --- | --- |
| `default` | `4%`, `#FFFFFF`, original, `100%` | box `#00000099`, `0px`, shadow `4%` | bottom-center; L/R `18%`, B `3%`, W/H `100%`/`10%` |
| `clean-outline` | `4%`, `#FFFFFF`, original, `100%` | outline `#000000CC`, `5%`, shadow `0px` | bottom-center; L/R `14%`, B `3%`, W/H `100%`/`14%` |
| `social-bold` | `5%`, `#FFFFFF`, uppercase, `100%` | outline `#000000E6`, `8%`, shadow `3%` | bottom-center; L/R `8%`, B `3%`, W/H `100%`/`22%` |
| `classic-yellow` | `4.2%`, `#FFD54F`, original, `100%` | outline `#000000E6`, `6%`, shadow `3%` | bottom-center; L/R `12%`, B `3%`, W/H `100%`/`16%` |
| `newsroom` | `4.2%`, `#FFFFFF`, uppercase, `100%`, spacing `1%` | box `#0B1F3ACC`, `8%`, shadow `0px` | bottom-left; L `5%`, R `35%`, B `3%`, W/H `100%`/`16%` |
| `editorial` | `4%`, `#FFF8E7`, original, `95%` | outline `#111111CC`, `4%`, shadow `3%` | bottom-center; L/R `16%`, B `3%`, W/H `100%`/`15%` |
| `high-contrast` | `4.3%`, `#000000`, original, `100%` | box `#FFD600FF`, `10%`, shadow `0px` | bottom-center; L/R `10%`, B `3%`, W/H `100%`/`18%` |
| `neon-karaoke` | `5%`, `#FFFFFF`, original, `100%` | outline `#080012E6`, `7%`, shadow `5%` | bottom-center; L/R `8%`, B `3%`, W/H `100%`/`20%` |

All use `auto` line height and a `0%` top margin. Unlisted letter spacing is
`0px`. `neon-karaoke` additionally enables progressive karaoke with highlight
color `#00F5D4`. Preview shows a representative static effect: progressive
mode highlights the first half of the cue and active-word mode highlights its
first word. Use `--no-karaoke` when only the static styling is wanted:

```bash
multisubs -i ./video.mp4 --preview-layout \
  --template neon-karaoke --no-karaoke
```

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

Karaoke works only with source-language transcription and cannot be combined
with translation. Layout preview does not invent timings: it shows the first
half of a progressive cue highlighted, or only the first word in active-word
mode. Cues with incomplete timing data in final rendering fall back to normal
subtitles instead of receiving invented timestamps.

### Customize typography

```bash
multisubs -i ./video.mp4 -l pt \
  --font "Inter" \
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

The typography controls include:

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

### Use a bundled font

multisubs ships 82 static desktop faces from six families. They are available
offline through `--font` without `--fonts-dir` or global installation:

| Family | Bundled weights | Italic |
| --- | --- | --- |
| Roboto | 100–900 | all bundled weights |
| Inter | 100–900 | all bundled weights |
| Montserrat | 100–900 | all bundled weights |
| Oswald | 200–700 | no |
| Lora | 400–700 | all bundled weights |
| Atkinson Hyperlegible Next | 200–800 | all bundled weights |

```bash
multisubs -i ./video.mp4 \
  --font "Atkinson Hyperlegible Next" \
  --font-weight bold \
  --italic
```

Every face is an unmodified static TTF served by the official Google Fonts API
and recorded with its exact versioned source URL in a packaged integrity
manifest. Each family includes the `OFL.txt` from the same pinned Google Fonts
catalog revision; no font download or font-cache write happens while multisubs
runs. Width and optical-size axes are kept at their Google Fonts defaults
because the CLI currently exposes weight and italic selection only. Shipping
all faces adds about 13 MB to the unpacked package.

### Use a custom font

Put the desired `.ttf`, `.otf`, or `.ttc` files directly in one flat directory.
The resolver does not search nested directories:

```text
fonts/
├── MyFont-Regular.ttf
├── MyFont-SemiBold.ttf
├── MyFont-Bold.ttf
└── MyFont-BoldItalic.ttf
```

Then point both font measurement and FFmpeg/libass to that directory:

```bash
multisubs -i ./video.mp4 \
  --fonts-dir ./fonts \
  --font "My Font" \
  --font-weight bold \
  --italic
```

`--font` matches the internal family metadata stored in the font, which may
differ from its filename. Multiple families and all their weight/italic faces
may share the same directory. The closest available weight is selected when an
exact face is absent, with a visible substitution diagnostic.

A custom matching family takes precedence over the same bundled family;
bundled families take precedence over fontconfig. An unbundled family may still
resolve through fontconfig, otherwise wrapping uses the documented Unicode
estimate. The custom directory is used only for that invocation and does not
install fonts globally. You are responsible for ensuring that supplied fonts
may be used and distributed in your intended output.

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
| `--karaoke`, `--no-karaoke` | off | Enable karaoke or disable an effect inherited from a template. |
| `--karaoke-mode MODE` | `progressive` when enabled | Use `progressive` or `active-word`. |
| `--karaoke-highlight-color COLOR` | `#FFD54F` | Set the karaoke highlight color. |

### Appearance

| Option | Default | Description |
| --- | --- | --- |
| `--template NAME` | `default` | Select one of the eight built-in presentation baselines. |
| `--font NAME` | `Roboto` | Bundled, custom, or system subtitle font family. |
| `--font-size LENGTH` | `4%` | Size relative to the render height, or PlayRes pixels. |
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

The complete custom-font workflow and provider precedence are documented in
[Use a custom font](#use-a-custom-font).

Defaults in the appearance and layout tables describe the `default` template.
A selected template supplies its documented baseline first; explicitly
provided flags then replace only their own fields.

### Layout and positioning

| Option | Default | Description |
| --- | --- | --- |
| `--position POSITION` | `bottom-center` | Native ASS semantic position. |
| `--margin-left LENGTH` | `18%` | Native ASS left margin. |
| `--margin-right LENGTH` | `18%` | Native ASS right margin. |
| `--margin-top LENGTH` | `0%` | Native ASS margin for top positions. |
| `--margin-bottom LENGTH` | `3%` | Native ASS margin for bottom positions. |
| `--max-width LENGTH` | `100%` | Maximum subtitle width. |
| `--max-height LENGTH` | `10%` | Maximum height used to derive line capacity. |
| `--position-x LENGTH` | — | Explicit global PlayRes X coordinate. |
| `--position-y LENGTH` | — | Explicit global PlayRes Y coordinate. |
| `--anchor POSITION` | — | Subtitle-box anchor for explicit coordinates. |

These defaults are identical for landscape, portrait, square, and rotated
inputs. Percentages resolve from each video's autorotated render geometry.
`--position` changes only alignment; margins and maximum dimensions retain their
defaults unless they are overridden independently.

Only the active vertical margin can be supplied explicitly: top positions use
`--margin-top`, bottom positions use `--margin-bottom`, and middle positions use
neither. An inactive vertical margin is rejected with an actionable error. The
default `bottom-center` layout therefore keeps `--margin-top` at `0%` and uses
the `3%` bottom inset. A top position needs an explicit `--margin-top` when an
inset is desired.

Available semantic positions:

| `top-left` | `top-center` | `top-right` |
| --- | --- | --- |
| `middle-left` | `center` | `middle-right` |
| `bottom-left` | `bottom-center` | `bottom-right` |

All layout lengths require an explicit `%` or `px` suffix. Percentages remain
resolution-aware; pixels refer to the generated ASS PlayRes canvas.

| Option | Percentage basis |
| --- | --- |
| `--font-size` | Autorotated render height. |
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
or explicitly supplied margins. The complete anchored envelope must fit inside
the canvas; invalid coordinates are rejected instead of being moved or clipped.

### Adaptive wrapping

multisubs measures the selected custom, bundled, or fontconfig face with Pillow
and RAQM when a concrete face is available. The selected custom or bundled
directory is also passed to FFmpeg/libass. Otherwise, it uses a Unicode-aware
width estimate. Wrapping takes
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
# Default: only the rendered video is kept; all subtitle artifacts are transient
output/
└── video-pt.mp4

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

When `--keep-transcriptions` is enabled, the versioned JSON transcript includes
source and processing metadata, original and displayed cue text, render
geometry, resolved layout and typography, wrapping diagnostics, and optional
karaoke metadata. Rendering diagnostics also record the requested and resolved
template names; omitted selection is recorded as requested `null` and resolved
`default`.

## 🧪 Development

Install the `dev` extra, then run the local checks:

```bash
python -m compileall multisubs
ruff format --check .
ruff check .
pyright
python -m pytest
rm -rf dist
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

multisubs source code is available under the [MIT License](LICENSE). The six
bundled font families retain the SIL Open Font License 1.1 found in each
`multisubs/assets/fonts/<family>/OFL.txt`. Other third-party libraries, models,
and system tools retain their own licenses.

## ⚠️ Current limitations

- One local input video is processed per invocation.
- Translation output is fixed to English.
- Karaoke is unavailable for translation; previews show a static representative
  highlight rather than timed word animation.
- There is no interactive subtitle editor or graphical interface.
- Speaker diarization and speaker-specific styling are not supported.
- The output uses hard subtitles; selectable soft subtitle tracks are not
  created.
- FFmpeg, ffprobe, and the selected model must be available on the host.
- Font families outside the six bundled families require `--fonts-dir` or a
  compatible system font provider.
