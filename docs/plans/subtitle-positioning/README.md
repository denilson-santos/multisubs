# Subtitle positioning roadmap

Status: In review

This directory contains the implementation plans for redesigning subtitle
appearance and deterministic positioning in multisubs. The work is intentionally
split into independently reviewable increments, but the features share the typed
configuration and pipeline changes described in the foundation plan.

## Product outcome

The new interface must let a user position subtitles without knowing ASS field
names or numeric alignment codes. Layout must remain proportional across
landscape, portrait, square, 720p, 1080p, and 4K videos.

The dynamically generated --style-* interface is removed by the breaking CLI
cutover. This is a deliberate compatibility break; internal ASS fields remain
an implementation detail.

The next major-version increment removes the public `--layout` preset layer.
Position, margins, maximum dimensions, and exact coordinates remain explicit;
completed preset plans are retained below as v2 implementation history.

## Plan status

This table is the source of truth for the package. Status values follow the
[plan catalog vocabulary](../README.md#status-vocabulary).

| Order | Plan | Status | Depends on | Delivery |
| --- | --- | --- | --- | --- |
| 0 | [Shared foundation](00-foundation.md) | Done | — | [#7](https://github.com/denilson-santos/multisubs/pull/7) |
| 1 | [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md) | Done | 0 | [#8](https://github.com/denilson-santos/multisubs/pull/8) |
| 2 | [Named positions](02-named-positions.md) | Done | 0, 1 | [#10](https://github.com/denilson-santos/multisubs/pull/10) |
| 3 | [Relative units](03-relative-units.md) | Done | 0, 1 | [#12](https://github.com/denilson-santos/multisubs/pull/12) |
| 4 | [Layout presets](04-layout-presets.md) | Done | 0–3 | [#13](https://github.com/denilson-santos/multisubs/pull/13) |
| 5 | [Custom coordinates](05-custom-coordinates.md) | Done | 0–3 | [#15](https://github.com/denilson-santos/multisubs/pull/15) |
| 6 | [Adaptive line wrapping](06-adaptive-line-wrapping.md) | Done | 0, 1, 3, 4 | [#33](https://github.com/denilson-santos/multisubs/pull/33) |
| 7 | [Placement modes and maximum height](07-placement-modes-and-maximum-height.md) | Done | 0–6 | [#35](https://github.com/denilson-santos/multisubs/pull/35) |
| 8 | [Layout preview](08-layout-preview.md) | Done | 0–7 | [#37](https://github.com/denilson-santos/multisubs/pull/37) |
| 9 | [Remove layout presets and use explicit defaults](09-remove-layout-presets.md) | In review | 0–8 | [#54](https://github.com/denilson-santos/multisubs/pull/54), [#55](https://github.com/denilson-santos/multisubs/pull/55), [#56](https://github.com/denilson-santos/multisubs/pull/56), `fix/reject-ineffective-margins` |

Package progress: 9 of 10 plans done. Feature 9's core implementation merged
through pull requests #54–#56; its final ineffective-margin validation is in
review on `fix/reject-ineffective-margins` for v3.0.0. Features 0–8 remain
complete implementation history.

## Delivery-gate status

Delivery gates are tracked separately from feature progress.

| Gate | Status | Depends on | Delivery |
| --- | --- | --- | --- |
| Breaking CLI cutover | Done | Plans 0–3 | [#29](https://github.com/denilson-santos/multisubs/pull/29) |
| Major-version release | Done | CLI cutover | [#30](https://github.com/denilson-santos/multisubs/pull/30), [v2.0.0](https://github.com/denilson-santos/multisubs/releases/tag/v2.0.0) |
| Preset removal and v3 release | Planned | Plan 9 | — |

Version 2.0.0 was promoted from staged `main` commit
`23667649c5baf9d1a64d6d7d266ec6272ccb49ae` without rebuilding through the
[successful production workflow](https://github.com/denilson-santos/multisubs/actions/runs/32383865271).

## Target CLI

Appearance:

~~~
--font Roboto
--font-size 4%
--text-color '#FFFFFF'
--bold
--italic
--backdrop box
--backdrop-color '#00000099'
--backdrop-size 0px
--shadow-size 4%
--fonts-dir ./fonts
~~~

Layout:

~~~
--position bottom-center
--margin-left 18%
--margin-right 18%
--margin-top 0%
--margin-bottom 5%
--max-width 100%
--max-height 10%
~~~

Feature 9 makes those values the universal native defaults and removes
aspect-ratio preset selection. `--position` changes only semantic alignment;
it does not select hidden margins or maximum dimensions.

Exact placement:

~~~
--position-x 50%
--position-y 86%
--anchor bottom-center
--max-width 72%
--max-height 14%
~~~

Named `--position` values use native ASS style alignment and margins. In that
mode, percentage `max-width` uses the width left after horizontal margins and is
optional; `100%` means all of that remaining width. `max-height` replaces a
fixed line count and supplies the vertical budget from which line capacity is
derived.

Custom X/Y coordinates use the full PlayRes canvas, reject explicitly supplied
margins, and require an explicit anchor, max-width, and max-height. Retained
native margin defaults compile to zero. The complete requested envelope must fit
the canvas for the selected anchor; it is rejected rather than silently shrunk
or moved. Only this explicit mode emits private ASS `\an`/`\pos` event placement.

Preview:

~~~
--preview-layout
--preview-at 00:00:10.500
--preview-text "Subtitle preview"
--preview-guides
~~~

## Configuration precedence after Feature 9

Configuration must be resolved in this order:

1. Built-in appearance defaults.
2. Built-in native layout field defaults.
3. Explicit command-line overrides.
4. Placement-mode selection and explicit-field presence validation.
5. Conversion of relative units after video geometry is known.
6. Final mode-specific cross-field validation.

An explicit option always wins over its matching default. Conflicting modes
produce an argument error before model loading; there is no hidden preset or
silent precedence between incompatible options.

## Delivery milestones

### Milestone 1: predictable placement

- Shared foundation.
- Video geometry and ASS canvas.
- Relative units.
- Named positions.

### Milestone 2: layout controls

- Presets.
- Custom coordinates.
- Adaptive wrapping.
- Native/explicit placement separation and maximum-height envelopes.

### Milestone 3: editing feedback

- Layout preview (Done).

### Milestone 4: explicit configuration

- Remove public layout presets and automatic aspect classification (In review).
- Publish the breaking contract in v3.0.0 after staging succeeds.

## Commit strategy

Use one focused implementation branch and pull request per numbered plan. The
suggested branch and commit subjects in each plan are defaults, not substitutes
for describing the actual change.

Commit rules for this package:

- Use an imperative subject, preferably with the prefixes recommended in
  docs/conventions.md: feat:, fix:, docs:, test:, refactor:, or chore:.
- Keep behavior and its focused tests in the same commit when practical.
- Isolate behavior-preserving structural changes in refactor: commits.
- Keep documentation updates reviewable in docs: commits.
- Do not leave WIP, fixup, generated media, model artifacts, or unrelated
  formatting commits in the final pull-request history.
- Every commit should leave the package importable and the focused test subset
  passing.
- Never combine two numbered plans in one pull request unless their documents
  are updated to explain why independent delivery became unsafe.

## Pull-request strategy

The default is one pull request per numbered plan, opened only after its
dependencies are merged. A dependent stacked pull request is acceptable when it
clearly identifies its base and is rebased after the dependency merges.

Implementation pull requests target `main` through the repository's GitHub Flow.
The package release uses the staged-artifact and version-tag process in
[delivery.md](../../delivery.md) after the package is complete and verified.

Each pull request must contain:

- A link to its plan document.
- The user-visible outcome.
- Included and excluded scope.
- CLI, Python API, JSON, SRT, ASS, and output-layout impact.
- FFmpeg/FFprobe, hardware, performance, and dependency impact.
- Tests added and exact verification commands run.
- Documentation changed.
- Before/after preview evidence when rendered geometry changes.
- Migration notes when an existing option or default changes.
- Remaining risks or follow-up plans.

Before final review:

1. Complete every acceptance criterion in the plan or document an explicit
   exception.
2. Change the dashboard row to In review and add the pull-request link.
3. Run the plan's focused tests and the repository pre-merge checks.
4. Confirm that generated previews and local media were not committed.
5. Rebase on the merged dependency and resolve documentation conflicts.

After merge, update the row to Done, recalculate package progress, and identify
the next unblocked plan.

## Branch, commit, and PR workflow

Start from an updated `main` branch, replacing the example branch with the
one specified by the individual plan:

~~~
git switch main
git pull --ff-only origin main
git switch -c feat/example-plan
~~~

Before staging a commit:

~~~
git status --short
git diff --check
git diff
~~~

Stage only the files that belong to the current logical change. Avoid git add -A
when the worktree contains unrelated user changes. Commit with the subject
suggested by the plan, adjusted to describe the actual diff:

~~~
git add path/to/implementation.py path/to/test.py
git diff --cached
git commit -m "feat: implement one focused behavior"
~~~

Before opening the pull request:

~~~
python -m compileall multisubs
python -m pytest
python -m ruff check .
python -m pyright
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
~~~

Run only tools installed and configured for the project, and record anything not
run in the pull-request description. Push the branch and create the pull request
through the repository interface or GitHub CLI:

~~~
git push -u origin feat/example-plan
gh pr create \
  --base main \
  --head feat/example-plan \
  --title "feat: implement one focused behavior" \
  --body-file /path/to/completed-pr-description.md
~~~

Do not use --fill without reviewing the generated description. The PR body must
be completed from the package template below and link the individual plan.

## Breaking CLI cutover

The final interface intentionally removes --style-* options, but intermediate
pull requests must not leave the main branch without an equivalent usable
appearance and positioning path.

Use a temporary internal adapter while the new typed configuration is being
assembled. Remove the old arguments in a dedicated cutover commit after
foundation, geometry, named positions, and relative units are complete and
tested together.

Suggested cutover pull request:

~~~
Title: feat!: replace raw ASS style options with subtitle layout controls
Branch: feat/subtitle-layout-cli-cutover
Base: main
~~~

The cutover pull request must:

- [x] Remove the temporary adapter and obsolete tests.
- [x] Update every public CLI example.
- [x] Document the old-to-new option mapping and changed defaults.
- [x] Mark the change for a major semantic-version release.
- [x] Verify multisubs --help from a built wheel in a clean environment.

The cutover merged through pull request #29. Version 2.0.0 then shipped through
the separate release pull request #30, an approved staging candidate, and an
annotated tag on that exact staged `main` commit. Production promoted the staged
files without rebuilding them. Features 6–8 can ship as backward-compatible
`2.x` increments when their final public and output contracts remain compatible
with v2.0.0; Feature 7 deliberately corrects Feature 6's untagged transitional
placement behavior before the next release.

## Pull-request description template

~~~
## Summary

- Plan:
- User-visible outcome:

## Scope

- Included:
- Excluded:

## Contract impact

- CLI:
- Python API:
- JSON/SRT/ASS:
- FFmpeg/FFprobe:
- Dependencies and performance:

## Verification

- [ ] Focused unit tests
- [ ] Full hermetic test suite
- [ ] Compile and CLI smoke checks
- [ ] Ruff and Pyright
- [ ] Relevant FFmpeg/libass integration tests
- [ ] Package build and metadata check

Commands and results:

## Documentation

- [ ] README
- [ ] PRD
- [ ] Architecture
- [ ] Conventions, when applicable

## Visual evidence

- Before:
- After:

## Migration and risks

- Migration:
- Known risks:
- Follow-ups:
~~~

## Definition of done

Every feature increment must:

- Add or update hermetic unit tests.
- Add an opt-in FFmpeg/libass integration test when rendered behavior changes.
- Update README.md for user-visible options.
- Update docs/prd.md when a requirement or acceptance criterion changes.
- Update docs/architecture.md when the pipeline, data model, or ASS contract
  changes.
- Update docs/conventions.md when the configuration or test conventions change.
- Reject invalid input before loading WhisperX whenever video analysis is not
  required for that validation.
- Preserve collision-safe publication and temporary-file cleanup.
- Preserve safe escaping of all transcription-derived ASS text.
- Pass the project verification commands documented in the repository
  instructions.

## Common verification matrix

At minimum, rendered layout changes must be exercised against:

| Geometry | Example size | Additional case |
| --- | --- | --- |
| Landscape | 1920x1080 | 1280x720 and 4K scaling |
| Portrait | 1080x1920 | Rotation metadata instead of stored portrait pixels |
| Square | 1080x1080 | Preset boundary ratios |
| Non-square pixels | Small synthetic fixture | Sample aspect ratio handling |

Text fixtures must include Portuguese, long unbroken tokens, CJK, right-to-left
text, emoji, braces, backslashes, commas, and explicit line breaks.
