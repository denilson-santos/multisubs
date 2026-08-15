# Feature 6: adaptive line wrapping

Status: planned

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Relative units](03-relative-units.md)
- [Layout presets](04-layout-presets.md)

## Objective

Replace the fixed 42-character visual line target with layout-aware cue capacity
while preserving the existing preference for punctuation, clauses, and pauses.

## Product rules

- Semantic boundaries remain more important than perfectly equal line lengths.
- No word may be removed, truncated, or mutated to satisfy layout.
- max-lines defaults to two.
- Long unbroken tokens may overflow when no safe split exists.
- A new cue is preferred over an unintended third line when timings allow.
- SRT receives intentional visual line breaks but cannot express position or safe
  areas.
- ASS remains the authoritative rendered layout.

## Internal cue separation

Represent:

- semantic_text: normalized words without visual line breaks;
- display_text: text after layout-specific wrapping;
- words: original usable word metadata;
- timing: cue start and end;
- placement: generated independently from text.

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

## Text-width estimation

The pure layout engine should:

- Use Unicode-aware display-width categories rather than Python string length.
- Treat combining marks as zero-width where appropriate.
- Account for wide CJK characters and emoji conservatively.
- Use resolved font size to convert display units into an estimated pixel width.
- Avoid claiming exact glyph measurement when the selected font or fallback font
  is not known.

Libass remains responsible for final font shaping. The ASS safe rectangle and
WrapStyle provide the final containment boundary.

If exact font measurement is later required, it should be a separate change with
an explicit font-resolution strategy rather than an implicit Pillow dependency.

## Cue construction algorithm

1. Build semantic word groups using aligned timings.
2. Prefer sentence endings.
3. Prefer clause endings.
4. Prefer meaningful pauses.
5. Enforce duration limits.
6. Estimate whether the cue fits max-lines in the resolved width.
7. Split at the highest-priority nearby semantic boundary.
8. Balance lines within the chosen cue without overriding higher semantic
   priorities.
9. Emit intentional line breaks for SRT and ASS.

Keep all thresholds centralized and documented.

## Fallback behavior

- Without word timestamps, wrap the coarse segment text using safe lexical
  boundaries.
- For languages without spaces, use Unicode-aware character boundaries without
  claiming linguistic segmentation.
- If a single token exceeds the width, preserve it intact and allow controlled
  overflow.
- If font fallback changes actual metrics, libass may adjust final wrapping
  within the safe region.

## Implementation tasks

- [ ] Separate semantic and display text.
- [ ] Pass resolved layout into cue layout.
- [ ] Replace MAX_CHARS_PER_LINE with a calculated width budget.
- [ ] Preserve MAX_CUE_DURATION and semantic boundary priorities.
- [ ] Add max-lines validation.
- [ ] Add Unicode display-width estimation.
- [ ] Account for backdrop and shadow bounds.
- [ ] Configure ASS WrapStyle and margins consistently.
- [ ] Define JSON and SRT serialization policy.
- [ ] Record resolved wrapping inputs for reproducibility.

## Unit tests

- The same sentence in landscape and portrait.
- Small and large font sizes.
- Narrow and wide max-width.
- One-, two-, and three-line limits.
- Sentence, clause, and pause boundary priority.
- Exact width thresholds.
- Very long token.
- Missing word timestamps.
- CJK without spaces.
- Right-to-left text.
- Combining marks and emoji.
- Content and timestamp preservation.

Property checks should ensure concatenating the semantic content of split cues
reconstructs the original normalized text.

## Integration tests

With a controlled installed font:

- Render one-line and two-line golden samples.
- Confirm no ordinary reference cue exceeds max-lines.
- Confirm the text remains inside the safe rectangle.
- Compare landscape, portrait, and square wrapping.
- Render complex-script fixtures when libass has the required shaping support.

## Documentation

- Replace the fixed 42-character architecture statement.
- Document max-width and max-lines.
- Explain approximate calculation versus final libass shaping.
- Document long-token fallback.
- Update FR-7 if expected wrapping outcomes change.
- Update JSON and SRT contracts if new fields are introduced.

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
3. test: render adaptive subtitle wrapping
   - Add controlled-font integration coverage across aspect ratios and scripts.
4. docs: document adaptive subtitle wrapping
   - Update cue policy, output contracts, limitations, and requirements.

Suggested pull request:

~~~
Title: feat: adapt subtitle wrapping to the resolved layout
Base: dev
~~~

The PR must compare the old fixed-character behavior with the new width budget,
show that semantic boundary priority is preserved, and identify any JSON or SRT
contract impact. Visual evidence must use a controlled, documented font.

Before requesting review:

- Run the complete cue-construction regression suite.
- Prove normalized semantic content is preserved after splitting.
- Exercise CJK, right-to-left, combining-mark, emoji, and long-token fixtures.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- Visual capacity changes with width, font size, and max-lines.
- Semantic boundary priority remains covered by regression tests.
- Normal cues fit the configured reference layouts.
- No text or timing information is lost.
- CJK, right-to-left, combining-mark, and emoji cases remain valid UTF-8 and
  render safely.
