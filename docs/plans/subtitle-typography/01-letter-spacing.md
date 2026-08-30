# Letter spacing

Status: Done

Depends on:

- [Font weight](00-font-weight.md)

## Objective

Let users add consistent horizontal space between rendered glyphs while making
adaptive wrapping and preview use the same effective width as libass.

## Scope

Included:

- Add `--letter-spacing LENGTH`, defaulting to `0px`.
- Accept non-negative `%` and `px`; percentages use resolved font size.
- Compile the resolved value into the ASS `Spacing` style field.
- Include letter spacing in concrete-font and Unicode-estimate width
  measurement, wrapping, preview, JSON, and guide diagnostics.

Excluded:

- Negative tracking, `em` units, kerning switches, horizontal scaling, and
  per-character spacing changes.
- Font-feature or ligature controls.
- Changes to vertical line spacing.

## Decisions and constraints

- The option is semantic even though ASS has a native `Spacing` field; users do
  not provide raw ASS syntax or renderer units without an explicit suffix.
- Percentage spacing resolves against font size, matching backdrop and shadow
  scaling rather than video width.
- Resolution uses the existing deterministic half-up PlayRes pixel rule.
- Spacing is applied to rendered grapheme advances, not Unicode code points or
  bytes. Combining marks and zero-width joiner sequences do not independently
  consume added tracking in the fallback estimator.
- `0px` must preserve current wrapping and ASS rendering behavior.
- A resolved value may not exceed four times the resolved font size; this keeps
  measurement and partition search bounded while allowing intentionally loose
  display typography.
- Pillow and libass can differ in shaping details. The controlled-font
  integration test defines a tolerance and JSON continues identifying whether
  measurement used a concrete face or the Unicode estimate.

## Public interface and contracts

~~~
--letter-spacing 2px
--letter-spacing 4%
~~~

Bare numbers, signed values, unsupported units, excessive precision, and values
that resolve beyond the configured safety bound fail before model loading after
geometry resolution where necessary.

The resolved value is stored in `SubtitleAppearance`. JSON adds requested and
resolved `letter_spacing` plus the percentage basis `resolved-font-size`.
SRT, timing, output layout, and artifact lifecycle are unchanged. ASS writes
the resolved spacing in PlayRes pixels and keeps transcript text escaped.

## Implementation

- Extend the appearance model, default configuration, accepted relative fields,
  geometry resolution, CLI request builder, and typed revalidation.
- Refactor `TextMeasurer.measure()` or wrap it with one shared typography
  measurement layer that adds tracking based on grapheme boundaries. Both
  Pillow/RAQM and Unicode-estimate modes must call the same adjustment.
- Ensure `estimate_text_width()`, global partition scoring, timed cue splitting,
  and `fit_first_text_segment()` consume the adjusted measurement without
  duplicating spacing arithmetic.
- Compile the resolved value into `ASS_STYLE_FIELDS`' existing `spacing` slot
  without changing field order.
- Surface requested and resolved values in transcription JSON and preview guide
  text when guides are enabled.

## Implementation tasks

- [x] Add typed configuration, default, CLI flag, parsing, resolution, and
  validation.
- [x] Add a grapheme-aware spacing adjustment to the common text measurer.
- [x] Compile the value into ASS and preserve zero-spacing output behavior.
- [x] Add JSON metadata and preview-guide typography diagnostics without
  leaking raw ASS tags.
- [x] Create `tests/test_wrapping.py` for direct shared-wrapping coverage rather
  than relying only on transcriber and preview tests.
- [x] Cover wrapping, cue splitting, preview truncation, karaoke, and fallback
  measurement with focused tests.
- [x] Update README.md, docs/prd.md, docs/architecture.md, and roadmap status.

## Unit tests

- Default `0px`, pixel and percentage parsing, half-up resolution, maximum
  bounds, duplicates, invalid units, negative input, and typed revalidation.
- Grapheme counts for Latin text, combining marks, emoji ZWJ sequences, CJK,
  RTL text, spaces, punctuation, and explicit line breaks.
- A cue that fits at `0px` but wraps or splits after positive letter spacing.
- Identical decisions between transcription wrapping and preview first-segment
  fitting for the same text and metrics.
- Exact ASS style field order/value and absence of event-level spacing tags.
- Progressive and active-word karaoke retain the configured style spacing.
- JSON requested/resolved values and percentage basis.

## Integration and manual verification

- Extend the controlled Roboto/libass bounds test with `0px`, `2px`, and a
  percentage-resolved value at landscape and portrait PlayRes sizes.
- Render ordinary and karaoke samples containing Latin, Portuguese combining
  marks, Arabic, CJK, and emoji; compare preview against the final video frame.
- Record before/after frames showing that increased spacing changes wrapping at
  the same maximum width without changing transcript content.

## Documentation

- Add the option, unit basis, examples, zero default, and non-negative
  limitation to README.md; add `--style-spacing` to the migration mapping.
- Extend FR-7/FR-9 and readability acceptance criteria in docs/prd.md.
- Update the appearance model, relative-length bases, wrapping measurement,
  ASS style, preview, and JSON contracts in docs/architecture.md.
- Document any reusable grapheme-measurement convention in docs/conventions.md.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-letter-spacing
~~~

Suggested commits:

1. `feat: add measured subtitle letter spacing`
   - Typed option, measurement, wrapping, ASS/JSON output, and focused tests.
2. `docs: document subtitle letter spacing`
   - README, PRD, architecture, and roadmap status.

Suggested pull request:

~~~
Title: feat: add measured subtitle letter spacing
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_cli.py tests/test_layout.py tests/test_text_measurement.py tests/test_wrapping.py tests/test_ass.py tests/test_preview.py tests/test_karaoke.py`.
- Run the relevant controlled-font integration tests with
  `python -m pytest -m integration tests/test_integration.py -k 'font or wrap or preview'`
  when prerequisites are available.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff check .`, and `python -m pyright`.
- In the final pre-PR documentation commit, move the plan and package to
  `In review` and record `feat/subtitle-letter-spacing` as the delivery
  reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 1 `Done`, replace the branch with the merged PR link, recalculate
  progress, and identify Plan 2 as the next unblocked plan.

## Acceptance criteria

- A positive letter spacing visibly increases glyph spacing in preview and
  final libass rendering.
- Wrapping and cue splitting account for that increase before ASS generation.
- Equivalent percentage values scale from resolved font size; pixel values stay
  fixed in PlayRes space.
- Invalid values fail with actionable diagnostics and no model load.
- `0px` preserves the current visual, SRT, timing, placement, and cleanup
  behavior.
