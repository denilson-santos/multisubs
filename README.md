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
  --text-color '#FFFFFF' \
  --bold \
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
| --font NAME | Roboto | Select the subtitle font family. |
| --font-size LENGTH | 4% | Set font size relative to the shorter render edge or in PlayRes pixels. |
| --text-color COLOR | #FFFFFF | Set text color using #RRGGBB or #RRGGBBAA. |
| --bold, --no-bold | off | Enable or disable bold text. |
| --italic, --no-italic | off | Enable or disable italic text. |
| --backdrop KIND | box | Select none, outline, or box. |
| --backdrop-color COLOR | #00000099 | Set outline, box, and shadow color. |
| --backdrop-size LENGTH | 0px | Set outline/box padding relative to resolved font size or in pixels. |
| --shadow-size LENGTH | 4% | Set shadow size relative to resolved font size or in pixels. |
| --fonts-dir DIR | — | Supply additional fonts to width measurement and FFmpeg/libass. |
| --layout PRESET | auto | Select auto, landscape, portrait, square, vertical-social, upper-third, or centered subtitle layout. |
| --position POSITION | preset value | Override the selected layout's semantic position. |
| --margin-left LENGTH | preset value | Override the left safe-area margin. |
| --margin-right LENGTH | preset value | Override the right safe-area margin. |
| --margin-top LENGTH | preset value | Override the top safe-area margin. |
| --margin-bottom LENGTH | preset value | Override the bottom safe-area margin. |
| --max-width LENGTH | preset value | Override the maximum subtitle line width relative to the safe-area width or in PlayRes pixels. |
| --position-x LENGTH | — | Attach a custom anchor to an X coordinate measured from the safe area's left edge. |
| --position-y LENGTH | — | Attach a custom anchor to a Y coordinate measured from the safe area's top edge. |
| --anchor POSITION | bottom-center for custom coordinates | Select the subtitle-box anchor used with `--position-x` and `--position-y`. |
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

When `--fonts-dir` is omitted, multisubs queries fontconfig where available so
measurement follows the concrete system font or fallback that libass is likely
to use. Other platforms retain the Unicode estimate when a concrete face cannot
be resolved. Font substitution or estimated measurement produces one progress
diagnostic and is recorded in JSON without exposing an absolute local font
path. Supplying a controlled font directory is recommended for reproducible
wrapping across machines.

### Migration from `--style-*`

The raw ASS options were removed in a breaking CLI cutover. Use these semantic
replacements:

| Removed option | Replacement |
| --- | --- |
| `--style-font` | `--font` |
| `--style-font-size` | `--font-size` with an explicit `%` or `px` suffix |
| `--style-primary-color` | `--text-color` using `#RRGGBB[AA]` |
| `--style-bold`, `--style-italic` | `--bold`/`--no-bold`, `--italic`/`--no-italic` |
| `--style-outline-color`, `--style-back-color` | `--backdrop-color` |
| `--style-border-style` | `--backdrop none`, `outline`, or `box` |
| `--style-outline-weight`, `--style-shadow-weight` | `--backdrop-size`, `--shadow-size` |
| `--style-margin-l`, `--style-margin-r`, `--style-margin-v` | `--margin-left`, `--margin-right`, `--margin-top`, `--margin-bottom` |

`--style-secondary-color`, `--style-underline`, `--style-strikeout`,
`--style-scale-x`, `--style-scale-y`, `--style-spacing`, and `--style-angle`
have no replacement because they expose ASS internals outside the supported
subtitle appearance model.

The new defaults preserve the former appearance while scaling with the video:
Roboto, 4% font size, white regular non-italic text, a black background box at
60% opacity with no extra padding, and a 4% shadow. Layout margins come from the
selected preset instead of the former raw vertical-margin default. This
breaking cutover was released in version 2.0.0.

### Layout presets

Use `--layout` to choose a complete position and safe-area baseline:

| Preset | Behavior |
| --- | --- |
| `auto` | Selects `landscape`, `portrait`, or `square` from the autorotated render canvas. |
| `landscape` | Bottom-center subtitles with 6% left/right and bottom insets. |
| `portrait` | Bottom-center subtitles with 8% left/right and bottom insets. |
| `square` | Bottom-center subtitles with 7% left/right and bottom insets. |
| `vertical-social` | Generic vertical composition with asymmetric 8%/12% side and 16% bottom safe-area insets. |
| `upper-third` | Top-center subtitles with 6% side and 8% top insets. |
| `centered` | Centered subtitles with an 8% inset on every side. |

Each preset also supplies a maximum subtitle width of `100%` of its safe area
and a two-line baseline. The side margins already remove the unsafe part of the
frame, so the preset does not subtract the same insets a second time through
`max-width`. An explicit `--max-width` accepts `%` or `px`; percentages use the
safe width remaining after the final margins are applied. The value is a ceiling
for wrapping, not a requested line length, and the selected horizontal anchor
can reduce the effective capacity further. Libass remains authoritative for
final shaping and may let an indivisible token overflow rather than mutating it.

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
PlayRes pixels, and the final merged safe rectangle is validated before model
loading. When custom coordinates are supplied, the preset still contributes
appearance and safe-area margins, while the custom anchor and X/Y become the
final placement inside that area. Changing a margin therefore changes the
containing rectangle used to resolve percentage widths and coordinates.

Normalized safe-area guide (`0` is the top/left edge and `1` is the
bottom/right edge):

| Preset | Safe X range | Safe Y range |
| --- | --- | --- |
| landscape | 0.06–0.94 | 0.00–0.94 |
| portrait | 0.08–0.92 | 0.00–0.92 |
| square | 0.07–0.93 | 0.00–0.93 |
| vertical-social | 0.08–0.88 | 0.08–0.84 |
| upper-third | 0.06–0.94 | 0.08–1.00 |
| centered | 0.08–0.92 | 0.08–0.92 |

### Adaptive subtitle wrapping

Subtitle cues are first built from semantic word and timing boundaries. The
selected preset then supplies a safe width, font size, backdrop/shadow allowance,
and a maximum of two visual lines. Whenever the requested or substituted font
can be resolved, Pillow measures its glyph advances with the resolved size and
style; RAQM supplies direction- and language-aware shaping when available. If a
concrete face cannot be resolved, a Unicode-aware fallback estimates
proportional widths, combining marks, CJK, and emoji without claiming exactness.
The internal Pillow size is normalized to libass's FreeType real-dimension
semantics and recorded as `metric_size`; it is not a second user-facing font
size.

A cue that fits completely remains on one line. When a break is necessary, the
layout engine evaluates the complete two- or three-line partition, preserves
semantic boundary priority, and avoids an unnecessary one-word final line
before comparing visual balance. Long unbroken tokens remain intact and may
overflow; text is never truncated or silently changed. SRT and ASS receive the
same intentional line breaks, while JSON keeps the existing `text` field
contract. `metadata.rendering.text_measurement` records the requested/resolved
font, source, shaping mode, and whether font metrics or the Unicode estimate was
used.

Use `--max-width` when the subtitle should occupy less than the selected safe
area:

~~~
multisubs -i ./video.mp4 --max-width 72%
multisubs -i ./video.mp4 --layout portrait --max-width 640px
~~~

### Relative layout units

The typed layout options accept an explicit unit suffix:

| Option | Percentage basis |
| --- | --- |
| `--font-size` | Shorter autorotated render edge |
| `--backdrop-size`, `--shadow-size` | Resolved font size |
| `--margin-left`, `--margin-right` | Render width |
| `--margin-top`, `--margin-bottom` | Render height |
| `--max-width` | Safe-area width after left/right margins |
| `--position-x` | Safe-area width after left/right margins |
| `--position-y` | Safe-area height after top/bottom margins |

Use `%` for resolution-independent values or `px` for fixed PlayRes pixels:

~~~
multisubs -i ./video.mp4 --font-size 4.5% --margin-left 8% \
  --margin-right 8% --margin-bottom 72px
~~~

Bare numbers, signs, exponent notation, and excessive precision are rejected.
Percentages are rounded deterministically to the nearest PlayRes pixel, with
half values rounded up. Geometry-dependent validation runs after ffprobe and
before WhisperX.

### Exact subtitle coordinates

Use `--position-x` and `--position-y` together to attach a subtitle-box anchor
to an exact point inside the selected safe area. Both options require `%` or
`px`; X starts at the safe area's left edge, Y starts at its top edge, and Y
increases downward. Pixel values are offsets inside that area. The default
custom anchor is `bottom-center`.

~~~text
      safe x = 0%                    safe x = 100%
              ┌──────────────────────────────┐  safe y = 0%
              │  top-left       top-center   │
              │                              │
              │            center            │
              │                              │
              │ bottom-left  bottom-center  │  safe y = 100%
              └──────────────────────────────┘
~~~

The anchor identifies the point on the subtitle box, not the glyph baseline:

~~~
multisubs -i ./video.mp4 \
  --position-x 50% --position-y 86% --anchor bottom-center
multisubs -i ./video.mp4 \
  --position-x 120px --position-y 80px --anchor top-left
~~~

`--position-x` and `--position-y` must be supplied as a pair. They cannot be
combined with `--position`, and `--anchor` without both coordinates is rejected.
The resolved anchor must fit inside the selected layout's safe rectangle; an
off-screen or clipped placement fails after ffprobe and before transcription.
For example, on a 1920px-wide canvas with 100px side margins,
`--position-x 600px --position-y 0px --anchor top-left` resolves to PlayRes
X=700. The safe width is 1720px and 1120px remain between that anchor and the
right margin. The effective line width is the smaller of that anchor capacity
and `--max-width`.

Coordinates are represented in generated ASS event overrides. JSON identifies
requested coordinates as `safe-area` values and final integer coordinates as
`playres` values. SRT has no positioning field, so it keeps text and timing but
cannot preserve coordinates.

### Subtitle positions

Use `--position` to override a preset with a semantic screen anchor. Presets
currently default to `bottom-center` except `upper-third` (`top-center`) and
`centered` (`center`).

| `top-left` | `top-center` | `top-right` |
| --- | --- | --- |
| `middle-left` | `center` | `middle-right` |
| `bottom-left` | `bottom-center` | `bottom-right` |

Left and right are physical screen directions, not language-relative start and
end values. A named position is a shortcut for attaching the corresponding box
anchor to the matching edge or center of the safe rectangle. For example,
`bottom-center` maps to the horizontal center and bottom edge of the safe area;
`center` maps to its exact center even when opposite margins differ. Both named
and custom placements are serialized privately as ASS `\an` plus `\pos` event
overrides. Numeric ASS alignment codes remain implementation details;
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
recorded under `metadata.rendering` in the versioned JSON transcript. Rendering
metadata also records the requested and resolved layout preset names. Relative
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
