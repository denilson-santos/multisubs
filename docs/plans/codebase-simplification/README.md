# Codebase simplification roadmap

Status: In progress

## Objective and scope

Make the current Python implementation, tests, and Markdown easier to change
without altering the public CLI, subtitle output, or runtime dependencies. The
work removes accidental complexity, repeated setup and assertions, obsolete
tests, and documentation that repeats another source of truth.

The baseline from `origin/main` at `6b64077` is 1,027 passing hermetic tests
with 75 integration tests deselected. Ruff and Pyright pass. Production has four
functions longer than 200 lines and 27 functions above Ruff's diagnostic
complexity of 10; Markdown contains about 97,000 words. These are audit signals,
not reasons to compress readable code or delete coverage mechanically.

## Plans and progress

| Order | Plan | Status | Depends on | Delivery |
| --- | --- | --- | --- | --- |
| 0 | [Configuration and request assembly](00-configuration-and-requests.md) | In progress | Current public contracts | `refactor/simplify-codebase` |
| 1 | [Text, measurement, and layout](01-text-and-layout.md) | In progress | Plan 0 | `refactor/simplify-codebase` |
| 2 | [ASS and animation rendering](02-ass-and-animation-rendering.md) | In progress | Plan 1 | `refactor/simplify-codebase` |
| 3 | [Transcription, preview, and media orchestration](03-pipeline-orchestration.md) | In progress | Plans 0–2 | `refactor/simplify-codebase` |
| 4 | [Test and documentation consolidation](04-tests-and-documentation.md) | In progress | Plans 0–3 | `refactor/simplify-codebase` |

Package progress: 0 of 5 plans delivered. Plans 0–4 are implemented and
verified locally; explicit delivery approval remains.

## Accepted constraints

- Preserve every documented CLI flag, default, validation order, output name,
  cleanup rule, JSON schema 3 field, SRT/ASS behavior, and template schema.
- Add no runtime dependency, framework, plug-in layer, service container, or
  speculative public abstraction.
- Prefer small pure helpers and existing module boundaries. Add an internal
  module only when it gives one stable responsibility a clear owner; retain
  compatibility imports for existing public Python entry points.
- Treat test age and count as neutral. Remove a test only when its contract is
  gone or another clearer test covers the same success, failure, and output
  boundary.
- Keep integration tests opt-in and do not run WhisperX transcription as a
  routine refactor check.
- Preserve all previously existing plan files and dashboards as history; only
  the new active refactor plan may be updated with implementation progress.

## Delivery order and strategy

Implement `0 -> 1 -> 2 -> 3 -> 4` as focused slices on the task branch
`refactor/simplify-codebase`, then prepare one pull request against `main` after
review. Keep behavior and focused tests together; structural commits must
remain importable and testable. Delivery changes still require user approval.

The first suggested branch is `refactor/simplify-codebase`; later branch names
are specified in their plans. Git staging, commits, pushes, and pull-request
changes still require the explicit delivery confirmation in `AGENTS.md`.

## Shared definition of done

- The complete hermetic suite, Ruff format/lint, Pyright, compile, and CLI help
  checks pass after every plan.
- The four functions initially longer than 200 lines have cohesive owners and
  are decomposed; a diagnostic Ruff C901 run reports no function above 20.
- Public behavior has characterization coverage before structural changes and
  focused tests assert project contracts rather than third-party internals.
- No test is removed without its replacement or obsolete contract being named
  in the implementing pull request.
- Active guidance has one owner per fact and stays below 24,000 words, excluding
  plan history. Preserve existing completed plans and dashboards unchanged.
- No media, transcript, model cache, generated subtitle, build artifact, or
  machine-specific path is committed.
