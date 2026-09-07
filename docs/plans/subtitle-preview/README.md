# Subtitle preview roadmap

Status: In review

## Objective and scope

Use the available multiline envelope correctly, then let users inspect one
animated subtitle in a silent MP4 with deterministic simulated word times.
Retain the static PNG preview for layout inspection.

## Plans and progress

Progress: 1/2 plans complete. Current plan: Plan 1. Plan 1 depends on Plan 0;
there are no external blockers.

| Plan | Status | Dependencies | Delivery |
| --- | --- | --- | --- |
| [0 — Multiline capacity](00-multiline-capacity.md) | Done | Completed preview and vector-box foundations | [PR #68](https://github.com/denilson-santos/multisubs/pull/68) |
| [1 — Animated preview clip](01-animation-clip.md) | In review | Plan 0; completed independent animations | `feat/animation-preview-clip` |

## Delivery order and strategy

Deliver Plan 0 first, then Plan 1, as separate focused draft PRs against `main`.
The active branch for Plan 1 is `feat/animation-preview-clip`, based on the
merged PR 68 commit in `origin/main`. Keep behavior and tests together, followed by
current documentation and roadmap updates. Branch names are implementation
instructions, not requests to create branches during planning.

Follow [AGENTS.md](../../../AGENTS.md) and [delivery](../../delivery.md).
Complete local work before requesting Git delivery confirmation. In the final
pre-PR documentation commit mark the active plan/package/catalog `In review`
and record the task branch; push before opening the PR. Do not add a commit
solely to record its URL. After confirmed merge, mark that plan `Done`, record
the merged PR, recalculate progress, and select the next plan. Keep the package
`Planned` while its next implementation has not begun, and `Done` at 2/2.

## Shared definition of done

- PNG and clip select the same first display cue from the same layout inputs.
- Simulated timing stays isolated from transcription and never claims speech sync.
- ASS geometry, effects, fonts, escaping, and rendering use production contracts.
- Tests cover capacity boundaries, timing, real FFmpeg output, and failure cleanup.
- Current user/product/architecture documents describe delivered behavior;
  generated media remain outside version control.
