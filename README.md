# multisubs

[![Development](https://github.com/denilson-santos/multisubs/actions/workflows/development.yml/badge.svg)](https://github.com/denilson-santos/multisubs/actions/workflows/development.yml)

multisubs is a command-line tool that transcribes a local video, creates timed subtitle files, and burns those subtitles into a new video.

It uses WhisperX for transcription and word alignment, then produces JSON, SRT, and ASS artifacts. FFmpeg renders the ASS subtitles into the final video.

## Requirements

- Python 3.10 through 3.13. WhisperX 3.8.6 does not support Python 3.14.
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

Customize subtitle appearance and layout:

~~~
multisubs \
  -i ./video.mp4 \
  -l pt \
  -o ./output \
  --font "Roboto" \
  --font-size 4.5% \
  --letter-spacing 1px \
  --text-color '#FFFFFF' \
  --font-weight semi-bold \
  --backdrop outline \
  --margin-bottom 8%
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
| --preview-layout | off | Render one subtitle layout preview PNG without transcription. |
| --preview-at HH:MM:SS.mmm | video midpoint | Select the frame timestamp used by the preview. |
| --preview-text TEXT | two-line sample | Replace the sample subtitle text used in the preview. |
| --preview-guides | off | Draw non-production placement, envelope, and canvas guides. |
| --karaoke | off | Enable word-timed karaoke highlighting in the rendered ASS/video output. |
| --karaoke-mode MODE | progressive when enabled | Select progressive or active-word highlighting. |
| --karaoke-highlight-color COLOR | #FFD54F when enabled | Set the karaoke highlight color using #RRGGBB or #RRGGBBAA. |
| --font NAME | Roboto | Select the subtitle font family. |
| --font-size LENGTH | 4% | Set font size relative to the shorter render edge or in PlayRes pixels. |
| --letter-spacing LENGTH | 0px | Add non-negative spacing between rendered grapheme clusters; percentages use the resolved font size and pixels use PlayRes space. |
| --line-height auto\|LENGTH | auto | Set the baseline distance between visual lines; auto keeps the measured font metrics. |
| --text-color COLOR | #FFFFFF | Set text color using #RRGGBB or #RRGGBBAA. |
| --opacity PERCENT | 100% | Multiply the opacity of the complete subtitle composition while preserving component alpha. |
| --text-case MODE | original | Preserve the transcription case or display subtitles in uppercase or lowercase. |
| --font-weight WEIGHT | regular (400) | Select a named or numeric font weight from 100 through 900. |
| --bold, --no-bold | off | Compatibility shorthand for bold (700) or regular (400). |
| --italic, --no-italic | off | Enable or disable italic text. |
| --backdrop KIND | box | Select none, outline, or box. |
| --backdrop-color COLOR | #00000099 | Set outline, box, and shadow color. |
| --backdrop-size LENGTH | 0px | Set outline/box padding relative to resolved font size or in pixels. |
| --shadow-size LENGTH | 4% | Set shadow size relative to resolved font size or in pixels. |
| --fonts-dir DIR | — | Supply additional fonts to width measurement and FFmpeg/libass. |
| --layout PRESET | auto | Select auto, landscape, portrait, square, vertical-social, upper-third, or centered subtitle layout. |
| --position POSITION | preset value | Override the selected layout's semantic position. |
| --margin-left LENGTH | preset value | Override native ASS left margin; ignored by explicit coordinates. |
| --margin-right LENGTH | preset value | Override native ASS right margin; ignored by explicit coordinates. |
| --margin-top LENGTH | preset value | Override native ASS top margin; ignored by explicit coordinates. |
| --margin-bottom LENGTH | preset value | Override native ASS bottom margin; ignored by explicit coordinates. |
| --max-width LENGTH | preset value; required for explicit coordinates | Set the maximum subtitle-box width. |
| --max-height LENGTH | preset value; required for explicit coordinates | Set the maximum subtitle-box height used to derive line capacity. |
| --position-x LENGTH | — | Attach an explicit anchor to a global PlayRes X coordinate. |
| --position-y LENGTH | — | Attach an explicit anchor to a global PlayRes Y coordinate. |
| --anchor POSITION | — | Required subtitle-box anchor used with explicit X/Y coordinates. |
| -v, --version | — | Print the package version. |
| -h, --help | — | Show every CLI option and accepted language code. |

Translation cannot use turbo or an English-only model ending in .en. Use a multilingual model such as medium or large instead.

Karaoke is available only for source-language transcription. `--karaoke` cannot
be combined with `--task translate`; translation changes the displayed words
and the source-language alignment cannot be mapped losslessly to them. The
karaoke options are also rejected by `--preview-layout`, which has no aligned
word timings to animate.

Supported source-language codes are limited to languages with a default
word-alignment model in the installed WhisperX release:

~~~
ar, ca, cs, da, de, el, en, es, eu, fa, fi, fr, gl, he, hi, hr, hu, id,
it, ja, ka, ko, lv, ml, nl, nn, no, pl, pt, ro, ru, sk, sl, sv, te, tl,
tr, uk, ur, vi, zh
~~~

### Appearance options

Appearance uses explicit, format-independent options. Colors use conventional
red-green-blue order and conventional alpha (`00` transparent, `FF` opaque);
conversion to ASS BGR order and inverted alpha happens only during ASS
serialization. Quote colors in shells because `#` can start a comment:

~~~
--text-color '#F8FAFC' --backdrop-color '#0F172AB3'
~~~

`--backdrop none` disables the outline/box, `outline` draws an edge around the
glyphs, and `box` draws one libass background box around the complete cue using
the selected color and padding.
The shadow remains independently controlled by `--shadow-size`. `--font`
selects a family name; `--fonts-dir` must name an existing directory containing
additional `.ttf`, `.otf`, or `.ttc` files. The directory is used only for the
current run: it does not install fonts on the host. The measurer matches the
font's internal family metadata rather than its filename, and the same directory
is passed to libass during rendering.

`--font-weight` accepts these equivalent named and numeric ranks:

| Name | Numeric rank |
| --- | ---: |
| `thin` | 100 |
| `extra-light` | 200 |
| `light` | 300 |
| `regular` | 400 |
| `medium` | 500 |
| `semi-bold` | 600 |
| `bold` | 700 |
| `extra-bold` | 800 |
| `black` | 900 |

Names are case-insensitive, and spaces or underscores can replace hyphens.
The aliases `hairline`, `ultra-light`, `normal`, `book`, `demi-bold`,
`ultra-bold`, and `heavy` map to their corresponding canonical ranks.
`--bold` and `--no-bold` remain compatibility shorthands, but combining either
with `--font-weight` is rejected instead of applying implicit precedence.

When `--fonts-dir` is omitted, multisubs queries fontconfig where available so
measurement follows the concrete system font or fallback that libass is likely
to use. Other platforms retain the Unicode estimate when a concrete face cannot
be resolved. Font-family or font-weight substitution, or estimated measurement,
produces one progress diagnostic and is recorded in JSON without exposing an
absolute local font path. The closest available weight is selected
deterministically when the requested family lacks an exact face. Supplying a
controlled font directory is recommended for reproducible wrapping across
machines.

`--letter-spacing` adds non-negative tracking between rendered grapheme
clusters. Use a pixel value for fixed PlayRes spacing or a percentage of the
resolved font size, for example `--letter-spacing 2px` or
`--letter-spacing 4%`. The default is `0px`; values above four times the
resolved font size are rejected to keep wrapping bounded.

`--line-height` controls the baseline-to-baseline distance for multi-line
subtitles. `auto` (the default) keeps the selected font's measured natural
metrics and preserves the existing single-event ASS output. An explicit
percentage is relative to that natural line height, while a pixel value is an
absolute PlayRes distance, for example `--line-height 125%` or
`--line-height 64px`. Values smaller than the natural line height are rejected
after the font is resolved, so explicit leading cannot make glyphs overlap.
The resolved advance is also used when calculating `--max-height` capacity.
When explicit leading is active for a multi-line cue, ASS uses synchronized
per-line events and one shared backdrop drawing; JSON records this as the
`positioned-lines` render strategy while SRT remains one logical cue.

`--opacity` accepts an explicit percentage from `0%` through `100%`, including
decimals such as `32.5%`. It multiplies the existing alpha of every subtitle
component—text, karaoke highlight, box or outline, and shadow—without changing
layout, wrapping, timing, or cue content:

~~~
multisubs -i ./video.mp4 --opacity 75%
multisubs -i ./video.mp4 --text-color '#FFFFFF80' --opacity 50%
~~~

The effective conventional alpha is `round_half_up(base_alpha * opacity / 100)`.
Thus an opaque component at `50%` resolves near alpha `80`, while a component
already configured as `#RRGGBB80` resolves near alpha `40`. `100%` preserves
the configured colors and `0%` makes all subtitle layers transparent without
removing their cues. Preview and final rendering use the same effective palette;
JSON records both base and effective component colors.

`--text-case` accepts `original`, `uppercase`, or `lowercase`; values are
case-insensitive and the default is `original`. Conversion uses Python's
Unicode casing before text measurement and wrapping, so length-changing cases
such as German `Straße` becoming `STRASSE` can change line or cue breaks:

~~~
multisubs -i ./video.mp4 --text-case uppercase
multisubs -i ./video.mp4 --text-case lowercase --preview-layout
~~~

The transform is locale-independent. It does not infer language-specific rules
such as Turkish dotted/dotless I. SRT, ASS, preview, and the rendered video use
the selected display case. JSON retains the original transcript, original cue
text, and aligned words, and adds each cue's transformed `display_text` plus
the requested/resolved text-case mode.

### Word-timed karaoke highlighting

Enable the opt-in effect with `--karaoke`. Each eligible displayed word changes
from the normal `--text-color` to the highlight color according to its aligned
WhisperX timestamps. The default mode is `progressive`: each word activates at
its start and remains highlighted through the cue. The default highlight is warm
yellow; choose another semantic color without using ASS syntax:

~~~
multisubs -i ./video.mp4 --karaoke --karaoke-highlight-color '#FFD54F'
~~~

Use `active-word` when only the currently spoken word should be highlighted:

~~~
multisubs -i ./video.mp4 --karaoke --karaoke-mode active-word
~~~

In active-word mode, a word is highlighted from its start through its end. If
aligned word times overlap, the prior word stops when the next begins; during a
gap, the complete cue remains visible in its normal color. Supplying
`--karaoke-mode` without `--karaoke` is rejected.

Progressive ASS keeps one dialogue event per cue and stores editable `\k` word
durations. Active-word ASS uses adjacent full-cue events for active intervals
and normal gaps so text, wrapping, background, and placement do not move. SRT
remains plain text and JSON keeps the original word records; JSON additionally
records the resolved mode, effect colors, and per-cue fallback count. If a cue
lacks a complete, chronological, lossless word mapping, it is rendered normally
and one aggregate warning reports that timestamps were not invented. Karaoke
does not add spaces, retokenize wrapped display text, or invent timings for
coarse segments. Richer syllable, sweep, fade, and translated karaoke modes are
not supported yet.

### Migration from `--style-*`

The raw ASS options were removed in a breaking CLI cutover. Use these semantic
replacements:

| Removed option | Replacement |
| --- | --- |
| `--style-font` | `--font` |
| `--style-font-size` | `--font-size` with an explicit `%` or `px` suffix |
| `--style-primary-color` | `--text-color` using `#RRGGBB[AA]` |
| `--style-bold` | `--font-weight bold`, `--font-weight 700`, or the `--bold` compatibility shorthand |
| `--style-italic` | `--italic`/`--no-italic` |
| `--style-outline-color`, `--style-back-color` | `--backdrop-color` |
| `--style-border-style` | `--backdrop none`, `outline`, or `box` |
| `--style-outline-weight`, `--style-shadow-weight` | `--backdrop-size`, `--shadow-size` |
| `--style-margin-l`, `--style-margin-r`, `--style-margin-v` | `--margin-left`, `--margin-right`, `--margin-top`, `--margin-bottom` |
| `--style-spacing` | `--letter-spacing` with an explicit `%` or `px` suffix |
| `--style-line-height` | `--line-height auto` or a positive `%`/`px` value |

`--style-secondary-color`, `--style-underline`, `--style-strikeout`,
`--style-scale-x`, `--style-scale-y`, and `--style-angle` have no replacement
because they expose ASS internals outside the supported subtitle appearance
model.

The new defaults preserve the former appearance while scaling with the video:
Roboto, 4% font size, white regular non-italic text, a black background box at
60% opacity with no extra padding, and a 4% shadow. Layout margins come from the
selected preset instead of the former raw vertical-margin default. This
breaking cutover was released in version 2.0.0.

### Layout presets

Use `--layout` to choose a complete native ASS position, margin, width, and
height baseline:

| Preset | Behavior |
| --- | --- |
| `auto` | Selects `landscape`, `portrait`, or `square` from the autorotated render canvas. |
| `landscape` | Bottom-center subtitles with 6% left/right and bottom insets. |
| `portrait` | Bottom-center subtitles with 8% left/right and bottom insets. |
| `square` | Bottom-center subtitles with 7% left/right and bottom insets. |
| `vertical-social` | Generic vertical composition with asymmetric 8%/12% side and 16% bottom insets. |
| `upper-third` | Top-center subtitles with 6% side and 8% top insets. |
| `centered` | Centered subtitles with an 8% inset on every side. |

Each preset supplies `max-width: 100%` of the width remaining after native
horizontal margins and a calibrated `max-height`. Landscape, portrait, square,
vertical-social, upper-third, and centered use respectively `10.5%`, `6%`,
`10.6%`, `6.6%`, `10.7%`, and `10%` of their alignment-specific available
height. These values preserve the ordinary two-line default while allowing line
capacity to change with an explicit height, font size, or font metrics.

`max-width` and `max-height` are ceilings rather than requested text dimensions.
Libass remains authoritative for final shaping and may let an indivisible token
overflow rather than mutating it.

Auto uses the autorotated render dimensions: ratios above 1.1 are landscape,
ratios below 0.9 are portrait, and the inclusive band between them is square.
The `vertical-social` preset is a generic overlay-safe baseline, not a guarantee
for any named platform whose interface may change.

For example:

~~~
multisubs -i ./video.mp4 --layout portrait
multisubs -i ./video.mp4 --layout upper-third --position top-right
multisubs -i ./video.mp4 --layout landscape
multisubs -i ./video.mp4 --layout square
multisubs -i ./video.mp4 --layout vertical-social
multisubs -i ./video.mp4 --layout centered
~~~

`--position` and the relative margin options override only their corresponding
preset fields. Preset selection happens before relative units are converted to
PlayRes pixels. In native mode, left/right margins define the horizontal ASS
layout region; top positions use only `margin-top`, bottom positions use only
`margin-bottom`, and middle positions are not moved vertically by margins.

Custom coordinates select a separate explicit mode. Preset and CLI margins may
still be recorded, but they do not affect coordinates, envelope validation, or
ASS rendering in that mode.

Normalized native layout guide (`0` is the top/left edge and `1` is the
bottom/right edge). The Y range includes only the vertical margin active for
the preset's alignment:

| Preset | Native X region | Active Y region |
| --- | --- | --- |
| landscape | 0.06–0.94 | 0.00–0.94 |
| portrait | 0.08–0.92 | 0.00–0.92 |
| square | 0.07–0.93 | 0.00–0.93 |
| vertical-social | 0.08–0.88 | 0.00–0.84 |
| upper-third | 0.06–0.94 | 0.08–1.00 |
| centered | 0.08–0.92 | 0.00–1.00 |

### Adaptive subtitle wrapping

Subtitle cues are first built from semantic word and timing boundaries. The
selected text-case transform is applied to display fragments while their
original word identities and timestamps remain attached. The selected layout
then supplies maximum width and height, font size, letter spacing, line height,
and backdrop/shadow allowances. Whenever the requested or substituted font
can be resolved, Pillow measures its glyph advances with the resolved size and
style; RAQM supplies direction- and language-aware shaping when available. If a
concrete face cannot be resolved, a Unicode-aware fallback estimates
proportional widths, combining marks, CJK, and emoji without claiming exactness.
The internal Pillow size is normalized to libass's FreeType real-dimension
semantics and recorded as `metric_size`; it is not a second user-facing font
size.

A cue that fits completely remains on one line. The line capacity is calculated
from `max-height`, the natural first-line height, the resolved baseline
advance, backdrop, and shadow; it is not a fixed `max-lines` setting. When a break is necessary, the layout engine
evaluates partitions up to that capacity, preserves semantic boundary priority,
and avoids an unnecessary one-word final line before comparing visual balance.
Long unbroken tokens remain intact and may overflow; text is never truncated or
silently changed. SRT and ASS receive the same transformed display text and
intentional line breaks. JSON keeps original cue text in `text` and records the
corresponding rendered form in `display_text`.

Use maximum dimensions when the subtitle should occupy a smaller visual area or
allow a different vertical line capacity:

~~~
multisubs -i ./video.mp4 --max-width 72%
multisubs -i ./video.mp4 --layout portrait --max-width 640px --max-height 180px
~~~

### Subtitle layout preview

Use `--preview-layout` to inspect the resolved subtitle appearance and
position on one real video frame without loading WhisperX, transcribing audio,
or producing a subtitle-burned video:

~~~
multisubs -i ./video.mp4 -o ./previews \
  --preview-layout \
  --preview-at 00:00:10.500 \
  --preview-text "A sample subtitle that may wrap" \
  --preview-guides \
  --layout landscape --position bottom-center
~~~

`--preview-at` uses `HH:MM:SS.mmm`. When it is omitted, multisubs uses the
video midpoint; if the container duration is unavailable, it uses the first
frame. The sample text is normalized, case-transformed, and wrapped with the
same resolved font, maximum width, maximum height, and line-capacity rules used
by a transcription run. Appearance, layout, relative-unit, coordinate, and font-directory options
are honored. Language, task, and model options are accepted but have no effect
in preview mode; `--keep-transcriptions` is rejected because previews do not
create transcription artifacts.

When the complete sample cannot fit the resolved envelope, the preview renders
only the first lexical segment that the normal cue-layout calculation would
place on screen. The remaining sample represents later timed cues and is not
shown on the selected frame. Intentional line breaks are preserved in ASS, so
libass cannot add lines beyond the capacity derived from `max-height`.

The result is published as `<video-stem>-subtitle-preview.png`, with `(1)`,
`(2)`, and later suffixes when that name already exists. Temporary ASS and
render files are removed after either success or failure. `--preview-guides`
adds diagnostic native margin/envelope or explicit coordinate overlays, the
resolved position or preset, and PlayRes dimensions; guides are not part of a
normal transcription render.

### Relative layout units

The typed layout options accept an explicit unit suffix:

| Option | Percentage basis |
| --- | --- |
| `--font-size` | Shorter autorotated render edge |
| `--letter-spacing` | Resolved font size |
| `--line-height` | Natural measured font line height for `%`; PlayRes space for `px` |
| `--backdrop-size`, `--shadow-size` | Resolved font size |
| `--margin-left`, `--margin-right` | Render width |
| `--margin-top`, `--margin-bottom` | Render height |
| `--max-width` | Native: width after left/right margins; explicit: render width |
| `--max-height` | Native: height after the active vertical margin, or render height for middle alignment; explicit: render height |
| `--position-x` | Render width |
| `--position-y` | Render height |

Use `%` for resolution-independent values or `px` for fixed PlayRes pixels:

~~~
multisubs -i ./video.mp4 --font-size 4.5% --letter-spacing 2px --margin-left 8% \
  --margin-right 8% --margin-bottom 72px
~~~

Bare numbers, signs, exponent notation, and excessive precision are rejected.
Percentages are rounded deterministically to the nearest PlayRes pixel, with
half values rounded up. Geometry-dependent validation runs after ffprobe and
before WhisperX.

`--letter-spacing` adds non-negative tracking between rendered grapheme
clusters. A percentage is relative to the resolved font size, while a pixel
value is fixed in PlayRes space; explicit line breaks reset the spacing count.
Combining marks and emoji zero-width-joiner sequences remain attached to their
base cluster. The default `0px` leaves existing wrapping and rendering
unchanged, and spacing above four times the resolved font size is rejected as
unsafe.

`--line-height` accepts `auto` or a positive `%`/`px` value. Percentages scale
the selected face's measured natural line height; pixels are PlayRes baseline
advances. Explicit values below the natural metric are rejected after font
resolution. `--max-height` remains the authoritative envelope: its capacity is
`natural_line_height + (line_count - 1) * resolved_line_height`, plus backdrop
and shadow allowances. Explicit line height may therefore split a cue earlier;
if a measured positioned block still exceeds its declared envelope, validation
fails rather than moving or clipping the subtitle.

### Exact subtitle coordinates

Use `--position-x` and `--position-y` together to attach a subtitle-box anchor
to an exact global PlayRes point. Both options require `%` or `px`; X starts at
the canvas left edge, Y starts at its top edge, and Y increases downward. Pixel
values are absolute PlayRes coordinates.

~~~text
    canvas x = 0%                  canvas x = 100%
              ┌──────────────────────────────┐  canvas y = 0%
              │  top-left       top-center   │
              │                              │
              │            center            │
              │                              │
              │ bottom-left  bottom-center  │  safe y = 100%
              └──────────────────────────────┘  canvas y = 100%
~~~

The anchor identifies the point on the subtitle box, not the glyph baseline:

~~~
multisubs -i ./video.mp4 \
  --position-x 50% --position-y 86% --anchor bottom-center \
  --max-width 60% --max-height 20%
multisubs -i ./video.mp4 \
  --position-x 120px --position-y 80px --anchor top-left \
  --max-width 900px --max-height 240px
~~~

`--position-x` and `--position-y` must be supplied as a pair. They cannot be
combined with `--position`. `--anchor`, `--max-width`, and `--max-height` are
required explicitly; preset values are not inherited. Margins are ignored.

The complete maximum envelope must fit inside the canvas for its anchor. For a
center anchor, X must be between half the maximum width and the canvas width
minus that half; Y follows the equivalent maximum-height rule. Left/top anchors
reserve their envelope toward the right/bottom, while right/bottom anchors
reserve it toward the left/top. Invalid placement fails after ffprobe and before
WhisperX; multisubs does not clamp the dimensions or move the coordinate.

For example, on a 1920px canvas, `max-width=60%` resolves to 1152px. A centered
horizontal anchor is valid from X=576 through X=1344. X=300 is rejected.

Migration note for users who tested unreleased source after Feature 6: custom
coordinates are no longer offsets inside preset margins, and an undersized
anchor capacity is no longer handled by silently reducing `max-width`. Supply
global PlayRes X/Y plus explicit maximum width and height. This restores the
stable v2.0.0 coordinate basis before the transitional behavior is released.

Coordinates are represented in generated ASS event overrides. JSON identifies
requested and resolved coordinates as `playres` values. SRT has no positioning
field, so it keeps text and timing but cannot preserve coordinates.

### Subtitle positions

Use `--position` to override a preset with a semantic screen anchor. Presets
currently default to `bottom-center` except `upper-third` (`top-center`) and
`centered` (`center`).

| `top-left` | `top-center` | `top-right` |
| --- | --- | --- |
| `middle-left` | `center` | `middle-right` |
| `bottom-left` | `bottom-center` | `bottom-right` |

Left and right are physical screen directions, not language-relative start and
end values. Named positions compile to native ASS style `Alignment` plus the
active margins and do not emit an event `\pos`. Unequal horizontal margins shift
the native layout region as defined by ASS. Custom placement alone emits private
ASS `\an` plus `\pos` event overrides. Numeric ASS alignment codes remain
implementation details; `--style-alignment` is not a supported option.

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
recorded under `metadata.rendering` in the versioned JSON transcript. Rendering
metadata also records the requested and resolved layout preset names. Relative
layout options record both their requested strings and resolved PlayRes pixels.
Text-measurement metadata records the requested weight token and form, its
canonical name and numeric rank, the inferred resolved face weight, and whether
a substitution occurred.

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

## Contributing and releases

The repository follows GitHub Flow: create a short-lived branch from `main`,
open a pull request back to `main`, and merge it with a merge commit, squash, or
rebase after the required `Development / development-gate` check passes. The
`dev` branch is retired and is not an integration target.

Each merge to `main` creates a staging candidate after manual approval. Staging
runs the hermetic and FFmpeg/libass suites, installs the built wheel in a clean
environment, and retains the attested wheel, source archive, and checksum
manifest for 90 days. A stable `vX.Y.Z` tag matching `multisubs.__version__`
promotes those exact files to a manually approved GitHub Release; the release
workflow never rebuilds them and does not publish to PyPI.

See [docs/delivery.md](docs/delivery.md) for branch rules, environment settings,
versioning, staging recovery, release drafts, and rollback guidance. The
breaking CLI migration is documented above and summarized in the
[v2.0.0 GitHub Release](https://github.com/denilson-santos/multisubs/releases/tag/v2.0.0).

## Current limitations

- The CLI processes one local input video per invocation.
- Translation has a fixed English target.
- There is no interactive subtitle editor or graphical interface.
- FFmpeg, ffprobe, a compatible font, and the selected model must be available on the host system.
