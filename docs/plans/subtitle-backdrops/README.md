# Subtitle backdrops roadmap

Status: Done

## Objective and scope

Use one measured vector surface for every cue-level `backdrop=box`, so one
line and multiple lines share padding, placement, and independent animation
rules. Preserve glyph outlines and the existing word-decoration contract.

## Plans and progress

Progress: 1/1 plans complete. Current plan: Complete. No blocking dependencies.

| Plan | Status | Dependencies | Delivery |
| --- | --- | --- | --- |
| [0 — Unified vector box](00-unified-vector-box.md) | Done | Completed line-height and independent-animation foundations | [PR #67](https://github.com/denilson-santos/multisubs/pull/67) |

## Delivery order and strategy

Plan 0 was delivered against `main` through PR #67. The user confirmed its
merge and successful Actions runs. The following delivery rules remain the
historical strategy for this package.

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
