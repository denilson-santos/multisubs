<div align="center">

# 🎬 multisubs

**Transcribe, style, preview, and burn subtitles into local videos from one CLI.**

[![Python 3.10–3.13](https://img.shields.io/badge/Python-3.10%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Latest release](https://img.shields.io/github/v/release/denilson-santos/multisubs?label=release)](https://github.com/denilson-santos/multisubs/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

multisubs turns a local video into a new video with hard subtitles. It supports
WhisperX, Faster-Whisper, NVIDIA Parakeet, and Qwen3-ASR, creates JSON, SRT, and
ASS assets, and renders the final result with FFmpeg. WhisperX is the default.

Your media stays on your machine. A network connection is needed only when
the selected ASR must download model assets that are not already cached.

## ✨ Highlights

| Feature | What it gives you |
| --- | --- |
| 🗣️ Selectable local ASR | Choose WhisperX, Faster-Whisper, Parakeet, or Qwen3-ASR; Whisper backends can also translate to English. |
| 🧩 Ready-made templates | Sixteen built-in presentations for Reels, TikTok, Shorts, podcasts, tutorials, and editorial clips. |
| 🎨 Semantic styling | Font, weight, size, letter spacing, line height, colors, opacity, casing, backdrop, and shadow controls. |
| 🔤 Bundled fonts | 82 static faces from six OFL families render offline without system installation. |
| 📐 Responsive layout | Fixed resolution-aware defaults with explicit position, margin, width, and height controls. |
| 🎯 Precise placement | Nine semantic positions, relative units, margins, safe envelopes, and exact PlayRes coordinates. |
| 👀 Fast previews | Render one subtitle preview frame without loading an ASR runtime or transcribing the video. |
| ✨ Subtitle animation | Independent entrance, emphasis, and exit phases for complete cues and aligned words. |
| 🧠 Adaptive wrapping | Coverage-aware font metrics keep measured advances aligned with the rendered subtitle face. |
| 🛡️ Safe outputs | Collision-safe names and temporary rendering prevent existing or partial files from being overwritten. |

## 📋 Requirements

- Python 3.10 through 3.13. The optional WhisperX 3.8.6 runtime does not
  support Python 3.14.
- FFmpeg and ffprobe available on `PATH`.
- An FFmpeg build with the `subtitles` filter and libass support; animated
  previews additionally require the `libx264` H.264 encoder.
- Enough CPU or GPU memory for the selected ASR model. Parakeet is optimized
  for NVIDIA GPUs; Qwen3-ASR also loads a separate 0.6B forced aligner when the
  source language supports word timestamps.
- The Python package installs `fontTools` for bounded Unicode cmap checks,
  `uniseg` 0.10.1 for pinned Unicode boundary data, SudachiPy/SudachiDict-small
  for Japanese grouping, jieba for Chinese grouping, and Typer for the CLI.
  The dictionaries are installed with the package dependencies; no font or
  dictionary is downloaded while multisubs runs.

CUDA is selected automatically when the chosen runtime reports an available
GPU. WhisperX and Faster-Whisper use float16 on CUDA and int8 on CPU; Parakeet
and Qwen3-ASR move their models to CUDA or CPU through PyTorch.

## 📦 Installation

Create an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Then choose one of the installation paths below. WhisperX is selected when
`--asr` is omitted, but its runtime is optional. For the CLI and previews
without transcription dependencies, install only the core package:

```bash
python -m pip install -e .
```

For development, add `dev` to the selected installation extra. For example,
use `.[dev,whisperx]` instead of `.[whisperx]`. Use `.[dev]` when no ASR is
needed.

### CPU-only ASR installation

Faster-Whisper runs on CPU without PyTorch:

```bash
python -m pip install -e '.[faster-whisper]'
```

For Parakeet or Qwen, select the CPU PyTorch wheel before installing the ASR:

```bash
python -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  --extra-index-url https://pypi.org/simple \
  torch==2.8.0
python -m pip install -e '.[parakeet]'  # or .[qwen]
```

WhisperX additionally requires the matching CPU audio and vision wheels:

```bash
python -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  --extra-index-url https://pypi.org/simple \
  torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0
python -m pip install -e '.[whisperx]'
```

To install every ASR for CPU use, install the complete CPU PyTorch set above,
then run `python -m pip install -e '.[asr-all]'`.

### NVIDIA CUDA ASR installation

An NVIDIA driver compatible with the selected CUDA runtime must already be
installed. For WhisperX, Parakeet, or Qwen3-ASR, install the PyTorch 2.8 CUDA
12.8 wheel before the corresponding multisubs extra:

```bash
# Parakeet or Qwen3-ASR
python -m pip install \
  --index-url https://download.pytorch.org/whl/cu128 \
  torch==2.8.0
python -m pip install -e '.[parakeet]'  # or .[qwen]

# WhisperX needs the complete matching PyTorch set
python -m pip install \
  --index-url https://download.pytorch.org/whl/cu128 \
  torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0
python -m pip install -e '.[whisperx]'
```

Faster-Whisper uses CTranslate2 rather than PyTorch. GPU execution requires an
NVIDIA driver plus the CUDA 12 cuBLAS (`libcublas.so.12`) and cuDNN 9
(`libcudnn.so.9`) system libraries. Install them with your operating system's
package manager by following the official [CUDA installation
guide](https://developer.nvidia.com/cuda-downloads) and [cuDNN installation
guide](https://docs.nvidia.com/deeplearning/cudnn/installation/latest/linux.html),
then install the backend:

```bash
python -m pip install -e '.[faster-whisper]'
```

Libraries installed in standard system locations do not require
`LD_LIBRARY_PATH`. multisubs selects CUDA automatically when the selected
runtime reports an available GPU.

Confirm that the required commands are available:

```bash
ffmpeg -version
ffprobe -version
multisubs --help
```

The first run may download the selected ASR, voice-activity detection, or
alignment models. Temporary connection failures during those downloads are
retried up to three times. Model caches remain managed by the selected runtime.

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

### Choose an ASR backend

Omitting `--asr` keeps the established WhisperX `turbo` behavior. Each backend
has its own default model:

```bash
multisubs -i ./video.mp4 -l pt --asr faster-whisper
multisubs -i ./video.mp4 --asr parakeet
multisubs -i ./video.mp4 -l pt --asr qwen
```

| ASR | Default model | Task and timing notes |
| --- | --- | --- |
| `whisperx` | `turbo` | Transcription with WhisperX alignment; English translation requires a multilingual non-Turbo model. |
| `faster-whisper` | `turbo` | Silero VAD and native word timestamps; the same translation restriction as WhisperX. |
| `parakeet` | `nvidia/parakeet-tdt-0.6b-v3` | Automatic multilingual transcription and native timestamps; optional `--lang` labels artifact metadata because NeMo does not expose the detected code. |
| `qwen` | `Qwen/Qwen3-ASR-1.7B-hf` | Native Hugging Face multilingual transcription; explicit or automatically detected aligner-supported languages receive word timestamps. |

Use `--model` to select another model listed in the command reference. The
backend runtime is imported only after validation and only when selected.

### Choose a built-in subtitle template

Select a complete presentation with one option:

```bash
multisubs -i ./video.mp4 -l pt \
  --template golden-title
```

`default` uses the current Roboto Regular, white-on-translucent-black style.
Explicit appearance, layout, and animation options override only their own
template fields:

```bash
multisubs -i ./video.mp4 -l pt \
  --template bold-headline \
  --text-color '#B8FF5A' \
  --margin-bottom 10%
```

| Template | Good for | Font | Baseline appearance and animation |
| --- | --- | --- | --- |
| `default` | General use | Roboto Regular | 4%, white/original, 100%; box `#00000099`/25%, shadow 0px; max-height 12%; no animation. |
| `bold-headline` | Short-form hooks | Montserrat ExtraBold | 4.8%, white uppercase; outline `#111827`/7%; pop in, fade out; max-height 9.9%. |
| `amber-word` | Explanations | Inter SemiBold | 4.65%, white/original; outline `#111827`/5%; active-word amber highlight; max-height 9.7%. |
| `mint-progress` | Tips and steps | Montserrat Medium | 5.24%, white/original; box `#111827D9`/15%; progressive mint highlight; max-height 11.3%. |
| `focus-marker` | Accessible captions | Atkinson Hyperlegible Next Bold | 4.99%, white/original; outline `#111827`/4%, word box `#FFD54F`/12%; active-word; max-height 11.8%. |
| `golden-title` | Topics and chapter titles | Oswald Bold | 5.06%, `#FACC15` uppercase; outline `#111827`/6%; bottom-left; max-height 11.3%; no animation. |
| `emerald-word` | Word-led explainers | Roboto Bold | 4%, white/original; outline `#111827`/5%, word box `#166534FF`/12%; active-word; max-height 9.9%. |
| `kinetic-lime` | Fast tutorials | Montserrat Bold | 5.2%, white/original; outline `#111827`/5%, active text `#D9F99D`; slide up 180ms, fade out 120ms; max-height 10.3%. |
| `coral-marker` | Advice and interviews | Roboto SemiBold | 4%, white/original; outline `#111827`/4%, word box `#FDA4AFFF`/14%, active text `#111827`; fade in 140ms/out 120ms, word fade 70ms; bottom-left, max-height 9.8%. |
| `editorial-reveal` | Reflective clips | Lora SemiBold Italic | 5.07%, `#FFF8ED`; outline `#111827`/4%; zoom in 200ms, fade out 160ms, progressive word fade 100ms; max-height 11.1%. |
| `headline-bounce` | Punchlines | Oswald SemiBold | 5.06%, `#FDE68A` uppercase; outline `#111827`/6%; fade in 120ms, slide down 160ms, active-word bounce 420ms; max-height 11.3%. |
| `yellow-pop` | Hooks and reactions | Montserrat ExtraBold | 4.9%, white uppercase; outline `#111827`/5%; active-word `#FBE003` pop 120ms; max-height 9.8%. |
| `yellow-trace` | Step-by-step clips | Inter Medium | 4.65%, white/original; box `#111827FF`/15%; progressive `#FBE003`; max-height 10.7%. |
| `neon-lime-marker` | Energetic explainers | Oswald Medium | 5.06%, white; outline `#111827`/4%, word box `#39FF14FF`/12%; active-word, word zoom 100ms/fade 70ms; max-height 11.1%. |
| `neon-cyan-reveal` | High-energy explainers | Atkinson Hyperlegible Next Bold | 4.99%, `#00F5FF`; outline `#111827`/5%; progressive slide-up 120ms; max-height 11.9%. |
| `neon-magenta-pulse` | Reactions | Roboto Bold | 3.8%, `#FF4FD8` uppercase; outline `#111827`/5%; active-word pulse 400ms; max-height 9.4%. |

Templates use 18% side margins, 0% top margin, 3% bottom margin, 100% maximum
width, automatic line height, zero letter spacing, full opacity, and no shadow.
Placement is bottom-center except `golden-title` and `coral-marker`
(bottom-left). Sizes are optically calibrated; maximum heights target two
lines. Explicit flags override template values. Static previews suppress
motion; animated previews use simulated word times. For example, disable an
inherited highlight phase with:

```bash
multisubs -i ./video.mp4 --preview-layout \
  --template mint-progress --animation-word-text-emphasis none
```

### Use a custom template directory

Custom templates live in a flat local directory and are selected by the JSON
name, independently of the filename:

~~~bash
mkdir -p ./templates
cat > ./templates/my-yellow-captions.json <<'JSON'
{
  "schema_version": 1,
  "name": "my-yellow-captions",
  "description": "A compact yellow caption variant.",
  "base": "yellow-pop",
  "style": {
    "typography": {
      "font_size": "3.6%"
    }
  },
  "layout": {
    "margins": {
      "bottom": "15%"
    }
  }
}
JSON

multisubs -i ./video.mp4 -l pt \
  --template-dir ./templates \
  --template my-yellow-captions
~~~

Only immediate regular JSON files are read. Each uses schema version 1 and a
unique lowercase kebab-case name; optional fields inherit from a built-in base
(default: `default`, never another custom file), then explicit CLI options
override them. Custom names take precedence over built-ins for that invocation.
Invalid files are reported even when they are not selected. See [internal
template resources](docs/architecture.md#internal-template-resources) for the
complete data contract.

### Translate speech to English

Translation requires WhisperX or Faster-Whisper with a multilingual, non-Turbo
Whisper model:

```bash
multisubs \
  -i ./interview.mp4 \
  -l pt \
  --asr whisperx \
  --task translate \
  --model medium \
  -o ./output
```

Translation output is always English. `turbo` and model names ending in `.en`
cannot be used with `--task translate`.

### Preview a layout before transcribing

Generate one PNG from a real video frame without loading an ASR runtime:

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
saved as `<video-stem>-subtitle-preview.png` with a numeric suffix on collision.
If the sample does not fit, the preview shows only its first fitting cue.

### Preview subtitle animation

Generate a silent MP4 without loading an ASR runtime or transcribing speech:

```bash
multisubs -i ./video.mp4 -o ./previews \
  --preview-animation \
  --preview-duration 4s \
  --preview-at 00:00:10.500 \
  --template focus-marker \
  --preview-text "This is how the word animation will look"
```

The selected frame is frozen behind a cue that starts 500 ms into the clip,
with 500 ms before and after it. Duration accepts whole `ms` or `s` values from
1 to 15 seconds, defaults to `4s`, and the total clip is one second longer.
Word times are simulated, not synchronized to speech. The output is
`<video-stem>-subtitle-animation-preview.mp4` (numbered on collision).
`--preview-guides` labels simulated timing. Preview modes publish no transcript
artifacts and reject `--keep-transcriptions`.

### Add subtitle animations

Text and backdrop have independent entrance, emphasis, and exit tracks at both
cue and aligned-word scope. This permits combinations such as a sliding cue box
with text that fades independently:

```bash
multisubs -i ./video.mp4 -l pt \
  --animation-cue-backdrop-entrance slide-left \
  --animation-cue-backdrop-entrance-duration 250ms \
  --animation-cue-text-entrance fade \
  --animation-cue-text-entrance-duration 0.15s \
  --animation-cue-text-emphasis breathe \
  --animation-cue-text-exit fade
```

Each phase has a deterministic duration; append `-duration` to override it
with `10ms`–`5000ms`, written in milliseconds or seconds. Run `multisubs --help`
for the choices available to each track.

Word text can be highlighted progressively:

```bash
multisubs -i ./video.mp4 -l pt \
  --animation-word-text-emphasis highlight \
  --animation-word-text-mode progressive \
  --animation-word-text-highlight-color '#FFD54F'
```

A word decoration is enabled by choosing its visual type. Its animation and
timing mode remain independent from word text:

```bash
multisubs -i ./video.mp4 -l pt \
  --word-backdrop box \
  --word-backdrop-color '#FFD54F' \
  --word-backdrop-size 12% \
  --animation-word-backdrop-mode active-word \
  --animation-word-backdrop-entrance fade \
  --animation-word-text-emphasis highlight \
  --animation-word-text-highlight-color '#111827'
```

`active-word` follows only the current alignment interval; `progressive` keeps
each affected word visible through the cue. Word effects require source-language
alignment and are disabled for translation or incomplete mappings. Unsupported
shaping cases retain cue-level effects and fall back to complete logical-line
rendering; word tracks are suppressed. Previews use the same fallback and
report a warning.

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

Lengths require `%` or PlayRes `px`. Font-weight accepts named or 100–900
numeric ranks. Text case is applied before measurement; retained JSON keeps the
original transcript and aligned words.

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

The unmodified static TTF faces are pinned in a package integrity manifest and
each family includes its OFL license. They work offline; multisubs does not
download fonts or write the system font cache. All faces add about 13 MB to the
unpacked package.

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

`--font` matches family metadata, not filenames. A custom matching family takes
precedence over its bundled equivalent; bundled fonts precede fontconfig.
Missing glyphs trigger a bounded search and visible fallback diagnostic. If no
covering face is found for positioned text, multisubs asks you to choose a
family or `--fonts-dir`; it never downloads one. Custom fonts are used only for
this run; ensure you have rights to use and distribute them.

### Coverage and fallback diagnostics

Coverage is checked against displayed text before wrapping. With
`--keep-transcriptions`, `rendering.text_measurement` reports the requested and
resolved face and fallback reason. `coverage: "verified"` confirms cmap
coverage, not complete shaping behavior; `unicode-estimate` denotes an
unverified fallback.

## ⚙️ Command reference

Run `multisubs --help` for the CLI's complete, authoritative help text.

### Input and processing

| Option | Default | Description |
| --- | --- | --- |
| `-i`, `--input-path PATH` | required | Path to one local input video. |
| `-o`, `--output-dir DIR` | current directory | Directory for generated files. |
| `--asr BACKEND` | `whisperx` | `whisperx`, `faster-whisper`, `parakeet`, or `qwen`. |
| `-l`, `--lang CODE` | automatic when exposed | Source-language code supported by the selected ASR. For Parakeet it labels metadata but does not condition transcription; English-only Whisper models use `en`. |
| `-t`, `--task TASK` | `transcribe` | `transcribe` or translate speech to English. |
| `-m`, `--model MODEL` | backend default | Model used by the selected ASR. |
| `-k`, `--keep-transcriptions` | off | Keep JSON, SRT, and ASS in a `subtitles` directory. |
| `--verbose` | off | Show detailed processing progress and backend logs. |
| `-v`, `--version` | — | Print the package version. |
| `-h`, `--help` | — | Show CLI help and backend-dependent support guidance. |

By default, multisubs shows only its own processing stages, relevant subtitle
warnings, errors, and final output path. Output printed by ASR runtimes and
native libraries is suppressed during processing, including backend warnings
and progress bars. Use `--verbose` to show detailed stages and the raw backend
output when diagnosing a run. If a backend fails, multisubs still reports the
failed operation; rerun with `--verbose` to inspect the backend diagnostics.

WhisperX models: `tiny.en`, `tiny`, `base.en`, `base`, `small.en`, `small`,
`medium.en`, `medium`, `large`, and `turbo`. Faster-Whisper accepts the same
small models plus `large-v1`, `large-v2`, `large-v3`, and `large-v3-turbo`.
Parakeet accepts `nvidia/parakeet-tdt-0.6b-v3`; Qwen accepts
`Qwen/Qwen3-ASR-1.7B-hf`.

### Preview and animation

| Option | Default | Description |
| --- | --- | --- |
| `--preview-layout` | off | Render one layout preview PNG without transcription. |
| `--preview-animation` | off | Render a silent H.264 MP4 with simulated word timing; mutually exclusive with `--preview-layout`. |
| `--preview-duration DURATION` | `4s` | Animated cue duration from `1s` through `15s`, using whole `ms` or `s`; requires `--preview-animation`. |
| `--preview-at HH:MM:SS.mmm` | video midpoint | Select the frame used by the preview. |
| `--preview-text TEXT` | sample text | Replace the preview subtitle text. |
| `--preview-guides` | off | Draw placement, envelope, and canvas guides. |
| `--animation-{cue\|word}-{text\|backdrop}-{entrance\|emphasis\|exit} TYPE` | inherited or `none` | Select one phase on one independent visual track; run `--help` for the effects valid for each phase. |
| `--animation-{cue\|word}-{text\|backdrop}-{entrance\|emphasis\|exit}-duration DURATION` | effect or template default | Override an enabled phase with `10ms`–`5000ms`, expressed as `150ms` or `0.15s`. |
| `--animation-word-text-mode MODE` | `active-word` | Use `active-word` or `progressive` timing for word text. |
| `--animation-word-backdrop-mode MODE` | `active-word` | Use `active-word` or `progressive` timing for the word decoration. |
| `--animation-word-text-highlight-color COLOR` | `#FFD54F` when enabled | Set the text color used by the `highlight` word emphasis. |

### Appearance

| Option | Default | Description |
| --- | --- | --- |
| `--template NAME` | `default` | Select a built-in or `--template-dir` custom presentation by JSON name. |
| `--template-dir DIR` | — | Read immediate custom template JSON files for this invocation; custom names take precedence over built-ins. |
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
| `--backdrop-size LENGTH` | `25%` | Outline thickness or box padding. |
| `--word-backdrop KIND` | `none` | Timed word decoration: `none`, `outline`, or `box`. |
| `--word-backdrop-color COLOR` | `#111827E6` | Timed word-decoration color. |
| `--word-backdrop-size LENGTH` | `25%` | Outline thickness or padding for each timed word decoration. |
| `--shadow-size LENGTH` | `0px` | Shadow size relative to the resolved font size or in pixels. |
| `--fonts-dir DIR` | — | Additional `.ttf`, `.otf`, or `.ttc` fonts for this run. |

With `--backdrop box`, every nonempty cue uses one continuous measured box
around the complete text block, regardless of whether it occupies one line or
several; padding, placement, and shadow are resolved from that same geometry.
Visible font bounds center the text vertically so baseline space does not appear
as extra padding. A single-line cue is also centered horizontally inside its
box while the complete box retains the requested screen anchor.

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
| `--max-height LENGTH` | `12%` | Maximum height used to derive line capacity. |
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
| `--backdrop-size`, `--word-backdrop-size`, `--shadow-size` | Resolved font size. |
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

Wrapping uses the selected font's measured metrics when available and a
Unicode-aware estimate otherwise; size, spacing, line height, decorations, and
maximum dimensions all contribute. Japanese and Chinese records receive
[language-specific grouping](docs/architecture.md#unicode-segmentation-and-source-mapping),
while validated alignment records remain the timing units for word effects.
Text is never truncated. If a source/alignment map is incomplete, the full cue
keeps its segment timing and word effects are disabled rather than inventing
timestamps. SRT and ASS share intentional line breaks; JSON retains source text
beside rendered `display_text`.

## 🌍 Supported languages

Omit `--lang` to use automatic multilingual transcription. WhisperX,
Faster-Whisper, and Qwen3-ASR expose the detected source-language code.
Parakeet recognizes the language internally but its normal NeMo result does not
expose that code, so `metadata.language` is `null` and artifact names omit the
language suffix. An explicit Parakeet `--lang` labels the artifacts; it does not
condition the model.

Models ending in `.en` always use English and reject an explicit non-English
`--lang`. Translation still produces English, regardless of the selected or
detected source language, and requires a multilingual non-Turbo model.
If a backend expected to expose detection returns an unsupported language or no
language, processing stops with guidance before unavailable alignment or
artifact generation.

WhisperX source languages are limited to those with a default alignment model:

```text
ar, ca, cs, da, de, el, en, es, eu, fa, fi, fr, gl, he, hi, hr, hu, id,
it, ja, ka, ko, lv, ml, nl, nn, no, pl, pt, ro, ru, sk, sl, sv, te, tl,
tr, uk, ur, vi, zh
```

Faster-Whisper supports its published Whisper language catalog. Parakeet v3
supports 25 European languages, including `en`, `es`, and `pt`. Qwen3-ASR
supports its published 30-language catalog; its forced aligner currently adds
word timestamps for `zh`, `en`, `yue`, `fr`, `de`, `it`, `ja`, `ko`, `pt`,
`ru`, and `es`. When `--lang` is omitted, Qwen detects the language first and
passes that result to the forced aligner when supported. Other detected
languages keep real five-minute chunk boundaries and use the documented coarse
timing fallback. Unsupported explicit combinations fail before model loading.

## 📁 Generated files

For `video.mp4` with selected or automatically detected source language `pt`:

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

# With --preview-animation: one silent frozen-background clip
output/
└── video-subtitle-animation-preview.mp4
```

Existing paths are never overwritten. multisubs adds suffixes such as `(1)` to
new files or directories when a name already exists.

Artifact names and JSON `metadata.language` use the resolved source-language
code when available, including for translation runs whose subtitle text is
English. When no code is available, `metadata.language` is `null` and names use
the source stem without a language suffix: `video.mp4`, `video.json`,
`video.srt`, and `video.ass`.

Work happens in a private temporary directory inside the requested output
directory. Completed artifacts are published only after FFmpeg succeeds. If
processing fails, transcription artifacts are retained there for diagnosis;
partial final media is not published.

When `--keep-transcriptions` is enabled, the schema-3 JSON records the selected
ASR and model and preserves normalized source word records beside display text,
geometry, resolved styling,
animation, template identity, and bounded text-mapping, segmentation, and
word-effect diagnostics. Word records are not replaced by derived linguistic
groups; internal paths, font objects, ASS tags, and custom template JSON are
not stored. See the [JSON contract](docs/architecture.md#json) for field details.

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

For local debugging, `python -m scripts.replay_subtitle_layout retained.json`
rebuilds collision-safe JSON/SRT/ASS without loading speech models. `--render`
uses a synthetic background; `--uncaptioned-video` explicitly selects a clean
video. Replay cannot recover text or boundaries discarded by earlier
processing. See the [regression instructions](docs/plans/multilingual-subtitles/00-regressions-and-decisions.md).

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

- One local video is processed per invocation; there is no graphical editor or
  speaker diarization.
- Translation always outputs English. Detection selects one language per run
  and can be unreliable for short or ambiguous audio.
- Japanese and Chinese grouping is deterministic but may differ from editorial
  choices.
- Word effects require usable alignment. Incomplete maps or unsupported
  shaping retain the complete cue and use the documented fallback; very short
  word intervals may be shorter than one visible video frame.
- Static previews show one fitting cue without motion; animated previews use
  simulated timing.
- Animation distance, scale, and easing are fixed by effect type. Output uses
  hard rather than selectable soft subtitles.
