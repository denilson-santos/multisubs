---
name: create-plan-docs
description: Create or revise multisubs implementation-plan documents under docs/plans, including package dashboards, statuses, dependencies, acceptance criteria, verification, commits, and pull-request guidance. Use when the user asks to plan, split, document, reprioritize, or update the delivery status of a feature, refactor, migration, or roadmap item in this repository.
---

# Create Plan Docs

Create implementation plans that are specific enough for another agent to execute and verify without rediscovering product decisions. Treat the repository documentation and current code as the source of truth.

## Keep planning separate from delivery

- Create or update planning documents only unless the user also requests implementation.
- Do not commit, push, create branches, or open pull requests unless the user explicitly requests those actions.
- Do not mark implementation tasks complete based only on a plan or proposal.
- Preserve completed and cancelled plans as decision history; do not delete them.

## Gather context

1. Read `AGENTS.md` completely.
2. Read `docs/plans/README.md` completely for the dashboard contract, status vocabulary, and lifecycle rules.
3. Read the target package dashboard and every plan whose scope or dependency affects the request.
4. Read the relevant portions of `README.md`, `docs/prd.md`, `docs/architecture.md`, and `docs/conventions.md` according to the documentation matrix in `AGENTS.md`.
5. Inspect the affected production code, tests, configuration, and package metadata. Base tasks and file references on the repository as it exists; do not plan against guessed architecture.
6. Check the current Git branch and worktree without modifying them. Use existing pull-request links and user-provided merge information when updating lifecycle status.

Ask a concise question only when an unresolved product choice would materially change the plan. Otherwise, record reasonable assumptions and continue.

## Choose the document changes

- For an existing plan, edit that plan and synchronize its package dashboard and the top-level catalog when their summaries change.
- For a new plan in an existing package, create a numbered Markdown document, add one dashboard row, and update dependencies, delivery order, milestones, and progress where applicable.
- For a new package, create `docs/plans/<package>/README.md`, create its plan documents, and add the package to `docs/plans/README.md`.
- Keep detailed implementation tasks in individual plan documents. Keep dashboards limited to objective, status, progress, dependencies, pull requests, delivery order, delivery strategy, and shared definition of done.
- Use [the plan template](assets/plan-template.md) as a starting point, adapting or omitting sections that do not apply.

## Develop the plan

Define and reconcile all of the following:

1. User-visible objective and measurable outcome.
2. Included scope, excluded scope, assumptions, and dependencies.
3. Public CLI, Python API, output, persistence, and compatibility effects.
4. Internal contracts, component boundaries, data flow, validation timing, and error behavior.
5. Implementation tasks ordered so intermediate commits remain coherent and testable.
6. Unit, integration, regression, and manual or visual verification proportional to the change.
7. Documentation updates required by `AGENTS.md`.
8. Security, privacy, performance, external-tool, migration, and rollback considerations when relevant.
9. Concrete acceptance criteria that describe observable completed behavior.

Resolve contradictions between a new plan and existing plans. Update every affected dependency reference instead of leaving incompatible roadmaps side by side.

## Plan Git and pull-request delivery

- Suggest a short branch name based on the change type and plan outcome.
- Target feature and maintenance pull requests to `dev` unless repository documentation establishes another base.
- Propose focused imperative commit subjects using the prefixes allowed by `docs/conventions.md`.
- Keep behavior and focused tests together when practical; separate structural refactors and documentation when that improves reviewability.
- Specify the exact focused and repository-wide verification commands relevant to the planned change.
- Require the pull-request description to link the plan, describe included and excluded scope, record contract impact, list commands actually run, identify documentation changes, and disclose remaining risks.
- Do not assume a pull request is merged from commits alone. Use an authoritative merge signal or explicit user confirmation before changing its status to `Done`.

## Maintain lifecycle status

Use only the exact vocabulary defined by `docs/plans/README.md`.

- Use `Proposed` while material scope or design decisions remain open.
- Use `Planned` once the design is accepted and implementation has not started.
- Change to `In progress` in the branch that begins implementation.
- Change to `In review` and record the pull-request link when review begins.
- Change to `Done` only after merge, then recalculate package and catalog progress.
- Use `Blocked` only with a named blocker and `Cancelled` only when retaining an abandoned decision.

Synchronize the individual plan heading, package dashboard, package progress text, current-plan summary, milestones, and top-level catalog in the same update. Never infer status from unchecked or checked boxes alone.

## Validate the documents

Before finishing:

1. Search for stale status, progress, feature-number, dependency, branch, and pull-request references.
2. Confirm every relative Markdown link resolves to an existing target.
3. Confirm every plan is represented exactly once in its package dashboard.
4. Confirm dependency order has no unintended cycle and names the actual prerequisites.
5. Confirm acceptance criteria are testable and implementation tasks cover tests and documentation.
6. Run `git diff --check` and inspect the complete diff.
7. Report the documents created or updated, important assumptions, remaining decisions, and verification performed.
