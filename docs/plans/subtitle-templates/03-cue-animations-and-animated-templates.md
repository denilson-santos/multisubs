# Independent subtitle element animations

Status: In review

Depends on:

- [Declarative template schema](02-declarative-template-schema.md)
- [Completed karaoke contract](../karaoke-subtitles/README.md)

## Objective

Give cue text, cue backdrop, word text, and word backdrop independent entrance,
emphasis, and exit effects. Separate decoration activation, word timing mode,
and effect speed so users can enable a word box with one style option and
customize each element without affecting another.

This revision incorporates the accepted element, mode, and duration decisions
into the existing implementation on `feat/subtitle-animations`. The earlier
six-phase implementation is a tested foundation, not completion of this
revised contract. The implementation and verification are complete; authorized
Git delivery now moves the completed branch through review.

## Scope

Included:

- Four independently configured tracks: `cue.text`, `cue.backdrop`,
  `word.text`, and `word.backdrop`, each with three phases.
- `style.word_backdrop.type` with `none`, `box`, and `outline`; default
  `none`. Appearance enables a decoration and chooses its shape.
- Separate `mode` in each word track: `active-word` or `progressive`.
  The word backdrop defaults to active-word, even with emphasis none.
- Optional per-phase `duration_ms` in internal templates and public
  unit-bearing duration overrides.
- Text `highlight` emphasis, replacing karaoke-specific effect naming;
  backdrop timing does not require highlight emphasis.
- Word `float` and smooth `breathe` emphasis, alongside pulse and bounce.
- Independent cue and word decoration layers, static PNG preview,
  lossless aligned-word fallback, and reproducible rendering metadata.
- Migrate all thirteen built-in templates and the current public CLI to the
  element hierarchy, preserving the no-option default presentation.

Excluded:

- `visibility`, `target`, `both`, aggregate presets, `highlight-word`,
  `highlight-progressive`, and `box` as an animation type.
- Lists of simultaneous emphasis effects on a single element.
- User-authored template files, raw ASS input, arbitrary easing, public travel
  distance or scale controls, rotations, blur, or frame-by-frame event output.
- Video/GIF previews, model-generated effects, or translated word animation.
- New font downloads or unrelated pipeline/output-lifecycle changes.

## Current implementation and remaining work

Already present in the local branch:

- Typed cue/word entrance, emphasis, exit, and timing normalization.
- Measured word placement and native ASS vector word boxes.
- Active-word/progressive boxes, a static representative preview, and
  thirteen templates with packaged fonts.
- The cue-backdrop top-left vector anchor correction.
- Baseline verification: 683 hermetic tests and 49 integration tests passed,
  along with Ruff, Pyright, compileall, a clean build, and package checks.

Those results apply to the previous contract. The branch still uses shared
cue/word phases, `box` emphasis, and fixed public durations. The tasks below
must be completed and verified for the new contract; do not report the
baseline counts as verification of element independence or duration overrides.

## Canonical internal template

Use internal resource schema version 4. This version is independent of the
retained transcription JSON version. Every template explicitly declares all
four tracks and every phase; only applicable phase durations may be omitted
to inherit the effect defaults.

~~~json
{
  "schema_version": 4,
  "name": "word-focus",
  "description": "Active yellow word decoration with independent text and backdrop effects.",
  "style": {
    "typography": {
      "font_family": "Atkinson Hyperlegible Next",
      "font_weight": "bold",
      "font_size": "4.5%",
      "italic": false,
      "letter_spacing": "0px",
      "line_height": "auto",
      "text_case": "original",
      "color": "#FFFFFF",
      "highlight_color": "#111827"
    },
    "backdrop": {
      "type": "box",
      "color": "#111827D9",
      "size": "8%"
    },
    "word_backdrop": {
      "type": "box",
      "color": "#FFD54F",
      "size": "12%"
    },
    "shadow": {
      "size": "0px"
    },
    "opacity": "100%"
  },
  "layout": {
    "position": "bottom-center",
    "margins": {
      "left": "10%",
      "right": "10%",
      "top": "0%",
      "bottom": "3%"
    },
    "max_width": "100%",
    "max_height": "18%"
  },
  "animation": {
    "cue": {
      "text": {
        "entrance": {"type": "fade", "duration_ms": 160},
        "emphasis": {"type": "none"},
        "exit": {"type": "fade", "duration_ms": 120}
      },
      "backdrop": {
        "entrance": {"type": "fade", "duration_ms": 160},
        "emphasis": {"type": "none"},
        "exit": {"type": "fade", "duration_ms": 120}
      }
    },
    "word": {
      "text": {
        "mode": "active-word",
        "entrance": {"type": "pop", "duration_ms": 160},
        "emphasis": {"type": "highlight"},
        "exit": {"type": "none"}
      },
      "backdrop": {
        "mode": "active-word",
        "entrance": {"type": "fade", "duration_ms": 100},
        "emphasis": {"type": "none"},
        "exit": {"type": "fade", "duration_ms": 100}
      }
    }
  }
}
~~~

The paths identify the elements. No separate target selector is needed.
Typography retains normal and highlight text colors. Word backdrop retains
decoration color and size, where size means box padding or glyph-outline
thickness, resolved from font size for percentages.

The cue backdrop follows the cue interval and needs no mode. The word backdrop
is disabled only by its style type. Setting that type to box or outline
activates the selected word timing policy, even when all its phases are none.
Without any overrides, that policy is active-word. Never display all word
decorations merely because emphasis is none.

Inactive backdrop tracks may retain valid effects, modes, and durations.
Their configuration is validated but they generate no events and do not by
themselves require alignment or block translation.

## Timing and phase semantics

### Word intervals

Clip aligned starts/ends to the logical cue and retain centisecond
quantization. Cap overlapping active-word ends at the next aligned start;
do not invent nonzero durations for empty aligned intervals.

For word backdrop:

| Mode | Entrance starts | Exit ends | With all phases none |
| --- | --- | --- | --- |
| active-word | Effective word start | Effective word end | Decoration appears only during that word; pauses remain undecorated. |
| progressive | Effective word start | Cue end | Decorations accumulate and disappear at cue end. |

A word from 500 to 1000 ms in a cue ending at 3000 ms, with 100 ms entrance
and exit fades, uses 500–600/900–1000 ms in active-word and
500–600/2900–3000 ms in progressive. A fade entrance does not automatically
supply an exit fade; exit none removes the decoration immediately at its
mode-defined end.

Text mode controls highlight persistence and the interval for word-local
motion. Preserve the readable baseline: entrance none leaves future words
visible normally; emphasis none does not recolor them; exit none leaves text
visible after its active interval. A selected entrance hides text until word
start and a selected exit removes it at the selected interval end. This
distinguishes always-readable text from the explicitly enabled timed decoration.

Use active-word as the default on both word tracks. `neon-karaoke` explicitly
selects progressive on word.text. Modes are independently overridable.

### Effect types

| Scope/element | Entrance | Emphasis | Exit |
| --- | --- | --- | --- |
| cue.text and cue.backdrop | none, fade, slide-up/down/left/right, pop, zoom | none, pulse, bounce, float, shake, flash, breathe | none, fade, slide-up/down/left/right, zoom |
| word.text | none, fade, slide-up/down, pop, zoom | none, highlight, pulse, bounce, float, breathe | none, fade, slide-up/down, zoom |
| word.backdrop | none, fade, slide-up/down, pop, zoom | none, pulse, bounce, float, breathe | none, fade, slide-up/down, zoom |

Highlight changes text color according to word.text.mode. It is not a motion
cycle and does not accept duration. Word-backdrop visibility is already owned
by its style activation and mode, so it needs no highlight effect.

Fade is an entrance/exit transition; breathe is a repeating smooth opacity
change during emphasis. Pop remains entrance-only. Reject unsupported
phase/type combinations with actionable validation errors.

Retain current effect geometry in config.py: cue slides 75% of font size,
word slides 35%, pop 76% → 112% → 100%, zoom 88% → 100% on entrance,
pulse peak 106% for cues and 108% for words, bounce distance 20%, float 12%.
Scale pop peak timing by its normalized duration, rather than retaining an
absolute peak timestamp when the user changes speed.

### Durations and precedence

- CLI accepts explicit positive durations such as `150ms` or `0.15s`.
  Normalize to integer milliseconds with Decimal; require whole-millisecond
  precision and a 10–5000 ms range. Reject bare numbers, zero, negatives,
  non-finite values, booleans, and unsupported units.
- Templates accept optional integer `duration_ms` in the same range.
- None and highlight accept no explicit duration. Resolved internal none
  phases may store 0 ms, but resource JSON must omit that field.
- Precedence is explicit CLI duration, then applicable template duration,
  then the selected effect's config.py default.
- A duration-only CLI override customizes the inherited effect.
- Changing an effect type uses that type's default duration unless CLI also
  supplies one. A template duration belongs to the template's selected effect,
  not an unrelated replacement effect.
- Explicit none discards an inherited duration; explicit none plus an explicit
  duration is an error. Unsupported duration values are still errors on a
  disabled decoration track.

Entrance/exit duration is the total transition time. Entrance and exit take
priority; shorten both proportionally when their sum exceeds the available
interval. Never extend cue/word timestamps. Preview does not simulate these
transitions.

For repeating emphasis such as pulse, float, and breathe, duration is one
cycle. Repeat complete cycles within the remaining interval and normalize a
last partial cycle to finish at the stable state before exit. Bounce, shake,
and flash also use deterministic cycles. If no stable interval remains, omit
emphasis motion. Highlight follows word timing and has no cycle duration.

Existing defaults remain the baseline: cue entrance fade 160 ms and
slide/pop/zoom 220 ms; cue exit fade 120 ms, slides 180 ms, zoom 160 ms;
word entrance fade 100 ms, slides/zoom 140 ms, pop 160 ms; word exit fade/zoom
100 ms and slides 120 ms. Cue emphasis uses pulse/bounce 600 ms, float
900 ms, shake 400 ms, flash 500 ms. Word pulse/bounce use 240 ms.
New suggested defaults: word float 600 ms, cue breathe 1200 ms, word breathe
600 ms, with breathe reducing opacity to 65% and smoothly returning.
These new numeric choices are implementation defaults, not externally sourced
product requirements; validate their representative renders.

Cycle event count depends on interval length and configured cycle duration.
Replace the previous constant-cycle assertion with a tested bound proportional
to words, visual lines, and quantized cycle boundaries. Never emit per-frame
events. The 10 ms lower bound and cue-duration limits bound normal expansion;
reject pathological external inputs with an actionable event-budget error
rather than silently dropping effects.

## CLI contract

Expose the following pattern for each of the four tracks:

~~~text
--animation-cue-text-entrance TYPE
--animation-cue-text-entrance-duration DURATION
--animation-cue-text-emphasis TYPE
--animation-cue-text-emphasis-duration DURATION
--animation-cue-text-exit TYPE
--animation-cue-text-exit-duration DURATION
~~~

Replace `cue-text` with `cue-backdrop`, `word-text`, and `word-backdrop`
for their independently validated phase options. Also expose:

~~~text
--animation-word-text-mode {active-word,progressive}
--animation-word-backdrop-mode {active-word,progressive}
--animation-word-text-highlight-color COLOR
--word-backdrop {none,outline,box}
--word-backdrop-color COLOR
--word-backdrop-size LENGTH
~~~

Keep cue `--backdrop`, color, and size as style controls. Word-backdrop
defaults are none, #111827E6, and 12%. Explicit mode or phase settings do not
implicitly enable a decoration.

Examples:

~~~bash
multisubs -i video.mp4 --word-backdrop box
multisubs -i video.mp4 --word-backdrop box --animation-word-backdrop-mode progressive
multisubs -i video.mp4 --word-backdrop box --animation-word-text-entrance pop --animation-word-backdrop-entrance fade --animation-word-backdrop-entrance-duration 150ms
multisubs -i video.mp4 --word-backdrop box --animation-word-backdrop-emphasis pulse --animation-word-backdrop-emphasis-duration 0.4s
multisubs -i video.mp4 --template neon-karaoke --animation-word-text-emphasis none
~~~

Reject removed karaoke options and intermediate shared-track animation options
without aliases or argparse prefix abbreviations. Put their exact replacement
mapping in PR/release notes; README documents only the final supported options.

## Rendering and module ownership

- models.py: immutable four-track configuration, typed phases, independent
  word modes, word backdrop kind, and effective-enabled predicates.
- config.py: scalar defaults, duration parsing, type expansion, exact override
  precedence, and cross-field validation. No renderer code in CLI/templates.
- templates.py: strict schema-4 decoding, optional applicable duration fields,
  exact catalog validation, and semantic compilation through config.py.
- animation.py: mode-defined intervals, cycle boundaries, phase fitting, and
  sampling from logical timelines. No I/O or transcript parsing.
- layout.py and text_measurement.py: shared measured fragment positions and
  decoration bounds; account for enabled word decorations in envelope checks.
- ass.py: independent event track identity, safe tags, palette composition,
  vector boxes, glyph outlines, and correct layer ownership.
- preview.py: independently selected representative word.text/word.backdrop
  states, suppressing all movement and transitions.
- transcriber.py: effective alignment requirements and resolved diagnostics.
- cli.py: explicit flag presence and user-facing errors before probing/loading.

Cue text state composes with word text state. Cue backdrop has its own cue
timeline, and word backdrop has its own selected word interval. Do not
implicitly apply text movement or opacity to either decoration. Independent
effects may intentionally separate elements while moving; their stable
geometry must remain aligned. Migrate formerly shared cue effects onto both
cue tracks where the template previously moved both elements.

Use layer 0 for cue decoration, layer 1 for word decoration, and layer 2 for
visible text. Vector boxes use local top-left drawing coordinates. Outline
means the glyph contour, not the border of a rectangular box. Render outline
layers with transparent glyph interiors so text is drawn only once.

When cue and word outlines coexist, the active word outline replaces the cue
outline for that word; restore it when the word decoration becomes inactive.
Test this with alpha and different animations to avoid doubled outlines or
glyph ghosts. Shadow keeps its existing cue-decoration ownership.

Every event contains at most one position/move tag, retains the source logical
timeline, and samples the appropriate track without restarting at word, line,
or cycle boundaries. Maintain stable wrapping and exact escaping.

## Preview, fallback, and retained output

Preview remains one PNG. Suppress all track motion and transitions, using
stable geometry and effective opacity. Select the first displayed word for
active-word, or the first half rounded up for progressive, independently for
text highlight and enabled word decoration. Disabled decoration never appears.

Any enabled word decoration requires alignment even when all of its phases
are none. Disabled decoration with stored effects requires none. Mode alone
on otherwise static word text does not require alignment. Reject translation
only when an effective word behavior requires timestamps.

Incomplete or lossy word mappings suppress word-local behavior for the cue and
render its normal text/cue decoration with cue animations. Keep one aggregate
warning without transcript contents and accurate fallback counts.

Keep the retained transcription schema at 3 for this unreleased Plan 3:
version 3 is already the planned public replacement for released schema 2.
Record the four resolved tracks under metadata.rendering.animation, with
word modes, configured phase durations, effective activation, and per-track
shortening diagnostics. Record canonical highlight and decoration colors in
rendering style/palette diagnostics. No raw ASS strings, local font paths,
template internals, or legacy effects.karaoke aliases.

Internal template version 4 does not imply retained JSON version 4. Re-evaluate
only if repository evidence shows the intermediate retained schema 3 has
already been published before delivery.

## Template migration

Keep all thirteen names and current font/layout baselines.

- default and the other static templates: all phases none, word backdrop none,
  word modes active-word.
- neon-karaoke: word.text highlight with progressive mode, word backdrop none.
- cinematic-fade: preserve its 220/180 ms fades on cue text and cue backdrop.
- impact-yellow: preserve cue pop/fade and word.text bounce.
- lower-third-slide: preserve cue slide-right/fade on both cue tracks.
- soft-zoom: preserve cue zoom/float/fade with the new documented cycle semantics.
- word-focus: use the canonical example above: active word box, text pop,
  independent text highlight and word-box fades.

Test exact default equivalence against config.py and all resource inventory
rules. Retain previous static reference renders; capture new references only
for intentionally revised animated behavior.

## Implementation tasks

The earlier implementation remains preserved as the foundation. The unchecked
items below refer specifically to this revision:

- [x] Add four-track models, typed word-backdrop kind, and mode ownership.
- [x] Parse and validate public durations and per-effect inheritance.
- [x] Replace shared CLI options with independent track options.
- [x] Migrate the strict catalog and all thirteen resources to schema 4.
- [x] Normalize independent mode intervals, proportional transitions, scaled
  pop peaks, and bounded repeating emphasis cycles.
- [x] Add word float and cue/word breathe.
- [x] Render independent cue/text/word-decoration layers, including outlines.
- [x] Preserve word-focus vector alignment and add regressions for distinct
  text/backdrop effects, alpha, and outline replacement.
- [x] Update preview for independent modes and disabled decorations.
- [x] Update alignment/translation checks and per-track retained diagnostics.
- [x] Update README, PRD, architecture, and conventions to the delivered contract.
- [x] Run focused, hermetic, integration, and clean package verification.
- [ ] During authorized Git delivery, prepare release notes, move the plan and
  package to In review, and push before opening the draft PR.

## Verification and acceptance criteria

Configuration and CLI tests must prove independent overrides on all twelve
phases, correct mode/default ownership, invalid duration/type errors,
template/default precedence, and absence of legacy flag abbreviations.

Timing tests must cover both modes, pauses, overlaps, zero-length words,
one-centisecond intervals, short entrance/exit fitting, repeated cycles, and
custom pop peak placement. Assert the 500–1000/3000 ms example numerically.
Emphasis none must never disable an enabled word decoration.

ASS/libass tests must compare independent text pop/backdrop fade, independent
cue effects, box and glyph-outline decoration, outline replacement, alpha,
two-line cues, native and explicit anchors, 16:9 and 9:16, and mixed text and
backdrop modes. Compare frames before/during/after aligned words and at cue end.
No duplicate glyphs, restarted motion, invalid placements, or invented timing.

Preview tests must prove first-word/half-cue selection independently for the
two word tracks without generating transition tags or importing model runtime.

Preserve SRT text/timestamps, JSON original transcription, artifact retention,
collision behavior, font providers, and ffmpeg media selection. Verify
configured durations remain reproducible while shortened intervals are
diagnosed rather than silently changing the request.

Run focused tests as the implementation progresses, then:

~~~text
python -m pytest
python -m pytest -m integration
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
rm -rf dist
python -m build
python -m twine check dist/*
git diff --check
~~~

Completed local verification:

- Ruff formatting/checks and Pyright passed.
- Hermetic suite: 695 passed, 49 deselected.
- FFmpeg/libass integration suite: 49 passed, 695 deselected.
- Compile and CLI-help smoke checks passed.
- A clean build produced the sdist and wheel; both passed Twine checks.
- The wheel installed outside the checkout, exposed all thirteen templates,
  and rendered a `word-focus` preview through FFmpeg/libass.

Before each build remove only the validated project dist directory. Audit
wheel/sdist inventory and verify the installed wheel from outside the checkout,
including previews for the new element configuration. Do not run routine full
WhisperX transcription or commit generated media.

## Documentation and delivery

README must contain only supported features, exact defaults, duration units,
phase/type choices, independent mode recipes, preview behavior, and relevant
limitations. Update PRD activation and timing requirements, architecture data
contracts and layer composition, and conventions for duration/cycle bounds.
Do not create CHANGELOG.md.

Use the existing task branch `feat/subtitle-animations`, preserving all local
foundation changes. Plan 2 remains completed history and is not retroactively
rewritten to the new schema.

Suggested focused commits after explicit delivery authorization:

1. `refactor: separate subtitle animation tracks by element`
2. `feat: add configurable animation durations and word modes`
3. `feat: render independent subtitle decorations and effects`
4. `feat!: expose element animation controls and migrate templates`
5. `docs: document independent subtitle animations`

Draft PR against main:
`feat!: add independent subtitle element animations and timing controls`.

The PR must link Plans 2 and 3, describe breaking CLI/schema changes, document
actual verification and renderer limits, and include representative visual
evidence without committing generated files. This final pre-PR documentation
commit moves the plan and package to In review while retaining the task branch
as the delivery reference.

Only after an authoritative merge signal mark the plan/package Done and
replace the branch reference with the merged PR link. The accumulated breaking
changes require a major release, expected v4.0.0. Version bump, tag, merge, and
release publication require their own user authorization and delivery checks.
Recover published changes through a new fix/revert release; never move a tag.
