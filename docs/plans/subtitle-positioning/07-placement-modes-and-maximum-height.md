# Feature 7: ASS placement modes and maximum subtitle height

Status: Planned

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Named positions](02-named-positions.md)
- [Relative units](03-relative-units.md)
- [Layout presets](04-layout-presets.md)
- [Custom coordinates](05-custom-coordinates.md)
- [Adaptive line wrapping](06-adaptive-line-wrapping.md)

## Objective

Separate the two supported positioning models so each follows predictable ASS
semantics, and replace the fixed internal line limit with a measurable maximum
subtitle-box height.

Named `--position` layouts must use native ASS alignment and margins. Explicit
`--anchor` plus `--position-x`/`--position-y` layouts must use global PlayRes
coordinates, ignore margins as ASS does for positioned events, and validate a
user-declared width/height envelope without silently shrinking it.

## Why this increment exists

Pull request [#33](https://github.com/denilson-santos/multisubs/pull/33) made
adaptive width measurement available, but also unified named and custom
placement through safe-area-local `\an`/`\pos` events. That coupling introduced
three undesirable effects:

- named positions stopped following native ASS margin behavior;
- custom coordinates changed from global PlayRes coordinates to offsets inside
  the margins;
- an invalid explicit envelope was silently reduced to the capacity around its
  anchor instead of being rejected.

These changes have not been included in a stable tag after `v2.0.0`. This plan
supersedes that placement refinement before adaptive wrapping is released, while
preserving the font-measurement and cue-partitioning work from Feature 6.

## Scope

Included:

- Define native and explicit placement as separate typed modes.
- Restore native ASS style alignment and margin behavior for `--position`.
- Restore global PlayRes meaning for explicit X/Y coordinates.
- Ignore all four margin options in explicit coordinate mode.
- Require an explicit `--anchor` with custom coordinates; do not inherit or
  default it.
- Require explicit `--max-width` and `--max-height` values in coordinate mode.
- Keep `--max-width` optional in named-position mode, with an implicit `100%`
  of the width remaining after native horizontal margins.
- Add `--max-height` and derive visual line capacity from measured vertical
  metrics rather than a public or fixed `max-lines` value.
- Validate the complete maximum envelope against its explicit anchor before
  loading WhisperX.
- Preserve semantic splitting, word timing, content, SRT/ASS escaping, font
  resolution, and collision-safe artifact behavior.
- Update rendering metadata so the chosen mode, coordinate space, requested
  envelope, resolved envelope, and derived line capacity are reproducible.

Excluded:

- Content-aware placement or collision detection against video imagery.
- Allowing an explicit subtitle envelope to extend outside the PlayRes canvas.
- Automatically moving an invalid coordinate, changing its anchor, or shrinking
  a requested envelope.
- Per-cue coordinates or per-cue width/height overrides.
- Text truncation, automatic font shrinking, hyphenation, or mutation.
- Changing `MAX_CUE_DURATION`, `PAUSE_BREAK_THRESHOLD`, or
  `MODEL_LOAD_ATTEMPTS`.
- Implementing layout preview; Feature 8 consumes the resolved contracts.

## Placement-mode contract

The resolved layout must identify exactly one mode:

| Mode | Selected by | ASS output | Margins | Coordinate space |
| --- | --- | --- | --- | --- |
| Native style | `--position` or preset position, without X/Y | Style `Alignment` and native `MarginL`/`MarginR`/`MarginV`; no generated `\pos` | Applied by libass | Not applicable |
| Explicit coordinates | `--position-x`, `--position-y`, and `--anchor` | Event `\an` plus `\pos` | Ignored | Full PlayRes canvas |

The modes remain mutually exclusive. `--position-x` and `--position-y` must be
supplied together, and `--anchor` is required with that pair.

### Native style placement

- `--position` maps to the private ASS `Alignment` field.
- `margin-left` and `margin-right` compile unchanged to `MarginL` and `MarginR`.
- A top alignment compiles `margin-top` to `MarginV`.
- A bottom alignment compiles `margin-bottom` to `MarginV`.
- Middle alignments follow native ASS behavior: vertical margin does not move
  the subtitle. The requested top/bottom values remain available to presets and
  metadata but must not be represented as a fictitious `\pos` safe rectangle.
- The inactive opposite vertical margin does not affect placement.
- Unequal horizontal margins intentionally shift the native ASS layout region.
- No event-level placement override is emitted for ordinary cues.

### Explicit coordinate placement

- `position-x` is measured from the PlayRes left edge and `position-y` from the
  PlayRes top edge; Y increases downward.
- Percentage X resolves against render width and percentage Y against render
  height. Pixel values are absolute PlayRes coordinates.
- Margins are accepted as preset or CLI values for configuration consistency,
  but are ignored by placement, envelope validation, and ASS serialization in
  this mode. The CLI help and progress output must make that visible.
- The selected anchor identifies which point of the maximum subtitle envelope
  is attached to X/Y.
- `max-width` and `max-height` must be supplied explicitly by the user in this
  mode, even if the chosen preset has dimension defaults. This prevents a
  hidden `100%` envelope from making an otherwise reasonable displacement
  invalid.

## Width contract

### Native mode

Let:

~~~text
available_width = canvas_width - margin_left - margin_right
~~~

`--max-width` is optional:

- omitted: effective maximum is `available_width`;
- `100%`: also resolves to `available_width`;
- another percentage: resolves against `available_width`;
- pixels: must be positive and cannot exceed `available_width`.

The wrapping budget is the resolved maximum minus the documented horizontal
decoration allowance. Do not expand or replace ASS margins to manufacture a
narrower region. Python inserts intentional display breaks using the measured
budget, while libass retains the real native margins as its final containment
boundary.

### Explicit mode

Percentage `max-width` resolves against the full canvas width. The resolved
value is the requested maximum envelope width, not a target and not a value that
may be clamped to anchor capacity. It includes the text block and its horizontal
backdrop/shadow allowance.

For canvas width `W`, maximum width `MW`, and anchor coordinate `X`, validate:

| Horizontal anchor | Valid X interval |
| --- | --- |
| left | `0 <= X <= W - MW` |
| center | `MW / 2 <= X <= W - MW / 2` |
| right | `MW <= X <= W` |

Implementation should avoid fractional-pixel ambiguity by validating the
equivalent doubled integer inequalities for center anchors:

~~~text
MW <= 2 * X
MW <= 2 * (W - X)
~~~

Example: on a 1920px canvas, `max-width=60%` resolves to 1152px. A center
anchor is valid only from X=576 through X=1344. X=300 is rejected; the program
must not reduce 1152px to make it fit.

With `max-width=100%`, the only valid horizontal coordinate is X=0 for a left
anchor, X=960 for a center anchor, or X=1920 for a right anchor. This is why the
explicit mode requires the user to declare its envelope instead of inheriting a
full-width preset implicitly.

## Height and derived-line contract

Add:

~~~text
--max-height LENGTH
~~~

`LENGTH` uses the existing strict `%` or `px` syntax. It is a maximum subtitle
box height, not an exact height and not a line count.

### Percentage bases

- Native top position: percentage of `canvas_height - margin_top`.
- Native bottom position: percentage of `canvas_height - margin_bottom`.
- Native middle position: percentage of the full canvas height because native
  ASS does not apply `MarginV` to middle alignment.
- Explicit coordinate mode: percentage of the full canvas height.

In native mode, omitting `--max-height` uses the selected preset's calibrated
height. Presets must express a real height rather than store a hidden fixed line
count. Their initial values are calibrated to preserve the current ordinary
two-line outcome with the default appearance while allowing the derived
capacity to change when height or font metrics change.

### Vertical measurement

Extend the text-measurement boundary with a resolved line height based on the
selected face, font size, style, and shaping engine. Include vertical backdrop
and shadow allowance explicitly. When a concrete face is unavailable, use a
documented conservative Unicode-estimate line height and record that mode.

Derive line capacity from the complete visual box:

~~~text
content_height = max_height - vertical_decoration_allowance
line_capacity = floor(content_height / measured_line_height)
~~~

Reject a configuration whose maximum height cannot contain one ordinary line
with its decorations. Keep the derived capacity as an internal resolved metric;
do not expose `--max-lines`.

The cue partitioner may emit as many visual lines as fit the derived capacity.
When an aligned cue cannot fit, create additional timed cues at the existing
semantic priorities. Without usable word timings, never invent timestamps;
preserve the text and allow the documented controlled overflow when no accurate
timed split is possible.

### Explicit vertical validation

For canvas height `H`, maximum height `MH`, and anchor coordinate `Y`, validate:

| Vertical anchor | Valid Y interval |
| --- | --- |
| top | `0 <= Y <= H - MH` |
| middle | `MH / 2 <= Y <= H - MH / 2` |
| bottom | `MH <= Y <= H` |

Use doubled integer inequalities for middle anchors:

~~~text
MH <= 2 * Y
MH <= 2 * (H - Y)
~~~

These rules apply to `middle-left`, `center`, and `middle-right`. Horizontal
center rules independently apply to `top-center`, `center`, and
`bottom-center`; the `center` anchor must satisfy both axes.

## Validation timing and diagnostics

Before FFprobe or WhisperX:

- Reject incomplete X/Y pairs.
- Reject `--position` combined with explicit coordinates.
- Reject `--anchor` without coordinates.
- Reject explicit coordinates without a user-supplied `--anchor`.
- Reject explicit coordinates without user-supplied `--max-width` and
  `--max-height`.
- Reject invalid relative-length syntax.

After FFprobe and before WhisperX:

- Resolve percentages against the mode-specific bases.
- Reject native margins that eliminate horizontal space.
- Reject non-positive or oversized maximum dimensions.
- Reject a maximum height that cannot contain one measured line.
- Reject every explicit envelope whose anchored edges leave the PlayRes canvas.

Diagnostics must identify the public option, resolved canvas or available
dimension, anchor, valid coordinate interval, and requested envelope. Do not
silently clamp, reposition, or switch modes.

## Typed model and component boundaries

### `multisubs/models.py`

- Represent native and explicit placement without inferring mode from loosely
  related optional fields throughout the pipeline.
- Replace `SubtitleLayout.max_lines` with `max_height`.
- Retain `CuePlacement` only for explicit per-event placement, or rename it so
  its type cannot imply that named style placement also emits `\pos`.

### `multisubs/config.py`

- Add `max_height` to immutable presets and layout overrides.
- Remove `parse_max_lines()` and preset `max_lines` values.
- Track whether maximum dimensions were explicitly supplied so coordinate mode
  cannot satisfy its requirement accidentally through preset inheritance.
- Calibrate and document preset height values with the default appearance.

### `multisubs/layout.py`

- Resolve mode before dimension bases.
- Keep native available-width/height calculations separate from explicit
  canvas-envelope validation.
- Remove anchor-capacity clamping and artificial ASS-margin calculation.
- Resolve explicit X/Y globally and validate the complete envelope by anchor.
- Resolve vertical metrics and derived line capacity once for cue layout.

### `multisubs/ass.py`

- Native mode: compile semantic alignment and actual active margins into the ASS
  style and omit event `\pos`.
- Explicit mode: compile neutral style margins because libass ignores margins
  for positioned events, then emit generated `\an`/`\pos` before escaped text.
- Keep generated tags isolated from transcription-derived content.

### `multisubs/transcriber.py`

- Replace max-lines input with the derived line capacity.
- Partition text by measured width and height without changing semantic priority
  or timing policy.
- Record placement mode and vertical measurement inputs in JSON metadata.

### `multisubs/cli.py`

- Add `--max-height` beside `--max-width`.
- Explain native margin behavior and global explicit coordinates.
- Report the resolved native layout or explicit envelope without presenting a
  synthetic named-position coordinate.

## Public and output contracts

### CLI and Python API

- `--max-width` remains backward-compatible in native mode.
- `--max-height` is additive.
- There is no public `--max-lines` option to migrate.
- Global custom coordinates restore the `v2.0.0` public coordinate basis before
  the safe-area-local Feature 6 behavior receives a stable release.
- Programmatic configuration receives the same mode and envelope validation as
  the CLI.

### JSON

Rendering metadata must record:

- `placement_mode`: `native-style` or `explicit`;
- requested and resolved margins, with an `applied` indicator for the mode;
- requested/resolved max width and height;
- percentage basis for each resolved dimension;
- explicit requested/resolved coordinates with `coordinate_space: playres`;
- measured line height, vertical decoration allowance, and derived line
  capacity;
- font measurement mode and the existing privacy-safe font identity.

Do not emit synthetic resolved X/Y coordinates for native style placement.
Remove Feature 6-only anchor-capacity metadata that no longer represents the
contract. Because these fields have not shipped after `v2.0.0`, reconcile them
before the next release rather than preserving contradictory transitional data.

### SRT and ASS

- SRT keeps text, timing, and intentional display breaks but cannot preserve
  placement or maximum dimensions.
- ASS is authoritative for native margins and explicit `\an`/`\pos` placement.
- Long indivisible tokens may overflow rather than being mutated.

## Implementation tasks

- [ ] Add a typed placement mode and replace `max_lines` with `max_height` in
      the resolved layout contract.
- [ ] Add `--max-height`, mode-specific CLI help, and early cross-option
      validation.
- [ ] Restore global PlayRes X/Y percentage and pixel resolution.
- [ ] Require explicit maximum width and height in coordinate mode.
- [ ] Implement full-envelope validation for all nine anchors on both axes.
- [ ] Restore native ASS alignment and active-margin compilation for named
      positions; omit event `\pos` in that mode.
- [ ] Remove anchor-capacity width clamping and synthetic ASS margins.
- [ ] Resolve optional native max-width against the width after horizontal
      margins, defaulting implicitly to 100%.
- [ ] Resolve native max-height against the alignment-specific available height
      and calibrate immutable preset values.
- [ ] Extend font measurement with line height and vertical decoration metrics.
- [ ] Derive internal line capacity from max-height and update cue partitioning.
- [ ] Preserve missing-word-timing and indivisible-token fallbacks.
- [ ] Reconcile JSON rendering metadata with the two-mode contract.
- [ ] Add focused configuration, layout, ASS, cue, serialization, and integration
      tests.
- [ ] Update README, PRD, architecture, conventions, and roadmap documentation.

## Unit tests

### Mode and units

- Native mode is selected when no X/Y pair exists.
- Explicit mode requires X, Y, anchor, max-width, and max-height.
- Explicit percentages resolve against full PlayRes width/height.
- Native max-width percentages recalculate after horizontal margin changes.
- Native top/bottom max-height uses only the active vertical margin; middle uses
  full canvas height.
- Margins do not alter explicit coordinates or envelope validation.
- Invalid combinations fail at the documented pre-probe boundary.

### Envelope bounds

- Test left, center, and right horizontal intervals at minimum, maximum, and one
  pixel outside.
- Test top, middle, and bottom vertical intervals at minimum, maximum, and one
  pixel outside.
- Exercise odd canvas/envelope dimensions using doubled integer inequalities.
- On 1920x1080, verify center anchor X=300 with max-width=1152 is rejected and
  X=576 is accepted.
- Verify `max-width=100%` permits only the anchor-specific zero-travel
  coordinate on that axis.
- Verify no invalid envelope is automatically narrowed or repositioned.

### Native ASS behavior

- All nine named positions compile to their private style Alignment value.
- Actual left/right margins are retained even when max-width is narrower.
- Top uses margin-top, bottom uses margin-bottom, and middle placement is not
  shifted by vertical margins.
- Named cues contain no generated `\pos`; explicit cues contain exactly one
  safe generated `\an`/`\pos` prefix.

### Height and cue layout

- Exact one-line, two-line, and next-line height thresholds.
- Font size, bold/italic face, backdrop, and shadow change derived capacity.
- Increasing max-height can increase line capacity without changing source
  text or timings.
- A height too small for one line is rejected.
- Aligned oversized cues split at timed semantic boundaries.
- Missing timings, CJK, right-to-left text, combining marks, emoji, explicit
  newlines, and long indivisible tokens remain safe.
- Concatenating semantic content across derived cues reconstructs the source.

## Integration and visual verification

With a controlled font and synthetic non-sensitive media:

- Render representative top, middle, and bottom named positions and measure
  native ASS margin behavior.
- Render unequal horizontal margins and confirm the native layout region shifts
  as libass defines it.
- Render explicit coordinates with non-zero margins and prove the resulting
  bounds are identical to the zero-margin run.
- Render the nine explicit anchors at valid boundary coordinates and confirm
  the maximum envelope stays inside the canvas.
- Verify invalid envelope examples fail before transcription.
- Render increasing max-height values and compare the measured line capacity to
  actual libass bounds using a documented tolerance.
- Re-run the Portuguese no-premature-break regression from Feature 6.
- Compare landscape, portrait, square, rotated, CJK, RTL, and emoji fixtures.

Attach representative before/after media to the pull request; do not commit
generated videos, subtitles, previews, fonts, or model artifacts.

## Documentation

- Update the README command reference, relative-unit bases, position diagrams,
  preset table, examples, and migration note from the transitional Feature 6
  behavior.
- Update FR-7, FR-9, readability requirements, and acceptance criteria in
  `docs/prd.md`.
- Update the execution flow, typed layout, cue construction, JSON metadata, and
  SRT/ASS contracts in `docs/architecture.md`.
- Update dimension, cue, and ASS rules in `docs/conventions.md`.
- Update Feature 8 so preview guides distinguish native margins from an
  explicit maximum envelope.

## Commit and pull-request plan

Suggested branch:

~~~text
feat/subtitle-placement-envelopes
~~~

Suggested commits:

1. `refactor: separate native and explicit subtitle placement`
   - Add the typed mode, restore global X/Y, restore native margins, remove
     capacity clamping, and cover ASS/configuration behavior.
2. `feat: validate explicit subtitle envelopes`
   - Require maximum dimensions, add all-anchor bounds validation, diagnostics,
     metadata, and boundary tests.
3. `feat: derive subtitle lines from maximum height`
   - Add max-height, vertical font metrics, preset calibration, adaptive cue
     capacity, and Unicode/timing fallback tests.
4. `test: render native and explicit subtitle layouts`
   - Add opt-in FFmpeg/libass comparisons for margins, envelopes, height, and
     representative scripts.
5. `docs: document subtitle placement and envelope modes`
   - Update README, PRD, architecture, conventions, roadmap, and migration
     guidance.

Suggested pull request:

~~~text
Title: feat: separate subtitle placement modes and bound subtitle height
Base: main
~~~

The pull request must link this plan, explain the superseded Feature 6 placement
contract, show native versus explicit ASS output, list all percentage bases,
include the complete envelope formulas, and record preset-height calibration.
It must identify JSON changes, missing-timing behavior, font/libass tolerance,
and the fact that margins are ignored in explicit mode.

Before requesting review:

- Run `python -m pytest tests/test_cli.py tests/test_config.py tests/test_layout.py tests/test_ass.py tests/test_transcriber.py`.
- Run the relevant opt-in FFmpeg/libass integration tests with the controlled
  font fixture.
- Run `python -m compileall multisubs`, `multisubs --help`, `python -m pytest`,
  `python -m ruff check .`, and `python -m pyright` when installed and
  configured.
- Run `python -m build` and verify the wheel in a clean supported Python
  environment because the public CLI and typed configuration change.
- Inspect `git diff --check` and confirm no generated media, subtitle artifacts,
  font files, caches, or unrelated user changes are staged.
- Update the package dashboard to `In review` and add the pull-request link.

## Acceptance criteria

- Named positions use native ASS style alignment and actual margins without an
  event `\pos` override.
- Explicit coordinates use global PlayRes axes and are unaffected by margins.
- Explicit mode requires user-supplied max-width and max-height.
- The complete requested explicit envelope fits the canvas for its anchor or
  fails before WhisperX; it is never silently clamped or moved.
- Native max-width is optional, and `100%` means all width after horizontal
  margins.
- Max-height determines internal line capacity from measured font and decoration
  height; no fixed or public max-lines setting remains.
- Increasing available height can increase the visual line count without losing,
  duplicating, reordering, or mutating words.
- Missing word timings never cause invented timestamps.
- JSON, SRT, ASS, CLI help, README, PRD, architecture, and conventions describe
  the same mode and envelope contracts.
- The focused suite, full hermetic suite, static checks, package build, and
  available FFmpeg/libass regressions pass.
