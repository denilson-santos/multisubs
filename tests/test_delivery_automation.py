import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / ".github" / "scripts" / "release.py"
VERIFY_WORKFLOW_PATH = (
    Path(__file__).parents[1] / ".github" / "workflows" / "_verify.yml"
)
SPEC = importlib.util.spec_from_file_location("release_validation", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
release_validation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_validation)

ReleaseValidationError = release_validation.ReleaseValidationError


def test_shared_builder_cleans_dist_immediately_before_build():
    commands = [
        line.strip()
        for line in VERIFY_WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
    ]
    build_index = commands.index("python -m build")

    assert commands[build_index - 1] == "rm -rf dist"


@pytest.mark.parametrize(
    "tag",
    ["1.2.3", "v1.2", "v1.2.3-rc1", "v01.2.3", "release-v1.2.3"],
)
def test_release_tag_requires_stable_semver(tag):
    with pytest.raises(ReleaseValidationError, match="stable vX.Y.Z"):
        release_validation.validate_release_tag(tag, "1.2.3")


def test_release_tag_must_match_package_version():
    with pytest.raises(ReleaseValidationError, match="does not match"):
        release_validation.validate_release_tag("v1.2.4", "1.2.3")


def test_release_tag_accepts_matching_package_version():
    release_validation.validate_release_tag("v1.2.3", "1.2.3")


def test_select_staging_artifact_uses_newest_live_match():
    selected = release_validation.select_staging_artifact(
        {
            "artifacts": [
                {
                    "id": 1,
                    "name": "staging-abc",
                    "expired": False,
                    "created_at": "2026-08-18T10:00:00Z",
                    "workflow_run": {"id": 11},
                },
                {
                    "id": 2,
                    "name": "staging-abc",
                    "expired": True,
                    "created_at": "2026-08-18T12:00:00Z",
                    "workflow_run": {"id": 12},
                },
                {
                    "id": 3,
                    "name": "staging-abc",
                    "expired": False,
                    "created_at": "2026-08-18T11:00:00Z",
                    "workflow_run": {"id": 13},
                },
            ]
        },
        "staging-abc",
    )

    assert selected["id"] == 3


def test_select_staging_artifact_rejects_missing_candidate():
    with pytest.raises(ReleaseValidationError, match="no non-expired"):
        release_validation.select_staging_artifact({"artifacts": []}, "staging-abc")


def _staging_run(**overrides):
    payload = {
        "path": ".github/workflows/staging.yml",
        "head_branch": "main",
        "head_sha": "a" * 40,
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "repository": {"full_name": "owner/multisubs"},
    }
    payload.update(overrides)
    return payload


def test_staging_run_requires_successful_main_workflow_for_push():
    source_sha = release_validation.validate_staging_run(
        _staging_run(), "owner/multisubs", "a" * 40
    )

    assert source_sha == "a" * 40


def test_staging_run_allows_approved_dispatch_to_rebuild_older_main_sha():
    source_sha = release_validation.validate_staging_run(
        _staging_run(event="workflow_dispatch"), "owner/multisubs", "b" * 40
    )

    assert source_sha == "a" * 40


@pytest.mark.parametrize(
    "overrides",
    [
        {"path": ".github/workflows/other.yml"},
        {"head_branch": "topic"},
        {"status": "in_progress", "conclusion": None},
        {"conclusion": "failure"},
        {"event": "pull_request"},
        {"repository": {"full_name": "other/repository"}},
    ],
)
def test_staging_run_rejects_untrusted_owner(overrides):
    with pytest.raises(ReleaseValidationError, match="successful staging"):
        release_validation.validate_staging_run(
            _staging_run(**overrides), "owner/multisubs", "a" * 40
        )


def test_push_staging_run_must_match_target_sha():
    with pytest.raises(ReleaseValidationError, match="promoted commit"):
        release_validation.validate_staging_run(
            _staging_run(), "owner/multisubs", "b" * 40
        )


def test_validate_distribution_requires_exact_versioned_files(tmp_path: Path):
    filenames = (
        "SHA256SUMS",
        "multisubs-1.2.3-py3-none-any.whl",
        "multisubs-1.2.3.tar.gz",
    )
    for filename in filenames:
        (tmp_path / filename).write_text("fixture", encoding="utf-8")

    assert release_validation.validate_distribution(tmp_path, "1.2.3") == filenames


def test_validate_distribution_rejects_extra_or_wrong_version(tmp_path: Path):
    for filename in (
        "SHA256SUMS",
        "multisubs-1.2.4-py3-none-any.whl",
        "multisubs-1.2.3.tar.gz",
        "unexpected.txt",
    ):
        (tmp_path / filename).write_text("fixture", encoding="utf-8")

    with pytest.raises(ReleaseValidationError, match="exactly one matching"):
        release_validation.validate_distribution(tmp_path, "1.2.3")


def test_draft_rerun_requires_matching_unpublished_release():
    release_validation.validate_draft_release(
        {
            "tagName": "v1.2.3",
            "isDraft": True,
            "body": "Source SHA: abc123",
        },
        "v1.2.3",
        "abc123",
    )


@pytest.mark.parametrize(
    "payload,message",
    [
        (
            {"tagName": "v1.2.3", "isDraft": False, "body": "Source SHA: abc"},
            "already published",
        ),
        (
            {"tagName": "v1.2.3", "isDraft": True, "body": "Source SHA: other"},
            "requested source SHA",
        ),
    ],
)
def test_draft_rerun_rejects_unsafe_existing_release(payload, message):
    with pytest.raises(ReleaseValidationError, match=message):
        release_validation.validate_draft_release(payload, "v1.2.3", "abc")


def test_release_assets_must_exactly_match_verified_distribution():
    payload = json.loads('{"assets": [{"name": "package.whl"}]}')

    release_validation.validate_release_assets(payload, ["package.whl"])

    with pytest.raises(ReleaseValidationError, match="differ"):
        release_validation.validate_release_assets(
            payload, ["package.whl", "source.tar.gz"]
        )
