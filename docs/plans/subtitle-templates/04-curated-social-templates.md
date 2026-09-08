# Curated social subtitle templates

Status: Done

Delivery: [#70](https://github.com/denilson-santos/multisubs/pull/70)

Depends on:

- [Declarative template schema](02-declarative-template-schema.md) and
  [independent animations](03-cue-animations-and-animated-templates.md), both Done.
- [Unified vector boxes](../subtitle-backdrops/00-unified-vector-box.md) and
  [multiline capacity](../subtitle-preview/00-multiline-capacity.md), both Done.

## Objective and scope

Replace the thirteen-template catalog with exactly twenty-five choices: the
preserved `default` baseline and twenty-four distinct social-video styles.
Simplify packaged JSON authoring while keeping the existing typed configuration
and ASS renderer contracts. The catalog, sparse loader, renderer validation, and
current documentation for all twenty-five choices are in place on the delivery
branch. The implementation and verification are complete; the plan was merged
through [PR #70](https://github.com/denilson-santos/multisubs/pull/70).

The twenty-five-choice catalog described by this historical plan was later
reduced to sixteen active choices in the custom-template delivery branch. The
completion evidence below remains the record for the original Plan 4 scope.

Remove these twelve files and index entries during implementation:
`clean-outline`, `social-bold`, `classic-yellow`, `newsroom`, `editorial`,
`high-contrast`, `neon-karaoke`, `cinematic-fade`, `impact-yellow`,
`lower-third-slide`, `soft-zoom`, and `word-focus` (all `.json`). Keep completed
plans as historical records. This plan supersedes their promises to retain
non-default names/visuals and require complete fields in every authored JSON;
it preserves their typed runtime, validation, font, and animation contracts.

No new fonts, dependencies, effects, CLI flags, public template-file support,
renderer backend, rounded boxes, gradients, blur, or transcription changes.
Do not remove bundled font faces merely because a preset stops using them.

Future public custom-file support and optional built-in inheritance are planned
separately in [Plan 5](05-custom-template-files.md), after this plan's delivery.
They do not expand this implementation's acceptance requirements.

## Initial visual selection — fifteen implemented choices

The following order is the new deterministic index order after `default`.
Names are filename stems, CLI choices, and JSON `name` values. Descriptions
must explain the visible treatment and intended use in concise English.

The first five additions extended the original nine-style proposal as requested:
fourteen new styles plus `default`, fifteen total. The last five rows add yellow,
green, and red palettes; all five target one line. This replaces the previous
ten-choice acceptance count without restoring any legacy preset.

| Name | Intended use and typography | Palette and decoration | Position and line capacity | Motion |
| --- | --- | --- | --- | --- |
| `studio-outline` | Talking-head tutorials; Inter Medium, 3.4%, original case | White; near-black outline 4%, no shadow | bottom-center, 1 line | Static |
| `bold-headline` | Brief hooks; Montserrat ExtraBold, 3.8%, uppercase | White; near-black outline 7%, no shadow | middle-center, 1 line | Cue text pop 120ms, fade exit 100ms; no looping emphasis |
| `podcast-panel` | Longer interview excerpts; Atkinson Hyperlegible Next Medium, 3.2%, original | White on near-black 85%-alpha cue box, padding 18%, no shadow | bottom-left, up to 2 lines | Static |
| `serif-quote` | Reflective quotes; Lora Medium Italic, 3.4%, original | Warm white #FFF8ED; near-black outline 4%, no shadow | bottom-center, up to 2 lines | Cue text fade 180ms in / 140ms out |
| `amber-word` | Explanatory clips with speech emphasis; Inter SemiBold, 3.4%, original | White, outline 5%; active word #FFD54F; no word box or shadow | bottom-center, 1 line | Active-word text highlight only |
| `mint-progress` | Sequential tips and demonstrations; Montserrat Medium, 3.3%, original | White on near-black 85%-alpha cue box, padding 15%; progressive text #A7F3D0 | bottom-center, 1 line | Progressive highlight only; no motion or shadow |
| `paper-label` | Compact editorial callouts; Roboto Medium, 3.2%, original | Near-black text #111827 on opaque warm-white #FFF8ED cue box, padding 20%, no shadow | top-left, 1 line | Matched cue text and box slide-right entrance 160ms, fade exit 120ms |
| `focus-marker` | Word-led educational captions; Atkinson Hyperlegible Next Bold, 3.4%, original | White with near-black outline 4%; active word dark #111827 on opaque amber #FFD54F word box, padding 12% | bottom-center, 1 line | Active-word text highlight and word box; no cue box, shadow, or motion |
| `soft-shadow` | Calm narration and lifestyle; Lora SemiBold upright, 3.5%, original | White, backdrop none; near-black #111827CC shared shadow color, shadow 4% | top-center, 1 line | Static |
| `golden-title` | Concise topic titles; Oswald Bold, 3.6%, uppercase | Golden yellow #FACC15; near-black outline 6%, no box or shadow | bottom-left, 1 line | Static |
| `sage-serif` | Wellness and reflective narration; Lora Regular upright, 3.4%, original | Pale green #BBF7D0; near-black outline 5%, no box or shadow | top-right, 1 line | Cue text fade 160ms in / 120ms out |
| `crimson-banner` | Strong statements and podcast takeaways; Oswald Medium, 3.3%, original | White on opaque deep-red #991B1B cue box, padding 18%, no shadow | bottom-right, 1 line | Matched cue text and box fade 140ms in / 100ms out |
| `lemon-card` | Short tips and practical reminders; Inter SemiBold, 3.2%, original | Near-black #111827 on opaque soft-yellow #FDE68A cue box, padding 20%, no shadow | top-center, 1 line | Static |
| `emerald-word` | Word-led explanations; Roboto Bold, 3.4%, original | White with near-black outline 5%; active word stays white on opaque deep-green #166534 word box, padding 12%, no shadow | bottom-right, 1 line | Active-word box only; no text highlight or motion |

Percent font sizes use render height; outline/padding/shadow sizes use font
size. Near-black means #111827, opaque unless alpha is specified. All styles
use full global opacity, zero letter spacing, natural `auto` line height, and
no unlisted decoration or animation. For outlines, animate the text track only;
for a visible cue box, animate its independent track only as specified above.
`soft-shadow` must retain `backdrop.color`: the renderer also uses it for shadow.

Start new layouts with left/right margins 10%, active vertical margin 12%,
and maximum width 100% of the available region. Middle alignment ignores
vertical margins. Top placements are optional alternatives for scenes whose
lower frame is occupied, not a universal platform safe-area guarantee.
The `default` keeps Roboto Regular 4%, white, #00000099 box with 25% padding,
zero shadow, bottom-center, L/R 18%, B 3%, max width 100%, max height 10%, and
all current inactive fields and metadata semantics after normalization.

### Height calibration and visual distinction

Choose each new template's `max_height` using bundled-font metrics through
`resolve_wrapping_metrics`, not an invented `max_lines` field. For natural
line height H, baseline advance L, and total vertical decoration D, choose a
resolved envelope E satisfying H + D <= E < H + L + D for one line, or
H + L + D <= E < H + 2L + D for two. Use existing geometry rounding and
word-decoration allowances. Record the final percentage and resolved capacity
for every fixture in the implementation evidence and exact README table.

Verify 1080x1920, 720x1280, 1080x1080, 1080x1350, and 1920x1080. Target decorated
stable height <= 6% of frame height for one line and <= 9% for two; reject
clipping during animation too. Prefer shortening into subsequent timed cues
over smaller illegible type. Keep existing long indivisible-token overflow
and timestamp-free fallback behavior; test and document their limitations.
Do not promise a fixed count with arbitrary custom fonts or CLI overrides.
The unchanged `default` is exempt from new layout thresholds.

At least two salient visual dimensions must distinguish every pair, including
`default`: typography family/weight/case, surface treatment, alignment, or
word behavior. Color or duration changes alone do not count. Inspect identical
text on identical backgrounds side by side, including stable frames and
transitions. Adjust proposed values before delivery if styles look redundant,
small, intrusive, or have poor contrast. In particular, compare `amber-word`
with `focus-marker`, and `default` with `podcast-panel`/`mint-progress`.
Also compare `golden-title` with `bold-headline` (condensed type and alignment),
`sage-serif` with `serif-quote`/`soft-shadow` (weight, outline, alignment),
`crimson-banner` with `podcast-panel` (type and alignment), `lemon-card` with
`paper-label` (type and alignment), and `emerald-word` with `focus-marker`
(type, alignment, and unchanged active text color). Recoloring alone is not
an acceptable distinction.

Use one chromatic family per added template, supported by white or near-black;
do not combine red and green or add rainbow/progressive color cycling. Keep
boxes opaque where a light/dark foreground relies on the panel for contrast.
Inspect yellow/green outlined glyphs against bright footage and red/green
surfaces against busy footage, including compressed small-screen frames.
`emerald-word` enables decoration through `word_backdrop.type=box` and the
active-word default mode, without `highlight_color` or a highlight phase;
its word box must disappear in gaps while the white text remains readable.
Verify this independently from templates with simultaneous text highlighting.

## First animated social extension — five choreographed additions

Append the following names after `emerald-word`, preserving the fifteen existing
resources and their resolved styles, including the shared box-alignment fixes.
This first extension established twenty templates (default plus nineteen new
choices) and remains implemented as the baseline for the yellow/neon additions.

These styles target TikTok, Instagram Reels, Shorts, and podcast cuts. More
elaborate means coordinated cue and word phases, a deliberate visual hierarchy,
and distinct typography, rather than additional layers covering the video.

| Name | Visual and use | Layout | Exact animation tracks |
| --- | --- | --- | --- |
| `kinetic-lime` | Fast explanations; Montserrat Bold, 3.4%, original case; white text, near-black outline 5%, active highlight #D9F99D | bottom-center, one line | cue.text: slide-up 180ms / none / fade 120ms; word.text active-word: none / highlight / none |
| `cobalt-pop` | Hooks and strong statements; Inter ExtraBold, 3.5%, uppercase; white text on opaque #1E40AF cue box, padding 18% | center, one line | cue.text and cue.backdrop: pop 180ms / none / zoom 140ms, synchronized; no word tracks |
| `coral-marker` | Spoken advice and interview cuts; Roboto SemiBold, 3.3%, original case; white text with near-black outline 4%; active dark text #111827 on opaque coral #FDA4AF word box, padding 14% | bottom-left, one line | cue.text: fade 140ms / none / fade 120ms; word.text active-word: none / highlight / none; word.backdrop active-word: fade 70ms / none / fade 70ms |
| `editorial-reveal` | Storytelling and reflective cuts; Lora SemiBold Italic, 3.4%, original case; warm white #FFF8ED with near-black outline 4% | bottom-center, one line | cue.text: zoom 200ms / none / fade 160ms; word.text progressive: fade 100ms / none / none; words reveal in speech order and remain until cue end |
| `headline-bounce` | Energetic punchlines and short takeaways; Oswald SemiBold, 3.5%, uppercase; warm yellow #FDE68A with near-black outline 6% | bottom-right, one line | cue.text: fade 120ms / none / slide-down 160ms; word.text active-word: none / bounce 420ms / none; no word box or highlight |

Track triplets mean entrance / emphasis / exit. Use only the effect names and
phase combinations accepted by `config.py`; durations equal to effect defaults
may be omitted from sparse JSON while preserving these resolved values.
An emphasis phase supports one effect: never combine highlight and bounce in
the same track. No cue-wide looping motion, flash, shake, or new easing controls.
The bounce uses the current bounded repeating implementation, not an invented
single-bounce option. Review long words and partial cycles for distraction.

All five start with L/R 10%, maximum width 90% of the remaining region, and
maximum height 6%; bottom positions use B 12%, while center has no active
vertical margin. Use auto line height, zero letter spacing and shadow, full
opacity, no cue backdrop for outlined styles, and no unlisted animations.
Resolve these candidate envelopes through the existing metrics at all five
fixture geometries. Each must derive one line; reserve space for pop overshoot,
bounce and slides within the frame and verify neighboring words do not overlap.
Adjust template size, width or durations if necessary, without changing global
defaults or inventing per-template amplitude fields. Record calibrated values.

Keep a shared vertical offset across a cue and stable fragment advances across
word intervals: progressive reveal must not recenter the visible prefix or resize
the box at every word. Single-line cue surfaces center their text internally;
the block retains its requested anchor. Check accent/descender bounds and both
side paddings, especially for Oswald and Lora.

The four word-driven additions require usable alignment in transcription and
retain existing translation rejection and plain fallback. `cobalt-pop` remains
usable with translation and untimed cues. Static preview suppresses movement
and word reveal, retaining existing representative highlight/decorations; use
animated previews or direct timed ASS renders to assess the actual choreography.
No new metadata, schema version, fonts, dependencies, renderer effects, or
migration-guide file is needed.

### Extension implementation tasks

- [x] Capture the current fifteen-template baselines, including default and the
  mint/crimson padding corrections, before adding resources.
- [x] Add the five schema-5 JSON resources with the table's resolved styles and
  append their filenames to `index.json` in the stated order.
- [x] Update exact inventory and baseline tests in `tests/test_templates.py`,
  CLI expectations, and packaging checks to twenty choices / twenty-one JSONs.
- [x] Validate inherited durations, independent disabling of each track,
  translation behavior, and missing-word fallback in existing test modules.
- [x] Render all five at the five fixture sizes on light, dark and busy
  backgrounds; inspect entrance, overshoot, midpoint, word gaps and exit with
  synthetic 80–150ms words, long words, short cues, and Portuguese accents.
- [x] Compare each addition against all nineteen other choices using identical
  captions; require two visible differences beyond color or duration. In
  particular compare kinetic-lime/amber-word, cobalt-pop/bold-headline,
  coral-marker/focus-marker, editorial-reveal/serif-quote, and
  headline-bounce/golden-title. Motion/reveal behavior may be one difference.
- [x] Add real-render regressions for balanced padding and animation containment,
  using pixel bounds rather than only checking generated ASS tags. Include
  existing mint-progress and crimson-banner to catch alignment regressions.
- [x] Update README catalog/examples, PRD counts and acceptance, architecture
  catalog description, and plan dashboards during implementation; rerun the
  verification commands below and rebuild source/wheel inventories.

The first extension acceptance required exactly five additions and twenty valid
indexed templates; its completed evidence is retained above. The yellow/neon
extension below adds five more choices while preserving those baselines.

## Yellow and neon word extension — five implemented additions

This extension adds five templates following the previous batches: two use exact
yellow #FBE003 and three use one neon accent each. All twenty-five choices are
implemented and preserve the default, prior visual baselines, and mint/crimson
alignment corrections. The five filenames follow `headline-bounce.json` in the
index. The catalog contains twenty-five choices and twenty-six JSON files
including the index.

| Name | Typography and surface | Placement | Word choreography |
| --- | --- | --- | --- |
| `yellow-pop` | Montserrat ExtraBold, 3.4%, uppercase; white text with #111827 outline 5%; active text #FBE003 | bottom-center | word.text active-word: pop 120ms / highlight / none; energetic spoken-word emphasis |
| `yellow-trace` | Inter Medium, 3.3%, original case; white on #111827 opaque cue box, padding 15%; spoken text #FBE003 | bottom-left | word.text progressive: none / highlight / none; yellow accumulates through the sentence on a stable panel |
| `neon-lime-marker` | Oswald Medium, 3.4%, original case; white with #111827 outline 4%; active text #111827 on #39FF14 opaque word box, padding 12% | bottom-center | word.text active-word: none / highlight / none; word.backdrop active-word: zoom 100ms / none / fade 70ms; compact moving marker |
| `neon-cyan-reveal` | Atkinson Hyperlegible Next Bold, 3.3%, original case; #00F5FF text with #111827 outline 5%; no box | bottom-left | word.text progressive: slide-up 120ms / none / none; cyan words enter in speech order and remain until cue end |
| `neon-magenta-pulse` | Roboto Bold, 3.4%, uppercase; #FF4FD8 text with #111827 outline 5%; no box | bottom-right | word.text active-word: none / pulse 400ms / none; bounded scale emphasis on the spoken word |

Triplets mean entrance / emphasis / exit. All unlisted tracks and phases are
inactive. No cue motion is needed. Use existing bounded pulse/zoom/pop semantics,
not new amplitudes, glow, blur, gradients, flickering, or color cycling.
The word text entrance and highlight are separate phases; do not attempt to
combine highlight with pulse in one emphasis phase. Author `highlight_color`
only for the first three styles; cyan and magenta use ordinary typography color.
In active-word mode, preserve the renderer's ordinary non-active text behavior;
do not promise isolated single-word captions. Progressive reveal keeps stable
whole-cue advances and does not recenter the visible prefix.

Start with L/R 10%, B 12%, maximum width 90% of the remaining region and maximum
height 6%, auto line height, zero letter spacing/shadow, and full opacity.
Calibrate through existing font metrics for exactly one line at all five fixture
geometries. Keep motion and word surfaces within the frame, avoid overlapping
neighbors, and preserve balanced visible box padding. Adjust size/envelope or
motion duration when necessary; keep #FBE003 exact in both yellow styles.
Neon means a saturated solid accent supported by dark contrast, not emitted
light. Inspect compressed bright and busy footage as well as dark backgrounds.

All five require aligned words for transcription, retain the current translation
restriction, and use existing plain fallback without usable word timings.
Static preview only represents the existing selected word states; assess actual
movement with timed production ASS or animated preview. No schema, renderer,
CLI flags, fonts, dependencies, retained metadata, or migration guide changes.

### Extension implementation and acceptance

- [x] Capture all twenty current resolved baselines and default ASS parity; add
  the five sparse schema-5 resources in canonical order without default-valued
  fields, unsupported properties, raw ASS tags, or new loader exceptions.
- [x] Update index, exact snapshots and catalog/CLI/package expectations in
  `tests/test_templates.py` and affected checks to 25 choices / 26 JSON files.
  Verify yellow highlight colors resolve exactly to #FBE003 and all five use
  active word tracks. Verify independent track disabling and explicit overrides.
- [x] Exercise short words (80–150ms), long words, gaps, short cues, punctuation,
  Portuguese accents, translation rejection and missing-alignment fallback with
  existing config/animation/ASS/transcriber tests. Verify phase shortening,
  progressive persistence and active marker removal during gaps.
- [x] Render the five additions at all five fixture geometries on light, dark
  and busy backgrounds (75 previews), plus timed clips. Inspect entrance,
  emphasis peaks, word transitions and exit for clipping, overlapping glyphs,
  stable alignment and balanced padding. Record render times and ASS event
  counts against identical current-template fixtures; investigate growth.
- [x] Compare against all 24 peers using identical captions and frames. Require
  two salient differences beyond hue/duration, especially yellow-pop versus
  kinetic-lime (case/weight and word pop), yellow-trace versus mint-progress
  (family and alignment), neon-lime-marker versus coral-marker (family and
  alignment/motion), cyan-reveal versus editorial-reveal (type and placement),
  and magenta-pulse versus headline-bounce (family and pulse behavior).
- [x] Run the focused and repository-wide commands below, including integration
  rendering. Rebuild and audit exactly 26 JSON resources in wheel/sdist, with
  25 unique indexed names and no obsolete files. Keep the 82-font inventory.
- [x] During implementation update README catalog/exact baselines/examples,
  PRD counts/acceptance, architecture inventory and both plan dashboards. Record
  actual evidence separately from the completed twenty-choice results.

Acceptance: exactly five additions and 25 working choices, unchanged previous
20 baselines, valid sparse/expanded equivalence, one-line capacity for all five,
exact yellow colors, distinct visible word animations, and successful real ASS
renders with no newly introduced clipping or padding regressions. The final
24 non-default styles have 22 one-line and two two-line baselines. Existing
long-token overflow and custom-override limitations still apply.

## Compact internal JSON contract

The current schema-4 `_expect_keys` requires every style/layout/track/phase
field. Deleting default-valued fields alone makes the entire catalog invalid.
Introduce internal schema 5 with a strict normalization boundary in
`multisubs/templates.py`; the renderer continues receiving complete immutable
`SubtitleConfig` values. Retained transcription JSON remains schema 3.

- Keep a strict schema-4 reader for complete definitions and regression fixtures;
  schema 5 is the only format shipped by the new catalog. Require a consistent
  index/resource version, reject unknown versions, and test both reader paths.
- Require `schema_version`, `name`, and `description`. Allow optional `style`,
  `layout`, and `animation`, and optional recognized nested fields. Omitted
  values inherit authoritative semantic defaults from `config.py`, never
  another template or a second hand-maintained default dictionary.
- Normalize recognized sparse fields into the existing semantic validator.
  Preserve the `default` font-weight input provenance special case and the
  distinction between inherited margins and explicitly supplied CLI options.
  Missing animation tracks/phases mean current inactive defaults; an enabled
  phase without duration inherits its existing effect duration.
- Require explicit `highlight_color` when text highlight is enabled. When
  disabled, omit it; reject non-null inactive highlight colors as today.
  Only motion phases accept `duration_ms`; none/highlight remain durationless.
  Null is not a generic synonym for omission; retain only previously supported
  nullable semantics. Reject wrong types, unknown fields, duplicate keys,
  invalid combinations, and unsupported effects with contextual TemplateError.
- Remove authored values equal to defaults, empty objects, inactive tracks,
  and duration overrides equal to effect defaults. Preserve every non-default
  value affecting rendering, layout, validation, timing, metadata, or subsequent
  CLI overrides. A disabled backdrop does not by itself make its color unused:
  it may supply shadow color or become active through an explicit override.
- Audit each removal from JSON through loader, config, layout, animation,
  palette resolution, and ASS compilation. Record the path, inherited value,
  consumer, and equivalence test in review evidence. Metadata (`name`,
  `description`, version, index) remains necessary even though not painted.
  Do not remove required private ASS Style columns or typed model fields.
- Canonical order: schema_version, name, description, style, layout, animation.
  Style: typography, backdrop, word_backdrop, shadow, opacity. Typography:
  font_family, font_weight, font_size, italic, letter_spacing, line_height,
  text_case, color, highlight_color. Decoration: type, color, size. Layout:
  position, margins (left/right/top/bottom), max_width, max_height. Animation:
  cue then word, text then backdrop, mode before entrance/emphasis/exit,
  type before duration_ms. Keep existing snake_case property names and units.
- Use UTF-8, two spaces, expanded nested objects, LF, final newline, canonical
  uppercase hex colors, and no comments, duplicate keys, or raw ASS tags.

The compact `default` may contain only its required identity fields if complete
semantic and output parity is proven. Do not change global defaults to compress
individual presets. Freeze expected resolved baselines in tests so later
changes to inherited defaults cause reviewable failures.

## Public compatibility

`--template` remains the selector, defaults to `default`, and offers exactly
twenty-five choices. Omitted versus explicit default retains its existing requested/
resolved identity distinction. Explicit options continue overriding individual
fields, including false/zero/none values and position overrides.

Removing twelve documented names intentionally breaks commands selecting those
names. Reject them through the existing early invalid-choice diagnostic; do
not add aliases that retain obsolete catalog entries or silently choose a
replacement. Record the breaking removal in release notes and explicitly state
that visual parity is not promised. Treat removal as a breaking change in
release planning under existing SemVer conventions; this plan does not
authorize a release or select a version number.

SRT/ASS wrapping may change for replaced presets, as intended. Preserve source
text/timings, retained metadata shape, rendering boundaries, collision-safe
outputs, retention cleanup, translation restrictions, and missing-word fallback.
Word effects still need real aligned words for transcription and remain
incompatible with translation unless all active word behavior is disabled.

## Initial implementation tasks — fifteen choices

- [x] Capture current `default` config, resolved geometry, CLI override cases,
  generated ASS, and controlled raster baselines before editing production files.
- [x] Implement schema-5 normalization with schema-4 compatibility and focused
  validation/equivalence tests; keep the existing catalog runnable in this step.
- [x] Author the fourteen new resources, normalize `default`, delete twelve old
  resources, and replace the index atomically with the fifteen-name inventory.
- [x] Calibrate heights and finalize palettes, weights, margins, durations,
  descriptions, and exact baselines using the matrix above.
- [x] Update catalog/CLI snapshots and all active references in tests, preview
  examples, packaging checks, and workflows; retain generic renderer coverage
  using explicit configs if a removed preset supplied a unique effect case.
- [x] Run semantic, output, real-render, and visual verification; compare the
  compact definitions to fully expanded equivalents, including CLI overrides.
- [x] Update current documentation and record actual results
  and synchronize plan, package dashboard, and catalog before Git delivery.

## Verification and acceptance

Use `tests/test_templates.py` for exact ordered inventory, filename/name matching,
strict JSON parsing, schema versions, immutable config, bundled faces, default
parity, sparse/expanded equivalence, missing required identity fields, invalid
optional values, and errors surfaced before probing/model loading. Check all
nested omission paths and explicit default/false/zero/none values. Include
shadow-color reuse, position/margin changes, enabling previously disabled word
or cue decoration, and duration/phase overrides in equivalence regressions.

Use existing CLI/config/layout/wrapping/ASS/animation/preview/transcriber tests
for omitted and explicit default, all twenty-four non-default choices, removed-name rejection,
word timing with gaps and short intervals, missing alignment, translation
validation, text conservation, escaping, derived line capacity, independent
tracks, and unchanged artifact schema/lifecycle. No full transcription needed.

Render every template with production ASS and FFmpeg/libass on synthetic light,
dark, and busy backgrounds at the five sizes. Use Portuguese accents,
punctuation, short/long sentences, and indivisible words; inspect font fallback
separately rather than promising full glyph coverage. Compare same-cue static
preview and stable final frames; inspect entrance, middle, word changes/gaps,
and exit for animated styles. Keep videos/contact sheets under ignored `data/`
or temporary directories. Record FFmpeg/libass/Pillow/font versions, geometry,
line capacities, timings, and findings. Skips are missing evidence.

Animated MP4 preview is currently In review on `feat/animation-preview-clip`.
It is an optional inspection convenience, not a prerequisite: use direct
production ASS rendering with synthetic typed word timings if it has not
merged into main. Do not include its unmerged commits in this implementation.
If available, its active tests/examples must use the replacement names.

### Completed local verification — twenty choices

These results include the five choreographed animated additions and establish
the local acceptance evidence for the extension.

- `python3 -m pytest -q`: 773 passed, 54 integration tests deselected.
- `python3 -m pytest -m integration tests/test_integration.py tests/test_preview_integration.py tests/test_animation.py -q`: 50 passed, including every catalog choice on 1920x1080 and 1080x1920 with bundled fonts and FFmpeg/libass.
- Filled cue and timed-word boxes use middle-row ASS anchors plus visible font
  bounds for their text lines while retaining the requested block anchor. At
  1080x1920, the reported `mint-progress` preview changed from approximately
  10px/19px to 15px/15px visible top/bottom spacing. The `crimson-banner`
  preview resolves to approximately 28px/26px left/right and 22px/20px
  top/bottom spacing while its complete box remains bottom-right.
- The initial fifteen choices rendered successfully at 720x1280, 1080x1080,
  and 1080x1350 (45 previews), with additional light and busy 1080x1920
  backgrounds (30 previews). A contact sheet and representative frames were
  inspected for contrast, placement, compact envelopes, and pairwise visual
  distinction; review artifacts remain under `/tmp` only.
- The five choreographed additions rendered at all five fixture geometries on
  light, dark, and `testsrc2` busy backgrounds (75 previews). Representative
  1080x1920 frames were checked side by side; detected stable bounds stayed
  inside the requested 10% horizontal margins and 12% bottom margin, with the
  cobalt and coral surfaces retaining visible text padding.
- `--preview-animation` produced five silent H.264 clips at 1080x1920 (90
  frames each) with the coordinated cue, word, and backdrop phases. Entrance,
  stable, partial-word, and exit frames were inspected in a contact sheet; no
  glyph or surface crossed the canvas during motion.
- Production ASS with Portuguese accents and synthetic 80–150ms word intervals
  compiled and rendered for all five additions. The event counts were 46
  (`kinetic-lime`), 8 (`cobalt-pop`), 59 (`coral-marker`), 33
  (`editorial-reveal`), and 56 (`headline-bounce`); each produced a valid
  1080x1920 H.264 render without duplicated glyphs.
- At 1080x1920, stable changed-pixel bounds were `kinetic-lime` (404,1635)–
  (674,1677), `cobalt-pop` (356,918)–(723,1001), `coral-marker`
  (102,1612)–(399,1691), `editorial-reveal` (415,1640)–(660,1685), and
  `headline-bounce` (257,1628)–(968,1681), confirming the requested anchors
  and containment.
- `ruff format --check .`, `ruff check .`, `python3 -m pyright`,
  `python3 -m compileall -q multisubs`, `multisubs --help`, and `git diff --check` all passed.
- `python3 -m build --no-isolation --wheel --sdist --outdir /tmp/multisubs-build-extension`
  and `python3 -m twine check /tmp/multisubs-build-extension/*` passed. Both artifacts
  contain exactly 26 template JSON files: the index plus the 25 indexed choices.
- The isolated build mode was attempted but could not download its pinned
  build dependency because network access is unavailable; the local no-isolation
  build supplied equivalent package and resource evidence.

### Completed local verification — yellow/neon extension

These results cover the five newly implemented word-animation templates and
the complete twenty-five-choice catalog.

- `python3 -m pytest -q`: 773 passed, 54 integration tests deselected;
  `tests/test_templates.py` contributed 88 passing checks for the complete
  ordered catalog and the five new animation definitions.
- `python3 -m pytest -m integration tests/test_integration.py
  tests/test_preview_integration.py tests/test_animation.py -q`: 50 passed.
- The five new templates rendered at all five fixture geometries on light,
  dark, and `testsrc2` backgrounds (75 static previews). Representative
  contact sheets show readable, compact, pairwise-distinct yellow, lime,
  cyan, and magenta treatments without canvas clipping.
- Production ASS with Portuguese accents and synthetic word intervals rendered
  through FFmpeg/libass for all five additions. Event counts were 38
  (`yellow-pop`), 14 (`yellow-trace`), 37 (`neon-lime-marker`), 24
  (`neon-cyan-reveal`), and 36 (`neon-magenta-pulse`); each produced a valid
  1080x1920 H.264 output.
- Stable 1080x1920 changed-pixel bounds remained inside the requested compact
  envelope: `yellow-pop` (224,1629)–(873,1684), `yellow-trace`
  (105,1625)–(694,1679), `neon-lime-marker` (315,1616)–(735,1685),
  `neon-cyan-reveal` (90,1631)–(709,1685), and `neon-magenta-pulse`
  (328,1630)–(973,1685).
- Every new template kept one-line capacity in the five geometry fixtures;
  translation validation rejected all five when their word animations were
  combined with `--translate`, and existing fallback/phase tests remained
  green.
- `python3 -m build --no-isolation --wheel --sdist
  --outdir /tmp/multisubs-build-yellow-neon` and `python3 -m twine check`
  passed. The wheel and sdist each contain exactly 26 template JSON files:
  `index.json` plus the 25 indexed choices, with no removed resources.
- `ruff format --check .`, `ruff check .`, `python3 -m pyright`,
  `python3 -m compileall -q multisubs`, `multisubs --help`, and
  `git diff --check` passed after the extension.

Run in the isolated development environment:

```sh
python -m pytest tests/test_templates.py tests/test_cli.py tests/test_config.py tests/test_layout.py tests/test_wrapping.py tests/test_ass.py tests/test_animation.py tests/test_preview.py tests/test_transcriber.py
python -m pytest -m integration tests/test_integration.py tests/test_preview_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Remove only existing build output `dist/` immediately before `python -m build`,
then run `python -m twine check dist/*`. Audit source/wheel/sdist for exactly twenty-five
indexed template resources plus index.json (twenty-six JSON files), and no obsolete
resources. Install the wheel in a clean environment outside the checkout and
exercise all catalog choices and at least one ASS render with packaged fonts.
Retain the existing 82-face/font-license inventory checks.

Acceptance requires all seven user checks: unchanged working default; exactly
twenty-four non-default templates; valid JSON and strict semantic loading; no dependency on
removed fields; successful ASS renders; clear matching names/descriptions; and
no visually redundant pairs. Additionally, twenty-two non-default baselines must have one-line
capacity and two must have two-line capacity in the defined fixture matrix,
with readable, compact, unclipped text and review evidence supporting the result.
Automated config uniqueness alone cannot establish visual distinction.

## Documentation and delivery

Update the root README catalog/count/examples/exact baselines and preview
examples, PRD template requirements and acceptance criteria, architecture
resource normalization and ASS contract, conventions' complete-key validation
rule to distinguish sparse authored resources from complete runtime config, and
the repository map in AGENTS.md. Keep delivery policy unchanged.

Suggested branch: `feat/curated-social-templates`, from updated `origin/main`
with the completed dependencies verified. Planning does not create a branch.
The implementation was delivered in these focused commits:

1. `refactor: support sparse packaged template definitions`
2. `feat!: curate social subtitle templates`
3. `docs: document curated templates and custom-template roadmap`

Draft PR: `feat!: curate social subtitle templates and simplify JSON resources`,
base `main`. Describe the removed choices in a BREAKING CHANGE note, link this
plan, list scope/exclusions, runtime and CLI impact, actual checks, visual
findings, documentation changes, and remaining limitations.

Follow [AGENTS.md](../../../AGENTS.md) and [delivery](../../delivery.md). The
implementation was delivered through [PR #70](https://github.com/denilson-santos/multisubs/pull/70).
Plan 5 now carries the active package delivery reference. After Plan 5 merges,
mark it Done, replace this package's branch with the merged PR link, and update
the package progress to 6/6.

Risks: defaults inheritance can conceal future visual drift, font metrics can
change line capacity, and removed names break saved commands. Address these
with resolved snapshots, controlled renders, and release notes for removed
names.
No new network access, private media, persisted caches, or model downloads.
Rollback the loader/catalog/docs together through a focused revert PR; retained
ASS artifacts stay usable and published tags remain immutable.

## Implementation status

All twenty-five choices, including the ten choreographed additions and the
alignment corrections, are implemented and locally verified on
`feat/curated-social-templates`. This plan is Done after the authoritative merge
signal from PR #70.
