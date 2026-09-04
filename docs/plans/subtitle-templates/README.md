# Subtitle templates roadmap

Status: In review

This package adds reproducible bundled fonts, named subtitle templates, and a
planned declarative animation layer on top of the completed
subtitle-positioning, karaoke, and typography contracts. It does not restore
the removed `--layout` preset system: a subtitle template is an explicit
semantic configuration baseline, may include documented style, placement, and
animation values, and remains independently overridable through semantic CLI
options.

## Product outcome

Users can render a useful subtitle presentation with one option, preview its
final static appearance before transcription, and then override individual
style, animation, or placement fields. Templates may activate an animation
when that behavior is intrinsic to their name and purpose;
`neon-karaoke` therefore enables progressive karaoke and can be neutralized
with `--animation-word none`. Planned cue-animation templates add fades,
directional slides, pop, and zoom while retaining static professional and
accessibility-oriented choices. The package ships every static weight and
italic face that the current CLI can select for each chosen family, so
built-in templates do not depend on host fonts and users can reuse those families directly with
`--font`, `--font-weight`, and `--italic`.

Omitting the template option preserves the current presentation: Roboto
Regular, white text, a translucent black box, the current shadow, and the
current bottom-center layout. The only intended rendering improvement is that
the exact bundled Roboto face replaces environment-dependent Roboto or fallback
selection.

## Shared public contract

Until Plan 3, the delivered template and karaoke options remain:

~~~
--template {default,clean-outline,social-bold,classic-yellow,newsroom,editorial,high-contrast,neon-karaoke}
--karaoke | --no-karaoke
~~~

`default` is the resolved template when the option is omitted. Configuration
precedence is:

1. The selected template, or `default` when none is named.
2. Explicit CLI overrides, applied field by field.
3. Existing syntax, presence, placement-mode, and geometry validation.

An explicit option always wins for its own field. Invalid final combinations
still fail at the existing validation boundary; templates do not suppress or
silently rewrite errors. `neon-karaoke` enables progressive word highlighting
as part of its baseline. Explicit `--no-karaoke` disables that effect while
retaining the template's font, palette, backdrop, and placement. Karaoke
translation restrictions remain enforced against the final composed
configuration. Preview represents progressive mode by highlighting the first
half of the displayed cue and active-word mode by highlighting its first word,
without inventing timing.

Plan 3 intentionally replaces the animation CLI with one consistent hierarchy:

~~~
--template {default,clean-outline,social-bold,classic-yellow,newsroom,editorial,high-contrast,neon-karaoke,cinematic-fade,impact-yellow,lower-third-slide,soft-zoom,word-focus}
--animation-entrance {none,fade,slide-up,slide-down,slide-left,slide-right,pop,zoom}
--animation-exit {none,fade,slide-up,slide-down,slide-left,slide-right,zoom}
--animation-word {none,karaoke}
--animation-word-mode {progressive,active-word}
--animation-word-highlight-color COLOR
~~~

Omitting a flag inherits that branch or field from the template. Explicit
`none` disables only the selected entrance, exit, or word-animation scope.
Plan 3 removes `--karaoke`, `--no-karaoke`, `--karaoke-mode`, and
`--karaoke-highlight-color` instead of retaining compatibility aliases. The
internal template JSON resources are packaged implementation data, not a user
extension surface.

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
| Roboto | Weights 100-900; upright and italic; normal width | 18 | `default`, `classic-yellow` |
| Inter | Weights 100-900, upright and italic, at the default optical size | 18 | `clean-outline` |
| Montserrat | Weights 100-900, upright and italic | 18 | `social-bold`, `neon-karaoke` |
| Oswald | Upright weights 200-700 | 6 | `newsroom` |
| Lora | Weights 400-700, upright and italic | 8 | `editorial` |
| Atkinson Hyperlegible Next | Weights 200-800, upright and italic | 14 | `high-contrast` |

Total planned inventory: 82 unmodified font binaries. Each family keeps its
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
| 2 | [Declarative template schema](02-declarative-template-schema.md) | In review | 1 | `refactor/declarative-template-schema` |
| 3 | [Cue animations and animated templates](03-cue-animations-and-animated-templates.md) | Planned | 2 and completed karaoke/preview contracts | — |

Package progress: 2 of 4 plans done. Plan 2 is in review on
`refactor/declarative-template-schema`.

## Dependencies and delivery order

The completed [subtitle-positioning](../subtitle-positioning/README.md) and
[subtitle-typography](../subtitle-typography/README.md) packages provide typed
configuration, relative-unit resolution, font weight selection, italic
selection, measurement, wrapping, preview, and ASS compilation. The completed
[karaoke package](../karaoke-subtitles/README.md) supplies the timing,
highlighting, validation, and fallback behavior reused by `animation.word`.
Plan 3 supersedes that package's public flag names and retained-JSON path
without changing its timed rendering algorithm.

Recommended delivery order:

1. Bundle, license, package, inventory, and resolve the six font families.
2. Add template selection, effect-aware precedence, metadata, the
   eight-template catalog, documentation, and visual verification.
3. Move the eight built-in definitions into strictly validated internal JSON
   resources organized as `style`, `layout`, and `animation`, without changing
   their resolved configuration or output.
4. Add the bounded cue-animation compiler, replace the karaoke-specific CLI
   with the unified animation hierarchy, and add five templates while
   preserving static preview semantics.

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

## Release and rollback

Plans 0 and 1 formed the backward-compatible template release. Plan 2 is an
internal behavior-preserving refactor and does not independently require a
release. Plan 3 deliberately removes the karaoke-specific flags and changes
the retained rendering-metadata schema, so the accumulated feature requires a
major SemVer release, expected to be `v4.0.0`. Do not create a tag
automatically after a plan merges; verify the accumulated diff, staged wheel,
sdist, packaged resources, migration notes, and FFmpeg/libass output before
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
  placement, and ASS compilation. `neon-karaoke` renders with its timed word
  animation in transcription and with the documented representative static
  highlight in preview; `--animation-word none` removes only that animation.
- The packaged template catalog has one deterministic index and one strictly
  validated JSON resource per built-in template. Runtime configuration remains
  immutable, unknown fields fail clearly, and a clean wheel contains the same
  catalog as the source tree.
- Existing template names and their resolved visual behavior remain
  compatible. The animation CLI and retained rendering metadata use only the
  new hierarchy; removed karaoke flags are rejected rather than aliased. Cue
  timing stays relative across word-animation intervals, explicit line-height
  events, native/explicit placement, and shared vector backdrops.
- Static preview omits cue motion and displays its stable final state. Karaoke
  retains its existing representative half-cue or first-word state.
- Hermetic tests, controlled FFmpeg/libass integration checks, package builds,
  clean-wheel smoke checks, Ruff, Pyright, and documentation checks pass.
- README.md, docs/prd.md, docs/architecture.md, and applicable conventions
  describe only the delivered interface, bundled-font behavior, licensing, and
  limitations.
