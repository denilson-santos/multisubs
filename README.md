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

- Python 3.10 through 3.13.
- FFmpeg and ffprobe available on `PATH`.
- An FFmpeg build with the `subtitles` filter and libass support; animated
  previews additionally require `libx264` by default, or the explicitly selected
  H.264 encoder.
- Optional `h264_nvenc` rendering requires an NVIDIA GPU and a driver compatible
  with the NVENC API used to compile FFmpeg. A working ASR CUDA runtime alone
  does not establish NVENC compatibility.
- Enough CPU or GPU memory for the selected ASR model.

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

FFmpeg and ffprobe are installed separately from the `ffmpeg-python` wrapper.
Install both executables from the same build, using your operating system's
packages or the [FFmpeg download page](https://ffmpeg.org/download.html).

The media integration suite has been validated on Linux with Python 3.10,
Pillow 12.3.0, and Typer 0.27.3 against these builds:

| Source | FFmpeg and ffprobe version |
| --- | --- |
| Ubuntu 22.04 packages | `4.4.2-0ubuntu0.22.04.1` |
| BtbN FFmpeg 9.0 release branch | `n9.0.2-27-g7e93014c5b-20261012` |

These checks use synthetic media and cover hard subtitles, audio preservation,
90°/180°/270° rotation, multilingual fonts, still previews, and animated
previews without loading an ASR model. Contributors can check another installed
build with `python -m pytest -m integration` from the development environment.

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

Choose the task you want to perform. Replace `./video.mp4` with your local
video; transcription recipes require the selected ASR's installation extra.

- **Processing:** [ASR backend](#choose-an-asr-backend) ·
  [Translation](#translate-speech-to-english) ·
  [Existing subtitles](#burn-an-existing-subtitle-file)
- **Styling:** [Templates](#choose-a-built-in-subtitle-template) ·
  [Typography](#customize-typography) · [Placement](#adjust-subtitle-placement) ·
  [Custom templates](#use-a-custom-template-directory)
- **Previews and effects:** [Layout preview](#preview-a-layout-before-transcribing) ·
  [Animation preview](#preview-subtitle-animation) ·
  [Cue animations](#add-subtitle-animations) ·
  [Word highlighting](#highlight-the-spoken-word)
- **Python:** [Transcript reuse](#transcribe-once-and-reuse-the-transcript) ·
  [Presentation overrides](#compose-subtitle-settings-in-python)

### Choose an ASR backend

Use `--asr` to select an installed backend. This example uses Faster-Whisper:

```bash
multisubs -i ./video.mp4 -l pt -o ./output --asr faster-whisper
```

Available backends are `whisperx` (the default), `faster-whisper`, `parakeet`,
and `qwen`. Omit `-l pt` for automatic language detection where supported.
See [backend defaults and models](#asr-backends-and-models) for the differences.

### Choose a built-in subtitle template

A template sets the font, colors, layout, and animations together:

```bash
multisubs -i ./video.mp4 -l pt -o ./output --template yellow-pop
```

Use `default` for plain captions, `bold-headline` for large headlines, or
`yellow-pop` for active-word emphasis. See the
[complete template catalog](#built-in-template-catalog) for all sixteen styles.
Explicit flags override only the corresponding template fields.

### Customize typography

Start with a template and change the settings you need:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --template bold-headline \
  --font "Inter" \
  --font-weight semi-bold \
  --font-size 4.5% \
  --text-color '#F8FAFC'
```

Quote hexadecimal colors in the shell. Lengths require `%` or `px`.
See [appearance options](#subtitle-appearance) for opacity, casing, and backdrops,
[relative layout units](#relative-layout-units) for size, spacing, and line height,
and the guides for [bundled fonts](#use-a-bundled-font) and
[custom fonts](#use-a-custom-font).

### Adjust subtitle placement

Place subtitles at the bottom center with a larger inset from the bottom edge:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --position bottom-center \
  --margin-bottom 8%
```

Top positions use `--margin-top`; middle positions use neither vertical margin.
See [native subtitle positions](#native-subtitle-positions) for all nine positions
and [exact coordinates](#custom-subtitle-coordinates) for custom placement.

### Preview a layout before transcribing

Render one PNG to check a template on a real video frame:

```bash
multisubs -i ./video.mp4 -o ./previews \
  --preview-layout \
  --template yellow-pop \
  --preview-text "This is how my subtitle will look"
```

This creates `video-subtitle-preview.png` without transcription or ASR loading.
The first video frame is used by default; use `--preview-at 00:00:10` to
choose another frame and `--preview-guides` to show placement guides. Only the
first fitting subtitle is shown, with motion suppressed.

### Preview subtitle animation

Render a silent clip of the template's animation on a frozen video frame:

```bash
multisubs -i ./video.mp4 -o ./previews \
  --preview-animation \
  --template yellow-pop \
  --preview-duration 4s \
  --preview-text "This is how the word animation will look"
```

This creates `video-subtitle-animation-preview.mp4` without transcription or
ASR loading. The background is the first video frame by default; optional
`--preview-at 00:00:10` selects another frozen frame. That choice does not
change the animation clock. A `4s` subtitle produces a five-second clip, with
half a second before and after the subtitle. Word timing is simulated. Both
sample previews accept the same styling options as rendering; see
[preview options](#subtitle-preview).

### Reuse transcription while trying subtitle styles

Transcription runs automatically reuse source speech in
`<output-dir>/.multisubs-cache`. Export subtitles without encoding a video:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --subtitles-only --template yellow-pop
```

This writes `video-pt.srt` and `video-pt.ass`. Change the template, typography,
layout, or animation and repeat the command: source speech is reused while the
subtitle presentation is rebuilt. The input video is still required for its
geometry. Export needs ffprobe; a cache hit does not run FFmpeg or initialize
a video encoder. A cache miss may require FFmpeg through the selected ASR.

To evaluate a style on moving video with real speech timing and source audio:

```bash
multisubs -i ./video.mp4 -l pt -o ./output --template yellow-pop \
  --preview-clip --preview-at 00:00:10 --preview-duration 8s
```

This writes `video-subtitle-clip-preview.mp4`. Start is required; duration
defaults to `10s` and accepts `1s` through `15s` in whole milliseconds using
`ms` or `s`. The end is limited to the video end. The clip preserves moving
source frames, autorotated geometry, and the existing subtitle animation phase
at the cut. Available audio is re-encoded as AAC for accurate cuts; silent inputs
stay silent. Video uses H.264/libx264 unless an explicit supported
[video encoder](#video-encoding) is selected. Only the clip is published.

On a miss, either command transcribes the **full input video**, enabling later
styles, clips, and complete renders to share the same speech. To render the
complete video, keep the same output directory and omit `--subtitles-only` and
`--preview-clip`. Use `--cache-dir DIR` to select another cache location, such as
`--cache-dir ~/.cache/multisubs` to share speech across different output
directories. Add `--refresh-cache` to recognize again and refresh the matching
entry after success; it works with the default or custom cache directory.
Progress reports the cache directory and when ASR and alignment are skipped.

Speech caching, subtitle exports, and real clips support `--task transcribe`.
Ordinary translation runs retain their uncached behavior. `--subtitles-only`
and `--preview-clip` reject `--keep-transcriptions`, external subtitles, and
other preview modes. Real clips reject sample text/guides; subtitle export also
rejects video encoding options.
The existing PNG and frozen-background animation previews remain ASR-free.

Speech entries contain the original text and available timestamps. They are
saved under `<output-dir>/.multisubs-cache/transcriptions/v1` by default, or
`DIR/transcriptions/v1` with `--cache-dir DIR`, before layout/rendering. They
remain after a later failure and are retained until you remove that dedicated
directory. Existing `speech-v1` entries remain readable when the matching entry
is absent from the new location; new transcriptions and refreshes use
`transcriptions/v1` and leave the old files untouched.
They are independent of `--keep-transcriptions`; retained runs share the cache
at the requested output root, outside each collision-safe run directory.
Sample previews and external-subtitle rendering do not access a speech cache.
Cache files use owner-only permissions on systems that support them.

Each lookup hashes the complete input file, so renamed identical media can reuse
speech while changed content cannot. Backend, model, requested language, and
recognition compatibility also participate. Differences in installed runtime
versions invalidate an entry; missing optional ASR packages do not prevent a hit.
To pick up changed model assets under the same model name, force a refresh.
Model downloads remain in the ASR runtime's own caches.

### Add subtitle animations

Fade a complete subtitle in and out:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --animation-cue-text-entrance fade \
  --animation-cue-text-entrance-duration 150ms \
  --animation-cue-text-exit fade
```

Use `none` to clear one inherited phase, for example
`--animation-word-text-emphasis none`. Use `--disable-cue-animations` or
`--disable-word-animations` to clear an entire scope. See the
[animation reference](#cue-and-word-effects) for independent text/backdrop
tracks and word decorations.

### Highlight the spoken word

Change the text color of the currently spoken word:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --animation-word-text-emphasis highlight \
  --animation-word-text-mode active-word \
  --animation-word-text-highlight-color '#FFD54F'
```

Use `progressive` instead of `active-word` to keep earlier words highlighted.
Word effects need word timestamps. When they cannot be applied safely, the
complete subtitle stays visible and multisubs reports why. Translation requires
word effects to be disabled. See [word effects](#cue-and-word-effects) for details.

### Use a custom template directory

Select a saved JSON template by its `name`:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --template-dir ./templates \
  --template my-yellow-captions
```

See [Define a custom template](#define-a-custom-template) to create the example
file. Custom names take precedence over built-ins for this invocation, and
all immediate JSON files in the directory are validated.

### Translate speech to English

Use WhisperX or Faster-Whisper with a multilingual, non-Turbo model:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --asr whisperx \
  --task translate \
  --model medium
```

Output is always English. `turbo`, `.en` models, Parakeet, and Qwen do not
support this translation mode. Choose a compatible template such as `default`,
`bold-headline`, or `golden-title`, or add `--disable-word-animations` to remove
a template's word effects. Cue animations and static backdrops remain available.

### Burn an existing subtitle file

Render a local SRT or ASS without transcription:

```bash
multisubs -i ./video.mp4 -o ./output --subtitle-file ./captions.srt
```

For an ASS file that uses custom fonts:

```bash
multisubs -i ./video.mp4 -o ./output \
  --subtitle-file ./styled.ass \
  --fonts-dir ./fonts
```

The result is a collision-safe `video-subtitled.mp4` copy with hard subtitles
and copied audio. ASS keeps its authored styling; SRT uses libass defaults.
This mode accepts input, output, `--fonts-dir`, `--verbose`, and the
[video encoding options](#video-encoding); transcription,
template, styling, animation, preview, and `--keep-transcriptions` options
are rejected. Python callers can use `render_subtitle_file()`;
see [public functions](#public-functions).

## ⚙️ Command reference

The blocks below follow the names and order shown by `multisubs --help`.
Run that command for the CLI's complete, authoritative help text.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-i`, `--input-path PATH` | required | Path to one local input video. |
| `-v`, `--version` | — | Print the package version. |
| `--verbose` | off | Show detailed processing progress and backend logs. |
| `-o`, `--output-dir DIR` | current directory | Directory for generated files. |
| `--subtitle-file PATH` | off | Burn an existing SRT or ASS file into the video without transcription. |
| `--asr BACKEND` | `whisperx` | `whisperx`, `faster-whisper`, `parakeet`, or `qwen`. |
| `-l`, `--lang CODE` | automatic when exposed | Source-language code supported by the selected ASR. For Parakeet it labels metadata but does not condition transcription; English-only Whisper models use `en`. |
| `-t`, `--task TASK` | `transcribe` | `transcribe` or translate speech to English. |
| `-m`, `--model MODEL` | backend default | Model used by the selected ASR. |
| `-k`, `--keep-transcriptions` | off | Keep JSON, SRT, and ASS in a `subtitles` directory. |
| `--cache-dir DIR` | `<output-dir>/.multisubs-cache` | Override the source-speech cache location for transcription runs, independently of presentation and retained artifacts. |
| `--refresh-cache` | off | Recognize again and atomically refresh the matching entry in the default or custom cache directory. |
| `--subtitles-only` | off | Export a collision-safe SRT/ASS pair without rendering video; supports transcription only. |
| `--template NAME` | `default` | Select a built-in or `--template-dir` custom presentation by JSON name. |
| `--template-dir DIR` | — | Read immediate custom template JSON files for this invocation; custom names take precedence over built-ins. |
| `--position POSITION` | `bottom-center` | Native ASS semantic position. |
| `-h`, `--help` | — | Show CLI help and backend-dependent support guidance. |

Defaults in the appearance and relative-unit tables describe the `default`
template. A selected template supplies its documented baseline first;
explicitly provided flags then replace only their own fields.

#### Progress and diagnostics

By default, multisubs shows only its own processing stages, relevant subtitle
warnings, errors, and final output path. Output printed by ASR runtimes and
native libraries is suppressed during processing, including backend warnings
and progress bars. Use `--verbose` to show detailed stages and the raw backend
output when diagnosing a run. If a backend fails, multisubs still reports the
failed operation; rerun with `--verbose` to inspect the backend diagnostics.

#### ASR backends and models

| ASR | Default model | Task and timing notes |
| --- | --- | --- |
| `whisperx` | `turbo` | Transcription with WhisperX alignment; translation uses six-second chunks and a shared layout fallback; English translation requires a multilingual non-Turbo model. |
| `faster-whisper` | `turbo` | Silero VAD and native word timestamps; translation uses the same six-second chunks and layout fallback as WhisperX. |
| `parakeet` | `nvidia/parakeet-tdt-0.6b-v3` | Automatic multilingual transcription and native timestamps; optional `--lang` labels artifact metadata because NeMo does not expose the detected code. |
| `qwen` | `Qwen/Qwen3-ASR-1.7B-hf` | Native Hugging Face multilingual transcription with quiet-boundary chunks up to three minutes; explicit or automatically detected aligner-supported languages receive word timestamps. |

Use `--model` to select another model listed in the command reference. The
backend runtime is imported only after validation and only when selected.

WhisperX models: `tiny.en`, `tiny`, `base.en`, `base`, `small.en`, `small`,
`medium.en`, `medium`, `large`, and `turbo`. Faster-Whisper accepts the same
small models plus `large-v1`, `large-v2`, `large-v3`, and `large-v3-turbo`.
Parakeet accepts `nvidia/parakeet-tdt-0.6b-v3`; Qwen accepts
`Qwen/Qwen3-ASR-1.7B-hf`.

#### Native subtitle positions

`--position` changes only alignment; margins and maximum dimensions retain their
defaults unless they are overridden independently.

Available semantic positions:

| `top-left` | `top-center` | `top-right` |
| --- | --- | --- |
| `middle-left` | `center` | `middle-right` |
| `bottom-left` | `bottom-center` | `bottom-right` |

### Video encoding

| Option | Default | Description |
| --- | --- | --- |
| `--video-encoder ENCODER` | FFmpeg selection | Select `libx264` or `h264_nvenc` for video rendering. |
| `--video-preset PRESET` | encoder default | Select an encoder-compatible speed/compression preset; requires `--video-encoder`. |
| `--video-quality INTEGER` | encoder default | Integer `0`–`51`, using CRF for x264 or CQ for NVENC; requires `--video-encoder`. |

#### Defaults

For normal rendering, omitting `--video-encoder` leaves encoder selection,
preset, and quality to FFmpeg. In the tested MP4 runs, FFmpeg selected
`libx264 / medium / CRF 23`. NVIDIA encoding is enabled only when explicitly
selected; using a GPU for transcription does not enable it for rendering.

| Encoder | Default preset | Default quality |
| --- | --- | --- |
| omitted | FFmpeg default | FFmpeg default |
| `libx264` (CPU) | `medium` | CRF `23` |
| `h264_nvenc` (NVIDIA) | `p4` | CQ `28`, VBR without a target bitrate |

#### Examples

Use NVIDIA with the recommended defaults (`p4 / CQ 28`):

```bash
multisubs -i ./video.mp4 -l pt -o ./output --video-encoder h264_nvenc
```

Use CPU with explicit defaults (`medium / CRF 23`):

```bash
multisubs -i ./video.mp4 -l pt -o ./output --video-encoder libx264
```

For faster CPU rendering, select `veryfast`. Quality remains CRF 23, but fine
details can be softer than with `medium`:

```bash
multisubs -i ./video.mp4 -l pt -o ./output \
  --video-encoder libx264 --video-preset veryfast
```

For higher NVIDIA fidelity and larger files, add `--video-quality 23` to the
NVIDIA command. CQ 23 and CQ 28 had similar encoding times in the
[real-footage benchmarks](docs/benchmarks/2026-10-18-real-rendering.md);
CQ 23 produced files 64–84% larger. Detailed speed/quality/size comparisons,
including earlier 4K tests, are in the
[rendering investigation](docs/benchmarks/2026-10-18-rendering.md).

#### Options and compatibility

`--video-preset` and `--video-quality` require `--video-encoder`.

- **Preset:** controls the speed/compression tradeoff. x264 accepts `ultrafast`,
  `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`,
  and `placebo`. NVENC accepts `p1` through `p7`, from fastest to slowest.
- **Quality:** integer `0`–`51`, using CRF for x264 and CQ for NVENC. Lower values
  generally preserve more detail and produce larger files. CRF and CQ numbers
  are not equivalent. NVENC CQ `0` requests automatic quality selection.

These options work with normal rendering, `--subtitle-file`,
`--preview-animation`, and `--preview-clip`. PNG `--preview-layout` accepts valid
encoding options and ignores them, so you can keep the same settings when
switching preview modes. PNG generation does not initialize the video encoder.
Animated previews use `libx264` when no encoder is selected and remain silent;
normal rendering copies audio. Encoding settings are independent of subtitle
templates.

Both explicit encoders produce H.264. The output keeps the input extension,
so its container must support H.264. NVENC requires a compatible NVIDIA GPU,
driver, and FFmpeg build. Encoder initialization errors stop processing before
transcription; the requested encoder is never silently replaced. Decoding and
subtitle filtering continue to use the CPU.

### Subtitle preview

| Option | Default | Description |
| --- | --- | --- |
| `--preview-layout` | off | Render one layout preview PNG without transcription; exclusive with other preview modes. Valid video encoding options are accepted and ignored. |
| `--preview-animation` | off | Render a silent H.264 MP4 with simulated word timing; exclusive with other preview modes. |
| `--preview-clip` | off | Render moving source video with actual transcript timing and available source audio; transcription only and exclusive with other preview modes. |
| `--preview-at HH:MM:SS` | first frame for samples; required for real clips | Whole-second frame selection for PNG/animation, or the required source start for `--preview-clip`; use two digits per field. |
| `--preview-duration DURATION` | animation `4s`; real clip `10s` | Animation cue or real clip duration, `1s` through `15s` in whole `ms` or `s`. Real clips stop at the media end; PNG rejects duration. |
| `--preview-text TEXT` | sample text | Replace sample subtitle text in PNG/animation previews. |
| `--preview-guides` | off | Draw placement, envelope, and canvas guides in PNG/animation previews. |

### Subtitle appearance

| Option | Default | Description |
| --- | --- | --- |
| `--font NAME` | `Roboto` | Bundled, custom, or system subtitle font family. |
| `--text-color COLOR` | `#FFFFFF` | Subtitle text color. |
| `--font-weight WEIGHT` | `regular` (`400`) | Named or numeric weight from 100 through 900. |
| `--bold`, `--no-bold` | off | Compatibility shorthand for weight 700 or 400. |
| `--italic`, `--no-italic` | off | Enable or disable italic text. |
| `--backdrop KIND` | `box` | `none`, `outline`, or `box`. |
| `--backdrop-color COLOR` | `#00000099` | Outline, box, and shadow color. |
| `--word-backdrop KIND` | `none` | Timed word decoration: `none`, `outline`, or `box`. |
| `--word-backdrop-color COLOR` | `#111827E6` | Timed word-decoration color. |
| `--opacity PERCENT` | `100%` | Opacity multiplier for the complete composition. |
| `--text-case MODE` | `original` | `original`, `uppercase`, or `lowercase`. |
| `--fonts-dir DIR` | — | Additional `.ttf`, `.otf`, or `.ttc` fonts for this run. |

Colors use `#RRGGBB` or `#RRGGBBAA`, where `00` is transparent and `FF` is
opaque. Text case is applied before measurement; retained JSON keeps the
original transcript and aligned words.

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

### Subtitle animations

| Option | Default | Description |
| --- | --- | --- |
| `--animation-{cue\|word}-{text\|backdrop}-{entrance\|emphasis\|exit} TYPE` | inherited or `none` | Select one phase on one independent visual track; run `--help` for the animation types valid for each phase. |
| `--animation-{cue\|word}-{text\|backdrop}-{entrance\|emphasis\|exit}-duration DURATION` | phase or template default | Override an enabled phase with `10ms`–`5000ms`, expressed as `150ms` or `0.15s`. |
| `--animation-word-text-mode MODE` | `active-word` | Use `active-word` or `progressive` timing for word text. |
| `--animation-word-backdrop-mode MODE` | `active-word` | Use `active-word` or `progressive` timing for the word decoration. |
| `--animation-word-text-highlight-color COLOR` | `#FFD54F` when enabled | Set the text color used by the `highlight` word emphasis. |
| `--disable-cue-animations` | off | Remove all cue text/backdrop animation phases, preserving the static cue backdrop. |
| `--disable-word-animations` | off | Remove all word text/backdrop animation phases, word highlight, and timed word decoration. |

#### Cue and word effects

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
alignment. They are rejected for translation; incomplete mappings use the
complete-cue fallback. Unsupported shaping cases retain cue-level effects and
fall back to complete logical-line rendering; word tracks are suppressed.
Previews use the same fallback and report a warning.

Source word timestamps are preserved, including zero durations. For an empty
word-effect interval after ASS centisecond rounding, multisubs first uses an
adjacent free gap large enough for the configured entrance and exit plus
100 ms of stable display. If no such gap fits, the word shares a nearby word's
animation and highlight interval. This estimates presentation timing only;
other positive intervals and cue times remain unchanged. Text and word backdrop
resolve their timing independently, and usable progressive intervals are kept.
If neither a gap nor a timed neighbor is available, the complete cue retains
its text and cue effects with word effects suppressed. Retained JSON reports
these estimates under `timing_recovery` in per-cue `word_effect` and aggregate
rendering `word_effects` diagnostics, separately from original word timestamps.

The two suppression flags operate independently by scope. Every
`entrance`, `emphasis`, and `exit` phase is an animation. Therefore,
`--disable-cue-animations` removes all cue text and backdrop animation tracks,
while preserving the static cue backdrop. `--disable-word-animations` removes
all word text and backdrop animation tracks, the word backdrop decoration, and
highlight color. The word backdrop is removed because it depends on aligned-word
timestamps even when its own phases are neutral.

### Relative layout units

| Option | Default | Description |
| --- | --- | --- |
| `--font-size LENGTH` | `4%` | Size relative to the render height, or PlayRes pixels. |
| `--letter-spacing LENGTH` | `0px` | Extra spacing between rendered grapheme clusters. |
| `--line-height auto\|LENGTH` | `auto` | Baseline distance for multi-line subtitles. |
| `--backdrop-size LENGTH` | `25%` | Outline thickness or box padding. |
| `--word-backdrop-size LENGTH` | `25%` | Outline thickness or padding for each timed word decoration. |
| `--shadow-size LENGTH` | `0px` | Shadow size relative to the resolved font size or in pixels. |
| `--margin-left LENGTH` | `18%` | Native ASS left margin. |
| `--margin-right LENGTH` | `18%` | Native ASS right margin. |
| `--margin-top LENGTH` | `0%` | Native ASS margin for top positions. |
| `--margin-bottom LENGTH` | `3%` | Native ASS margin for bottom positions. |
| `--max-width LENGTH` | `100%` | Maximum subtitle width. |
| `--max-height LENGTH` | `12%` | Maximum height used to derive line capacity. |

#### Native margins

These defaults are identical for landscape, portrait, square, and rotated
inputs. Percentages resolve from each video's autorotated render geometry.

Only the active vertical margin can be supplied explicitly: top positions use
`--margin-top`, bottom positions use `--margin-bottom`, and middle positions use
neither. An inactive vertical margin is rejected with an actionable error. The
default `bottom-center` layout therefore keeps `--margin-top` at `0%` and uses
the `3%` bottom inset. A top position needs an explicit `--margin-top` when an
inset is desired.

#### Percentage bases

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

#### Adaptive wrapping

Wrapping uses the selected font's measured metrics when available and a
Unicode-aware estimate otherwise; size, spacing, line height, decorations, and
maximum dimensions all contribute. Japanese and Chinese records receive
[language-specific grouping](docs/architecture.md#unicode-segmentation-and-source-mapping),
while validated alignment records remain the timing units for word effects.
Text is never truncated. If a source/alignment map is incomplete, the full cue
keeps its segment timing and word effects are disabled rather than inventing
timestamps. For translation, six-second backend chunks are tried before the
layout fallback makes up to three retries, reducing the effective font size
by 4% per step when translated text cannot fit its measured envelope. SRT and ASS
share intentional line breaks; JSON retains source text beside rendered
`display_text` and records requested versus effective rendering values.

### Custom subtitle coordinates

| Option | Default | Description |
| --- | --- | --- |
| `--position-x LENGTH` | — | Explicit global PlayRes X coordinate. |
| `--position-y LENGTH` | — | Explicit global PlayRes Y coordinate. |
| `--anchor POSITION` | — | Subtitle-box anchor for explicit coordinates. |

Coordinate percentages use render width for X and render height for Y.
Pixels refer to the global ASS PlayRes canvas.

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

## 🎨 Subtitle templates

### Built-in template catalog

Choose a template with `--template NAME`. Omitted selection uses `default`:
Roboto Regular with white text on a translucent black box.

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
lines. Explicit appearance, layout, and animation flags override only their
corresponding template fields.

### Define a custom template

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

## 🔤 Fonts and coverage

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

## 🐍 Python API

Use the package-root APIs to keep source transcription separate from styling
and rendering. Start with [transcript reuse](#transcribe-once-and-reuse-the-transcript)
or [template overrides](#compose-subtitle-settings-in-python); full signatures
and configuration rules follow the examples.

### Transcribe once and reuse the transcript

Use the Python API to transcribe a video once and render subtitles later with
different templates or video framing. `transcribe_speech()` returns the original
speech segments and available word times without creating subtitle files.
`render_transcript()` generates SRT, styled ASS, and a hard-subtitled video using
the normal subtitle pipeline and the final video's geometry, without another
ASR call:

```python
from multisubs import transcribe_speech, render_transcript

speech = transcribe_speech("video.mp4", lang="pt", asr_backend="faster-whisper")
artifacts = render_transcript(speech, "video.mp4", "output", template="yellow-pop")
```

Cache `speech.to_dict()` as JSON and pass the restored dictionary directly to
`render_transcript()`. For a cut, select the content and shift its supplied times
to the cut's timeline before rendering. Missing word times and unknown language
keep the normal fallbacks.

Save the source speech data for a later run:

```python
import json
from pathlib import Path

Path("speech.json").write_text(
    json.dumps(speech.to_dict(), ensure_ascii=False), encoding="utf-8"
)
```

### Compose subtitle settings in Python

Use `build_subtitle_config()` to combine a built-in or custom template with
sparse presentation overrides before acquiring media or transcribing. Pass the
returned immutable `SubtitleConfig` directly to `render_transcript()`.
This example loads the `speech.json` cache saved above:

```python
import json
from pathlib import Path

from multisubs import build_subtitle_config, render_transcript

config = build_subtitle_config(
    template="yellow-pop",
    overrides={
        "position": "bottom-center",
        "margin_bottom": "8%",
        "font_size": "4.5%",
        "italic": False,
        "animation_word_text_emphasis": "none",
    },
)
speech = json.loads(Path("speech.json").read_text(encoding="utf-8"))
artifacts = render_transcript(speech, "video.mp4", "output", subtitle_config=config)
```

See [public functions](#public-functions) for the signatures and
[subtitle configuration reference](#subtitle-configuration-reference) for all
override keys, inheritance rules, and errors.

### Public functions

Import these functions from `multisubs`. File and directory paths accept `str`
or `Path`; arguments after `*` must be passed by name. Where available,
`progress` accepts a callback that receives a message string, such as
`progress=print`.

#### transcribe_speech()

Recognize speech in a local video and return source segments and available
word timestamps as a `SpeechTranscript`.

```text
transcribe_speech(
    input_path, lang=None, task="transcribe", model_name=None,
    *, asr_backend="whisperx", progress=None, verbose=False,
) -> SpeechTranscript
```

- `asr_backend` selects `"whisperx"`, `"faster-whisper"`, `"parakeet"`, or
  `"qwen"`; `model_name=None` uses that backend's default model.
- `lang=None` uses automatic language detection where the backend exposes it.
  See [backend and language behavior](#asr-backends-and-models) for the differences.
- `task` accepts only `"transcribe"` through this API.
- The result preserves source text, segment/word association, and supplied
  timestamps, including missing alignment. Subtitle files are created later by
  `render_transcript()`.

Use `speech.to_dict()` to obtain lossless version-1 data for JSON caching, and
`SpeechTranscript.from_dict(data)` to validate and restore it. See the
[source speech contract](docs/architecture.md#deferred-speech-rendering) for
fields and timing limits.

#### build_subtitle_config()

Combine a selected template with only the presentation settings you supply.

```text
build_subtitle_config(
    *, template=None, template_dir=None, overrides=None,
) -> SubtitleConfig
```

The returned `SubtitleConfig` is immutable and can be reused across renders.
Call this function before expensive media work to validate template selection
and overrides. Pass the result through `render_transcript(subtitle_config=...)`.
See [configuration rules and supported keys](#subtitle-configuration-reference).

#### render_transcript()

Create SRT, ASS, and a hard-subtitled video from existing speech data using the
final video's geometry.

```text
render_transcript(
    transcript, video_path, output_dir,
    *, template=None, template_dir=None, subtitle_config=None, progress=None,
    video_encoding=None,
) -> GeneratedSubtitleArtifacts
```

- `transcript` accepts a `SpeechTranscript` or its version-1 dictionary, such as
  the result of `json.load()`. Its task must be `"transcribe"`.
- Segment and word times must already be local to `video_path`. For a cut,
  select the content and shift the supplied times before calling this function.
- Choose a template with `template` and optional `template_dir`, or pass a
  complete `subtitle_config`. These alternatives cannot be combined.
- Rendering reuses the supplied speech without another ASR call. Missing
  alignment keeps normal timing fallbacks and reports suppressed word effects
  through `progress`, or `UserWarning` when no callback is supplied.
- `video_encoding` accepts the immutable `VideoEncodingConfig` exported from
  `multisubs`, separately from `subtitle_config` and its template overrides.

```python
from multisubs import VideoEncodingConfig, render_transcript

artifacts = render_transcript(
    speech,
    "video.mp4",
    "output",
    template="yellow-pop",
    video_encoding=VideoEncodingConfig(
        encoder="h264_nvenc",
        preset="p4",
        quality=28,
    ),
)
```

`VideoEncodingConfig(encoder=None, preset=None, quality=None)` preserves existing
FFmpeg selection. Explicit encoders inherit the defaults in
[video encoding](#video-encoding). The same keyword is supported by
`render_subtitle_file()` and `embed_subtitles()`; `build_subtitle_config()`
continues to accept only presentation settings.

The returned `GeneratedSubtitleArtifacts` contains three `Path` attributes:
`srt_path`, `ass_path`, and `video_path`. All three files use one collision-safe
stem in `output_dir` and are published after successful rendering.

#### render_subtitle_file()

Burn an existing local SRT or ASS into a new video with copied audio.

```text
render_subtitle_file(
    video_path, subtitle_path, output_dir, *, fonts_dir=None, video_encoding=None,
) -> Path
```

`fonts_dir` supplies an optional local font directory. ASS keeps its authored
styling; SRT uses libass defaults. The returned `Path` points to the
collision-safe output video. See the
[existing subtitle recipe](#burn-an-existing-subtitle-file) for an example.

### Subtitle configuration reference

`build_subtitle_config()` supports all 57 CLI presentation settings through
`overrides`, a `Mapping[str, object]` such as a dictionary. The same composition
and validation rules apply to Python and the native CLI.

Use long option names with `--` removed and hyphens replaced by underscores:
`--font-size` becomes `font_size`, and `--disable-word-animations` becomes
`disable_word_animations`. Values use native CLI units and choices; Boolean
settings take Python `True` or `False`.

#### Template selection and inheritance

- `template=None` selects the name `default`.
- `template_dir` accepts `str` or `Path`. Custom names take precedence over
  built-ins, including `default`, and every discovered JSON file is validated.
- Only supplied fields replace the selected template's values. Omitted keys
  and `None` inherit; explicit `False` and valid zero values such as `"0px"`
  or `"0%"` are preserved.
- Use `"none"` to clear one inherited effect, or the scope disable flags below
  to clear related animation features together.

#### Text and fonts

- `font`: family name, such as `"Inter"`. `fonts_dir`: an optional directory
  supplied as `str` or `Path`.
- `font_weight`: a weight name such as `"semi-bold"`, a numeric string such as
  `"600"`, or an integer rank in steps of 100 from 100 through 900.
- `bold`: Boolean shorthand for weight 700 (`True`) or 400 (`False`). An
  explicit `font_weight` cannot be combined with `bold`.
- `italic`: Boolean. `text_case`: `"original"`, `"uppercase"`, or `"lowercase"`.
- `text_color`: `"#RRGGBB"` or `"#RRGGBBAA"`, such as `"#F8FAFC"`.
- `font_size` and `letter_spacing`: unit-bearing lengths such as `"4.5%"`
  and `"1px"`.
- `line_height`: `"auto"` or a length such as `"125%"` or `"32px"`.

See [appearance](#subtitle-appearance) for weight names and
[relative-unit bases](#percentage-bases) for how percentages resolve.

#### Backdrops and opacity

- `backdrop` and `word_backdrop`: `"none"`, `"outline"`, or `"box"`.
- `backdrop_color` and `word_backdrop_color`: hexadecimal colors with optional
  alpha, using the same syntax as `text_color`.
- `backdrop_size`, `word_backdrop_size`, and `shadow_size`: unit-bearing lengths
  such as `"12%"`, `"3px"`, or `"0px"`.
- `opacity`: a percentage string from `"0%"` through `"100%"`, applied to the
  complete composition.

#### Placement and dimensions

- `position`: one of the [nine named positions](#native-subtitle-positions), such
  as `"bottom-center"`.
- `margin_left`, `margin_right`, `margin_top`, and `margin_bottom`: lengths
  such as `"8%"` or `"24px"`. Only the active vertical margin may be supplied:
  top positions accept `margin_top`, bottom positions accept `margin_bottom`,
  and middle positions accept neither, even with a zero value.
- `max_width` and `max_height`: maximum subtitle dimensions, expressed as
  percentage or pixel lengths.
- `position_x`, `position_y`, and `anchor`: explicit coordinates and a named
  box anchor, such as `"50%"`, `"80%"`, and `"bottom-center"`.

For explicit coordinates, supply `position_x`, `position_y`, `anchor`,
`max_width`, and `max_height` together in `overrides`. Explicit `position` or
margin overrides cannot accompany them; inherited template placement does not
cause a conflict. The complete envelope must fit the final video canvas.
See [exact coordinates](#custom-subtitle-coordinates).

#### Animation phases and word effects

Each of the four tracks has independent entrance, emphasis, and exit phases.
Build an override key with these patterns:

```text
animation_{scope}_{element}_{phase}
animation_{scope}_{element}_{phase}_duration
```

Use `cue` or `word` for `scope`, `text` or `backdrop` for `element`, and
`entrance`, `emphasis`, or `exit` for `phase`. For example,
`animation_cue_text_entrance="fade"` selects a cue entrance, and
`animation_cue_text_entrance_duration="150ms"` sets its duration.

Animation names depend on the track and phase; see the
[animation reference](#cue-and-word-effects) and `multisubs --help` for valid
choices. Duration strings accept `"10ms"` through `"5000ms"`, including seconds
such as `"0.15s"`, and must resolve to whole milliseconds. `"none"` and
`"highlight"` phases do not accept a duration override.

Additional word and suppression settings:

- `animation_word_text_mode` and `animation_word_backdrop_mode`:
  `"active-word"` or `"progressive"`.
- `animation_word_text_highlight_color`: a hexadecimal color; requires
  `animation_word_text_emphasis="highlight"`. Setting the emphasis to `"none"`
  also removes its inherited highlight color.
- `disable_cue_animations=True`: clears every cue text/backdrop phase while
  preserving the static cue backdrop.
- `disable_word_animations=True`: clears every word text/backdrop phase,
  word decoration, and highlight color.

Scope disables apply after override validation. Invalid animation settings
still raise an error even when their scope is disabled.

#### Errors and validation timing

Import configuration errors from `multisubs`:

- `ValidationError`: unknown override names, invalid values, or conflicting
  options. Unknown names are rejected even when their value is `None`.
- `TemplateError`: invalid custom directories/files or packaged templates.
- `MultisubsError`: the shared base class for both exceptions.

Composition reads configuration resources and checks supplied directories.
It does not probe media, run FFmpeg or ASR, load font faces, access the network,
or materialize assets. It leaves caller mappings and template baselines intact.

Relative lengths stay unresolved in the returned configuration. Geometry-dependent
limits and envelope checks run during rendering against each final video.
Reuse the same config for different geometries by passing only
`subtitle_config=config` to `render_transcript()`.

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
languages keep real low-energy-boundary chunks capped at three minutes and use
the documented coarse timing fallback. Unsupported explicit combinations fail
before model loading.

## 📁 Generated files

For `video.mp4` with selected or automatically detected source language `pt`:

```text
# Default transcription: rendered video and reusable source speech
output/
├── .multisubs-cache/
│   └── transcriptions/
│       └── v1/
└── video-pt.mp4

# With --keep-transcriptions
output/
├── .multisubs-cache/
└── video/
    ├── video-pt.mp4
    └── subtitles/
        ├── video-pt.json
        ├── video-pt.srt
        └── video-pt.ass

# With --preview-animation: one silent frozen-background clip
output/
└── video-subtitle-animation-preview.mp4

# With --subtitle-file captions.srt or styled.ass
output/
└── video-subtitled.mp4

# With --subtitles-only
output/
├── .multisubs-cache/
├── video-pt.srt
└── video-pt.ass

# With --preview-clip (real source audio/video and speech timing)
output/
├── .multisubs-cache/
└── video-subtitle-clip-preview.mp4

# With render_transcript(...), language pt
output/
├── video-pt.srt
├── video-pt.ass
└── video-pt.mp4
```

Existing paths are never overwritten. multisubs adds suffixes such as `(1)` to
new files or directories when a name already exists.

Artifact names and JSON `metadata.language` use the resolved source-language
code when available, including for translation runs whose subtitle text is
English. When no code is available, `metadata.language` is `null` and names use
the source stem without a language suffix: `video.mp4`, `video.json`,
`video.srt`, and `video.ass`.

Work happens in a private temporary directory inside the requested output
directory. Rendered artifacts are published only after FFmpeg succeeds;
subtitle-only exports are published after their preparation succeeds. If
normal transcription fails, its artifacts are retained there for diagnosis;
partial final media is not published.

Transcription runs retain reusable source speech under
`<output-dir>/.multisubs-cache/transcriptions/v1` by default. `--cache-dir DIR`
moves that storage to `DIR/transcriptions/v1`; translation, sample previews,
external subtitle rendering, and Python rendering APIs do not create an
automatic speech cache. See
[transcription reuse and real previews](#reuse-transcription-while-trying-subtitle-styles)
for the retention and refresh policy.

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

To require the NVIDIA encoder checks on a compatible local GPU, run
`MULTISUBS_TEST_NVENC=1 python -m pytest -m integration tests/test_video_encoding_integration.py`.
These checks use synthetic media through the CLI and public rendering APIs;
they do not load an ASR model.

For local debugging, `python -m scripts.replay_subtitle_layout retained.json`
rebuilds collision-safe JSON/SRT/ASS without loading speech models. `--render`
uses a synthetic background; `--uncaptioned-video` explicitly selects a clean
video. Replay cannot recover text or boundaries discarded by earlier
processing. See the [regression instructions](docs/plans/multilingual-subtitles/00-regressions-and-decisions.md).

For local rendering benchmarks on Linux, run
`python -m scripts.benchmark_rendering --output-dir data/benchmarks --quality`.
This uses synthetic media without ASR and records repeated preparation,
decode/filter, and encode measurements in a fresh ignored directory. Optional
`--nvenc` cases require a compatible NVIDIA GPU, driver, and FFmpeg build.
See the [method, results, and optimization candidates](docs/benchmarks/2026-10-18-rendering.md)
before interpreting throughput or quality comparisons.

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
