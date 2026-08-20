# Delivery workflow

## GitHub Flow

`main` is the only long-lived branch. Create a short-lived branch from the
latest `main`, open a pull request back to `main`, and merge it with a merge
commit, squash, or rebase after the required
`Development / development-gate` check succeeds. Delete the merged remote
branch automatically.

`development`, `staging`, and `production` are GitHub environments. They do not
have corresponding Git branches:

| Environment | Source | Approval | Result |
| --- | --- | --- | --- |
| development | Pull request to `main` | None | Required quality gate |
| staging | Commit in `main` or an explicit full SHA contained in `main` | `denilson-santos`; self-review allowed | Attested wheel, sdist, and checksums retained for 90 days |
| production | Stable version tag, or manual rehearsal from a staged SHA | `denilson-santos`; self-review allowed | GitHub Release for a tag; no publication during rehearsal |

Do not merge new work into `dev`. During the one-time migration, first merge the
remaining `dev` content into `main`. After the automation and protections are
verified, delete the remote `dev` branch and only those remote topic branches
that `git branch --remotes --merged origin/main` proves are incorporated. Keep
local `bkp_dev_*` branches unless their owner explicitly requests deletion.

## Workflows and permissions

- `development.yml` runs for pull requests to `main`, cancels stale runs for the
  same pull request, and exposes one stable aggregate check.
- `staging.yml` runs for pushes to `main`. Its manual input accepts only a full
  lowercase commit SHA that is an ancestor of `origin/main`. A newer staging
  request cancels an older candidate that has not completed.
- `production.yml` runs for `v*` tags and validates the stricter stable
  `vX.Y.Z` form. Manual dispatch is a non-publishing rehearsal.
- `_verify.yml` is the shared trusted builder. It tests Python 3.10 and 3.13 on
  `ubuntu-24.04`, uses CPU PyTorch wheels, and keeps FFmpeg/libass checks in
  staging.

All third-party workflow actions are pinned to full reviewed SHAs. Dependabot
may propose GitHub Actions updates, but each update must retain a full SHA and
be reviewed before merge. Repository token permissions default to read-only.
Only staging receives `id-token: write` and `attestations: write`; only the
production publication job receives `contents: write`. No workflow uses
`pull_request_target`, package-index token, or model credential.

## Repository settings

Apply these settings after the development workflow has completed successfully
on its bootstrap pull request.

Repository merge settings:

- Enable merge commits, squash merges, and rebase merges.
- Enable branch updates and automatic deletion of merged head branches.

Active `main` ruleset:

- Require a pull request and `Development / development-gate`.
- Require the branch to be current before merge and require conversation
  resolution.
- Allow merge, squash, and rebase without requiring linear history; block force
  pushes and branch deletion.
- Require zero approving reviews while the repository has only one maintainer.

Environment settings:

- `development`: no reviewers, secrets, or variables; allow pull-request refs.
- `staging`: allow `main`; require reviewer `denilson-santos`; do not prevent
  self-review.
- `production`: allow `main` for rehearsals and tags matching `v*` for releases;
  require reviewer `denilson-santos`; do not prevent self-review.

Add an active tag ruleset for `v*` that blocks updates and deletion. Do not
require signed tags until every release operator has a documented signing setup.

Before changing settings, list current rulesets, environments, variables, and
secrets. Merge rather than replace unrelated configuration. Record the final
settings and the successful bootstrap run in the pull-request description.

## Version and release procedure

1. Update `multisubs.__version__` in a normal pull request using semantic
   versioning. The version is the package source of truth.
2. Merge the pull request into `main` and approve its staging job.
3. Confirm staging completed, including hermetic tests, FFmpeg/libass tests,
   clean wheel installation, checksums, provenance attestation, and artifact
   upload.
4. Create and push an annotated stable tag that matches the version:

   ~~~
   git tag -a v1.2.3 -m "Release v1.2.3" <staged-main-sha>
   git push origin v1.2.3
   ~~~

5. Approve the production environment. Production locates
  `staging-<full-sha>`, downloads it without rebuilding, validates the exact
  file set and checksums, confirms its owning staging run succeeded from
  `main`, and verifies that the exact trusted shared-workflow revision signed
  every artifact.
6. Production creates a draft containing the wheel, source archive, and
   `SHA256SUMS`, validates those asset names, and then publishes it as the latest
   GitHub Release. It never publishes to PyPI.

## Recovery and rollback

- Run the production manual dispatch with a staged full SHA to rehearse the
  complete lookup, download, checksum, and provenance path without creating a
  release.
- If a staging artifact expires, manually dispatch staging with the exact full
  SHA while it remains reachable from `main`, approve the rebuild, and rerun the
  production rehearsal before recreating the tag-triggered run.
- If production stops after creating a draft, rerun the tag workflow. It may
  resume only when the draft records the same tag and `Source SHA`; it replaces
  only the three expected asset names. A published release is never modified.
- If a tag has no valid staging artifact, points outside `main`, uses an invalid
  format, or differs from the package version, production fails before obtaining
  release-write permission.
- If a published release is faulty, revert or fix the code through a pull
  request and publish a new semantic patch version. Never move or delete a
  published version tag as a rollback mechanism.
