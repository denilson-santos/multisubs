# Subtitle templates roadmap

Status: In review

Delivery branch: `feat/custom-template-files`

This package adds reproducible bundled fonts, named subtitle templates, and a
declarative animation layer on top of the completed
subtitle-positioning, karaoke, and typography contracts. It does not restore
the removed `--layout` preset system: a subtitle template is an explicit
semantic configuration baseline, may include documented style, placement, and
animation values, and remains independently overridable through semantic CLI
options.

## Current proposal

[Plan 4](04-curated-social-templates.md) established the sparse social-video
catalog and Plan 5's final delivery retains sixteen choices: `default` plus
fifteen curated styles. Nine redundant Plan 4 presets were removed in this
follow-up while preserving the yellow, green, red, lime, coral, cyan, and
magenta styles that remain in the active catalog. The following delivered
behavior describes Plans 0–3;
legacy names below are historical/current baselines, not the current catalog.

## Product outcome

[Plan 5](05-custom-template-files.md) is In review after Plan 4. It adds a
local `--template-dir` catalog with selection through `--template NAME` and
an optional built-in `base`. Custom names take precedence for selection;
bases always resolve against the built-in catalog. Inheritance precedence is
base, custom fields, then explicit CLI options. Its public version-1 format is
separate from private schema 5. The implementation is active on `feat/custom-template-files`.

Users can render a useful subtitle presentation with one option, preview its
final static appearance before transcription, and then override individual
style, animation, or placement fields. The curated catalog includes restrained
word emphasis in `amber-word`, progressive timing in `mint-progress`, a measured
active-word marker in `focus-marker`, and compact colored accents in
`golden-title` and `emerald-word`, plus choreographed `kinetic-lime`,
`coral-marker`, `editorial-reveal`, `headline-bounce`, `yellow-pop`,
`yellow-trace`, `neon-lime-marker`, `neon-cyan-reveal`, and
`neon-magenta-pulse` styles for short-form social cuts. Animated templates
provide independent text/backdrop tracks, configurable durations, and separate
word modes while retaining static professional and
accessibility-oriented choices. Yellow word templates use exact `#FBE003`;
neon templates use saturated solid accents with dark contrast. The package ships every static weight and
italic face that the current CLI can select for each chosen family, so
built-in templates do not depend on host fonts and users can reuse those families directly with
`--font`, `--font-weight`, and `--italic`.

Omitting the template option preserves the current presentation: Roboto
Regular, white text, a translucent black box, the current shadow, and the
current bottom-center layout. The only intended rendering improvement is that
the exact bundled Roboto face replaces environment-dependent Roboto or fallback
selection.

## Shared public contract

`default` is the resolved template when the option is omitted. Configuration
precedence is:

1. The selected template, or `default` when none is named.
2. Explicit CLI overrides, applied field by field.
3. Existing syntax, presence, placement-mode, and geometry validation.

An explicit option always wins for its own field. Invalid final combinations
still fail at the existing validation boundary; templates do not suppress or
silently rewrite errors. Plan 3 defines four tracks: cue.text, cue.backdrop,
word.text, and word.backdrop. Each has independent entrance, emphasis, exit,
and optional per-phase duration overrides.

The CLI follows `--animation-<cue|word>-<text|backdrop>-<phase>` and
`--animation-<cue|word>-<text|backdrop>-<phase>-duration`. Duration values
include units such as `150ms` or `0.15s`. Word tracks additionally expose
independent active-word/progressive modes. Refer to
[Plan 3's complete contract](03-cue-animations-and-animated-templates.md#cli-contract)
for choices, defaults, precedence, and validation.

`--word-backdrop {none,outline,box}` enables the decoration and chooses its
shape; none is the default. An enabled decoration follows its word mode
(default active-word) even with emphasis none. Text highlighting is a separate
word.text emphasis. Disabled decoration tracks generate no rendering or
alignment requirements.

Preview remains one image, suppressing motion and representing each word
track's selected mode independently. Current resources use strict schema 5 with
sparse authored values expanded from the semantic defaults; the schema-4 reader
remains available for complete historical fixtures. Resources remain packaged
implementation data rather than a user extension surface.
The revised four-track contract was implemented, verified, and delivered in
[PR #65](https://github.com/denilson-santos/multisubs/pull/65).

## Bundled font families

"All variations" means every unmodified static TTF served by the official
Google Fonts API for the current weight and italic controls. The catalog pins
the Google Fonts revision, API family version, stylesheet, and exact versioned
binary URL. Variable font files, non-default width and optical-size instances,
web formats, source files, and separate sister families are outside this
package because the current CLI cannot select those axes and libass does not
reliably render variable-font instances.

| Family | Bundled static faces | Count | Used by |
| --- | --- | ---: | --- |
| Roboto | Weights 100-900; upright and italic; normal width | 18 | `default`, `emerald-word`, `coral-marker`, `neon-magenta-pulse` |
| Inter | Weights 100-900, upright and italic, at the default optical size | 18 | `amber-word`, `yellow-trace` |
| Montserrat | Weights 100-900, upright and italic | 18 | `bold-headline`, `mint-progress`, `yellow-pop` |
| Oswald | Upright weights 200-700 | 6 | `golden-title`, `headline-bounce`, `neon-lime-marker` |
| Lora | Weights 400-700, upright and italic | 8 | `editorial-reveal` |
| Atkinson Hyperlegible Next | Weights 200-800, upright and italic | 14 | `focus-marker`, `neon-cyan-reveal` |

Total inventory: 82 unmodified font binaries. Each family keeps its
original `OFL.txt`; the project does not need a `THIRD_PARTY_NOTICES.md` file.
The root `LICENSE` continues to cover multisubs source code under MIT, while the
font files remain under SIL Open Font License 1.1.

## Plan status

This table is the source of truth for the package. Status values follow the
[plan catalog vocabulary](../README.md#status-vocabulary).

| Order | Plan | Status | Depends on | Delivery |
| --- | --- | --- | --- | --- |
| 0 | [Bundled OFL font catalog](00-bundled-ofl-font-catalog.md) | Done | Completed positioning and typography packages | [#60](https://github.com/denilson-santos/multisubs/pull/60) |
| 1 | [Built-in subtitle templates](01-built-in-subtitle-templates.md) | Done | 0 and completed karaoke package | [#61](https://github.com/denilson-santos/multisubs/pull/61) |
| 2 | [Declarative template schema](02-declarative-template-schema.md) | Done | 1 | [#64](https://github.com/denilson-santos/multisubs/pull/64) |
| 3 | [Independent subtitle element animations](03-cue-animations-and-animated-templates.md) | Done | 2 and completed karaoke/preview contracts | [#65](https://github.com/denilson-santos/multisubs/pull/65) |
| 4 | [Curated social templates](04-curated-social-templates.md) | Done | 2, 3; completed vector boxes and multiline capacity | [#70](https://github.com/denilson-santos/multisubs/pull/70) |
| 5 | [Custom template directory](05-custom-template-files.md) | In review | 4 | `feat/custom-template-files` |

Package progress: 5 of 6 plans done. Current plan: Plan 5 (In review).
Plans 0–4 are delivered; Plan 5 is complete on its task branch with no blocking
technical dependency. Animated preview clips remain optional for its verification.

## Dependencies and delivery order

The completed [subtitle-positioning](../subtitle-positioning/README.md) and
[subtitle-typography](../subtitle-typography/README.md) packages provide typed
configuration, relative-unit resolution, font weight selection, italic
selection, measurement, wrapping, preview, and ASS compilation. The completed
[karaoke package](../karaoke-subtitles/README.md) supplies the timing,
highlighting, validation, and fallback behavior reused by `animation.word`.
Plan 3 supersedes that package's public flag names and retained-JSON path
while reusing its lossless mapping and fallback rules.

Recommended delivery order:

1. Bundle, license, package, inventory, and resolve the six font families.
2. Add template selection, effect-aware precedence, metadata, the
   eight-template catalog, documentation, and visual verification.
3. Move the eight built-in definitions into strictly validated internal JSON
   resources organized as `style`, `layout`, and `animation`, without changing
   their resolved configuration or output.
4. Add the bounded cue/word animation compiler, replace the karaoke-specific
   CLI with independent text/backdrop controls, word modes, and configurable
   durations, and migrate the historical catalog while preserving static preview.
5. Replace non-default choices with twenty-four curated styles and introduce compact
   internal resource normalization, after the completed
   [vector-box](../subtitle-backdrops/00-unified-vector-box.md) and
   [multiline-capacity](../subtitle-preview/00-multiline-capacity.md) work.
   The [animated clip](../subtitle-preview/01-animation-clip.md) is optional,
   not a blocking dependency.
6. After Plan 4, expose a flat custom-template directory and selection by name
   with one optional built-in base,
   a separately versioned public contract, CLI overrides, and source provenance.

Keep these plans in separate pull requests. Plan 1 must consume the packaged
font catalog rather than introduce a second asset-resolution path. Plan 3 must
consume the schema and typed runtime contracts from Plan 2 rather than parsing
template JSON or generating raw ASS tags in CLI code.

## Commit and pull-request strategy

Use one short-lived implementation branch and pull request per numbered plan,
targeting `main`. Keep font binaries, their original license texts, the
machine-readable inventory, provider behavior, and packaging verification
together in Plan 0. Keep the initial template registry, CLI behavior, tests,
and user documentation together in Plan 1. Keep the behavior-preserving JSON
resource and typed-configuration migration in Plan 2. Keep public animation
behavior, ASS compilation, animated templates, render verification, and
user-facing documentation together in Plan 3.

Each pull request must link its plan, describe package-size impact, list exact
verification commands, identify documentation changes, and record remaining
font-rendering risks. Before opening it, move the active plan and package to
`In review`, retain the task branch as the dashboard delivery reference, and
push the complete branch. After an authoritative merge signal, mark that plan
`Done`, replace the branch with the merged pull-request link, and recalculate
package and catalog progress.

Plan 4 keeps loader normalization and tests in a coherent first commit, then
ships catalog replacement with regression/visual evidence and the associated
breaking-change documentation in one separate draft PR. Its removal of
documented names is a breaking change.

## Release and rollback

Plans 0 and 1 formed the backward-compatible template release. Plan 2 is an
internal behavior-preserving refactor and does not independently require a
release. Plan 3 deliberately removes the karaoke-specific flags and changes
the retained rendering-metadata schema, so the accumulated feature requires a
major SemVer release, expected to be `v4.0.0`. Do not create a tag
automatically after a plan merges; verify the accumulated diff, staged wheel,
sdist, packaged resources, release notes, and FFmpeg/libass output before
the normal release workflow.

Each plan is independently revertible before release. Plan 3 must be revertible
without reverting the internal JSON schema introduced by Plan 2. After
publication, recover through a normal revert or fix pull request and a new
SemVer release; never move an existing tag.

## Shared definition of done

- Every one of the 82 planned font binaries is an unmodified official Google
  Fonts artifact represented exactly once in the font manifest and accompanied
  by the correct family `OFL.txt`.
- Every distribution build starts after removing `dist/`. The resulting wheel
  and sdist contain the manifest, every declared font file, and every family
  license; a clean wheel installation can use them without network access or
  system font installation.
- Explicit `--fonts-dir` faces take precedence over bundled faces, bundled
  faces take precedence over fontconfig, and Pillow/RAQM and FFmpeg/libass use
  the same resolved provider directory.
- README includes a complete custom-font recipe covering the flat directory
  structure, supported formats, internal family names, weight/italic selection,
  provider precedence, non-installing behavior, and licensing responsibility.
- No absolute asset path or machine-specific path is serialized to retained
  JSON, and routine invocations do not hash every bundled binary.
- Omitting `--template` and selecting `default` resolve to the exact
  current semantic defaults in `multisubs/config.py`.
- Explicit CLI appearance, layout, and animation options override one template
  field at a time without hidden coupling or validation bypasses.
- Every template previews and renders with the same font, values, wrapping,
  placement, and ASS compilation. `mint-progress` renders progressive word
  timing in transcription, `focus-marker` renders its measured active-word box,
  and `--animation-word-text-emphasis none` removes only text emphasis while
  preserving any selected word decoration.
- The packaged template catalog has one deterministic index and one strictly
  validated JSON resource per built-in template. Runtime configuration remains
  immutable, unknown fields fail clearly, and a clean wheel contains the same
  catalog as the source tree.
- Plans 0–3 preserved existing template names and visuals. Plan 4 intentionally
  supersedes that requirement for non-default names and permits sparse authored
  resources while retaining complete validated runtime configurations. The
  animation CLI and retained rendering metadata use only the
  new hierarchy; removed karaoke flags are rejected rather than aliased. Cue
  timing stays relative across word-animation intervals, explicit line-height
  events, native/explicit placement, and shared vector backdrops.
- Static preview omits every cue/word motion phase and displays the stable
  state. Karaoke retains its representative half-cue or first-word state.
- Hermetic tests, controlled FFmpeg/libass integration checks, package builds,
  clean-wheel smoke checks, Ruff, Pyright, and documentation checks pass.
- README.md, docs/prd.md, docs/architecture.md, and applicable conventions
  describe only the delivered interface, bundled-font behavior, licensing, and
  limitations.

For Plan 4, completion historically required exactly twenty-five choices, preserved
default output, strict sparse/expanded equivalence, calibrated one/two-line
capacities, and real ASS/visual evidence for all twenty-four non-default styles, including the ten
choreographed additions and balanced box padding. Its acceptance criteria
supersede named legacy-template examples above; completed plans stay intact.

Plan 5 completion additionally requires validated custom files in transcription
and both preview modes, deterministic inheritance/disable behavior, preserved
built-in output, and custom provenance without local template paths. Its
implementation receives a separate branch and draft PR after Plan 4.
