# Simplify ASS and animation rendering

Status: In review

Depends on: [Plan 1](01-text-and-layout.md).

## Objective

Turn ASS generation into an explicit compile-and-serialize pipeline instead of
one large conditional writer, while retaining byte-stable static output where
the current contract requires it.

## Scope

Included: `ass.py`, `animation.py`, `render_capabilities.py`, related models,
and ASS/animation/word-highlight tests.

Excluded: new effects, visual redesign, easing controls, renderer replacement,
or changes to SRT and JSON contracts.

## Decisions and implementation

- Separate preparation of styles, placements, visual events, guide events, and
  final text serialization. User text remains escaped independently of trusted
  generated tags.
- Use one typed internal event path for static, cue-animated, word-animated,
  preview, outline, and vector-box cases; specialization stays in small event
  producers rather than mode flags spread across serialization.
- Preserve layer ordering, centisecond timing, animation continuity, one shared
  cue box, fragment placement, shaping-safe full-line fallback, and the private
  ASS field order.
- Extract an internal module only if `ass.py` remains responsible for unrelated
  compilation and wire-format concerns after helper extraction.

## Tasks and verification

- [x] Retain structural tests for plain, boxed, outlined, cue-animation,
  progressive, active-word, and fallback ASS output.
- [x] Decompose `write_ass()` into explicit preparation and event-writing
  stages; keep event producers separate where output contracts differ.
- [x] Remove only the repeated settle assertion; retain all animation cases and
  landscape/portrait coverage.
- [x] Verify real libass renders for every cue/word motion, highlight color
  transitions, and animated preview output.

Run:

~~~
.venv/bin/python -m pytest tests/test_ass.py tests/test_animation.py
.venv/bin/python -m pytest -m integration tests/test_integration.py tests/test_preview_integration.py
.venv/bin/python -m pytest
~~~

## Delivery

Included on the shared branch: `refactor/simplify-codebase`.
Suggested commits: `test: characterize ASS rendering modes`, then
`refactor: separate ASS compilation from serialization`; these are commits
within the shared refactor, not a separate pull request.
Use the standard plan status and explicit Git delivery approval lifecycle.

## Acceptance criteria

- `write_ass()` coordinates cohesive stages and no longer owns the full branch
  tree for every rendering mode.
- Static/default output remains byte-compatible where asserted; animated output
  preserves event timing, geometry, colors, opacity, effects, and layer order.
- Malformed typed inputs and unsafe text fail or escape at the same boundary.
- Focused and controlled libass tests cover every retained renderer strategy.
