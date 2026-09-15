# Subtitle preview roadmap

Status: Done

## Objective and scope

Use the available multiline envelope correctly, then let users inspect one
animated subtitle in a silent MP4 with deterministic simulated word times.
Retain the static PNG preview for layout inspection.

## Plans and progress

Progress: 2/2 plans complete. Plans 0 and 1 are merged in PRs #68 and #69.

| Plan | Status | Dependencies | Delivery |
| --- | --- | --- | --- |
| [0 — Multiline capacity](00-multiline-capacity.md) | Done | Completed preview and vector-box foundations | [PR #68](https://github.com/denilson-santos/multisubs/pull/68) |
| [1 — Animated preview clip](01-animation-clip.md) | Done | Plan 0; completed independent animations | [PR #69](https://github.com/denilson-santos/multisubs/pull/69) |

## Delivery order and strategy

Plan 0 preceded Plan 1; both are complete. Scope any future preview work in a
new plan.

## Shared definition of done

- PNG and clip select the same first display cue from the same layout inputs.
- Simulated timing stays isolated from transcription and never claims speech sync.
- ASS geometry, effects, fonts, escaping, and rendering use production contracts.
- Tests cover capacity boundaries, timing, real FFmpeg output, and failure cleanup.
- Current user/product/architecture documents describe delivered behavior;
  generated media remain outside version control.
