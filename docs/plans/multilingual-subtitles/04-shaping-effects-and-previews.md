# Preserve shaping and bidirectional order in effects and previews

Status: Planned

Depends on: [Plan 1](01-font-coverage-and-metrics.md),
[Plan 2](02-text-and-alignment-mapping.md), and
[Plan 3](03-linguistic-cues-and-timing.md).
Animated preview integration additionally requires the availability check in the
[dashboard](README.md#relationship-to-existing-plans).

## Objective and scope

Ensure the renderer does not destroy valid text shaping by placing logical
fragments independently from left to right. Apply the same font, grouping, and
effect-capability decision to final subtitles, static previews, and animation
previews. Test suspected RTL/Indic failures before labeling them confirmed.

This increment keeps FFmpeg/libass authoritative. It does not introduce a
second video renderer, reverse Unicode strings manually, or promise arbitrary
per-word motion on every complex writing system.

## Rendering contract

Use verified positioned groups for scripts/effects whose rendered geometry is
proven safe. For shaping-sensitive or bidirectional lines, prefer one complete
logical line per text event so libass retains shaping context and visual order.
Keep explicit line-height positioning between whole lines, and preserve cue
outlines/one shared backdrop using the same resolved line geometry.

Evaluate full-line interval events with trusted color overrides for highlighting
first. They must pass shaping/ligature and mixed-direction comparisons; ASS
color tags are not automatically proof that shaping remains intact. Word boxes
require verified visual group bounds, not cumulative logical prefix widths.

When the requested word-level motion, highlighting, or decoration cannot be
rendered safely, suppress both word tracks for that cue and render the full
text with safe cue-level styling/animation. Emit one aggregate warning and an
additive fallback reason such as `unsupported-word-shaping`. This is an explicit
capability limitation, not evidence that animated RTL is fixed. If even the
static full-line path lacks required font/shaping support, use Plan 1's
actionable error behavior instead of emitting corrupt text.

## Ordered implementation tasks

- [ ] Add controlled Arabic, Persian, Urdu, Hebrew, Hindi, Telugu, and Malayalam
  render fixtures, including Latin numbers, punctuation, parentheses, and mixed
  directional runs. Establish reference full-line libass masks first.
- [ ] Introduce an internal renderer capability result per cue/line based on
  actual content, font/shaping support, requested effects, and group mapping.
  Do not use language code alone as an allowlist for safe fragments.
- [ ] Audit `_position_line_fragments` in `layout.py`: its prefix-width formula
  advances in logical order and is not a bidirectional visual-layout algorithm.
  Restrict it to the tested safe path or replace it with proven visual run
  information from the selected backend; never solve RTL with string reversal.
- [ ] Audit `ass.py` positioned word text, fragmented outlines, word backdrops,
  full-line interval serialization, and static fallback. Ensure the selected
  path preserves ligatures, joins, combining marks, and stable line geometry.
- [ ] Keep glyph/outline motion synchronized and avoid duplicate text layers
  when suppressing word effects. Apply global opacity once and preserve normal
  color in gaps. Respect cue phase origin through split events and line events.
- [ ] Compile literal text through existing ASS escaping. Test braces,
  backslashes, commas, RTL controls, and separators; generated overrides remain
  separate trusted compiler data.
- [ ] Record actual renderer strategy and word fallback reasons in JSON and
  diagnostics before serialization. A font fallback is not a timing fallback;
  report them separately and count each affected cue only once per category.
- [ ] Update `_preview_timing_units`, `_build_preview_word_cue`,
  `build_simulated_karaoke_cue`, and preview text preparation to reuse source
  groups and legal boundaries. Remove duplicate CJK/grapheme token heuristics.
- [ ] Keep `--lang` ignored as a speech option in previews. Infer only script
  information from sample text and use a deterministic generic locale where
  ambiguous; do not add model-based detection. Production uses the resolved
  output language. Document that ambiguous Han-only preview text cannot prove
  the same language-specific grouping without that language context.
- [ ] Preserve static preview representative states (first active group or
  progressive half) and the animated preview's exact duration, lead/tail,
  frozen frame, no audio, 30 fps, and simulated timing label. Simulation uses
  groups, but remains isolated from real speech timing and its fallback rules.
- [ ] Make previews apply the same shaping fallback as production. Warn outside
  the image/video rather than adding mandatory diagnostic overlays to user
  media. Remove corresponding Plan 0 `xfail` marks.

## Verification and acceptance

For each controlled font, compare plain full-line reference versus highlighted
line at several intervals. Measure glyph geometry independently of color so
expected highlights do not conceal misplaced letters. Check Arabic joining,
Indic conjuncts/marks, Hebrew and mixed-number visual order, stable line
positions, and backdrop alignment. A static fallback must match the reference
text geometry and contain no residual word motion, highlight, or boxes.

Exercise active-word/progressive combinations, word outlines and boxes, cue
motion, nonzero letter spacing, explicit line height, opacity, native anchors,
and custom envelopes. When a requested spacing/effect combination cannot be
shaped safely, test its declared fallback instead of asserting unsupported
visual output is correct. No full cross-product is needed; use representative
pairwise combinations plus every confirmed regression.

Acceptance: safe effects demonstrably preserve rendering; unsafe word effects
use legible full-line text with exact fallback metadata. PNG, simulated MP4,
and production agree on font and capability for identical text/context; no
preview imports WhisperX/PyTorch. Group-based simulation conserves the existing
centisecond timeline and rejects impossible durations without losing text.

```sh
python -m pytest tests/test_layout.py tests/test_ass.py tests/test_animation.py tests/test_karaoke.py tests/test_preview.py tests/test_cli.py tests/test_subtitler.py
python -m pytest -m integration tests/test_integration.py tests/test_karaoke.py tests/test_preview_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Record versions and exact fonts for every script. Tests skipped because a font
or shaper is missing cannot establish support for that configuration.

## Documentation and delivery

Update README supported presentation/fallback limitations and preview timing;
PRD FR-16/FR-17/FR-18 to distinguish group-based simulation, real aligned
groups, and unsupported word-effect fallback; architecture renderer strategy,
bidirectional text, preview flow, and JSON; conventions for shaping-safe tests.
When implemented, synchronize the preview dashboard with a prospective link
to this plan without changing its merge status absent authoritative evidence.

Suggested branch: `fix/shaping-safe-subtitle-effects`.
Suggested commits: `fix: preserve shaping in subtitle effect rendering`,
`fix: share multilingual groups with subtitle previews`,
`docs: document script-aware effect capabilities`.
Draft PR title: `fix: preserve multilingual shaping in subtitles and previews`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy).

Main risks are shaping changes across override runs, ambiguous mixed-direction
group bounds, inconsistent preview locale, and event expansion. Keep full-line
fallback and current event budgets. Roll back through a scoped revert; never
restore unsafe positioned effects merely to hide a fallback warning.
