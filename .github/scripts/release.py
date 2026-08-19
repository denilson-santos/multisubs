"""Validate immutable staging artifacts before a GitHub release promotion."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_STABLE_TAG = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_STAGING_WORKFLOW_PATH = ".github/workflows/staging.yml@main"


class ReleaseValidationError(ValueError):
    """Report a release input that cannot be promoted safely."""


def validate_release_tag(tag: str, package_version: str) -> None:
    """Require a stable vX.Y.Z tag matching the package source of truth."""
    if _STABLE_TAG.fullmatch(tag) is None:
        raise ReleaseValidationError(
            f"release tag {tag!r} must use the stable vX.Y.Z format"
        )
    expected = f"v{package_version}"
    if tag != expected:
        raise ReleaseValidationError(
            f"release tag {tag!r} does not match package version {package_version!r}"
        )


def select_staging_artifact(
    payload: Mapping[str, Any], artifact_name: str
) -> Mapping[str, Any]:
    """Select the newest non-expired staging artifact with an owning run."""
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReleaseValidationError("GitHub artifact response has no artifacts list")

    candidates: list[Mapping[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        workflow_run = artifact.get("workflow_run")
        if (
            artifact.get("name") == artifact_name
            and artifact.get("expired") is False
            and isinstance(artifact.get("id"), int)
            and isinstance(workflow_run, Mapping)
            and isinstance(workflow_run.get("id"), int)
        ):
            candidates.append(artifact)

    if not candidates:
        raise ReleaseValidationError(
            f"no non-expired staging artifact named {artifact_name!r} was found"
        )
    return max(
        candidates,
        key=lambda artifact: (
            str(artifact.get("created_at", "")),
            int(artifact["id"]),
        ),
    )


def validate_staging_run(
    payload: Mapping[str, Any], repository: str, target_sha: str
) -> str:
    """Require a successful staging run from main for the requested candidate."""
    source_sha = payload.get("head_sha")
    source_repository = payload.get("repository")
    if (
        payload.get("path") != _STAGING_WORKFLOW_PATH
        or payload.get("head_branch") != "main"
        or payload.get("status") != "completed"
        or payload.get("conclusion") != "success"
        or payload.get("event") not in {"push", "workflow_dispatch"}
        or not isinstance(source_sha, str)
        or _FULL_SHA.fullmatch(source_sha) is None
        or not isinstance(source_repository, Mapping)
        or source_repository.get("full_name") != repository
    ):
        raise ReleaseValidationError(
            "artifact owner must be a successful staging workflow run from main"
        )
    if payload.get("event") == "push" and source_sha != target_sha:
        raise ReleaseValidationError(
            "push-triggered staging run does not match the promoted commit"
        )
    return source_sha


def validate_distribution(directory: Path, package_version: str) -> tuple[str, ...]:
    """Require one wheel, one source archive, and their checksum manifest."""
    if not directory.is_dir():
        raise ReleaseValidationError(
            f"distribution directory does not exist: {directory}"
        )
    filenames = tuple(
        sorted(path.name for path in directory.iterdir() if path.is_file())
    )
    wheel_prefix = f"multisubs-{package_version}-"
    expected_wheels = [
        name
        for name in filenames
        if name.startswith(wheel_prefix) and name.endswith(".whl")
    ]
    source_name = f"multisubs-{package_version}.tar.gz"
    expected = sorted((*expected_wheels, source_name, "SHA256SUMS"))
    if len(expected_wheels) != 1 or list(filenames) != expected:
        raise ReleaseValidationError(
            "distribution must contain exactly one matching wheel, one matching "
            "source archive, and SHA256SUMS"
        )
    return filenames


def validate_draft_release(
    payload: Mapping[str, Any], tag: str, target_sha: str
) -> None:
    """Allow a rerun to resume only the matching unpublished draft."""
    if payload.get("tagName") != tag:
        raise ReleaseValidationError("existing release tag does not match the request")
    if payload.get("isDraft") is not True:
        raise ReleaseValidationError(
            f"release {tag!r} is already published and will not be modified"
        )
    body = payload.get("body")
    if not isinstance(body, str) or f"Source SHA: {target_sha}" not in body:
        raise ReleaseValidationError(
            "existing draft does not record the requested source SHA"
        )


def validate_release_assets(
    payload: Mapping[str, Any], expected_filenames: Sequence[str]
) -> None:
    """Require the draft to contain exactly the verified distribution files."""
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ReleaseValidationError("release response has no assets list")
    actual = sorted(
        asset["name"]
        for asset in assets
        if isinstance(asset, Mapping) and isinstance(asset.get("name"), str)
    )
    expected = sorted(expected_filenames)
    if actual != expected:
        raise ReleaseValidationError(
            "release assets differ from verified files: "
            f"expected {expected}, got {actual}"
        )


def _read_json() -> Mapping[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, Mapping):
        raise ReleaseValidationError("expected a JSON object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    tag_parser = subparsers.add_parser("validate-tag")
    tag_parser.add_argument("--tag", required=True)
    tag_parser.add_argument("--version", required=True)

    artifact_parser = subparsers.add_parser("select-artifact")
    artifact_parser.add_argument("--name", required=True)

    staging_run_parser = subparsers.add_parser("validate-staging-run")
    staging_run_parser.add_argument("--repository", required=True)
    staging_run_parser.add_argument("--sha", required=True)

    distribution_parser = subparsers.add_parser("validate-dist")
    distribution_parser.add_argument("--directory", type=Path, required=True)
    distribution_parser.add_argument("--version", required=True)

    draft_parser = subparsers.add_parser("validate-draft")
    draft_parser.add_argument("--tag", required=True)
    draft_parser.add_argument("--sha", required=True)

    assets_parser = subparsers.add_parser("validate-assets")
    assets_parser.add_argument("filenames", nargs="+")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one release validation command."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-tag":
            validate_release_tag(args.tag, args.version)
        elif args.command == "select-artifact":
            artifact = select_staging_artifact(_read_json(), args.name)
            workflow_run = artifact["workflow_run"]
            print(f"staging_artifact_id={artifact['id']}")
            print(f"staging_run_id={workflow_run['id']}")
        elif args.command == "validate-staging-run":
            source_sha = validate_staging_run(_read_json(), args.repository, args.sha)
            print(f"staging_source_sha={source_sha}")
        elif args.command == "validate-dist":
            for filename in validate_distribution(args.directory, args.version):
                print(filename)
        elif args.command == "validate-draft":
            validate_draft_release(_read_json(), args.tag, args.sha)
        elif args.command == "validate-assets":
            validate_release_assets(_read_json(), args.filenames)
        else:  # pragma: no cover - argparse guarantees a known command
            raise AssertionError(f"unknown command: {args.command}")
    except (OSError, json.JSONDecodeError, ReleaseValidationError) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
