# Plan 0: GitHub Flow and environment pipelines

Status: Done

Pull request: [#17](https://github.com/denilson-santos/multisubs/pull/17)

Depends on:

- Final reconciliation of `dev` into `main`, including merged PR #15.

## Objective

Give maintainers one protected GitHub Flow branch and a traceable promotion path
that builds a distribution once in staging and publishes the identical files in
production.

## Scope

Included:

- GitHub Flow documentation and repository-setting contract.
- Development, staging, and production GitHub Actions environments.
- Python 3.10/3.13 validation and accurate package metadata.
- Attested GitHub-hosted wheel/sdist artifacts and stable GitHub Releases.
- A production rehearsal and safe draft-release resumption.

Excluded:

- PyPI, TestPyPI, containers, cloud deployment, GPU runners, and real WhisperX
  model downloads.
- Mandatory second-person review while the repository has one maintainer.
- Rewriting historical completed-plan references to their original `dev` base.

## Decisions and constraints

- `main` is the only long-lived branch; environment names do not map to branches.
- Pull requests use squash merge and the aggregate development gate.
- Staging approval and production approval use `denilson-santos` with self-review
  allowed.
- Actions are pinned by full SHA, pull-request permissions are read-only, and no
  package registry credential is introduced.
- Staging artifacts expire after 90 days. Historical candidates must be rebuilt
  from a full SHA still reachable from `main`.

## Public interface and contracts

`requires-python` changes from `>=3.10` to `>=3.10,<3.14`, matching WhisperX
3.8.6. CLI flags, Python call signatures, JSON/SRT/ASS formats, output layout,
rendering, and artifact cleanup are unchanged.

The automation interface consists of pull requests to `main`, optional staging
rebuilds from a full main SHA, stable `vX.Y.Z` tags, and non-publishing production
rehearsals from a staged SHA.

## Implementation

- Reuse one trusted verification workflow for both development and staging.
- Build and attest the distribution only in staging; identify it by the complete
  source SHA and retain its checksum manifest.
- Let production discover the newest live artifact for that exact SHA, verify
  its trusted signer and checksums, and pass verified files to a release-only
  job with `contents: write`.
- Keep tag, version, artifact, file-set, draft, and release-asset validation in a
  small Python script covered by hermetic tests.

## Implementation tasks

- [x] Create the authorized implementation branch from the latest `dev` content.
- [x] Establish the Ruff formatting baseline required by development CI.
- [x] Add Python 3.10/3.13 development verification and an aggregate gate.
- [x] Add approved staging builds, FFmpeg/libass tests, clean installation,
      checksums, attestation, and 90-day artifact retention.
- [x] Add production validation, rehearsal, immutable promotion, and safe draft
      publication.
- [x] Add hermetic release-validation tests and Dependabot for Actions.
- [x] Update Python compatibility, GitHub Flow, delivery, and active-plan docs.
- [x] Complete the available local verification on Python 3.10; leave the
      Python 3.13 run to the development matrix.
- [x] Rebase onto the reconciled `main`.
- [x] Obtain delivery approval, commit, push, open the pull request, and record
      its link.
- [x] Configure GitHub settings, approve staging, run production rehearsal, and
      retire merged remote branches.

## Unit tests

- Stable tag syntax and package-version equality.
- Missing, expired, malformed, and duplicate staging artifacts.
- Successful staging-run ownership, source revision, and event validation.
- Exact wheel/sdist/checksum file set and package version.
- Matching draft resumption; rejection of a published or wrong-SHA release.
- Exact release asset names.

## Integration and manual verification

- Run the existing hermetic suite on Python 3.10 and 3.13 in development.
- Run all FFmpeg/libass integration tests and clean wheel installation in staging.
- Run production rehearsal against the staged migration SHA.
- Confirm invalid tags, non-main SHAs, absent artifacts, bad checksums, and bad
  attestations fail before publication.

## Documentation

- Update README, PRD, conventions, AGENTS, plan guidance, and active dashboards.
- Keep the complete branch protection, environment, release, recovery, and
  rollback procedure in `docs/delivery.md`.

## Commit and pull-request plan

Suggested branch:

~~~
chore/github-flow-automation
~~~

Suggested commits:

1. `chore: establish the CI formatting baseline`
2. `chore: align the supported Python range`
3. `ci: validate pull requests for development`
4. `ci: promote verified release artifacts`
5. `docs: adopt GitHub Flow delivery guidance`

Suggested pull request:

~~~
Title: chore: adopt GitHub Flow and environment pipelines
Base: main
~~~

Before requesting review, run every local check below, rebase on the reconciled
`main`, change this plan and dashboard to `In review`, and add the pull-request
link. Do not apply repository settings until the development workflow succeeds.

## Acceptance criteria

- A pull request to `main` cannot merge without the development aggregate gate.
- A merge to `main` waits for staging approval and produces one attested artifact
  containing exactly a wheel, sdist, and checksum manifest.
- Production rehearsal verifies that artifact without a release; a valid stable
  tag publishes the same files after approval and without rebuilding.
- Published releases, invalid tags, version mismatches, non-main commits,
  missing artifacts, checksum failures, and provenance failures are safe failures.
- `main` becomes the only long-lived remote branch after explicit cleanup
  approval, while local backup branches remain untouched.
