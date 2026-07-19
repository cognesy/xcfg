"""Structural and behavioural tests for the release pipeline.

A release runs rarely and fails expensively, so the pieces are checked here
rather than discovered when a tag fires. Two halves:

* the version checker actually catches every mismatch it claims to;
* the workflow is wired in the order that makes those checks meaningful --
  validate, then gate, then build, then publish.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
CHECKER = REPO_ROOT / "tools" / "check_release_version.py"

sys.path.insert(0, str(REPO_ROOT))
from tools.check_release_version import check, normalize_tag, package_version  # noqa: E402

# -- the version checker --------------------------------------------------


def test_declared_version_is_readable() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", package_version())


def test_declared_version_matches_the_installed_package() -> None:
    import xcfg

    assert xcfg.__version__ == package_version()


def test_matching_tag_passes() -> None:
    assert check(f"v{package_version()}") == []


def test_tag_without_the_v_prefix_passes() -> None:
    assert check(package_version()) == []


def test_mismatched_tag_is_caught() -> None:
    problems = check("v99.99.99")
    assert any("declares" in problem for problem in problems)


def test_non_semver_tag_is_caught() -> None:
    problems = check("v1.2")
    assert any("MAJOR.MINOR.PATCH" in problem for problem in problems)


def test_empty_tag_is_rejected() -> None:
    with pytest.raises(SystemExit):
        normalize_tag("   ")


def test_checker_exits_nonzero_on_mismatch() -> None:
    """The workflow relies on the exit code, not the output."""
    result = subprocess.run(
        [sys.executable, str(CHECKER), "v99.99.99"], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "error:" in result.stderr


def test_checker_exits_zero_on_match() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECKER), f"v{package_version()}"], capture_output=True, text=True
    )
    assert result.returncode == 0


# -- the workflow ---------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict[Any, Any]:
    assert WORKFLOW.is_file(), "release workflow is missing"
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_workflow_triggers_on_version_tags(workflow: dict[Any, Any]) -> None:
    # `on` parses as the boolean True in YAML 1.1.
    triggers = workflow.get(True, workflow.get("on"))
    assert isinstance(triggers, dict), "workflow declares no triggers"
    assert "v*.*.*" in triggers["push"]["tags"]
    assert "workflow_dispatch" in triggers


def test_release_job_validates_before_building(workflow: dict[Any, Any]) -> None:
    """Order matters: a stale version must fail before artifacts exist."""
    steps = workflow["jobs"]["release"]["steps"]
    commands = [step.get("run", "") for step in steps]
    validate = next(i for i, c in enumerate(commands) if "check_release_version.py" in c)
    build = next(i for i, c in enumerate(commands) if "uv build" in c)
    assert validate < build


def test_release_job_runs_the_quality_gate(workflow: dict[Any, Any]) -> None:
    commands = " ".join(step.get("run", "") for step in workflow["jobs"]["release"]["steps"])
    for expected in ("ruff check", "mypy", "pytest"):
        assert expected in commands


def test_release_job_attaches_both_artifacts(workflow: dict[Any, Any]) -> None:
    steps = workflow["jobs"]["release"]["steps"]
    release_step = next(s for s in steps if "action-gh-release" in str(s.get("uses", "")))
    files = release_step["with"]["files"]
    assert "dist/*.whl" in files
    assert "dist/*.tar.gz" in files


def test_publishing_is_opt_in(workflow: dict[Any, Any]) -> None:
    """A PyPI upload cannot be undone, so a tag push alone must not publish."""
    publish = workflow["jobs"]["publish"]
    assert publish["if"] == "${{ inputs.publish }}"


def test_publish_uses_trusted_publishing_not_a_token(workflow: dict[Any, Any]) -> None:
    publish = workflow["jobs"]["publish"]
    assert publish["permissions"]["id-token"] == "write"
    commands = " ".join(step.get("run", "") for step in publish["steps"])
    assert "--trusted-publishing" in commands
    assert "PYPI_TOKEN" not in WORKFLOW.read_text(encoding="utf-8")


def test_changelog_has_an_entry_for_the_current_version() -> None:
    """The workflow extracts release notes from this heading."""
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{package_version()}]" in changelog
