# Feature 7: configurable maximum subtitle lines

Status: Planned

Depends on:

- [Shared foundation](00-foundation.md)
- [Layout presets](04-layout-presets.md)
- [Adaptive line wrapping](06-adaptive-line-wrapping.md)

## Objective

Let users choose the maximum number of visual lines in each subtitle cue so a
video can use single-line captions when its orientation, composition, or editing
style benefits from a smaller vertical footprint.

## Scope

Included:

- Add an explicit `--max-lines` layout override.
- Support one-, two-, and three-line limits.
- Apply the selected limit consistently to layout-aware cue splitting, SRT, ASS,
  and rendering metadata.
- Preserve words, ordering, semantic boundary priorities, and available aligned
  timings when a smaller limit creates additional cues.

Excluded:

- Adding a new content-aware or orientation-specific line-count heuristic outside
  the existing preset-resolution rules.
- Per-cue or timestamp-range line-count overrides.
- Exact glyph measurement or font-fallback prediction.
- Rewriting, truncating, hyphenating, or shrinking text to make it fit.

## Public interface

Add:

~~~
--max-lines COUNT
~~~

Accepted values are the decimal integers `1`, `2`, and `3`. Zero, negative
values, signs, decimals, scientific notation, booleans passed through the Python
configuration boundary, and values above three are rejected.

The CLI option is an explicit override rather than an independent default:

1. Resolve the selected layout preset.
2. Apply `--max-lines` when the user supplied it.
3. Validate the final `SubtitleLayout`.
4. Pass the resolved value into cue layout.

Built-in presets continue to resolve to two lines unless a preset plan documents
another calibrated value. Therefore omitting the option preserves the current
two-line user outcome, while `--max-lines 1` requests single-line captions.

## Semantics and constraints

- The value is a maximum, not a requested exact count. Short captions remain on
  one line even when the limit is two or three.
- `--max-lines 1` emits no intentional line break inside an ordinary cue.
- When aligned word timings are available, split an oversized cue at the best
  semantic word boundary and use those timings for the resulting cues.
- Prefer sentence endings, clauses, and meaningful pauses before balancing line
  widths. The line limit must not replace the existing readability priorities.
- Preserve every word exactly once and keep cue timestamps chronological.
- A long indivisible token may overflow horizontally rather than being mutated.
- Without word timings, do not invent precise timestamps merely to create more
  cues. Keep the coarse segment timing, emit no more than the configured number
  of intentional line breaks, and allow controlled horizontal overflow when no
  safe timed split exists.
- Continue applying the duration ceiling independently; increasing max-lines
  must not create overlong cues.

## Public and output contracts

### CLI and Python configuration

- Parse and validate the option before FFprobe or WhisperX loading because the
  accepted range is geometry-independent.
- Store the resolved integer on `SubtitleLayout.max_lines`.
- Preserve the existing typed `SubtitleConfig` boundary; do not pass a loose CLI
  value directly into `transcriber.py` or `ass.py`.
- Programmatic callers receive the same range validation as CLI callers.

### JSON, SRT, and ASS

- Record requested and resolved max-lines values in rendering metadata using
  JSON-compatible integers; use `null` for the requested value when it came from
  a preset.
- Preserve the semantic transcription text policy established by adaptive
  wrapping. Do not make a display newline the only representation of content.
- Serialize the chosen display breaks to SRT physical lines and ASS `\N` through
  the existing safe serializers.
- Keep the output directory, file naming, retention, and collision contracts
  unchanged.

### FFmpeg and dependencies

- Do not add a runtime dependency or change the FFmpeg filter boundary.
- Expect the one-line setting to produce more cues for dense speech. Document
  and measure that effect without changing WhisperX model behavior.

## Internal implementation

- Add a strict `parse_max_lines()` helper or equivalent typed argparse
  conversion in the configuration boundary.
- Extend explicit layout-override merging so max-lines wins field by field over
  the selected preset.
- Ensure the adaptive cue-layout stage receives the resolved line limit rather
  than reading a module constant or CLI namespace.
- Reuse the width estimator and semantic split selection from Feature 6. Do not
  add a second character-count-based wrapping path for single-line mode.
- Keep semantic cues and rendered display cues distinguishable when one semantic
  group must become several timed cues.
- Include requested and resolved values in reproducibility metadata and progress
  diagnostics where other resolved layout choices are reported.
- Keep the resolved value on `SubtitleConfig` so Feature 8 can apply the same
  behavior when layout preview is implemented; Feature 7 does not implement the
  preview mode itself.

## Implementation tasks

- [ ] Add strict max-lines parsing and direct validation.
- [ ] Add the option to the layout CLI group and typed request construction.
- [ ] Merge the explicit value after preset resolution.
- [ ] Pass the resolved value into adaptive cue layout.
- [ ] Enforce one-, two-, and three-line limits for aligned cues.
- [ ] Define and implement the missing-word-timing overflow fallback.
- [ ] Record requested and resolved values in rendering metadata.
- [ ] Add focused CLI, configuration, cue-layout, serialization, and integration
      tests.
- [ ] Update user, product, architecture, and roadmap documentation.

## Unit tests

- Parse `1`, `2`, and `3` exactly.
- Reject zero, negatives, signed values, decimals, scientific notation, empty
  input, oversized numeric strings, and values above three before model loading.
- Resolve the preset value when the flag is absent.
- Prove the explicit value overrides auto, landscape, portrait, and square
  presets without mutating their definitions.
- Confirm a short caption stays on one line for every accepted limit.
- Confirm single-line mode emits no intentional newline and splits an aligned
  oversized cue at a timed semantic boundary.
- Confirm two-line mode preserves the established default output.
- Exercise three-line mode and exact width thresholds.
- Preserve punctuation and pause priorities when a line limit forces a split.
- Preserve normalized semantic content, word order, IDs, and chronological
  timestamps across additional cues.
- Cover missing word timestamps, CJK without spaces, right-to-left text,
  combining marks, emoji, explicit input newlines, and long indivisible tokens.
- Confirm JSON metadata distinguishes an inherited value from an explicit one.

Property-oriented coverage should concatenate the semantic content of all
derived cues and prove it reconstructs the source content for every accepted
line limit.

## Integration and visual verification

With a controlled installed font and synthetic non-sensitive media:

- Render the same ordinary sentence with max-lines one, two, and three.
- Assert that ordinary reference cues do not exceed the requested line count.
- Compare landscape and portrait videos to confirm the explicit value wins over
  their presets.
- Verify single-line captions remain inside the safe rectangle when the text can
  be split at timed word boundaries.
- Verify the SRT line count and rendered ASS bounding height agree for reference
  fixtures.
- Document the controlled-overflow result for a long token and a coarse segment
  without word timestamps.

Attach representative one-line and two-line renders to the pull request rather
than committing generated media.

## Documentation

- Add `--max-lines` to the README command reference and layout examples.
- Explain inherited preset values, explicit override precedence, and the
  difference between a maximum and an exact line count.
- Update FR-7 and caption-readability requirements in `docs/prd.md`.
- Update cue construction, typed layout, fallback, JSON metadata, and SRT/ASS
  contracts in `docs/architecture.md`.
- Update `docs/conventions.md` only if the change establishes a new reusable cue
  policy not already covered by its readability and content-preservation rules.

## Commit and pull-request plan

Suggested branch:

~~~
feat/configurable-subtitle-lines
~~~

Suggested commits:

1. `feat: add a maximum subtitle line override`
   - Add strict parsing, typed configuration, preset precedence, metadata, and
     focused CLI/configuration tests.
2. `feat: enforce configurable subtitle line limits`
   - Connect the resolved value to adaptive cue layout and cover semantic,
     timing, Unicode, and fallback behavior.
3. `test: render configurable subtitle line limits`
   - Add opt-in one-, two-, and three-line FFmpeg/libass coverage.
4. `docs: document configurable subtitle line limits`
   - Update usage, product requirements, architecture contracts, and roadmap
     status.

Suggested pull request:

~~~
Title: feat: add configurable subtitle line limits
Base: main
~~~

The pull request must link this plan, distinguish inherited and explicit values,
show the one-line user outcome in landscape and portrait media, and document the
missing-timing and indivisible-token limitations. It must state that no new
dependency, FFmpeg policy, or output-layout change is introduced.

Before requesting review:

- Run `python -m pytest tests/test_cli.py tests/test_config.py tests/test_layout.py tests/test_transcriber.py`.
- Run the relevant opt-in FFmpeg/libass integration tests when the controlled
  runtime and fixture are available.
- Run `python -m compileall multisubs`, `multisubs --help`, `python -m pytest`,
  `python -m ruff check .`, and `python -m pyright` when installed and configured.
- Inspect `git diff --check` and confirm no generated media or subtitle artifacts
  are staged.
- Update the package dashboard to `In review` and add the pull-request link.

## Acceptance criteria

- Users can select a one-, two-, or three-line maximum with `--max-lines`.
- Omitting the option uses the selected preset and preserves the resolved
  two-line baseline for current built-in presets.
- Invalid values fail with an actionable argument error before FFprobe and
  WhisperX loading.
- An explicit value overrides the preset consistently across supported video
  orientations.
- Ordinary aligned cues do not exceed the configured number of visual lines.
- Single-line mode does not emit intentional display newlines and creates timed
  cue splits when safe aligned boundaries are available.
- No word is removed, duplicated, reordered, or mutated, and no timestamp is
  invented when aligned word timings are unavailable.
- JSON, SRT, ASS, documentation, and rendered output describe or use the same
  resolved max-lines value.
