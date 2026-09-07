# Unified vector box backdrop

Status: Done

Delivered in [PR #67](https://github.com/denilson-santos/multisubs/pull/67).

Depends on completed foundations:

- [Line height](../subtitle-typography/02-line-height.md).
- [Independent subtitle element animations](../subtitle-templates/03-cue-animations-and-animated-templates.md).

## Objective

Render every cue-level `backdrop=box` as one continuous measured rectangle,
whether its text occupies one or several lines. Text and background must share
layout geometry and retain independent animation tracks, avoiding a renderer
switch when a cue wraps or enables word behavior.

## Scope and accepted decisions

- Reuse the vector drawing path and positioned visual-line model already used
  for multi-line boxes and positioned word text. One line is a one-line block.
- Cover ordinary cues, cue animations, both word modes, missing-word fallback,
  and static preview. Preserve layers 0/1/2 for cue background, word decoration,
  and text respectively.
- Keep `outline` attached to glyph geometry and `none` undecorated. Word boxes
  already use measured decorations; their timing and geometry are not being
  redesigned.
- Do not add CLI flags, alternate renderers, image assets, rounded corners,
  gradients, dependencies, font downloads, or a public backend selector.
- Geometry is the stable layout geometry. Text-only movement must not resize
  or move the cue box; the cue backdrop track owns its own motion.

## Current code and compatibility

`multisubs/ass.py` routes every nonempty box cue through positioned visual lines,
neutralizes the text style, and calls `_append_shared_backdrop_event` for the
single cue surface. `multisubs/layout.py::position_visual_lines` computes line
positions, fragment placements, the filled backdrop bounds, the outer shadow
envelope, and the common animation anchor.

CLI options, non-default template baselines, public Python signatures, JSON
schema version 3, SRT text/timing, cue segmentation, wrapping decisions,
output names, and retention remain unchanged. The default template and
semantic cue/word backdrop padding now use `25%` of the resolved font size so
their spacing scales with typography. Retained ASS event structure and
single-line raster appearance may change intentionally: native-box pixel
parity is not an acceptance requirement. Consistent measured padding and
placement are required, and visible differences must be recorded.

JSON `render_strategy` and preview guides must report `positioned-lines` for
box cues even with one line, retaining existing vocabulary and aggregate
semantics. Do not misreport placement mode as explicit merely because internal
text events contain coordinates.

This plan supersedes the single-line/`auto` ASS-structure preservation promises
in the completed line-height plan and static-output promises in the completed
animation plan **only for cue boxes**. Those plans remain historical records;
their completed status and delivery references do not change. Update current
PRD acceptance criteria 24 and 29 during implementation, along with any other
current statements promising a native or single-event box.

## Implementation tasks

- [x] Add focused regressions for one-line ordinary, word-enabled, and fallback
  boxes before replacing the native path.
- [x] Route every nonempty box cue through `build_visual_lines` and
  `position_visual_lines`, including motion-suppressed preview. Reuse resolved
  metrics rather than measuring separately for the background.
- [x] Audit `PositionedVisualLine.block_bounds`: distinguish the filled box
  (text bounds plus padding) from the outer shadow allowance. Count shadow once
  in the layout envelope, render it once, and verify left/right as well as
  centered anchors. Extend a private typed geometry contract only if needed;
  do not independently reconstruct bounds in the serializer.
- [x] Neutralize native box and duplicate text shadow for every box text event.
  Reuse `_append_shared_backdrop_event` for one logical cue surface. Static
  cues emit one box event; animated cues may use bounded non-overlapping
  intervals for that same surface, never one box per word or text line.
- [x] Audit drawing color/alpha and shadow tags in both static and animated
  paths. Preserve the configured effective palette and apply global opacity
  once. Keep the shared animation origin and original cue timeline through
  derived boundaries, with no new per-frame expansion.
- [x] Keep whole-line text shaping for ordinary lines; preserve existing
  fragment placements when word behavior requires them. Fallback cues use
  the same box path as ordinary cues without inventing timestamps.
- [x] Align strategy selection in `transcriber.py::_line_height_render_strategy`
  and `preview.py` guide generation with actual ASS compilation; share a small
  internal decision helper if needed to prevent the three paths drifting.
- [x] Resolve any newly exposed one-line envelope errors consistently with
  wrapping. Preserve the documented indivisible-token overflow behavior;
  do not introduce rejection of previously valid cues merely by routing them
  through the stricter positioned-line check. Keep explicit canvas validation
  and actionable `ValidationError`/`ArtifactError` boundaries intact. Do not
  silently clamp, shrink text, or fall back to a native box.
- [x] Update focused tests and intentional ASS expectations, render controlled
  fixtures, and update current documentation and delivery statuses.

## Unit and regression verification

Use `tests/test_ass.py`, `tests/test_layout.py`, `tests/test_wrapping.py`,
`tests/test_animation.py`, `tests/test_preview.py`, `tests/test_karaoke.py`, and
`tests/test_transcriber.py` for these observable contracts:

- One, two, and three lines, including unequal widths: one visible cue surface
  at any instant, no native box behind text, no duplicate visible glyphs.
- All nine anchors, asymmetric native margins, explicit coordinates, portrait
  and landscape geometry; padding in px and %, zero/nonzero shadow, `auto` and
  explicit line height. Natural height plus baseline advances determines the
  text block, with decoration allowance counted once.
- Stable text/box geometry across equivalent ordinary, word, and fallback cues;
  independent cue text/box fade, slide, and scale, short phases, word gaps, and
  progressive activation preserve their logical intervals.
- Transparent/translucent/opaque colors and 0%/partial/100% global opacity;
  changing alpha does not change bounds or accumulate dark seams.
- Literal braces, backslashes, combining marks, CJK, RTL, and emoji remain
  escaped text. Font-estimate fallback remains explicit in diagnostics.
- Width-boundary and indivisible-token cases keep wrapping and error policy;
  empty input emits no box and existing timestamp validation remains intact.
- JSON and preview agree with emitted strategy for single-line boxes and mixed
  cues; logical JSON/SRT text, count, and timing stay unchanged. Equivalent
  `outline`/`none` output and word-outline attachment remain stable.
- Event growth remains proportional to existing cue/line/word/phase boundaries;
  a static one-line ordinary cue needs one background and one text event.

## Integration and visual verification

Extend `tests/test_integration.py` and `tests/test_preview_integration.py` with
short synthetic backgrounds and controlled bundled fonts; use no WhisperX.
Capture the pre-change baseline before modifying rendering.

Render one/two/three-line boxes at 1920x1080 and 1080x1920 with left, center,
and right alignment across top/middle/bottom placement. Include Roboto regular,
a bold face, italic, accents/descenders, letter spacing, nonzero shadow, and
explicit coordinates near valid canvas boundaries. Cover a default cue and
representative `high-contrast`, `lower-third-slide`, and `word-focus` cases.

Verify measured rectangle edges and stable anchor locations within one PlayRes
pixel in controlled fixtures. Check the interior alpha away from glyphs and
antialiased edges using the existing integration-test pixel tolerance. Assert
no translucent overlap seams, clipped text, doubled shadows, or unexpected
anchor shifts. Compare preview to a motion-suppressed final frame with identical
text and representative word state, with guides disabled.

Inspect frames before/during/after cue and word transitions, including a box-only
animation, text-only animation, and missing-word fallback. Use a covering font
for complex-script visual checks and report font/shaping limitations explicitly;
the one-pixel rectangle tolerance is not a promise of exact glyph metric parity
between Pillow and libass. Record font and FFmpeg/libass versions, observed
single-line differences, and fixture timing/event counts. Keep generated media
in temporary/ignored locations and include review evidence without committing it.

## Documentation

- README: describe one measured continuous box for any line count and retained
  ASS structure; document the proportional `25%` default cue/word backdrop
  padding.
- PRD: align FR-9 and acceptance criteria 24/29 with unified boxes, preserving
  public native-position semantics and independent animation requirements.
- Architecture: update cue construction, SRT/ASS contract, layers, common
  geometry, shadow envelope, preview, and render-strategy diagnostics.
- Conventions: update only if the geometry/shadow ownership rule needs an
  explicit reusable engineering constraint. No delivery policy changes.
- Synchronize this plan, its dashboard, and the top-level catalog.

## Delivery and verification commands

Active branch: `refactor/unify-box-backdrop`, based on the updated `origin/main`
merge of PR 66. The word-outline correction is therefore already in the base;
no unrelated branch commits are being bundled.

Suggested commits:

1. `refactor: unify cue box rendering on measured geometry` — renderer, layout,
   diagnostics, focused regressions, and controlled integration coverage.
2. `docs: document unified vector box backdrops` — user/product/architecture
   contracts and final pre-PR roadmap status.

Run in the project's development environment:

~~~sh
python -m pytest tests/test_ass.py tests/test_layout.py tests/test_wrapping.py tests/test_animation.py tests/test_preview.py tests/test_karaoke.py tests/test_transcriber.py
python -m pytest -m integration tests/test_integration.py tests/test_preview_integration.py
python -m compileall multisubs
multisubs --help
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
~~~

The integration commands require FFmpeg/libass and the controlled font
prerequisites; report skips as missing evidence, not successful visual
verification. Complete package build/metadata checks required by the
[delivery gate](../../delivery.md) from a clean build output directory.

Complete implementation and verification before requesting explicit staging,
commit, push, and PR confirmation under [AGENTS.md](../../../AGENTS.md). After
confirmation, use PR title `refactor: unify cue box rendering on measured geometry`,
target `main`, and open as draft. Link this plan and report scope/exclusions,
ASS/diagnostic impact, commands actually run, visual differences, documentation,
and remaining font-measurement risks. The final documentation commit sets plan,
package, and catalog to `In review` with the task branch as delivery reference.
Push the complete branch before opening; do not add a post-open metadata commit.
After authoritative merge, mark them `Done`, record 1/1 completion, and replace
the branch reference with the merged PR link in the next status update.

## Acceptance criteria

- Every nonempty cue box uses the shared vector geometry regardless of line
  count, word behavior, fallback, or preview; no box relies on native opaque
  text borders and no visible surface is duplicated across text intervals.
- Padding, anchor, line spacing, shadow, and alpha satisfy the controlled tests;
  preview and final stable frames agree and independent animation tracks remain
  independent without moving the stable layout.
- Valid existing commands keep wrapping, plain transcript/timing, translation
  restrictions, and collision-safe artifact lifecycle. The default cue and
  word backdrop padding change to the documented proportional `25%` value;
  outline and none retain their behavior.
- Retained ASS changes and `positioned-lines` diagnostics are documented and
  covered by regression tests. Required quality checks pass and visual evidence
  substantiates the intended appearance change.

## Risks and rollback

The principal risk is the difference between measured font advances and libass
shaping; using one geometry source reduces internal disagreement but cannot
eliminate that external difference. Shadow bounds and the compatibility path for
one-line envelopes require explicit regressions before rollout. Reuse metrics
and bound event counts to limit the additional per-cue work. No new network,
cache, persistence, or migration is introduced. Roll back through a focused
revert PR; released artifacts/tags remain immutable under the delivery policy.
