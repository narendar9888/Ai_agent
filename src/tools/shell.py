"""Execution tool: run_command with security allowlist and sandbox boundaries."""

import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager, SecurityError


class RunCommandTool(BaseTool):
    """Executes safe commands in the repository directory."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="run_command",
            category=ToolCategory.EXECUTION,
            description="Run an allowed shell command in the repository workspace.",
            parameters={
                "command": {"type": "string", "required": True, "description": "Shell command to execute"}
            },
            estimated_token_cost=800,
            estimated_time_ms=1500,
            risk=0.20,
            capabilities=["command-execution", "environment-interaction"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        cmd_str = args.get("command", "").strip()

        if not cmd_str:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: Empty command provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Empty command"
            )

        try:
            parts = security.validate_command(cmd_str)
        except SecurityError as se:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Security violation: {str(se)}",
                outcome=ToolOutcome.BLOCKED,
                execution_time_ms=duration_ms,
                error_message=str(se)
            )

        try:
            proc = subprocess.run(
                cmd_str,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=security.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            stdout_clean = proc.stdout.strip()
            stderr_clean = proc.stderr.strip()

            combined = []
            if stdout_clean:
                combined.append(f"STDOUT:\n{stdout_clean}")
            if stderr_clean:
                combined.append(f"STDERR:\n{stderr_clean}")

            full_output = "\n".join(combined) if combined else f"Command exited with code {proc.returncode} (no output)."
            full_output = security.truncate_output(full_output)
            tokens = self.estimate_tokens(full_output)

            success = (proc.returncode == 0)
            outcome = ToolOutcome.HIGH_PROGRESS if success else ToolOutcome.FAILURE

            return ToolResult(
                tool_name=self.metadata.name,
                success=success,
                output=full_output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                error_message=stderr_clean if not success else None
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Command timed out after {security.timeout_seconds} seconds.",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=duration_ms,
                error_message="Timeout expired"
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error executing command: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=duration_ms,
                error_message=str(e)
            )
