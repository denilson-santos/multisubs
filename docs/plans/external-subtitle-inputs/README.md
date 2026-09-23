# External subtitle inputs roadmap

Status: Planned

## Objective and scope

Support two ASR-free workflows: generate SRT and ASS from timed-cue JSON
using the input video's geometry and burn the generated ASS into that video,
or burn an existing SRT or ASS file into a copied video. The workflows have separate
public contracts and can be used independently.

## Plans and progress

Progress: 0/2 implementations complete. Both plans are accepted and ready
for implementation; implementation has not started. Plan documents merged in
[PR #95](https://github.com/denilson-santos/multisubs/pull/95).

| Plan | Status | Dependencies | Implementation delivery |
| --- | --- | --- | --- |
| [0 — Timed-cue JSON workflow](00-compile-timed-cue-json.md) | Planned | Existing layout, ASS, SRT, and FFmpeg contracts | Not started |
| [1 — Burn an external subtitle file](01-burn-external-subtitle-file.md) | Planned | Existing FFmpeg boundary; independent of Plan 0 | Not started |

## Delivery order and strategy

Implement Plan 0 first so its generated ASS and video can exercise Plan 1,
then deliver Plan 1 in its own focused pull request. Neither plan is a runtime
prerequisite of the other. Each plan proposes a short-lived branch from
current `main` and a draft pull request against `main` after explicit Git
delivery confirmation.

## Shared definition of done

- The current transcription and preview invocations retain their flags,
  defaults, artifacts, and ASR behavior.
- Both new modes validate inputs before expensive work, import no ASR runtime,
  and never overwrite or modify supplied video, JSON, SRT, or ASS files.
- Output publication remains collision-safe; failures leave no published
  partial artifact or unrelated cleanup.
- README, PRD, architecture, CLI help, and public Python docstrings describe
  each mode's actual input, output, style, and timing contract.
- Focused hermetic tests, FFmpeg integration tests, repository checks, and
  documented manual visual inspection cover the delivered behavior.
