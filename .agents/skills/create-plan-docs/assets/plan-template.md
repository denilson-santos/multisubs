# [Plan title]

Status: [Proposed or Planned]

Depends on:

- [Dependency](relative-plan.md)

## Objective

[Describe the user-visible outcome and why this increment exists.]

## Scope

Included:

- [Included behavior or contract.]

Excluded:

- [Explicit non-goal or deferred work.]

## Decisions and constraints

- [Accepted product or technical decision.]
- [Compatibility, validation, performance, privacy, or external-tool constraint.]

## Public interface and contracts

[Describe CLI, Python API, JSON/SRT/ASS, output-layout, configuration, error, and migration effects that apply. State explicitly when a surface is unaffected.]

## Implementation

- [Describe the affected component and intended responsibility.]
- [Describe data flow, validation timing, and failure behavior.]

## Implementation tasks

- [ ] [Small, verifiable implementation task.]
- [ ] [Focused tests for the behavior and failure paths.]
- [ ] [Required documentation and status updates.]

## Unit tests

- [Pure behavior, boundary, validation, and regression cases.]

## Integration and manual verification

- [External boundary or end-to-end scenario.]
- [Visual evidence or manual verification when automation is insufficient.]

## Documentation

- [README, PRD, architecture, conventions, migration, or help-text update.]

## Commit and pull-request plan

Suggested branch:

~~~
[type/short-plan-name]
~~~

Suggested commits:

1. `[type]: [focused imperative outcome]`
   - [Included implementation and verification.]
2. `docs: [document the user-visible outcome]`
   - [Included documentation and roadmap updates.]

Suggested pull request:

~~~
Title: [type]: [reviewable outcome]
Base: dev
~~~

Before requesting review:

- [Run focused verification.]
- [Run repository-wide checks required by the project.]
- [Update the package dashboard to In review and add the PR link.]

## Acceptance criteria

- [Observable, testable completed behavior.]
- [Relevant invalid or failure behavior.]
- [Documentation and compatibility outcome.]

## Open decisions

- [Delete this section when no material decision remains.]
