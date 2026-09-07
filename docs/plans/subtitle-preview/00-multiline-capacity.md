# Use multiline capacity when selecting preview text

Status: Done

Depends on:

- [Layout preview](../subtitle-positioning/08-layout-preview.md).
- [Unified vector box](../subtitle-backdrops/00-unified-vector-box.md).

Delivery: [PR #68](https://github.com/denilson-santos/multisubs/pull/68), merged
into `main`.

## Objective and evidence

When a sample exceeds the envelope, choose a readable first cue that uses
available lines instead of favoring a prefix approximately one line wide.

Reproduced at 1920x1080 with default styling and `--max-width=60%`: horizontal
margins leave 1228px, maximum width is 737px, text budget is 715px, natural
line height is 43px, and vertical padding is 22px. `--max-height=190px`
permits three lines but selects two; 195px permits four and displays the full
four-line sample. The four-line threshold of 194px is correct.

`wrapping.py::_layout_break_key` currently compares the unwrapped prefix width
to one line's budget. Both lexical preview and aligned-word boundary selection
use this key. `fit_first_text_segment` takes the selected prefix, then wraps it.

## Scope and contracts

Correct shared boundary ranking while preserving sentence/clause/pause priority
and avoidable-orphan policy. Among otherwise equivalent fitting candidates,
prefer the longest fitting prefix; line partition scoring continues to balance
that prefix. Earlier punctuation may legitimately leave unused space. A maximum
is not a target requiring blank lines or stretched boxes.

Audit the comparison of decorated width against an already decoration-reduced
budget in `_layout_text_lines` and `_partition_text_units`: count decoration
once, consistently with `layout.py`, and add an exact-fit regression.

No flags, default values, timestamp synthesis, or renderer changes. Actual cue
boundaries may improve in the shared aligned path, but preserve every source
word, its original times and order; do not silently restrict the fix to PNG.
Keep indivisible-token overflow and explicit-envelope validation. Do not promise
monotonic line counts across semantic boundaries; test monotonic prefix coverage
for punctuation-free equal-priority examples.

## Implementation tasks

- [x] Add regressions for the reported 190/195px case with controlled metrics.
- [x] Replace one-line prefix-distance ranking with the shared fitting-prefix
  policy; preserve semantic priority and orphan avoidance in both callers.
- [x] Audit width accounting and exact-fit cases with padding and shadow.
- [x] Verify `preview.py`, aligned layout splitting, and fallback behavior use
  consistent rules without changing source timing or dropping words.
- [x] Exercise punctuation, pauses, one-word tails, CJK, combining marks, emoji,
  auto/explicit line height, native/explicit placement, and fallback measurement.
- [x] Inspect partition-search cost for long samples and small widths; avoid
  adding combinatorial searches when ranking already fitting candidates.
- [x] Update README preview limitations, PRD FR-7/FR-16 and relevant acceptance
  criteria, architecture cue construction, and these roadmap statuses.

The plan remains `In review` until its delivery branch is reviewed and merged.
The implementation now measures raw content against the
decoration-reduced budget, ranks the longest fitting prefix after semantic and
orphan priorities, and stops candidate evaluation after the first overflowing
ordered prefix.

## Verification and acceptance

At 190px the unpunctuated default sample uses three lines and more text than
the previous two-line result; at 195px it fits in four. Render both with bundled
Roboto, recording measured metrics, rather than treating system-font pixels as
portable constants. Include 9:16 and width changes with fixed height. Short
samples remain short; semantic boundaries remain higher priority. Compare PNG
ASS line breaks to shared wrapping results, and check aligned text conservation.

Run:

```sh
python -m pytest tests/test_wrapping.py tests/test_preview.py tests/test_transcriber.py tests/test_layout.py
python -m pytest -m integration tests/test_preview_integration.py tests/test_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Complete clean build, Twine metadata, and artifact audits from the
[delivery gate](../../delivery.md). Skipped integration tests are missing
evidence. Keep synthetic renders in temporary directories; no transcription
or model download is needed.

Local verification completed:

- Controlled 1920x1080 metrics used bundled Roboto: `max-width=60%` resolved
  to `737px`, content budget `715px`, natural line height `43px`, vertical
  decoration `22px`, and capacities 3/4 for `190px`/`195px`. The sample now
  retains three and four visual lines respectively.
- Real FFmpeg preview renders passed for both heights at 1920x1080 and for a
  1080x1920 render with the fixed-width configuration; PNG dimensions matched
  the probed canvas.
- Focused layout/preview/transcriber suite: 162 passed. Full suite: 710
  passed, 53 deselected. Integration suite: 41 passed.
- `compileall`, `multisubs --help`, Ruff format/check, Pyright, and
  `git diff --check` passed. A 100-word synthetic sample completed prefix
  selection in approximately 0.18s after stopping at the first non-fitting
  prefix.

## Delivery and risks

Branch: `fix/preview-multiline-capacity`, from updated `origin/main`.
Suggested commits: `fix: use multiline capacity when selecting subtitle cues`,
then `docs: document multiline preview selection`.
Draft PR title: `fix: use multiline capacity when selecting subtitle cues`.
Link this plan, explain shared cue-boundary impact, list actual checks and
visual evidence, and follow the [dashboard delivery lifecycle](README.md).

Main risk: a shared ranking change alters real cue grouping. Regression tests
must assert semantic boundaries and timing conservation, not only PNG line count.
Rollback through a focused revert PR; no schema or data migration is required.
