# Delivery automation roadmap

Status: In progress

This package migrates multisubs from a long-lived `dev` integration branch to
GitHub Flow and promotes one verified commit through GitHub environments.

## Plan status

| Order | Plan | Status | Depends on | Branch or pull request |
| --- | --- | --- | --- | --- |
| 0 | [GitHub Flow and environment pipelines](00-github-flow-and-environment-pipelines.md) | In progress | Final `dev` to `main` reconciliation | `chore/github-flow-automation` |

Package progress: 0 of 1 plans done; Plan 0 is being implemented locally.

## Delivery order

1. Reconcile the merged PR #15 and remaining `dev` content into `main`.
2. Open the automation pull request against the reconciled `main` and observe a
   successful development workflow.
3. Configure environments and rulesets without replacing unrelated settings.
4. Merge, approve staging, and run the non-publishing production rehearsal.
5. Delete the retired remote `dev` and already-merged remote topic branches.

## Delivery strategy

Use branch `chore/github-flow-automation` and one pull request titled
`chore: adopt GitHub Flow and environment pipelines` against `main`. Keep the
formatting baseline, Python contract, workflow implementation, and documentation
in focused commits. Stage, commit, push, repository-setting changes, and branch
deletion require the explicit delivery confirmation described in `AGENTS.md`.

## Definition of done

- `main` is the only long-lived branch and accepts squash-merged pull requests
  only after the required development gate.
- Staging verifies Python 3.10/3.13, FFmpeg/libass, packaging, clean installation,
  checksums, and provenance before retaining the candidate.
- Production promotes the same files, supports a safe rehearsal, and cannot
  overwrite a published release.
- Runtime behavior and JSON/SRT/ASS contracts are unchanged; supported Python is
  accurately declared as 3.10–3.13.
- Local verification, the bootstrap pull request, staging, environment settings,
  and branch cleanup are recorded before the plan is marked Done.
