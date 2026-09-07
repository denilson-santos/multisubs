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
| 🧩 Ready-made templates | Twenty-five built-in presentations for Reels, TikTok, Shorts, podcasts, tutorials, and editorial clips. |
| 🎨 Semantic styling | Font, weight, size, letter spacing, line height, colors, opacity, casing, backdrop, and shadow controls. |
| 🔤 Bundled fonts | 82 static faces from six OFL families render offline without system installation. |
| 📐 Responsive layout | Fixed resolution-aware defaults with explicit position, margin, width, and height controls. |
| 🎯 Precise placement | Nine semantic positions, relative units, margins, safe envelopes, and exact PlayRes coordinates. |
| 👀 Fast previews | Render one subtitle preview frame without loading WhisperX or transcribing the video. |
| ✨ Subtitle animation | Independent entrance, emphasis, and exit phases for complete cues and aligned words. |
| 🧠 Adaptive wrapping | Font-aware wrapping that favors readable language and timing boundaries. |
| 🛡️ Safe outputs | Collision-safe names and temporary rendering prevent existing or partial files from being overwritten. |

## 📋 Requirements

- Python 3.10 through 3.13. WhisperX 3.8.6 does not support Python 3.14.
- FFmpeg and ffprobe available on `PATH`.
- An FFmpeg build with the `subtitles` filter and libass support; animated
  previews additionally require the `libx264` H.264 encoder.
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
  --template golden-title
```

The current Roboto Regular, white-on-translucent-black presentation remains the
`default`. Every explicit appearance, layout, or animation option overrides only
its corresponding template field:

```bash
multisubs -i ./video.mp4 -l pt \
  --template bold-headline \
  --text-color '#B8FF5A' \
  --margin-bottom 10%
```

| Template | Good for | Font | Main presentation |
| --- | --- | --- | --- |
| `default` | General use | Roboto Regular | White, original case, translucent black box, bottom-center. |
| `studio-outline` | Interviews, courses, demos | Inter Medium | White text with a clean dark outline, bottom-center. |
| `bold-headline` | Reels, TikTok, Shorts hooks | Montserrat ExtraBold | Compact uppercase white headline with a measured pop. |
| `podcast-panel` | Podcasts and longer interviews | Atkinson Hyperlegible Next Medium | White text on a dark two-line panel, bottom-left. |
| `serif-quote` | Documentary and reflective clips | Lora Medium Italic | Warm italic serif text with a subtle outline and fade. |
| `amber-word` | Explanations and speaking points | Inter SemiBold | Outlined text with an amber active-word highlight. |
| `mint-progress` | Tips, steps, and demonstrations | Montserrat Medium | Dark panel with progressive mint word highlighting. |
| `paper-label` | Editorial callouts and labels | Roboto Medium | Dark text on a warm paper card with a slide-in. |
| `focus-marker` | Accessible educational captions | Atkinson Hyperlegible Next Bold | Outlined text with an amber active-word marker. |
| `soft-shadow` | Calm narration and lifestyle clips | Lora SemiBold | White serif text with a soft shadow, top-center. |
| `golden-title` | Concise topics and chapter titles | Oswald Bold | Golden uppercase text with a dark outline, bottom-left. |
| `sage-serif` | Wellness and reflective narration | Lora Regular | Soft green serif text with a gentle fade, top-right. |
| `crimson-banner` | Podcast takeaways and strong statements | Oswald Medium | White text on a compact crimson banner, bottom-right. |
| `lemon-card` | Practical reminders and short tips | Inter SemiBold | Dark text on a soft yellow card, top-center. |
| `emerald-word` | Word-led explainers | Roboto Bold | White outlined text with a deep green active-word box. |
| `kinetic-lime` | Fast explanations and tutorials | Montserrat Bold | White outlined text with a lime active-word highlight, bottom-center. |
| `cobalt-pop` | Hooks and strong statements | Inter ExtraBold | Uppercase white text on a cobalt panel with a coordinated pop. |
| `coral-marker` | Advice and interview cuts | Roboto SemiBold | White outlined text with a coral active-word marker, bottom-left. |
| `editorial-reveal` | Storytelling and reflective clips | Lora SemiBold Italic | Warm serif text that reveals words in order, bottom-center. |
| `headline-bounce` | Energetic punchlines and takeaways | Oswald SemiBold | Uppercase yellow outlined text with a bounded active-word bounce. |
| `yellow-pop` | Hooks and reactions | Montserrat ExtraBold | Uppercase outlined text with an exact `#FBE003` active-word pop. |
| `yellow-trace` | Tips and step-by-step clips | Inter Medium | White text on a compact panel with progressive `#FBE003` highlighting. |
| `neon-lime-marker` | Energetic explainers | Oswald Medium | Outlined text with a neon-lime active-word marker. |
| `neon-cyan-reveal` | High-energy explainers | Atkinson Hyperlegible Next Bold | Neon-cyan text with progressive slide-up word reveals. |
| `neon-magenta-pulse` | Reactions and creator commentary | Roboto Bold | Uppercase neon-magenta text with an active-word pulse. |

The exact template baselines are:

| Template | Size and text | Backdrop | Native layout | Animation |
| --- | --- | --- | --- | --- |
| `default` | `4%`, `#FFFFFF`, original, `100%` | box `#00000099`, `25%`, shadow `0px` | bottom-center; L/R `18%`, B `3%`, W/H `100%`/`10%` | none |
| `studio-outline` | `3.4%`, `#FFFFFF`, original | outline `#111827`, `4%`, shadow `0px` | bottom-center; L/R `10%`, B `3%`, W/H `100%`/`6%` | none |
| `bold-headline` | `3.8%`, `#FFFFFF`, uppercase | outline `#111827`, `7%`, shadow `0px` | center; L/R `10%`, W/H `100%`/`6%` | pop in, fade out |
| `podcast-panel` | `3.2%`, `#FFFFFF`, original | box `#111827D9`, `18%`, shadow `0px` | bottom-left; L/R `10%`, B `3%`, W/H `100%`/`9%` | none |
| `serif-quote` | `3.4%`, `#FFF8ED`, italic | outline `#111827`, `4%`, shadow `0px` | bottom-center; L/R `10%`, B `3%`, W/H `100%`/`9%` | fade in/out |
| `amber-word` | `3.4%`, `#FFFFFF`, original | outline `#111827`, `5%`, shadow `0px` | bottom-center; L/R `10%`, B `3%`, W/H `100%`/`6%` | active-word amber highlight |
| `mint-progress` | `3.3%`, `#FFFFFF`, original | box `#111827D9`, `15%`, shadow `0px` | bottom-center; L/R `10%`, B `3%`, W/H `100%`/`6%` | progressive mint highlight |
| `paper-label` | `3.2%`, `#111827`, original | box `#FFF8EDFF`, `20%`, shadow `0px` | top-left; L/R `10%`, T `12%`, W/H `100%`/`6%` | slide right in, fade out |
| `focus-marker` | `3.4%`, `#FFFFFF`, original | outline `#111827`, `4%`; word box `#FFD54F`/`12%` | bottom-center; L/R `10%`, B `3%`, W/H `100%`/`6%` | active-word highlight and box |
| `soft-shadow` | `3.5%`, `#FFFFFF`, original | none; shadow `#111827CC`/`4%` | top-center; L/R `10%`, T `12%`, W/H `100%`/`6%` | none |
| `golden-title` | `3.6%`, `#FACC15`, uppercase | outline `#111827`, `6%`, shadow `0px` | bottom-left; L/R `10%`, B `3%`, W/H `100%`/`6%` | none |
| `sage-serif` | `3.4%`, `#BBF7D0`, original | outline `#111827`, `5%`, shadow `0px` | top-right; L/R `10%`, T `12%`, W/H `100%`/`6%` | fade in/out |
| `crimson-banner` | `3.3%`, `#FFFFFF`, original | box `#991B1BFF`, `18%`, shadow `0px` | bottom-right; L/R `10%`, B `3%`, W/H `100%`/`6%` | fade in/out |
| `lemon-card` | `3.2%`, `#111827`, original | box `#FDE68AFF`, `20%`, shadow `0px` | top-center; L/R `10%`, T `12%`, W/H `100%`/`6%` | none |
| `emerald-word` | `3.4%`, `#FFFFFF`, original | outline `#111827`, `5%`; word box `#166534FF`/`12%` | bottom-right; L/R `10%`, B `3%`, W/H `100%`/`6%` | active-word box |
| `kinetic-lime` | `3.4%`, `#FFFFFF`, original | outline `#111827`, `5%`; active text `#D9F99D` | bottom-center; L/R `10%`, B `12%`, W/H `90%`/`6%` | slide up 180ms, fade out 120ms; active-word highlight |
| `cobalt-pop` | `3.5%`, `#FFFFFF`, uppercase | box `#1E40AFFF`, `18%`, shadow `0px` | center; L/R `10%`, W/H `90%`/`6%` | text and box pop in 180ms, zoom out 140ms |
| `coral-marker` | `3.3%`, `#FFFFFF`, original | outline `#111827`, `4%`; word box `#FDA4AFFF`/`14%`, active text `#111827` | bottom-left; L/R `10%`, B `12%`, W/H `90%`/`6%` | fade in 140ms, fade out 120ms; word marker fades 70ms |
| `editorial-reveal` | `3.4%`, `#FFF8ED`, italic | outline `#111827`, `4%`, shadow `0px` | bottom-center; L/R `10%`, B `12%`, W/H `90%`/`6%` | zoom in 200ms, fade out 160ms; progressive word fade 100ms |
| `headline-bounce` | `3.5%`, `#FDE68A`, uppercase | outline `#111827`, `6%`, shadow `0px` | bottom-right; L/R `10%`, B `12%`, W/H `90%`/`6%` | fade in 120ms, slide down 160ms; active-word bounce 420ms |
| `yellow-pop` | `3.4%`, `#FFFFFF`, uppercase | outline `#111827`, `5%`, shadow `0px` | bottom-center; L/R `10%`, B `12%`, W/H `90%`/`6%` | active-word pop 120ms plus exact `#FBE003` highlight |
| `yellow-trace` | `3.3%`, `#FFFFFF`, original | box `#111827FF`, `15%`, shadow `0px` | bottom-left; L/R `10%`, B `12%`, W/H `90%`/`6%` | progressive `#FBE003` highlight |
| `neon-lime-marker` | `3.4%`, `#FFFFFF`, original | outline `#111827`, `4%`; word box `#39FF14FF`/`12%` | bottom-center; L/R `10%`, B `12%`, W/H `90%`/`6%` | active-word highlight; word marker zoom 100ms, fade 70ms |
| `neon-cyan-reveal` | `3.3%`, `#00F5FF`, original | outline `#111827`, `5%`, shadow `0px` | bottom-left; L/R `10%`, B `12%`, W/H `90%`/`6%` | progressive word slide-up 120ms |
| `neon-magenta-pulse` | `3.4%`, `#FF4FD8`, uppercase | outline `#111827`, `5%`, shadow `0px` | bottom-right; L/R `10%`, B `12%`, W/H `90%`/`6%` | active-word pulse 400ms |

All use `auto` line height, zero letter spacing, and full opacity. The static layout preview
suppresses motion and shows a deterministic representative state; the animated
preview clip runs the same phases with simulated word times. `progressive` word
tracks affect the first half of the cue in the static preview, while
`active-word` tracks affect only its first word. Word-highlight templates require
aligned word timing during transcription; disable an inherited phase without
changing the other tracks:

```bash
multisubs -i ./video.mp4 --preview-layout \
  --template mint-progress --animation-word-text-emphasis none
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
When the sample is larger than the resolved envelope, the preview keeps the
first prospective cue and uses all visual lines that fit before choosing its
next cue boundary. Sentence, clause, and pause boundaries still take priority;
among equivalent boundaries, the longest fitting prefix is retained. Words
that would belong to later hypothetical cues are omitted from this static
frame. Font metrics, backdrop/shadow allowances, and `--max-height` therefore
determine both the line breaks and how much sample text is visible.

### Preview subtitle animation

Generate a silent MP4 without loading WhisperX or transcribing speech:

```bash
multisubs -i ./video.mp4 -o ./previews \
  --preview-animation \
  --preview-duration 4s \
  --preview-at 00:00:10.500 \
  --template focus-marker \
  --preview-text "This is how the word animation will look"
```

The selected frame is captured once and frozen as the background. `--preview-at`
therefore chooses the background frame only; the subtitle cue starts at 500 ms,
and the clip adds 500 ms before and after it. Duration accepts whole `ms` or `s`
values from 1 to 15 seconds, defaults to `4s`, and the total clip is one second
longer. Word times are deterministic demonstrations, not synchronization with
source speech. The output is saved as
`<video-stem>-subtitle-animation-preview.mp4`, with a numeric suffix on
collision. `--preview-guides` remains available and labels the timing as
simulated. No JSON, SRT, ASS, audio, or transcription directory is published;
`--keep-transcriptions` is rejected in both preview modes.

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

Entrance supports `none`, `fade`, the applicable slide directions, `pop`, and
`zoom`. Emphasis supports `none`, `pulse`, `bounce`, `float`, and `breathe`;
cue tracks additionally support `shake` and `flash`. Exit supports `none`,
`fade`, the applicable slide directions, and `zoom`. Every motion phase has a
deterministic default duration. Append `-duration` to its option to use a value
from `10ms` through `5000ms`, written in milliseconds or seconds.

Word text can be highlighted progressively, providing a karaoke-style result:

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

`active-word` affects only the current validated word interval and leaves pauses
undecorated. `progressive` keeps each affected word visible through the end of
the cue. Word behavior requires source-language alignment and therefore cannot
be combined with translation. Cues with incomplete timing mappings fall back
to ordinary subtitles. Preview does not invent timing: it shows the first word
for `active-word` and the first half of the cue for `progressive`.

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
- `--opacity`: multiplies the alpha of text, cue/word backdrops, shadow, and timed
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
| `--template NAME` | `default` | Select one of the twenty-five built-in presentation baselines. Legacy preset names are rejected. |
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

# With --preview-animation: one silent frozen-background clip
output/
└── video-subtitle-animation-preview.mp4
```

Existing paths are never overwritten. multisubs adds suffixes such as `(1)` to
new files or directories when a name already exists.

Work happens in a private temporary directory inside the requested output
directory. Completed artifacts are published only after FFmpeg succeeds. If
processing fails, transcription artifacts are retained there for diagnosis;
partial final media is not published.

When `--keep-transcriptions` is enabled, the versioned JSON transcript includes
source and processing metadata, original and displayed cue text, render
geometry, resolved layout and typography, wrapping diagnostics, and the four
independent cue/word text/backdrop animation tracks. Rendering diagnostics also record the
requested and resolved template names; omitted selection is recorded as
requested `null` and resolved `default`. The current retained JSON contract
uses schema version `3` and stores animation data under
`metadata.rendering.animation`.

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
- Aligned-word behavior is unavailable for translated transcription output;
  static PNG previews suppress all motion and show one representative state for
  each configured word track, while animated MP4 previews use simulated timing.
- A static preview shows only the first fitting sample cue; later hypothetical
  cues are not rendered in the same frame.
- Animation distance, scale, and easing are fixed per semantic type; phase
  duration can be customized from `10ms` through `5000ms`.
- There is no interactive subtitle editor or graphical interface.
- Speaker diarization and speaker-specific styling are not supported.
- The output uses hard subtitles; selectable soft subtitle tracks are not
  created.
- FFmpeg and ffprobe must be available on the host; animated MP4 previews also
  need the `libx264` encoder. The selected Whisper model is required only for
  normal transcription.
- Font families outside the six bundled families require `--fonts-dir` or a
  compatible system font provider.
