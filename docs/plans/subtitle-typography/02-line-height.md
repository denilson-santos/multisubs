# Line height

Status: Done

Delivery: [#44](https://github.com/denilson-santos/multisubs/pull/44)

Depends on:

- [Font weight](00-font-weight.md)
- [Letter spacing](01-letter-spacing.md)

## Objective

Let users control the vertical distance between lines of a multi-line subtitle
while keeping maximum-height capacity, preview, final rendering, backdrop, and
placement based on the same measured geometry.

## Scope

Included:

- Add `--line-height auto|LENGTH`, defaulting to `auto`.
- Accept positive `%` or `px` lengths when the value is explicit.
- Resolve percentages against the selected font face's measured natural line
  height and pixels in PlayRes space.
- Use the resolved baseline advance in maximum-height line capacity, wrapping,
  preview, JSON, and final ASS rendering.
- Preserve one logical cue in JSON/SRT even when ASS needs multiple generated
  events to position its visual lines.
- Support ordinary, progressive karaoke, and active-word output.

Excluded:

- Negative leading, overlapping lines, per-line values, animated leading, and
  different line heights inside one cue.
- Replacing maximum height or exposing a public maximum-lines option.
- Switching normal subtitle rendering to FFmpeg `drawtext` or adding a direct
  libass Python binding.

## Decisions and constraints

- `auto` preserves the current font-metric line height and existing single ASS
  dialogue event path.
- An explicit percentage means a percentage of the measured natural line
  height, so `100%` is mathematically equivalent to the automatic value before
  deterministic integer PlayRes rounding. A pixel value is the requested
  baseline-to-baseline advance.
- After font resolution, an explicit value smaller than the natural line height
  is rejected. The initial feature supports increasing or preserving line
  height, not intentional overlap.
- Total text-block height is
  `natural_line_height + (line_count - 1) * resolved_line_height`. Backdrop and
  shadow allowances remain additional outer decorations.
- `max-height` stays authoritative. Line capacity becomes one plus the number
  of requested baseline advances that fit after the first natural line and
  decorations. Increasing line height may therefore reduce the allowed number
  of lines and cause earlier cue splitting.
- ASS has no per-style line-height field. The
  [libass API](https://github.com/libass/libass/blob/master/libass/ass.h)
  exposes global `ass_set_line_spacing()`, but the
  [FFmpeg subtitles filter](https://ffmpeg.org/ffmpeg-filters.html#subtitles-1)
  used by this project does not expose it. Explicit line height is therefore
  compiled into generated per-line ASS events rather than approximated with
  blank or mutated transcript lines.
- The user-facing placement mode does not change. Native mode still interprets
  margins and named position; explicit mode still interprets X/Y and anchor.
  The ASS compiler may emit private `\an`/`\pos` tags for individual visual
  lines when explicit line height is active, and JSON records
  `render_strategy: positioned-lines` separately from `placement_mode`.
- Default `auto` emits none of this additional markup and preserves the current
  retained ASS structure.

## Public interface and contracts

~~~
--line-height auto
--line-height 125%
--line-height 64px
~~~

Unknown keywords, bare numbers, negative values, unsupported units, and
excessive precision fail during CLI/configuration validation. Values that
resolve below the selected font's natural line height or leave no line inside
`max-height` fail after ffprobe/font resolution and before WhisperX.

The typed appearance contract stores `auto` or a relative length before
geometry/font resolution and the resolved baseline advance afterward. JSON
adds requested, natural, and resolved line heights, their percentage basis,
derived line capacity, and render strategy. SRT text/timing and JSON transcript
segments remain unchanged. Retained ASS may contain multiple synchronized
dialogue/drawing events for one logical multi-line cue only when explicit line
height is active.

## Renderer strategy

- Extend `TextMeasurementInfo`/`TextMeasurer` with the ascent, descent, and
  natural baseline advance required to position lines. The Unicode fallback
  supplies explicit estimated metrics and keeps its diagnostic.
- Extend `WrappingMetrics` with natural and resolved line height and use the
  new block-height formula for capacity and preview first-segment fitting.
- Build a typed visual-line model after wrapping. Each line retains its exact
  display fragments and aligned-word references, plus measured width, baseline
  offset, cue-relative timing state, and resolved anchor position.
- For explicit line height and two or more lines, serialize one synchronized
  text event per visual line. Derive top-, middle-, and bottom-anchored baseline
  positions from the full block so its selected anchor remains fixed.
- In native placement, derive the anchor point from the existing resolved
  margin region and named ASS alignment. In explicit placement, reuse the
  validated global X/Y point. Validate the measured visual block against the
  declared max-width/max-height envelope; do not clamp or move it.
- For `backdrop box`, generate one typed background drawing on a lower ASS layer
  using the measured full block bounds, configured color, padding, and shadow,
  while text-line events avoid duplicate boxes. `none` and `outline` continue
  using glyph-level rendering. This production drawing contract remains
  separate from preview guide drawings and escaped transcript text.
- Partition karaoke display fragments by visual line. The effect compiler must
  preserve cue-relative activation times across synchronized line events.
  Progressive mode may use interval events instead of one editable `\k` event
  only for the explicit-line-height path; this retained-ASS representation
  difference is documented in JSON and README. Active-word mode reuses its
  existing interval boundaries across every visible line.
- Preview uses the same visual-line model and ASS compiler. Guides show natural
  and resolved line height, line capacity, the actual single-event or
  positioned-lines strategy, and the final block envelope.

## Implementation tasks

- [x] Add `auto`/length parsing, typed configuration, CLI help, and validation.
- [x] Expose measured ascent, descent, natural line height, and estimated
  fallback metrics without leaking font paths.
- [x] Update maximum-height capacity and wrapping metadata with the multi-line
  block-height formula.
- [x] Introduce typed visual lines and anchor-relative baseline positioning for
  native and explicit modes.
- [x] Add layered ASS serialization for line events and one shared box backdrop
  while preserving safe escaping.
- [x] Make ordinary, progressive karaoke, active-word, and preview compilation
  consume the same positioned-line model.
- [x] Add JSON render-strategy and requested/resolved line-height diagnostics.
- [x] Add focused unit, controlled libass integration, visual regression, and
  zero-default tests.
- [x] Update README.md, docs/prd.md, docs/architecture.md, docs/conventions.md
  where the new rendering boundary is reusable, and roadmap status.

## Unit tests

- `auto`, `100%`, larger percentages, pixels, half-up resolution, and typed
  revalidation.
- Rejection of empty values, unknown keywords, bare numbers, negative values,
  invalid units, excessive precision, zero, and resolved values below natural
  line height.
- Capacity boundaries for one, two, and several lines using the formula above,
  including backdrop/shadow allowances and insufficient `max-height`.
- Equivalent preview and transcription wrapping decisions for the same metrics.
- Single-line cues preserve the traditional ASS path and indivisible-token
  overflow behavior even when line height was requested explicitly.
- Preview and retained JSON report positioned-lines only when the final display
  text actually expands into multiple visual lines.
- Baseline offsets for all nine anchors, asymmetric native margins, and explicit
  coordinates.
- Block bounds and one shared box drawing for left-, center-, and right-aligned
  lines of different widths.
- Layer ordering, ASS escaping, braces, backslashes, commas, Unicode, RTL, CJK,
  emoji, and intentional line breaks.
- Progressive and active-word timing across line boundaries, gaps, fallback
  cues, and words whose display fragments do not map losslessly.
- JSON logical cue count remains unchanged while ASS render-event count may
  increase.
- `auto` preserves current ASS dialogue count, style, wrapping, preview, and
  karaoke paths.

## Integration and manual verification

- First prove per-line baseline placement and shared box composition using a
  controlled font and FFmpeg/libass fixture before exposing the CLI option.
- Render `auto`, `100%`, `125%`, and fixed-pixel line heights with two and three
  lines at landscape, portrait, square, and autorotated geometries.
- Cover all vertical anchor families, native margins, explicit coordinates,
  backdrop none/outline/box, shadow, font weights, and letter spacing.
- Compare preview and final frames and measure baseline deltas within a defined
  one-pixel PlayRes tolerance.
- Verify progressive and active-word karaoke before, during, and after a word
  transition on different lines.
- Confirm no generated media, font files, or subtitle artifacts are committed.

## Documentation

- Add `--line-height`, `auto`, unit bases, examples, minimum value, max-height
  interaction, and retained-ASS event behavior to README.md.
- Extend FR-7, FR-9, FR-16, readability requirements, and acceptance criteria in
  docs/prd.md.
- Update natural/resolved font metrics, wrapping capacity, visual-line model,
  native/explicit placement internals, ASS layers/drawings, karaoke, preview,
  JSON, and FFmpeg/libass limitations in docs/architecture.md.
- Update docs/conventions.md with reusable generated-event layering, text
  escaping, and controlled visual-tolerance rules.

## Performance, migration, and rollback

- Cache keys for measured typography include font weight, font, font size,
  letter spacing, and line height. Do not cache transcript text across runs.
- Explicit line height increases ASS events proportionally to visible lines and
  karaoke intervals. Add bounded fixture assertions and disclose the measured
  impact in the pull request.
- Existing commands and retained ASS remain unchanged under `auto`; no data
  migration is required.
- The plan is independently revertible before release. After release, rollback
  follows a revert pull request and new patch tag rather than moving a tag.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-line-height
~~~

Suggested commits:

1. `refactor: model positioned subtitle lines`
   - Metric contracts, visual-line model, baseline geometry, and focused tests
     without changing default output.
2. `feat: add configurable subtitle line height`
   - CLI/configuration, capacity, layered ASS rendering, preview, karaoke, JSON,
     and integration tests.
3. `docs: document subtitle line height`
   - README, PRD, architecture, conventions, and roadmap status.

Suggested pull request:

~~~
Title: feat: add configurable subtitle line height
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_cli.py tests/test_layout.py tests/test_text_measurement.py tests/test_wrapping.py tests/test_ass.py tests/test_preview.py tests/test_karaoke.py tests/test_transcriber.py tests/test_subtitler.py`.
- Run `python -m pytest -m integration tests/test_integration.py -k 'line or font or preview or karaoke'`
  with the controlled FFmpeg/libass prerequisites.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff check .`, and `python -m pyright`.
- In the final pre-PR documentation commit, move the plan and package to
  `In review` and record `feat/subtitle-line-height` as the delivery reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 2 and the package `Done`, replace the branch with the merged PR
  link, recalculate catalog progress, and assess the accumulated changes for a
  minor release without creating a tag automatically.

## Acceptance criteria

- `auto` preserves current preview, wrapping, ASS event structure, final
  rendering, and karaoke behavior.
- An explicit valid line height produces the documented baseline distance in
  both preview and final rendering within the controlled tolerance.
- Maximum-height capacity and cue splitting use the same resolved line height
  as rendering and never place more lines than the declared envelope permits.
- Native margins/named positions and explicit coordinates/anchors keep their
  existing user-facing semantics.
- Box, outline, shadow, font weight, letter spacing, progressive karaoke, and
  active-word output remain visually stable and safely escaped.
- Invalid or too-small values fail before model loading with actionable errors.
- SRT and JSON logical transcript content/timing remain unchanged; JSON makes
  the expanded ASS render strategy explicit.
