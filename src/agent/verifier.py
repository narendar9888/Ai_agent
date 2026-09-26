"""Deterministic verifier for autonomous software engineering tasks."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..tools.base import BaseTool, SecurityManager, ToolOutcome
from .state import PlannerState, VerificationStatus


@dataclass
class VerificationResult:
    status: str  # "VERIFIED" or "FAILED"
    tests_passed: bool
    build_passed: bool
    changed_files: int
    tool_calls: int
    tokens: int
    execution_seconds: float
    diff_summary: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "tests_passed": self.tests_passed,
            "build_passed": self.build_passed,
            "changed_files": self.changed_files,
            "tool_calls": self.tool_calls,
            "tokens": self.tokens,
            "execution_seconds": round(self.execution_seconds, 2),
            "diff_summary": self.diff_summary[:200],
            "error": self.error_message,
        }


class DeterministicVerifier:
    """
    Implements deterministic verification per PS Section 28:
    Validates git diff + build status + test suite execution.
    Never relies on LLM verbal claims of correctness.
    """

    def __init__(self, run_tests: bool = True, run_build: bool = True):
        self.run_tests_enabled = run_tests
        self.run_build_enabled = run_build

    def verify(
        self,
        state: PlannerState,
        tools: Dict[str, BaseTool],
        security: SecurityManager,
        target_test: str = ""
    ) -> VerificationResult:
        build_passed = True
        tests_passed = True
        error_msg = None
        changed_files_count = 0
        diff_text = ""

        # 1. Deterministic Git Diff Check
        if "git_diff" in tools:
            diff_res = tools["git_diff"].execute({}, state.workspace_dir, security)
            diff_text = diff_res.output
            if "git_status" in tools:
                status_res = tools["git_status"].execute({}, state.workspace_dir, security)
                changed_files_count = len(status_res.new_files)
            else:
                changed_files_count = len(state.modified_files)

        # If no files changed at all, implementation is incomplete
        if changed_files_count == 0 and not state.modified_files and ("No uncommitted modifications" in diff_text or not diff_text):
            return VerificationResult(
                status="FAILED",
                tests_passed=False,
                build_passed=False,
                changed_files=0,
                tool_calls=state.step_counter,
                tokens=state.budget.used_tokens,
                execution_seconds=state.budget.used_seconds,
                diff_summary="No changes were made to repository files.",
                error_message="Verification failed: No modified files detected in workspace."
            )

        # 2. Deterministic Build / Syntax Verification
        if self.run_build_enabled and "run_build" in tools:
            build_res = tools["run_build"].execute({}, state.workspace_dir, security)
            build_passed = build_res.success
            if not build_passed:
                error_msg = f"Build verification failed: {build_res.error_message or build_res.output[:200]}"

        # 3. Deterministic Test Suite Verification
        if self.run_tests_enabled and build_passed and "run_tests" in tools:
            test_res = tools["run_tests"].execute(
                {"target": target_test} if target_test else {},
                state.workspace_dir,
                security
            )
            tests_passed = (test_res.outcome == ToolOutcome.VERIFICATION_SUCCESS) or test_res.success
            if not tests_passed:
                error_msg = f"Test suite failed: {test_res.error_message or test_res.output[:200]}"

        is_verified = build_passed and tests_passed and (changed_files_count > 0 or len(state.modified_files) > 0)
        status_str = "VERIFIED" if is_verified else "FAILED"

        state.verification_status = (
            VerificationStatus.VERIFIED_PASS if is_verified else VerificationStatus.VERIFIED_FAIL
        )

        return VerificationResult(
            status=status_str,
            tests_passed=tests_passed,
            build_passed=build_passed,
            changed_files=max(changed_files_count, len(state.modified_files)),
            tool_calls=state.step_counter,
            tokens=state.budget.used_tokens,
            execution_seconds=state.budget.used_seconds,
            diff_summary=diff_text[:300] if diff_text else "Modifications present",
            error_message=error_msg,
        )
