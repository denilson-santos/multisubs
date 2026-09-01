# Feature 9: remove layout presets and use explicit defaults

Status: In review

Delivery: [#54](https://github.com/denilson-santos/multisubs/pull/54),
[#55](https://github.com/denilson-santos/multisubs/pull/55),
[#56](https://github.com/denilson-santos/multisubs/pull/56), follow-up
`fix/reject-ineffective-margins`

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Named positions](02-named-positions.md)
- [Relative units](03-relative-units.md)
- [Layout presets](04-layout-presets.md)
- [Custom coordinates](05-custom-coordinates.md)
- [Adaptive line wrapping](06-adaptive-line-wrapping.md)
- [Placement modes and maximum height](07-placement-modes-and-maximum-height.md)
- [Layout preview](08-layout-preview.md)

## Objective

Remove the public `--layout` preset layer and make subtitle placement a direct,
predictable composition of `--position`, margins, maximum dimensions, and the
existing explicit-coordinate options.

An invocation that does not provide layout options must use one documented set
of defaults on every video geometry. It must not silently choose different
values from the video's aspect ratio.

## Scope

Included:

- Remove `--layout` and every public preset name from the CLI.
- Remove automatic landscape, portrait, and square classification.
- Replace preset-provided native values with centralized field defaults.
- Resolve percentage font size against autorotated render height so videos with
  the same output height retain the same resolved size across aspect ratios.
- Keep every effective explicit layout field independently overridable and
  reject explicit fields that the selected placement mode cannot apply.
- Remove preset types, parsing, merging, progress output, preview labels, and
  JSON metadata.
- Preserve named native ASS placement, explicit PlayRes placement, adaptive
  wrapping, preview, and collision-safe outputs.
- Retain the former concrete values only as plan-level regression fixtures and,
  when useful, release-note context.
- Treat the CLI, Python API, and JSON metadata changes as a major-version
  compatibility break.

Excluded:

- Removing `multisubs/layout.py`; it remains responsible for geometry-aware unit
  resolution, native regions, wrapping budgets, and explicit-envelope checks.
- Renaming or removing `--preview-layout`; it selects preview mode rather than a
  layout preset and remains useful.
- Making `--position` set margins or maximum dimensions implicitly.
- Adding a `--safe-area` flag, named safe-area profiles, configuration files,
  environment variables, or platform-specific social-media presets.
- Changing the nine position names, margin/coordinate/maximum-dimension
  percentage bases, ASS placement modes, cue segmentation, font measurement,
  or output-file lifecycle.
- Automatically translating a removed preset name into a replacement command.

## Decisions and constraints

### Fixed native defaults

Use one product-selected universal native baseline:

| Field | Default |
| --- | --- |
| `position` | `bottom-center` |
| `margin-left` | `18%` |
| `margin-right` | `18%` |
| `margin-top` | `0%` |
| `margin-bottom` | `5%` |
| `max-width` | `100%` |
| `max-height` | `10%` |

This deliberately changes the previous defaults on every aspect ratio while
removing aspect-ratio-dependent configuration. The historical-equivalence table
below records the former concrete values for testing and release preparation.
Native `max-height` percentages and percentage font size now share render height
as their vertical reference. This keeps their proportion stable across aspect
ratios that have the same output height and avoids shrinking text merely because
a portrait canvas is narrower.

The defaults must be constants in `multisubs/config.py`, parsed through the same
strict `RelativeLength` path as user values, and copied into each new immutable
`SubtitleConfig`. They must not be mutable global `SubtitleLayout` instances.

### Position remains independent

`--position` selects only native ASS alignment. For example,
`--position top-center` changes the anchor but retains the default side, top,
bottom, width, and height values unless the user overrides those fields.

Native ASS continues to apply only the vertical margin active for the selected
position. A top position therefore uses the configured top margin; a bottom
position uses the bottom margin; middle alignment ignores both vertical margins
for placement. Explicitly supplying an inactive vertical margin must fail before
probing with an actionable message naming the active alternative. The default
bottom position therefore stores a zero top margin and a 5% bottom inset; a top
position uses the zero default unless the user supplies its active top margin.
This ASS behavior must stay explicit in help and docs.

### Explicit coordinates keep explicit envelopes

The fixed native `max-width` and `max-height` defaults must not accidentally
satisfy explicit-mode requirements. When X/Y coordinates are present, the user
must still supply `--anchor`, `--max-width`, and `--max-height`; any explicitly
supplied margin must fail before probing. Mode detection and presence validation
therefore occur before native defaults are filled; retained native defaults
compile to zero in explicit placement.

### Compatibility and release

- Passing `--layout`, including `--layout auto`, must fail as an unrecognized
  argument through argparse before FFprobe or WhisperX.
- Do not add a hidden alias, warning-only compatibility period, or environment
  switch. The approved delivery is a clean major-version cutover.
- Removing preset fields from JSON is an output-contract break. Increment
  `schema_version` from `1` to `2`.
- The implementation is eligible only for `v3.0.0` or a later major version.
  The version bump and stable tag follow the normal staged release workflow
  after the implementation pull request is merged.
- Existing completed preset plans remain as implementation history; this plan
  supersedes their current public preset contract.

## Public interface and contracts

### CLI

Remove:

~~~text
--layout {auto,landscape,portrait,square,vertical-social,upper-third,centered}
~~~

Keep:

~~~text
--position POSITION
--margin-left LENGTH
--margin-right LENGTH
--margin-top LENGTH
--margin-bottom LENGTH
--max-width LENGTH
--max-height LENGTH
--position-x LENGTH
--position-y LENGTH
--anchor POSITION
--preview-layout
~~~

The parser help and README command table must show the exact fixed defaults for
native fields rather than “preset value.” The nine position choices, strict
`%`/`px` syntax, and percentage bases remain unchanged. Early validation rejects
inactive vertical margins and all explicitly supplied margins in coordinate
mode with actionable alternatives.

### Python API and typed models

Remove the `layout_preset` keyword from `generate_transcriptions()` and
`validate_subtitle_config()`. Remove `SubtitleLayoutPreset`, `LayoutPreset`,
`SubtitleConfig.layout_preset`, and preset-only `layout_overrides` bookkeeping.

`SubtitleConfig.layout` becomes the complete requested layout. Native configs
contain all fixed defaults plus effective user overrides; explicit configs
contain the validated coordinate envelope and may carry neutralized margin
defaults only after explicit margin conflicts have been rejected. Programmatic
callers that use removed preset symbols or keywords must migrate to explicit
field values.

No compatibility wrapper should retain the removed keyword because doing so
would preserve two competing configuration paths in the new major version.

### Resolution and validation

`resolve_subtitle_config()` must no longer classify geometry, retrieve a preset,
or merge an override set. It validates the typed config, resolves its unit-bearing
values against the existing mode-specific bases, calculates the native region or
explicit envelope, and returns the resolved config directly.

Remove `classify_layout_preset()`, `parse_layout_preset()`,
`get_layout_preset()`, `LAYOUT_PRESET_CHOICES`, `LAYOUT_PRESETS`, aspect-ratio
thresholds used only for preset selection, and `_effective_layout_overrides()`.

Validation timing remains unchanged:

- syntax, unknown flags, missing explicit-mode fields, and incompatible options
  fail before probing;
- explicitly supplied inactive vertical margins and coordinate-mode margins
  fail before probing with actionable diagnostics;
- geometry-dependent margins, maximum dimensions, and explicit envelope bounds
  fail after FFprobe and before WhisperX;
- invalid input never causes a silent fallback to old preset behavior.

### JSON

Change the top-level `schema_version` to `2` and remove:

~~~json
"requested_preset": "auto",
"resolved_preset": "portrait"
~~~

Keep requested and resolved position, margins, maximum dimensions, percentage
bases, placement mode, native region or explicit coordinates, wrapping metrics,
appearance, and effects metadata. Those concrete values are sufficient to
reproduce the rendered configuration without a preset identity.

SRT text/timing, ASS style/event behavior, retained artifact names, and cleanup
behavior do not change. Rendered placement and cue line capacity can change on
portrait or square input because that is the intended removal of `auto`.

### Progress and preview

Normal and preview progress messages must stop reporting a preset. Preview
guides must remove the `Preset:` line and continue to display mode, position or
anchor, resolved envelope, typography metrics, opacity, text case, and PlayRes.

Preview must use exactly the same fixed defaults and overrides as final
rendering and must continue to return before importing WhisperX/PyTorch.

## Historical equivalence reference

This mapping is an internal planning and regression reference. It may support
concise release notes, but it must not be copied into `README.md`; the README
documents only the current interface and current features. Omitting layout
options uses the new universal baseline rather than reproducing one former
preset.

| Removed value | Replacement layout options |
| --- | --- |
| `auto` | No exact equivalent; use the new defaults or choose explicit values for the intended geometry. |
| `landscape` | `--position bottom-center --margin-left 6% --margin-right 6% --margin-bottom 6% --max-width 100% --max-height 10.5%` |
| `portrait` | `--position bottom-center --margin-left 8% --margin-right 8% --margin-bottom 8% --max-width 100% --max-height 6%` |
| `square` | `--position bottom-center --margin-left 7% --margin-right 7% --margin-bottom 7% --max-width 100% --max-height 10.6%` |
| `vertical-social` | `--position bottom-center --margin-left 8% --margin-right 12% --margin-bottom 16% --max-width 100% --max-height 6.6%` |
| `upper-third` | `--position top-center --margin-left 6% --margin-right 6% --margin-top 8% --max-width 100% --max-height 10.7%` |
| `centered` | `--position center --margin-left 8% --margin-right 8% --max-width 100% --max-height 10%` |

The project no longer makes an aspect-ratio policy decision. This consequence
must be clear in the breaking-change release notes without adding legacy preset
recipes to the README.

## Implementation

### `multisubs/config.py`

- Define immutable scalar default constants for every native layout field.
- Build complete native `SubtitleLayout` values directly from defaults and
  explicit arguments.
- Detect explicit coordinate mode and validate user presence before applying
  native defaults.
- Reject explicit margin options that the selected native or coordinate mode
  cannot apply, and report the effective alternative.
- Remove preset definitions, parsers, choices, and merge-only state.

### `multisubs/models.py`

- Remove preset enums/value objects and preset state from `SubtitleConfig`.
- Remove `layout_overrides` if no remaining consumer requires it.
- Retain `SubtitleLayout`, `SubtitlePosition`, `SubtitlePlacementMode`, and
  `CuePlacement` as the placement contracts.

### `multisubs/layout.py`

- Resolve the complete requested layout without aspect-ratio classification or
  preset merging.
- Preserve existing unit bases, rounding, native ASS region behavior, explicit
  envelope validation, and wrapping-metric derivation.
- Delete preset-only helpers and imports.

### `multisubs/cli.py`, `multisubs/transcriber.py`, and `multisubs/preview.py`

- Remove the parser option and Python keyword path.
- Remove preset names from progress messages and preview guide labels.
- Emit JSON schema 2 without requested/resolved preset fields.
- Preserve all early heavy-import boundaries.

### Tests

- Replace preset parsing, immutability, selection, merge, and rendering tests
  with default completeness, override independence, cross-geometry stability,
  historical equivalence, JSON schema, and stale-public-interface tests.
- Keep historical preset render values as parametrized regression fixtures so
  equivalence can be verified without retaining presets in production code or
  documenting legacy recipes in the README.

## Implementation tasks

- [x] Centralize the seven native layout defaults and add completeness tests.
- [x] Set the inactive top-margin default to zero for the default bottom-center
      position and synchronize resolved metadata fixtures.
- [x] Remove preset types, constants, parsing, classification, merge logic, and
      override bookkeeping from the typed configuration path.
- [x] Remove `--layout` and the programmatic `layout_preset` keyword and prove
      both fail before external work.
- [x] Preserve explicit-coordinate presence validation before native defaults
      are applied.
- [x] Reject explicitly supplied inactive vertical margins and coordinate-mode
      margins before probing with actionable diagnostics.
- [x] Resolve percentage font size against render height and verify equal-height
      landscape and portrait canvases produce the same resolved size.
- [x] Remove preset output from progress messages and preview guides.
- [x] Bump JSON to schema 2 and remove preset metadata with serialization tests.
- [x] Replace preset integration coverage with fixed-default and historical
      equivalence render assertions.
- [x] Update README, PRD, architecture, conventions, AGENTS.md, this roadmap,
      and record the breaking-change release requirements.
- [x] Move the plan and package to `In review` and record the task branch in the
      final pre-PR documentation commit.

## Unit tests

- Parser help contains no `--layout` or preset choices.
- Every removed `--layout` invocation exits `2` before FFmpeg, FFprobe, PyTorch,
  or WhisperX imports/calls.
- Default native config contains exactly the seven documented values.
- Landscape, portrait, square, and rotated inputs begin from identical requested
  defaults and resolve only their percentages against their own geometry.
- Equal-height landscape and portrait inputs resolve the same percentage font
  size; pixel font sizes remain unchanged.
- Each explicit layout option overrides only its matching default.
- Changing `--position` does not mutate margins or maximum dimensions.
- Top and bottom positions accept only their active explicit vertical margin;
  middle positions reject both while retained defaults remain valid.
- Explicit X/Y still require an explicit anchor, maximum width, and maximum
  height even though native mode has defaults.
- Explicit placement rejects user-supplied margins and off-canvas envelopes
  without clamping.
- Two config instances cannot mutate or leak defaults into one another.
- Removed Python symbols and keywords are absent; retained typed configurations
  validate and resolve normally.
- JSON uses schema 2, omits both preset keys, and retains complete concrete
  layout metadata.
- Preview guides and progress messages contain no preset label or name.
- Existing escaping, cue wrapping, karaoke, typography, publication, and cleanup
  regressions continue to pass.

## Integration and manual verification

- Render default previews on synthetic landscape, portrait, square, and rotated
  videos and verify the documented fixed values resolve proportionally.
- Compare the new default landscape render with the former `landscape` preset
  fixture within the existing libass tolerance.
- Render the historical concrete values from the plan fixture table and compare
  their native regions and subtitle bounds with the previous expected
  measurements.
- Render representative top, center, and bottom positions to confirm that
  position changes do not carry hidden margin changes.
- Reject one explicit-coordinate preview with user-supplied margins before
  FFprobe or FFmpeg is called.
- Verify preview mode still produces one valid collision-safe PNG without
  importing WhisperX/PyTorch.
- Build and install a wheel in a clean supported environment; confirm
  `multisubs --help` contains the fixed defaults and no preset interface.

Generated media remains local or attached to the pull request and must not be
committed.

## Documentation

- `README.md`: remove preset examples/table and `--layout`; show only the current
  fixed defaults, position semantics, explicit coordinates, preview behavior,
  and other supported v3 features. Do not add former-preset recipes or a preset
  migration section.
- `docs/prd.md`: rewrite FR-9 and acceptance criterion 12 around explicit fields
  and universal defaults; reconcile the caption-readability requirement and
  maximum-height acceptance criterion with the documented portrait default
  change; remove aspect-ratio preset selection.
- `docs/architecture.md`: remove preset ownership/merge flow and metadata; record
  the direct default/override resolution path and JSON schema 2.
- `docs/conventions.md`: replace preset immutability/merge rules with centralized
  immutable field-default and mode-presence rules; reconcile release
  documentation so legacy migration details belong in release notes or a
  changelog while the README describes the current product interface.
- `AGENTS.md`: remove preset-specific repository-map and style-change guidance
  while keeping geometry, output, and CLI documentation requirements current.
- `docs/plans/subtitle-positioning/README.md`: record this superseding increment,
  delivery state, and major-release gate.
- Completed numbered plans remain available as historical decision records and
  must not be deleted or marked incomplete.

## Security, performance, compatibility, and rollback

- No dependency, network, model, filesystem, FFmpeg filter, or ASS escaping
  boundary changes are expected.
- Removing classification and merge logic slightly reduces configuration work;
  transcription and rendering performance should be unchanged.
- The main risk is silent visual change for users who relied on `auto` for
  portrait or square media, including a larger derived line capacity on
  portrait input. Mitigate it with exact changed-default notes, verified
  regression fixtures, release notes, render comparisons, and a major version.
- Before release, rollback is a normal revert through a pull request. After a
  `v3.0.0` release, never move the tag; restore compatibility only in a new
  SemVer release if the product decision changes.

## Commit and pull-request plan

Suggested branch:

~~~text
feat/remove-layout-presets
~~~

Suggested commits:

1. `refactor: centralize default subtitle layout fields`
   - Add the fixed constants and behavior-preserving default construction tests.
2. `feat!: remove subtitle layout presets`
   - Remove CLI/Python preset interfaces, model and resolver state, JSON fields,
     preview/progress labels, and focused regression tests.
3. `test: verify historical layout equivalence`
   - Replace preset integration cases with fixed-default and plan-level
     historical-value render assertions.
4. `docs: document explicit subtitle layout defaults`
   - Update user, product, architecture, conventions, agent, roadmap, and
     release documentation; keep the README limited to current features, set
     the plan/package to `In review`, and retain the branch as the delivery
     reference.

Suggested pull request:

~~~text
Title: feat!: remove subtitle layout presets
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_cli.py tests/test_config.py tests/test_layout.py tests/test_preview.py tests/test_transcriber.py tests/test_ass.py`.
- Run the focused synthetic FFmpeg/libass default and historical-equivalence
  render cases.
- Run `python -m compileall multisubs` and `multisubs --help`.
- Run `python -m pytest`.
- Run `python -m ruff format --check .`, `python -m ruff check .`, and
  `python -m pyright`.
- Run `python -m build`, validate package metadata, install the wheel in a clean
  supported environment, and inspect its CLI help.
- Search current code and documentation for stale `--layout`, preset symbols,
  preset metadata, and aspect-classification references; exclude completed plan
  history from mechanical removal.
- Run `git diff --check` and confirm no generated media, subtitles, fonts,
  caches, build output, or unrelated changes are staged.
- In the final pre-PR documentation commit, update the plan and package to
  `In review` and record `feat/remove-layout-presets` as the dashboard delivery
  reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

The pull-request description must link this plan, list the exact old and new
defaults by geometry, describe the CLI/Python/JSON breaks, record schema 2,
report the historical regression fixtures, list all commands actually run,
attach relevant visual evidence, and identify `v3.0.0` as the earliest eligible
release. The README must remain focused on the resulting current interface.

After merge:

- Mark this plan and the package `Done`, replace the branch with the merged PR
  link, and recalculate package/catalog progress in the next package-status
  update.
- Bump `multisubs.__version__` to `3.0.0` in a normal follow-up pull request.
- After the exact `main` commit passes staging, create and push the annotated
  `v3.0.0` tag and let production promote the staged artifacts without rebuild.

## Acceptance criteria

- `multisubs --help` exposes no `--layout` option or preset name and shows all
  fixed native defaults.
- No `--safe-area` option or replacement preset/profile abstraction is added.
- A removed `--layout` invocation fails before external probing or model work.
- Every native invocation starts from the documented universal defaults,
  independent of aspect-ratio class; explicit values override only their field.
- Percentage font size uses autorotated render height and remains equal across
  landscape and portrait outputs with the same height.
- Default landscape rendering matches the documented universal baseline within
  the existing measurement tolerance.
- Historical landscape, portrait, square, vertical-social, upper-third, and
  centered values remain reproducible in regression tests without remaining
  public presets.
- `--position` changes alignment without applying hidden margins, width, or
  height values.
- Explicit inactive vertical margins fail before probing and identify the active
  alternative; middle positions reject both vertical margin flags.
- Explicit X/Y mode retains its required fields, global PlayRes axes,
  margin-independent envelope, rejects explicitly supplied margins, and retains
  its off-canvas failure behavior.
- Preview and final rendering resolve the same layout without preset labels or
  WhisperX/PyTorch imports on the preview path.
- JSON schema 2 contains no requested/resolved preset fields and retains all
  concrete values required to reproduce placement and wrapping.
- SRT, ASS, output naming, artifact retention, transcription, translation,
  typography, karaoke, escaping, and collision safety remain unchanged.
- Release notes clearly identify the breaking change, changed portrait/square
  placement and line-capacity defaults, and major-version requirement. The
  README documents only current features and contains no removed-preset
  migration section or legacy recipes.
- Focused tests, full hermetic tests, static checks, package build, clean-wheel
  CLI verification, and applicable FFmpeg/libass regressions pass.
