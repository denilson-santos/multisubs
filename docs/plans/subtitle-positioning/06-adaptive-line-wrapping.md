# Feature 6: adaptive line wrapping

Status: In review

Pull request: [#33](https://github.com/denilson-santos/multisubs/pull/33)

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Relative units](03-relative-units.md)
- [Layout presets](04-layout-presets.md)

## Objective

Replace the fixed 42-character visual line target with layout-aware cue capacity
while preserving the existing preference for punctuation, clauses, and pauses.
Measure against the font that will actually be rendered whenever it can be
resolved, and avoid premature or visually poor breaks such as leaving a single
short word on the final line.

## Scope

Included:

- Resolve a concrete font face for measurement when `--fonts-dir` or the local
  libass-compatible system provider makes that deterministic.
- Measure text with the resolved face, size, weight, style, language, and text
  direction before deciding whether a visual break is necessary.
- Retain a documented Unicode-aware estimator when the rendered font cannot be
  resolved reliably.
- Replace greedy line selection with bounded global partitioning for the
  supported one-, two-, and three-line layouts.
- Penalize avoidable orphan lines without weakening sentence, clause, pause,
  timing, or content-preservation rules.
- Record the requested font, resolved font, font source, and measurement mode in
  reproducibility metadata.
- Make margins the containing rectangle for percentage maximum width and custom
  coordinate resolution.
- Resolve named positions and custom coordinates through one explicit ASS
  anchor/position path.

Excluded:

- Bundling or redistributing Roboto or another default font.
- Claiming pixel-identical metrics between Pillow and every libass build,
  shaping engine, or platform font provider.
- Mutating text, shrinking the font, or hyphenating words to make a cue fit.
- Changing `MAX_CUE_DURATION`, `PAUSE_BREAK_THRESHOLD`, or
  `MODEL_LOAD_ATTEMPTS`.
- Content-aware positioning or collision detection against video imagery.

## Product rules

- Semantic boundaries remain more important than perfectly equal line lengths.
- If the complete cue fits the measured width budget, it remains on one line.
- `max-width` is a ceiling for line wrapping, not a target line width.
- Avoid a one-word or disproportionately short final line when another valid
  split with the same semantic priority fits the budget.
- No word may be removed, truncated, or mutated to satisfy layout.
- max-lines defaults to two.
- Long unbroken tokens may overflow when no safe split exists.
- A new cue is preferred over an unintended third line when timings allow.
- SRT receives intentional visual line breaks but cannot express position or safe
  areas.
- ASS remains the authoritative rendered layout.

This feature makes the cue-layout engine capable of enforcing the resolved
`SubtitleLayout.max_lines` value supplied by presets. The explicit user override
is added separately by [Feature 7](07-maximum-lines.md), after this engine is in
place.

The public `--max-width LENGTH` override is delivered here because width is the
layout input that replaces the fixed character target. It accepts the existing
`%` and `px` syntax and overrides only the selected preset's maximum width.

## Internal cue separation

Represent:

- semantic_text: normalized words without visual line breaks;
- display_text: text after layout-specific wrapping;
- words: original usable word metadata;
- timing: cue start and end;
- placement: generated independently from text.

The public width override is:

~~~
--max-width LENGTH
~~~

`LENGTH` uses the existing `%` or `px` parser. Percentages resolve against the
safe-area width remaining after horizontal margins. The final budget is the
smaller of that ceiling and the capacity available from the selected horizontal
anchor. There is no public max-lines flag
in this feature; presets provide the internal two-line default and Feature 7
adds the explicit user override.

JSON policy must be explicit:

- Preserve the documented text field behavior for the current release line.
- If semantic_text is added, make it additive and introduce schema_version first.
- Do not silently change text meaning or timing metadata.

## Available-width calculation

Calculate a cue's usable width from:

1. Resolved safe rectangle.
2. max-width.
3. Horizontal anchor.
4. Resolved font size.
5. Backdrop and shadow allowance.

The calculation produces a width budget in PlayRes coordinates.

Resolution is intentionally staged:

1. Resolve margins against the autorotated render axes.
2. Build the safe rectangle.
3. Resolve percentage max-width and custom X/Y values against safe width or
   height; custom pixel values are offsets from the safe left/top origin.
4. Convert named or custom placement to a PlayRes anchor point.
5. Calculate anchor capacity: rightward for left anchors, leftward for right
   anchors, and twice the shorter side for centered anchors.
6. Use `min(max-width, anchor capacity)` as the effective wrapping budget.

All preset baselines use `max-width: 100%` because their margins already define
the intended safe width. A named `--position` derives both its anchor and the
matching safe-area edge/center point. Public `--anchor` remains exclusive to
custom X/Y mode. Both modes are serialized as private per-event `\an`/`\pos`
tags so asymmetric margins also produce an exact safe-area center.

## Text-width estimation

Introduce a font-resolution and measurement boundary rather than treating a
single average-glyph multiplier as rendered width.

Font resolution follows this order:

1. Search the validated `--fonts-dir` for a face matching family, bold, and
   italic settings. Read the face metadata instead of matching filenames only.
2. On platforms where the same provider used by libass can be queried safely,
   resolve the requested face through that provider. On Linux, use `fc-match`
   through an argument vector and validate the returned regular file before
   opening it.
3. If a concrete face cannot be proven, use the Unicode-aware estimator and
   report the unresolved requested font. Do not silently measure another font
   while claiming it is the requested one.

The primary measurer should:

- Add Pillow as an explicit runtime dependency after verifying its license,
  Python 3.10-3.13 wheels, installation size, and supported shaping features.
- Load the exact resolved TrueType/OpenType face and measure advance width with
  `ImageFont.getlength()`; use RAQM when available for direction-, language-,
  and shaping-aware measurement.
- Use the resolved font size, bold/italic face, direction, and language when
  selecting or configuring the face.
- Add outline, shadow, and opaque-box allowances after measuring glyph advance;
  those decorations must not be hidden inside a generic glyph multiplier.
- Cache the resolved face and repeated measurements in memory for the duration
  of one run. Cache keys include every input that can change width, and the
  cache must not persist transcript text to disk.

The fallback estimator should:

- Use Unicode-aware display-width categories rather than Python string length.
- Treat combining marks as zero-width where appropriate.
- Account for wide CJK characters and emoji conservatively.
- Use resolved font size and centralized, calibrated category factors rather
  than one undocumented factor for all scripts.
- Expose that the result is an estimate and include the measurement mode in the
  rendering metadata.

Record additive rendering metadata in this shape, following the repository's
existing schema-version policy:

~~~json
{
  "text_measurement": {
    "mode": "font-metrics",
    "requested_font": "Roboto",
    "resolved_font": "Roboto",
    "resolved_style": "Regular",
    "font_source": "fonts-dir",
    "shaping": "raqm",
    "metric_size": 36
  }
}
~~~

`mode` is `font-metrics` or `unicode-estimate`; unresolved fields are `null`,
not guessed values. Do not store an absolute system font path in portable output
metadata. `metric_size` records the internal Pillow size after normalizing its
ascent and descent to libass's FreeType real-dimension sizing; it is not a public
style override. Libass remains authoritative for final shaping and rendering,
so the integration suite defines a documented tolerance between measured and
rendered bounds rather than requiring exact equality.

## Cue construction algorithm

1. Build semantic word groups using aligned timings.
2. Prefer sentence endings.
3. Prefer clause endings.
4. Prefer meaningful pauses.
5. Enforce duration limits.
6. Measure the complete cue against the resolved width budget. If it fits, emit
   it as one line and do not search for a break.
7. When a break is required, enumerate valid word-boundary partitions up to the
   resolved max-lines value. Use a bounded dynamic-programming search for two or
   three lines instead of greedily filling the first line.
8. Score complete candidate partitions in this order:
   - invalid timing, lost content, or a line-count violation;
   - semantic boundary class: sentence, clause, meaningful pause, then lexical;
   - horizontal overflow;
   - avoidable one-word or disproportionately short orphan lines;
   - line balance and raggedness;
   - stable source order as the deterministic tie-breaker.
9. If no valid display partition fits, split into additional timed cues at the
   best semantic word boundary when aligned timings permit it.
10. Emit the selected intentional line breaks identically to SRT and ASS.

Keep all thresholds and scoring weights centralized and documented. An orphan
penalty is comparative, not a rule that rejects valid language: a one-word line
remains allowed when the word is indivisible or every alternative has a worse
semantic, timing, overflow, or line-count result.

## Fallback behavior

- Without word timestamps, wrap the coarse segment text using safe lexical
  boundaries.
- For languages without spaces, use Unicode-aware character boundaries without
  claiming linguistic segmentation.
- If a single token exceeds the width, preserve it intact and allow controlled
  overflow.
- If the requested font cannot be resolved, emit a concise diagnostic, record
  `unicode-estimate`, and keep the ASS safe rectangle as the hard render
  containment boundary.
- Never invent timestamps solely to satisfy the width or orphan score.
- If libass ultimately selects a different fallback font, its wrapping may
  differ from the predicted breaks; the metadata and diagnostic must make this
  limitation visible.

## Implementation tasks

- [x] Separate semantic and display text.
- [x] Pass resolved layout into cue layout.
- [x] Replace MAX_CHARS_PER_LINE with a calculated width budget.
- [x] Preserve MAX_CUE_DURATION and semantic boundary priorities.
- [x] Add internal max-lines validation and enforcement.
- [x] Add Unicode display-width estimation.
- [x] Account for backdrop and shadow bounds.
- [x] Configure ASS WrapStyle and margins consistently.
- [x] Define JSON and SRT serialization policy.
- [x] Record resolved wrapping inputs for reproducibility.
- [x] Add the public `--max-width` override and preset width baselines.
- [x] Add a typed font resolver for `--fonts-dir` and supported system font
      providers, including family, bold, and italic face selection.
- [x] Add Pillow as a justified direct dependency and implement cached,
      shaping-aware font measurement behind a small internal interface.
- [x] Keep the Unicode estimator as an explicit fallback and calibrate its
      category factors with controlled fixtures.
- [x] Record requested/resolved font information and measurement mode without
      leaking machine-specific absolute paths.
- [x] Replace greedy line filling with bounded global partitioning for one,
      two, and three lines.
- [x] Add orphan and raggedness scoring below semantic and overflow priorities.
- [x] Add regression coverage for the premature Portuguese line break observed
      with zero horizontal margins and `--max-width 100%`.
- [x] Resolve max-width percentages against safe width and set preset baselines
      to 100% without duplicating horizontal insets.
- [x] Treat custom X/Y as safe-area-local offsets and translate the result to
      PlayRes coordinates.
- [x] Resolve named positions and custom coordinates through the same validated
      per-event ASS placement path.
- [x] Limit the effective width by the horizontal capacity of off-center custom
      anchors and expose that capacity in rendering metadata.

## Unit tests

- The same sentence in landscape and portrait.
- Small and large font sizes.
- Narrow and wide max-width.
- One-, two-, and three-line limits.
- Sentence, clause, and pause boundary priority.
- Exact width thresholds.
- Margin changes recalculate percentage max-width against the new safe width.
- Named positions map to safe-area edges/center with asymmetric margins.
- Custom top-left at a 600px safe-area X offset on a 1920px canvas with 100px
  side margins resolves to PlayRes X=700 and an 1120px anchor capacity.
- Very long token.
- Missing word timestamps.
- CJK without spaces.
- Right-to-left text.
- Combining marks and emoji.
- Content and timestamp preservation.
- Font resolution from `--fonts-dir`, including family names that differ from
  filenames and bold/italic face selection.
- Available system-provider resolution and a deterministic unresolved-font
  fallback.
- Metadata for font-metrics and Unicode-estimate modes without absolute paths.
- A sentence whose full measured width is below the budget remains on one line.
- Candidate partitions of equivalent semantic quality avoid a one-word final
  line and prefer the less ragged result.
- The observed regression text remains on one line for the controlled 1920-wide
  fixture with zero horizontal margins and `--max-width 100%`:

  ~~~text
  divulgou um vídeo nas redes sociais agradecendo o apoio recebido nos últimos dias.
  ~~~

Property checks should ensure concatenating the semantic content of split cues
reconstructs the original normalized text. The hermetic suite covers the
resolved width budget, one-, two-, and three-line internal limits, long tokens,
CJK text, combining marks, emoji, and timed-word preservation.

## Integration tests

With a controlled installed font:

- Render one-line and two-line golden samples.
- Confirm no ordinary reference cue exceeds max-lines.
- Confirm the text remains inside the safe rectangle.
- Compare Pillow advance measurements with libass-rendered bounds using an
  explicit tolerance that covers rounding and shaping differences.
- Verify the Portuguese regression cue is not broken before `dias.` when its
  rendered bounds fit the 1920-wide budget.
- Resolve the same controlled face through `--fonts-dir`, then exercise a
  missing requested font and verify its diagnostic and fallback metadata.
- Compare landscape, portrait, and square wrapping.
- Render complex-script fixtures when libass has the required shaping support.

The existing opt-in FFmpeg/libass suite remains the render boundary; generated
media is not committed.

## Documentation

- [x] Replace the fixed 42-character architecture statement.
- [x] Document max-width and preset-provided max-lines behavior.
- [x] Explain approximate calculation versus final libass shaping.
- [x] Document long-token fallback.
- [x] Update FR-7 and caption-readability requirements.
- [x] Update JSON and SRT contracts; keep the existing JSON `text` field and
      keep semantic/display helper fields internal to the serializers.
- [x] Document requested versus resolved fonts, measurement modes, system-font
      limitations, and the additive metadata fields.
- [x] Document why Pillow is direct, its shaping limitations, and the libass
      comparison tolerance.

## Commit and pull-request plan

Suggested branch:

~~~
feat/adaptive-subtitle-wrapping
~~~

Suggested commits:

1. refactor: separate semantic and display subtitle text
   - Preserve content and serialization contracts with regression tests.
2. feat: size subtitle cues from the resolved layout
   - Add Unicode-aware width budgets, max-lines behavior, and cue tests.
3. feat: measure subtitle text with resolved font metrics
   - Add explicit font resolution, Pillow measurement, caching, fallback
     metadata, and dependency checks.
4. fix: avoid premature and orphaned subtitle breaks
   - Add global partition scoring and the Portuguese 1920-wide regression.
5. test: render adaptive subtitle wrapping
   - Add controlled-font integration coverage across aspect ratios and scripts.
6. docs: document adaptive subtitle wrapping
   - Update cue policy, output contracts, limitations, and requirements.

Suggested pull request:

~~~
Title: feat: adapt subtitle wrapping to the resolved layout
Base: main
~~~

The PR must compare the old fixed-character behavior with the new width budget,
show that semantic boundary priority is preserved, and identify any JSON or SRT
contract impact. Visual evidence must use a controlled, documented font and
include the reported before/after case where `dias.` previously became an orphan
line despite the complete cue fitting the available width. The dependency
rationale, requested/resolved font behavior, measurement fallback, libass
tolerance, and cache/performance impact must be stated explicitly.

Before requesting review:

- Run the complete cue-construction regression suite.
- Prove normalized semantic content is preserved after splitting.
- Exercise CJK, right-to-left, combining-mark, emoji, and long-token fixtures.
- Run `python -m pytest tests/test_layout.py tests/test_transcriber.py tests/test_ass.py tests/test_config.py tests/test_cli.py`.
- Run the controlled-font opt-in FFmpeg/libass regression suite.
- Run `python -m compileall multisubs`, `multisubs --help`, `python -m pytest`,
  `python -m ruff check .`, and `python -m pyright` when installed and
  configured.
- Because the dependency set changes, run `python -m build` and install the
  generated wheel in a clean Python 3.10-3.13 environment represented by CI.
- Inspect `git diff --check` and confirm no generated media, subtitle artifacts,
  font files, or caches are staged.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- Visual capacity changes with width, font size, and max-lines.
- A complete cue that fits its font-measured width budget has no intentional
  line break.
- The Portuguese regression cue remains one line in the controlled 1920-wide,
  zero-horizontal-margin, 100%-max-width fixture.
- When a break is necessary, equally valid semantic candidates do not leave an
  avoidable one-word or disproportionately short final line.
- Semantic boundary priority remains covered by regression tests.
- Normal cues fit the configured reference layouts.
- No text or timing information is lost.
- A resolved font uses cached font metrics; an unresolved font uses a visible,
  deterministic Unicode-estimate fallback and never masquerades as exact.
- Requested/resolved font and measurement mode are reproducible without
  exposing absolute local font paths.
- Measurement overhead is bounded by one font-resolution pass per style and an
  in-memory cache; the PR records the benchmark and tolerance used.
- CJK, right-to-left, combining-mark, and emoji cases remain valid UTF-8 and
  render safely.
