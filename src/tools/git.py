"""Git operations: git_status and git_diff."""

import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager


class GitStatusTool(BaseTool):
    """Returns repository Git working tree status."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_status",
            category=ToolCategory.UNDERSTANDING,
            description="Inspect git working tree status (untracked, modified, and staged files).",
            parameters={},
            estimated_token_cost=300,
            estimated_time_ms=100,
            risk=0.01,
            capabilities=["git-inspection", "state-tracking"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        try:
            proc = subprocess.run(
                ["git", "status", "--short"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=security.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if proc.returncode != 0:
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"git status error: {proc.stderr.strip()}",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=duration_ms,
                    error_message=proc.stderr.strip()
                )

            raw = proc.stdout.strip()
            modified = []
            if raw:
                for line in raw.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        modified.append(parts[1])
                output = f"Git status:\n{raw}"
                outcome = ToolOutcome.MEDIUM_PROGRESS
            else:
                output = "Working tree clean. No modified or untracked files."
                outcome = ToolOutcome.LOW_PROGRESS

            tokens = self.estimate_tokens(output)
            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                new_files=modified,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error executing git status: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )


class GitDiffTool(BaseTool):
    """Returns current repository git diff against HEAD."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_diff",
            category=ToolCategory.UNDERSTANDING,
            description="View git diff showing uncommitted changes in the repository.",
            parameters={
                "path": {"type": "string", "default": "", "description": "Optional file path to limit diff"}
            },
            estimated_token_cost=500,
            estimated_time_ms=120,
            risk=0.01,
            capabilities=["diff-inspection", "verification"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        path_arg = args.get("path", "").strip()

        cmd = ["git", "diff"]
        if path_arg:
            security.validate_path(path_arg)
            cmd.append(path_arg)

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=security.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if proc.returncode != 0:
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"git diff error: {proc.stderr.strip()}",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=duration_ms,
                    error_message=proc.stderr.strip()
                )

            diff_output = proc.stdout.strip()
            if not diff_output:
                output = "No uncommitted modifications detected in git diff."
                outcome = ToolOutcome.LOW_PROGRESS
            else:
                output = f"Repository Diff:\n{diff_output}"
                outcome = ToolOutcome.HIGH_PROGRESS

            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error executing git diff: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )
