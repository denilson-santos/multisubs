# Multilingual subtitle correctness

Status: In review

## Objective and scope

Correct the overlapping Japanese subtitles reported on 2026-09-09, preserve
language-appropriate text and boundaries, and verify other supported writing
systems through the same production and preview pipeline. Only the added
central subtitle in the reported video is evidence for this package.

The package covers font coverage and measurement, source-text preservation,
lexical grouping of aligned characters, Unicode line breaking, timed effects,
bidirectional/shaped text, and a reproducible multilingual render matrix.
Speech-recognition accuracy, new source languages, translation targets, and a
subtitle editor are excluded. Plan 0 established the reproducible foundation
and was merged as [PR #75](https://github.com/denilson-santos/multisubs/pull/75).
Plan 1 implemented the production font correction and was merged as
[PR #76](https://github.com/denilson-santos/multisubs/pull/76). Plan 2 implemented
lossless source-text and alignment mapping and was merged as
[PR #77](https://github.com/denilson-santos/multisubs/pull/77). Plan 3 implemented
linguistic cue/line boundaries while preserving alignment-record timing for
word text and backdrop highlights and was merged as
[PR #78](https://github.com/denilson-santos/multisubs/pull/78). Plan 4 now makes
effects and previews safe for shaping-sensitive and bidirectional text.

## Plans and progress

Progress: 3/6 plans merged. Current plan: Plan 4, in review on
`fix/shaping-safe-subtitle-effects`.
Regression fixtures, local replay tooling, and backend evaluation are
available. Plan 4 is active; Plan 5 has not started. Plan 0 records the selected
libraries and their limits.

| Plan | Status | Dependencies | Delivery |
| --- | --- | --- | --- |
| [0 — Regressions and backend decisions](00-regressions-and-decisions.md) | Done | Existing source and completed layout/font/animation foundations | [PR #75](https://github.com/denilson-santos/multisubs/pull/75) |
| [1 — Font coverage and consistent metrics](01-font-coverage-and-metrics.md) | Done | Plan 0 | [PR #76](https://github.com/denilson-santos/multisubs/pull/76) |
| [2 — Lossless text and alignment mapping](02-text-and-alignment-mapping.md) | Done | Plan 0 | [PR #77](https://github.com/denilson-santos/multisubs/pull/77) |
| [3 — Linguistic boundaries and record-timed highlights](03-linguistic-cues-and-timing.md) | Done | Plans 1 and 2 | [PR #78](https://github.com/denilson-santos/multisubs/pull/78) |
| [4 — Shaping-safe effects and previews](04-shaping-effects-and-previews.md) | In progress | Plans 1, 2, and 3 | `fix/shaping-safe-subtitle-effects` |
| [5 — Multilingual verification and rollout](05-verification-and-rollout.md) | Planned | Plans 0–4 | Not started |

## Delivery order and milestones

Recommended sequence: **0 → 1 → 2 → 3 → 4 → 5**. Plans 1 and 2 are
architecturally independent after Plan 0, but sequential implementation avoids
conflicting edits in orchestration and models.

| Milestone | Required plans | Observable outcome |
| --- | --- | --- |
| Reproducible diagnosis | 0 | Synthetic reproductions, executable checks, and backend decisions recorded |
| Font defect corrected | 1 | Japanese glyphs receive matching measured/rendered spacing |
| Text and timing corrected | 2–3 | Korean spaces survive; Japanese groups guide cue/line cuts while highlights preserve alignment-record timing |
| Safe presentation across scripts | 4 | Effects and previews preserve shaping or explicitly use a tested fallback |
| Release evidence complete | 5 | Multilingual visual, artifact, and clean-install gates pass |

## Relationship to existing plans

The completed [wrapping plan](../subtitle-positioning/06-adaptive-line-wrapping.md),
[font catalog](../subtitle-templates/00-bundled-ofl-font-catalog.md),
[typography](../subtitle-typography/README.md),
[animations](../subtitle-templates/03-cue-animations-and-animated-templates.md),
and [multiline selection](../subtitle-preview/00-multiline-capacity.md) remain
historical delivery records. This package tightens their correctness contracts;
it does not reopen completed work or restore removed karaoke flags.

Prospective changes are explicit: family resolution alone will no longer prove
glyph coverage; alignment records will no longer define lexical words but will
remain the default word-effect timing units; CJK width will no longer imply
that spaces must be removed. Linguistic grouping selects cue/line boundaries
and representative preview content, while real or simulated effect units remain
an explicit, separate contract. The longest fitting prefix rule remains, but
only among linguistically legal candidates of equal priority.

The [animated preview plan](../subtitle-preview/01-animation-clip.md) still has
an older `In review` dashboard record. On 2026-09-09, an origin fetch and ancestry
checks verified preview implementation `106eaa2` and automatic detection
`1ce2100` are both present on base `9841330e94d4f72ae111548f5d1f18b9468a98e1`.
These capabilities are available for this implementation. Updating the older
package's delivery status is separate from this package; preserve its history.

## Delivery strategy

Use one focused draft PR per plan, each against updated `main` after its actual
prerequisites are present. Suggested branches, commits, and pull-request
content live in the individual plans. Git delivery follows the repository
approval and review rules.

Follow [AGENTS.md](../../../AGENTS.md) and [delivery](../../delivery.md): complete
implementation and verification before requesting explicit Git delivery
confirmation; do not stage, commit, push, or mutate PRs based on this plan alone.
After confirmation, deliver only scoped changes. The PR describes the problem,
included/excluded scope, public contracts, documentation, actual commands and
results, visual evidence, dependencies, and remaining limitations, and links
its individual plan.

Set the active plan/package/catalog to `In progress` when implementation starts.
In the final pre-PR documentation commit, set them to `In review` and record the
task branch as delivery reference. Push the complete branch before opening the
draft PR; add no post-open commit solely for the PR URL. After authoritative
merge evidence, mark that plan `Done`, replace its branch with the merged PR,
and recalculate progress. Keep the package `Proposed` while material decisions
remain; otherwise use `Planned` between increments and `Done` only at 6/6.

## Shared definition of done

- Every confirmed defect has a regression that fails on the old behavior and
  passes on the correction; suspected defects are classified by evidence.
- Font selection covers displayed text and agrees with actual libass output;
  unsupported rendering never silently claims exact metrics.
- Source text, meaningful separators, punctuation, word metadata, logical order,
  and timestamps are conserved; only display casing and intentional wrapping
  change presentation. Derived grouping never fabricates speech timestamps.
- A legal visual line break, including one inside a linguistic group, never
  disables effects for otherwise complete alignment records. Static fallback
  reports an actual invalid mapping or unsupported rendering capability.
- Preview PNG, simulated MP4, ordinary subtitles, and animated subtitles share
  font, text, layout, and render capability decisions.
- Current CLI flags/defaults, English-only translation, output naming,
  collision safety, retention, and cleanup are preserved except explicitly
  documented fallback/error changes.
- Hermetic, controlled-font FFmpeg, packaging, quality, and documentation gates
  pass. A skipped required render is missing evidence, not a passed language.
- User media/transcripts and generated assets remain local and untracked;
  fixtures committed for regression are synthetic, small, and licensed.
- Current documentation describes only delivered behavior. Font/dictionary
  dependencies receive provenance, license, size, offline, and compatibility
  checks before adoption. Recovery uses a normal fix/revert PR and a new release.
