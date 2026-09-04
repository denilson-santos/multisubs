# Cue animations and animated templates

Status: Planned

Depends on:

- [Declarative template schema](02-declarative-template-schema.md)
- [Completed karaoke contract](../karaoke-subtitles/README.md)

## Objective

Add a bounded subtitle-animation system with independently selectable cue
entrance, cue exit, and word animation; migrate karaoke into that unified
model; and add five useful templates that exercise motion without making it
mandatory.

This increment intentionally breaks the karaoke-specific CLI and retained
rendering-metadata contract. Consistency takes priority over aliases: the old
karaoke options are removed, and the next release after this plan must be a
major SemVer release.

## Scope

Included:

- Add cue entrance types `none`, `fade`, `slide-up`, `slide-down`,
  `slide-left`, `slide-right`, `pop`, and `zoom`.
- Add cue exit types `none`, `fade`, `slide-up`, `slide-down`, `slide-left`,
  `slide-right`, and `zoom`.
- Represent karaoke as word animation type `karaoke`, alongside `none`.
- Expose separate semantic flags for cue entrance, cue exit, word animation,
  word mode, and word highlight color.
- Remove `--karaoke`, `--no-karaoke`, `--karaoke-mode`, and
  `--karaoke-highlight-color` without compatibility aliases.
- Let every animation be selected manually without requiring a template.
- Compile cue-relative fade, motion, and scale through trusted ASS tags while
  preserving escaped transcript text.
- Keep animation continuous across word intervals, explicit line-height
  events, multiple visual lines, and shared vector backdrops.
- Keep preview as one static PNG: cue animation at its stable final state and
  word animation in its documented representative state.
- Add `cinematic-fade`, `impact-yellow`, `lower-third-slide`, `soft-zoom`, and
  `word-focus` using only bundled fonts.
- Replace retained rendering metadata with a versioned unified `animation`
  branch.

Excluded:

- User-authored template JSON or animation files.
- Raw ASS tags, arbitrary expressions, custom easing curves, animation chains,
  per-frame rendering, or executable hooks.
- Public duration, distance, scale, overshoot, or easing tuning in the first
  release.
- Per-line, per-glyph, bounce, shake, typewriter, rotation, blur, color-cycle,
  or backdrop-only animation.
- Audio-reactive or model-generated motion.
- Video/GIF preview or simulated timing inside the PNG preview.
- A compatibility period for removed karaoke flags or retained-JSON aliases.

## Decisions and constraints

### Canonical animation model

Templates and the resolved runtime use the same semantic hierarchy:

~~~json
{
  "animation": {
    "cue": {
      "entrance": {
        "type": "pop",
        "duration_ms": 220
      },
      "exit": {
        "type": "fade",
        "duration_ms": 100
      }
    },
    "word": {
      "type": "karaoke",
      "mode": "active-word"
    }
  }
}
~~~

There is no `cue.preset`. Entrance and exit are independent phases, and word
animation follows the same `type` convention. A `none` phase contains only its
type. Type-specific values such as duration, distance, scale, and overshoot are
validated only for the types that use them.

Karaoke normal and highlight colors remain style values under
`style.typography.color` and `style.typography.highlight_color`. The animation
branch identifies behavior and mode; it does not duplicate palette ownership.
Shadow remains a sibling of typography and backdrop under `style`.

### Public animation contract

Expose these exact options:

~~~text
--animation-entrance {none,fade,slide-up,slide-down,slide-left,slide-right,pop,zoom}
--animation-exit {none,fade,slide-up,slide-down,slide-left,slide-right,zoom}
--animation-word {none,karaoke}
--animation-word-mode {progressive,active-word}
--animation-word-highlight-color COLOR
~~~

Configuration composition is leaf-oriented:

1. Resolve the selected template, or `default` when omitted.
2. Apply each explicitly supplied animation flag only to its corresponding
   phase or field.
3. Expand selected public types into their fixed typed defaults.
4. Validate the complete style, layout, and animation configuration once.

Omitted flags inherit the template. Explicit `none` disables only its scope:
entrance, exit, or word animation. For example, disabling the word animation
on `word-focus` retains its cue fade; disabling its entrance and exit retains
active-word highlighting.

`--animation-word-mode` and `--animation-word-highlight-color` are valid only
when the final word animation type is `karaoke`. The highlight option updates
`style.typography.highlight_color` through the normal color validator. Karaoke
translation restrictions apply to the final composed word animation. Cue
animation remains valid with transcription or translation.

The four removed karaoke options must fail as unknown arguments. README shows
only the new interface. Release notes or a changelog record this migration:

| Removed option | Replacement |
| --- | --- |
| `--karaoke` | `--animation-word karaoke` |
| `--no-karaoke` | `--animation-word none` |
| `--karaoke-mode MODE` | `--animation-word-mode MODE` |
| `--karaoke-highlight-color COLOR` | `--animation-word-highlight-color COLOR` |

### Fixed animation type defaults

Public flags select semantic types, not renderer syntax or tuning knobs. Each
type expands once at the configuration boundary into an immutable definition.

Entrance defaults:

| Type | Duration | Fixed behavior |
| --- | ---: | --- |
| `none` | 0 ms | Existing stable state. |
| `fade` | 160 ms | Opacity transitions to the resolved stable value. |
| `slide-up` | 220 ms | Starts `75%` of resolved font size below the anchor and moves upward. |
| `slide-down` | 220 ms | Starts `75%` above the anchor and moves downward. |
| `slide-left` | 220 ms | Starts `75%` to the right and moves left. |
| `slide-right` | 220 ms | Starts `75%` to the left and moves right. |
| `pop` | 220 ms | Scales from `76%` to `112%` by 130 ms, then settles at `100%`. |
| `zoom` | 220 ms | Scales from `88%` to `100%`. |

Exit defaults:

| Type | Duration | Fixed behavior |
| --- | ---: | --- |
| `none` | 0 ms | Remains in the stable state through cue end. |
| `fade` | 120 ms | Opacity transitions from the stable value to transparent. |
| `slide-up` | 180 ms | Moves `75%` of resolved font size upward. |
| `slide-down` | 180 ms | Moves `75%` downward. |
| `slide-left` | 180 ms | Moves `75%` left. |
| `slide-right` | 180 ms | Moves `75%` right. |
| `zoom` | 160 ms | Scales from `100%` to `88%` while fading out. |

Slide names describe visible travel direction. Slide motion is linear because
ASS `\move` is constant-speed. Pop and zoom transform scale around the resolved
anchor rather than changing font size and causing reflow. Pop is entrance-only;
an exit pop is excluded until it has a distinct, useful semantic definition.

Phase time is relative to the logical cue after ASS timestamp quantization. If
entrance plus exit exceeds a short cue, reduce both nonzero durations
proportionally with deterministic integer rounding. Never extend, shift, or
overlap cue timestamps. A zero-length quantized cue renders the stable final
state.

Maximum width and height validate the stable final layout. Temporary entrance
offsets, exit offsets, and pop overshoot may clip at a canvas edge but must not
move, clamp, resize, or rewrap the stable caption.

### Internal event and ASS model

Keep typed phase expansion and cue-relative state calculation in a focused
module such as `multisubs/animation.py`. It performs no transcript escaping,
file I/O, package loading, FFmpeg execution, or model imports. `ass.py` remains
the sole boundary that emits trusted override tags.

Refactor direct string emission through a private typed dialogue-event model.
Each derived event retains:

- logical cue start and end;
- its own event start and end;
- final anchor and PlayRes position;
- visual-line and backdrop-layer identity;
- independently escaped text or trusted vector drawing content;
- word-animation state, when active.

Animation state is sampled from the logical cue timeline, never restarted at a
derived event boundary. This applies to active-word intervals, progressive
karaoke intervals, explicit-line-height lines, and shared box backdrops.
Adjacent slices must not flicker, jump, overlap glyphs, or reset the backdrop.

Generated tags must obey these constraints:

- emit at most one `\pos` or `\move` positioning tag per line;
- use `\move` for directional motion and the resolved anchor as the stable
  destination or origin;
- use `\fscx` and `\fscy` only inside trusted `\t` transforms for pop/zoom;
- compose fade alpha with typography, highlight, backdrop, shadow, and global
  opacity exactly once;
- apply the same cue-relative movement, scale, and opacity state to every
  visual line and its shared vector box;
- escape transcript fragments before assembling trusted overrides.

Event expansion remains bounded by existing word intervals, visual-line count,
and a constant number of phase boundaries. Do not generate frame-by-frame ASS
Dialogue events. Verify behavior against the supported FFmpeg/libass boundary
and the documented [ASS animation tags](https://aegisub.org/docs/latest/ass_tags/).

### Static preview contract

`--preview-layout` continues to create one collision-safe PNG without
transcription. It suppresses entrance and exit motion and renders the stable
final opacity, scale, position, wrapping, and backdrop. Guides describe only
the final layout envelope and anchor.

Word animation keeps the existing representative image behavior:

- progressive karaoke highlights the first half of the displayed cue,
  rounding up;
- active-word karaoke highlights the first displayed word;
- `none` shows no highlighted word.

The command output or preview metadata should identify the selected entrance,
exit, and word animation so users can verify template composition. The PNG is
not evidence of animation timing.

### Template catalog extension

The eight existing templates preserve their current resolved visuals. Their
cue entrance and exit remain `none`; `neon-karaoke` keeps progressive word
animation through the new internal path. Add these exact baselines with bundled
fonts:

| Template | Style | Layout | Animation |
| --- | --- | --- | --- |
| `cinematic-fade` | Lora SemiBold italic, `4.2%`, `#FFF4E6`, `95%`; outline `#111111D9` at `4%`, shadow `2%` | bottom-center; L/R `15%`, T `0%`, B `3%`, W/H `100%`/`16%` | entrance fade 220 ms; exit fade 180 ms; word none |
| `impact-yellow` | Montserrat Black uppercase, `5.2%`, `#FFD60A`, `100%`; outline `#000000E6` at `8%`, shadow `4%` | bottom-center; L/R `8%`, T `0%`, B `3%`, W/H `100%`/`22%` | entrance pop 220 ms; exit fade 100 ms; word none |
| `lower-third-slide` | Oswald SemiBold uppercase, `4.1%`, `#FFFFFF`, `100%`; box `#0B1F3AE6` at `7%`, shadow `0px` | bottom-left; L `5%`, R `38%`, T `0%`, B `3%`, W/H `100%`/`16%` | entrance slide-right 220 ms at `75%`; exit fade 100 ms; word none |
| `soft-zoom` | Inter Medium, `4.3%`, `#F8FAFC`, `100%`; outline `#111827CC` at `4%`, shadow `2%` | bottom-center; L/R `14%`, T `0%`, B `3%`, W/H `100%`/`16%` | entrance zoom 220 ms from `88%`; exit fade 120 ms; word none |
| `word-focus` | Atkinson Hyperlegible Next Bold, `4.5%`, `#FFFFFF`, highlight `#FFD54F`, `100%`; box `#111827D9` at `8%`, shadow `0px` | bottom-center; L/R `10%`, T `0%`, B `3%`, W/H `100%`/`18%` | entrance fade 160 ms; exit fade 120 ms; active-word karaoke |

Unlisted typography uses `0px` letter spacing, `auto` line height, upright text
unless stated italic, and original case unless stated uppercase. Descriptions
must identify intended use, animation behavior, and whether aligned-word timing
is required. `word-focus` inherits the existing karaoke fallback and
translation restrictions.

## Public interface and contracts

Examples:

~~~text
multisubs -i video.mp4 --animation-entrance slide-up
multisubs -i video.mp4 --animation-exit fade
multisubs -i video.mp4 --animation-word karaoke --animation-word-mode active-word
multisubs -i video.mp4 --template cinematic-fade
multisubs -i video.mp4 --template impact-yellow --animation-entrance none --animation-exit none
multisubs -i video.mp4 --template word-focus --animation-word none
~~~

`--template` expands from eight to thirteen stable names. Omitted template and
explicit `default` stay visually static. Existing names retain their resolved
visual behavior, but scripts using removed karaoke flags must adopt the new
animation names.

SRT text and timing are unchanged and contain no generated animation markup.
ASS remains the authoritative animated artifact. Output paths, collision-safe
naming, artifact retention/cleanup, source transcript text, aligned words, cue
IDs and times, model selection, and FFmpeg video/audio policy are unchanged.

Retained transcription JSON advances from schema version 2 to 3. Replace
`metadata.rendering.effects.karaoke` with one resolved structure:

~~~json
{
  "schema_version": 3,
  "metadata": {
    "rendering": {
      "animation": {
        "cue": {
          "entrance": {
            "type": "fade",
            "duration_ms": 160
          },
          "exit": {
            "type": "fade",
            "duration_ms": 120
          },
          "shortened_cues": 0
        },
        "word": {
          "type": "karaoke",
          "mode": "active-word",
          "normal_color": "#FFFFFF",
          "highlight_color": "#FFD54F",
          "fallback_cues": 0
        }
      }
    }
  }
}
~~~

For type `none`, omit fields that do not apply rather than inventing null
values. Diagnostics contain resolved semantic values and counts, never raw ASS
tags or internal template mappings. Do not retain `effects.karaoke` or another
compatibility alias.

## Implementation

- Extend Plan 2 models with typed entrance, exit, and word-animation variants;
  remove any remaining generic effect or cue-preset ownership.
- Add fixed type expansion, phase validation, short-cue normalization, and
  cue-relative sampling in `multisubs/animation.py`.
- Replace the four karaoke flags with the five animation flags in
  `multisubs/cli.py`, preserving explicit-presence tracking and early errors.
- Keep `multisubs/config.py` authoritative for semantic defaults and final
  cross-field validation; never accept raw ASS syntax.
- Refactor `multisubs/ass.py` through the typed event representation and compile
  cue-global fade, motion, scale, and word state around escaped fragments.
- Synchronize phase state across ordinary cues, word-animation intervals,
  explicit line height, multiple lines, and shared vector boxes.
- Suppress cue motion in preview while retaining stable style/layout and the
  representative word highlight.
- Add the five resources to the deterministic catalog index and package audits.
- Migrate retained rendering metadata to schema version 3 with no legacy
  karaoke alias.

## Implementation tasks

- [ ] Add typed cue entrance, cue exit, and word-animation variants.
- [ ] Add fixed per-type defaults, semantic validation, and deterministic
  short-cue normalization.
- [ ] Add the five new animation flags and remove all four karaoke flags.
- [ ] Preserve template inheritance and field-level explicit overrides,
  including independent `none` values.
- [ ] Introduce the private typed ASS dialogue-event representation.
- [ ] Compile fade, four slide directions, pop, and zoom through trusted tags.
- [ ] Keep cue state continuous across word/line slices and vector backdrops.
- [ ] Preserve static ASS output when all resolved animation types are `none`.
- [ ] Keep preview as a final-state PNG with representative word highlighting.
- [ ] Add five exact animated template resources and stable CLI choices.
- [ ] Migrate retained JSON to schema version 3 and remove legacy effect keys.
- [ ] Add unit, regression, property-oriented, integration, and visual tests.
- [ ] Update README.md, docs/prd.md, docs/architecture.md, applicable
  conventions, release notes, and plan lifecycle status.

## Unit tests

### Configuration and CLI

- Omission inherits each template phase; explicit `none` disables only the
  selected entrance, exit, or word branch.
- Every accepted type expands to its exact immutable definition; unknown names
  fail through argparse before probing or model imports.
- The removed karaoke flags fail as unknown arguments and no hidden aliases
  remain in help, parsing, config, or tests.
- Word mode and highlight color reject a final word type other than `karaoke`.
- Existing templates preserve exact style/layout/animation values; the five new
  resources resolve their documented values and bundled font faces.
- `word-focus --animation-word none` retains both fades and static values;
  disabling both cue phases retains active-word karaoke.
- Cue animation remains valid during translation when word animation is
  `none`; karaoke keeps its early translation diagnostic.

### Timing and state

- Cover long, exact-boundary, shorter-than-entrance, shorter-than-exit,
  shorter-than-total, one-centisecond, and zero-length quantized cues.
- Normalized phases remain ordered, non-negative, deterministic, and inside the
  cue without changing timestamps.
- Slide coordinates are correct for four directions, nine anchors,
  native/explicit positions, percentage/pixel layouts, and both orientations.
- Pop reaches `112%` and settles to `100%`; zoom reaches its stable scale
  without changing measured font size, wrapping, or final bounds.
- Global opacity and RGBA component alpha compose exactly once in entrance,
  stable, and exit states.

### Serialization and retained data

- Static output remains byte-for-byte equal for ordinary, explicit placement,
  line-height, karaoke, and box cases when all cue phases are `none`.
- Generated lines contain at most one positioning/movement tag and only trusted
  transform fields.
- Braces, backslashes, ASS-looking text, commas, newlines, Unicode, RTL,
  combining marks, emoji, and CJK remain escaped data.
- Word intervals do not restart cue phases or duplicate same-line glyphs.
- Shared vector backdrops use the same cue-global phase and lower layer.
- Event count has a tested bound based on visual lines, word intervals, and a
  constant number of phase boundaries, never frames or cue duration.
- SRT and JSON contain no generated ASS overrides.
- JSON schema version 3 records exact resolved phase and word-animation data,
  diagnostic counts, and no `effects.karaoke` key.

## Integration and manual verification

- Render every entrance and exit type on controlled 1920x1080 and 1080x1920
  fixtures; extract frames at cue start, entrance midpoint, stable state, exit
  midpoint, and cue end.
- Verify nine anchors, explicit coordinates, two-line explicit line height,
  outline, shared vector box, no backdrop, opacity below 100%, and a short cue.
- Combine pop/fade with progressive and active-word karaoke, including word
  boundaries during both cue phases, and confirm motion/opacity never restart.
- Preview all thirteen templates in 16:9 and 9:16; verify stable position,
  scale, opacity, wrapping, font, backdrop, guides, and both representative
  karaoke states.
- Compare all eight existing templates with pre-feature visual references.
- Attach representative frame sequences or short media to the pull request
  without committing generated assets, transcripts, or source videos.

## Documentation

- Update README highlights, template gallery, exact baseline table, animation
  recipes, command reference, preview explanation, generated-JSON summary, and
  limitations with only the new interface.
- Record the removed-to-new flag mapping and JSON schema change in release
  notes or the project changelog, not as historical migration material in
  README.
- Update docs/prd.md requirements, exclusions, acceptance criteria, constraints,
  and template inventory.
- Update docs/architecture.md configuration composition, event model,
  cue-global timeline, tag safety, preview state, and schema version 3.
- Update docs/conventions.md with reusable animation composition,
  cue-relative-timing, event-bound, and render-verification rules.
- Do not document internal template JSON as a supported customization feature.

## Commit and pull-request plan

Suggested branch:

~~~text
feat/subtitle-animations
~~~

Suggested commits:

1. `refactor: model subtitle dialogue events before serialization`
   - Add the typed event model and preserve static ASS behavior.
2. `feat: compile cue-relative subtitle animations`
   - Add typed phases, fixed defaults, timing normalization, trusted ASS
     compilation, and composition tests.
3. `feat!: unify subtitle animation controls`
   - Add the five animation flags, remove karaoke-specific flags, validate
     composition, and migrate retained metadata to schema version 3.
4. `feat: add animated subtitle templates`
   - Add five resources, package inventory, exact snapshots, and preview/render
     coverage.
5. `docs: document unified subtitle animations`
   - Update README, PRD, architecture, conventions, release notes, and roadmap.

Suggested pull request:

~~~text
Title: feat!: unify subtitle animations and add animated templates
Base: main
~~~

Before opening the pull request:

~~~text
python -m pytest tests/test_templates.py tests/test_config.py tests/test_cli.py tests/test_ass.py tests/test_preview.py tests/test_transcriber.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
rm -rf dist
python -m build
python -m twine check dist/*
git diff --check
git status --short
~~~

Run the complete opt-in FFmpeg/libass matrix separately and record commands,
tool versions, fixture geometry, font providers, and results in the pull-request
description. Audit clean wheel/sdist contents and preview every new template
from the installed wheel.

The pull request must link Plans 2 and 3, state the breaking CLI and JSON
contracts, list actual verification, identify documentation changes, include
migration notes, attach representative motion evidence, and disclose renderer
risks.

In the final pre-PR documentation commit, move Plan 3 and the package to
`In review`, record `feat/subtitle-animations` as the delivery reference, and
push the complete branch before opening the PR. Do not add a post-open commit
solely to record its number or URL.

After merge, mark Plan 3 and the package `Done`, replace its branch reference
with the merged pull-request link, recalculate package/catalog progress, and
evaluate the accumulated breaking feature for release as `v4.0.0`.

## Release and rollback

This plan requires a major release because it removes four public flags and
changes retained transcription JSON from schema version 2 to 3. Do not tag
automatically after merge. Verify the accumulated diff, clean distributions,
installed-wheel behavior, migration notes, and controlled FFmpeg/libass output
before the normal production release workflow.

Before release, Plan 3 can be reverted without reverting Plan 2's internal
schema. After publication, recover through a normal revert or fix pull request
and a new SemVer release; never move or reuse `v4.0.0`.

## Acceptance criteria

- Users can independently select every documented entrance, exit, and word
  animation without a template; omission and explicit overrides compose as
  documented.
- The CLI exposes only the unified animation hierarchy; all removed karaoke
  flags are rejected and release notes contain the exact replacement mapping.
- Existing template names and no-option default preserve resolved visual
  behavior; five new templates provide distinct fade, slide, pop, zoom, yellow,
  and active-word presentations with bundled fonts.
- Explicit `none` disables only its entrance, exit, or word-animation scope.
- Cue-global state stays continuous across ordinary, word-animation,
  explicit-line-height, multi-line, native/explicit-position, and shared-box
  event strategies without flicker, jumps, or duplicate glyphs.
- Short cues receive deterministic bounded phases without timestamp changes;
  stable wrapping and placement remain authoritative.
- Preview remains one collision-safe PNG, performs no transcription/model
  imports, shows final cue state, and uses the representative word highlight.
- ASS contains only trusted generated animation tags around escaped text; SRT
  and JSON contain no generated tags.
- Retained JSON uses schema version 3 and one `metadata.rendering.animation`
  branch with no legacy karaoke effect path.
- Translation, model selection, cue construction, artifact cleanup, collision
  handling, FFmpeg media policy, and font precedence remain unchanged except
  for the documented animation interface.
- Hermetic tests, static regressions, bounded-event tests, landscape/portrait
  renders, all-template previews, clean builds, archive audits, clean-wheel
  smokes, Ruff, Pyright, compileall, CLI help, and documentation checks pass.
