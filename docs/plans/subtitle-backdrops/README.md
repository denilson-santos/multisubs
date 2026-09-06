# Subtitle backdrops roadmap

Status: In review

## Objective and scope

Use one measured vector surface for every cue-level `backdrop=box`, so one
line and multiple lines share padding, placement, and independent animation
rules. Preserve glyph outlines and the existing word-decoration contract.

## Plans and progress

Progress: 0/1 plans complete. Current plan: Plan 0. No blocking dependencies.

| Plan | Status | Dependencies | Delivery |
| --- | --- | --- | --- |
| [0 — Unified vector box](00-unified-vector-box.md) | In review | Completed line-height and independent-animation foundations | `refactor/unify-box-backdrop` |

## Delivery order and strategy

Implement Plan 0 as one focused pull request against `main`, with behavior and
regression tests together and a final documentation commit. The active delivery
branch is `refactor/unify-box-backdrop`.

Complete local implementation and verification before requesting explicit Git
delivery confirmation under [AGENTS.md](../../../AGENTS.md). After confirmation,
the final pre-PR documentation commit moves the plan, package, and catalog to
`In review`, retaining the task branch as delivery reference. Push the complete
branch before opening a draft PR. After an authoritative merge signal, update
all statuses to `Done`, progress to 1/1, and delivery to the merged PR link.

## Shared definition of done

- Box text and background consume the same resolved layout geometry.
- Hermetic contracts and controlled FFmpeg/libass renders verify static,
  animated, timed-word, fallback, and preview behavior.
- Plain transcript/timing and artifact lifecycle stay stable; the default cue
  and word backdrop padding use the documented proportional `25%` value.
- README, PRD, architecture, and render diagnostics describe the new behavior.
- Historical plans remain preserved; Plan 0 explicitly identifies superseded
  single-event compatibility promises.
