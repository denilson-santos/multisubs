# Simplify text, measurement, wrapping, and layout

Status: In review

Depends on: [Plan 0](00-configuration-and-requests.md).

## Objective

Clarify the transformations from source text and font metrics to display units,
visual lines, and resolved placements without changing Unicode or geometry
outcomes.

## Scope

Included: `text_segmentation.py`, `text_measurement.py`, `font_catalog.py`,
`wrapping.py`, `layout.py`, and their unit/regression tests.

Excluded: different line-breaking policy, new dictionaries/fonts, approximate
RTL/Indic word rendering, and changes to public layout options.

## Decisions and implementation

- Keep source mapping, linguistic grouping, visual breaking, measurement, and
  placement as separate stages with typed inputs and explicit fallbacks.
- Name shared boundary/partition operations once; remove compatibility joins
  only after proving production and supported Python callers do not use them.
- Keep Pillow/RAQM as measurement owner, fontTools as coverage owner, and
  libass integration tests as render authority. Do not add a cache layer.
- Consolidate repeated range searches and line-capacity calculations into pure
  helpers while retaining longest-fitting legal prefix and half-up rounding.
- Preserve every mapping diagnostic and never fabricate source characters or
  word timestamps.

## Tasks and verification

- [x] Retain source reconstruction, CJK grouping, shaping fallbacks,
  relative-unit rounding, and placement-envelope regression coverage.
- [x] Decompose source mapping, font resolution, partitioning, and placement
  functions along the existing data flow.
- [x] Audit test matrices/fixtures; consolidate only repeated setup and add a
  focused regression for bounded partition tie-breaking.
- [x] Run focused Unicode regressions and an opt-in Japanese measured-render
  check.

Run:

~~~
.venv/bin/python -m pytest tests/test_text_segmentation.py tests/test_text_measurement.py tests/test_font_catalog.py tests/test_wrapping.py tests/test_layout.py tests/test_multilingual_regressions.py
.venv/bin/python -m pytest -m integration tests/test_multilingual_integration.py
.venv/bin/python -m pytest
~~~

## Delivery

Included on the shared branch: `refactor/simplify-codebase`.
Suggested commits: `test: characterize text and layout boundaries`, then
`refactor: simplify text and layout stages`; these are commits within the shared
refactor, not a separate pull request.
Use the standard plan status and explicit Git delivery approval lifecycle.

## Acceptance criteria

- Source reconstruction, display casing, linguistic groups, effect-unit
  identity, cue/line boundaries, font selection, wrapping, and placements match
  the characterized output.
- Unsupported or lossy inputs retain the same visible text and bounded
  diagnostics instead of taking a silent shortcut.
- Pure stages can be understood and tested independently without importing
  WhisperX, PyTorch, or FFmpeg.
- Removed helpers/tests are listed with their replacement or obsolete caller.
