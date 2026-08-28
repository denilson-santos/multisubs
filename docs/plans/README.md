# Implementation plan catalog

This directory groups implementation plans by product or architecture area.
Each package must contain a README.md that is the source of truth for its plan
statuses, dependencies, implementation pull requests, and delivery order.

## Packages

| Package | Status | Progress | Current plan | Package dashboard |
| --- | --- | ---: | --- | --- |
| Subtitle positioning | Done | 9/9 | Complete | [Open dashboard](subtitle-positioning/README.md) |
| Karaoke subtitles | Done | 1/1 | Complete | [Open dashboard](karaoke-subtitles/README.md) |
| Delivery automation | Done | 1/1 | Complete | [Open dashboard](delivery-automation/README.md) |
| Subtitle typography | In review | 0/5 | Font weight | [Open dashboard](subtitle-typography/README.md) |

Progress includes foundation plans when they are required delivery work.

## Required package dashboard

Every direct child directory must keep a README.md containing:

- Package objective and scope.
- One row for every plan.
- Current status and blocking dependencies.
- Delivery branch while work is active or in review, replaced by the merged
  pull-request link when the plan is Done.
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
| In review | The recorded delivery branch is complete and ready for or undergoing pull-request review. |
| Done | The implementation and documentation are merged. |
| Blocked | Work cannot proceed; the dashboard must name the blocker. |
| Cancelled | The plan will not be implemented; retain its decision history. |

## Updating status

- Update the package dashboard in the same branch that starts a plan.
- Record the task branch as the delivery reference while implementation is in
  progress.
- In the final documentation commit before opening the pull request, move the
  plan to In review and retain the branch reference. Do not add a post-open
  commit solely to record the pull-request number or URL.
- After merge, use the next package-status update to move the plan to Done and
  replace the branch reference with the merged pull-request link.
- Keep the package-level row above consistent with its child dashboard.
- Never infer progress only from commits; record it explicitly.
