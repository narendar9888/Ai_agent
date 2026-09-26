"""Tests for deterministic verification (PS Section 28)."""

from pathlib import Path
import subprocess
from src.agent.state import PlannerState
from src.agent.verifier import DeterministicVerifier
from src.tools import get_default_tools
from src.tools.base import SecurityManager


def setup_git_repo(path: Path):
    subprocess.run(["git", "init", "-q"], cwd=path)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path)
    (path / "file.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=path)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=path)


def test_verifier_fails_when_no_changes(tmp_path: Path):
    setup_git_repo(tmp_path)
    state = PlannerState(task_description="Fix bug", workspace_dir=tmp_path)
    tools = get_default_tools()
    security = SecurityManager(workspace_dir=tmp_path)
    verifier = DeterministicVerifier(run_tests=False, run_build=False)

    res = verifier.verify(state, tools, security)
    assert res.status == "FAILED"
    assert "No modified files" in (res.error_message or "")


def test_verifier_passes_with_changes_and_valid_build(tmp_path: Path):
    setup_git_repo(tmp_path)
    # Make a modification
    (tmp_path / "file.txt").write_text("modified content")

    state = PlannerState(task_description="Fix bug", workspace_dir=tmp_path)
    state.modified_files.add("file.txt")
    tools = get_default_tools()
    security = SecurityManager(workspace_dir=tmp_path)

    verifier = DeterministicVerifier(run_tests=False, run_build=True)
    res = verifier.verify(state, tools, security)

    assert res.status == "VERIFIED"
    assert res.build_passed is True
    assert res.changed_files >= 1
