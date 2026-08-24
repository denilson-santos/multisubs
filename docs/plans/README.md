# Implementation plan catalog

This directory groups implementation plans by product or architecture area.
Each package must contain a README.md that is the source of truth for its plan
statuses, dependencies, implementation pull requests, and delivery order.

## Packages

| Package | Status | Progress | Current plan | Package dashboard |
| --- | --- | ---: | --- | --- |
| Subtitle positioning | In progress | 7/9 | Placement modes and maximum height | [Open dashboard](subtitle-positioning/README.md) |
| Karaoke subtitles | Planned | 0/1 | Word-timed highlighting | [Open dashboard](karaoke-subtitles/README.md) |
| Delivery automation | Done | 1/1 | Complete | [Open dashboard](delivery-automation/README.md) |

Progress includes foundation plans when they are required delivery work.

## Required package dashboard

Every direct child directory must keep a README.md containing:

- Package objective and scope.
- One row for every plan.
- Current status and blocking dependencies.
- Implementation branch or pull-request link when one exists.
- Recommended delivery order.
- Package-specific commit and pull-request strategy.
- Cross-cutting definition of done.

Do not duplicate detailed implementation tasks in the dashboard. Those belong in
the individual plan documents.

## Status vocabulary

Use only these values:

| Status | Meaning |
| --- | --- |
| Proposed | Scope or design is still awaiting a decision. |
| Planned | Design is accepted and implementation has not started. |
| In progress | Implementation work is active. |
| In review | A pull request is open and acceptance checks are pending. |
| Done | The implementation and documentation are merged. |
| Blocked | Work cannot proceed; the dashboard must name the blocker. |
| Cancelled | The plan will not be implemented; retain its decision history. |

## Updating status

- Update the package dashboard in the same branch that starts a plan.
- Add the pull-request link as soon as it exists.
- Move a plan to In review before requesting final review.
- Move a plan to Done after merge through the next package-status update.
- Keep the package-level row above consistent with its child dashboard.
- Never infer progress only from commits; record it explicitly.
