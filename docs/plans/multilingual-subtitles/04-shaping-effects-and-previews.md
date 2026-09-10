# Preserve shaping and bidirectional order in effects and previews

Status: In review

Delivery branch: `fix/shaping-safe-subtitle-effects`.

Depends on: [Plan 1](01-font-coverage-and-metrics.md),
[Plan 2](02-text-and-alignment-mapping.md), and
[Plan 3](03-linguistic-cues-and-timing.md).
Animated preview integration additionally requires the availability check in the
[dashboard](README.md#relationship-to-existing-plans).

## Objective and scope

Ensure the renderer does not destroy valid text shaping by placing logical
fragments independently from left to right. Apply the same font, boundary
preferences, effect-unit contract, and effect-capability decision to final
subtitles, static previews, and animation previews. Test suspected RTL/Indic
failures before labeling them confirmed.

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

- [x] Add controlled Arabic, Persian, Urdu, Hebrew, Hindi, Telugu, and Malayalam
  render fixtures, including Latin numbers, punctuation, parentheses, and mixed
  directional runs. Establish reference full-line libass masks first.
- [x] Introduce an internal renderer capability result per cue/line based on
  actual content, font/shaping support, requested effects, and group mapping.
  Do not use language code alone as an allowlist for safe fragments.
- [x] Audit `_position_line_fragments` in `layout.py`: its prefix-width formula
  advances in logical order and is not a bidirectional visual-layout algorithm.
  Restrict it to the tested safe path or replace it with proven visual run
  information from the selected backend; never solve RTL with string reversal.
- [x] Audit `ass.py` positioned word text, fragmented outlines, word backdrops,
  full-line interval serialization, and static fallback. Ensure the selected
  path preserves ligatures, joins, combining marks, and stable line geometry.
- [x] Keep glyph/outline motion synchronized and avoid duplicate text layers
  when suppressing word effects. Apply global opacity once and preserve normal
  color in gaps. Respect cue phase origin through split events and line events.
- [x] Compile literal text through existing ASS escaping. Test braces,
  backslashes, commas, RTL controls, and separators; generated overrides remain
  separate trusted compiler data.
- [x] Record actual renderer strategy and word fallback reasons in JSON and
  diagnostics before serialization. A font fallback is not a timing fallback;
  report them separately and count each affected cue only once per category.
- [x] Update `_preview_timing_units`, `_build_preview_word_cue`,
  `build_simulated_karaoke_cue`, and preview text preparation to reuse Plan 3's
  boundary and effect-unit adapters. Linguistic groups select representative
  fitting content; script-appropriate simulated units drive effects without
  pretending to be real alignment records. Remove duplicate ad hoc heuristics.
- [x] Keep `--lang` ignored as a speech option in previews. Infer only script
  information from sample text and use a deterministic generic locale where
  ambiguous; do not add model-based detection. Production uses the resolved
  output language. Document that ambiguous Han-only preview text cannot prove
  the same language-specific grouping without that language context.
- [x] Preserve static preview representative states (first active effect unit or
  progressive half) and the animated preview's exact duration, lead/tail,
  frozen frame, no audio, 30 fps, and simulated timing label. Simulation uses
  the explicit preview effect units, but remains isolated from real speech
  timing and its fallback rules.
- [x] Make previews apply the same shaping fallback as production. Warn outside
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
preview imports WhisperX/PyTorch. Effect-unit simulation conserves the existing
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

Automated verification completed locally on 2026-09-10:

- Focused hermetic suite: 437 passed, 12 deselected.
- Real FFmpeg/libass suite covering production, karaoke, preview, and
  multilingual paths: 55 passed, 26 deselected. The new shaping comparisons
  used DejaVu Sans Book from `fonts-dejavu-core` with SHA-256
  `690243adfefe0ce154b547db6205794bd30ac4277275179517a90994f4980648`
  for Arabic, Persian, Urdu, and Hebrew; FreeSans Regular with SHA-256
  `b59dd5eeab73f77897ae0144a6b443a004efa6a90a5e1a5b550ea28978cd38e8`
  for Hindi and Malayalam; and Nirmala UI Regular with SHA-256
  `ad02cdfc06e144ac45f318e8e5a64cbe04c7479d4beb91d25f5a319a466b1767`
  for Telugu, under FFmpeg 4.4.2. The existing Japanese comparison used
  WenQuanYi Zen Hei Regular 0.9.45-8 with its recorded hash.
- Full hermetic suite: 986 passed, 63 integration tests deselected by default.
- `compileall`, `multisubs --help`, Ruff format/lint, Pyright, and
  `git diff --check`: passed.

## Documentation and delivery

Update README supported presentation/fallback limitations and preview timing;
PRD FR-16/FR-17/FR-18 to distinguish simulated effect units, real alignment
records, linguistic boundary groups, and unsupported word-effect fallback;
architecture renderer strategy,
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
