"""Modification tools: edit_file and apply_patch."""

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager


class EditFileTool(BaseTool):
    """Applies a controlled string replacement or file creation/overwrite."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="edit_file",
            category=ToolCategory.MODIFICATION,
            description="Edit a file by replacing old_text with new_text, or create/overwrite with content.",
            parameters={
                "path": {"type": "string", "required": True, "description": "Relative path to file"},
                "old_text": {"type": "string", "description": "Exact text segment to replace"},
                "new_text": {"type": "string", "description": "Replacement text segment"},
                "content": {"type": "string", "description": "Complete file content if creating or overwriting entirely"}
            },
            estimated_token_cost=800,
            estimated_time_ms=150,
            risk=0.10,
            capabilities=["code-modification", "file-creation"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        path_str = args.get("path", "")
        old_text = args.get("old_text")
        new_text = args.get("new_text", "")
        content = args.get("content")

        if not path_str:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: No file path provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Missing path"
            )

        try:
            target_path = security.validate_path(path_str)

            # Case 1: Direct content write (creating or rewriting file)
            if content is not None:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                duration_ms = int((time.time() - start_time) * 1000)
                output = f"Successfully wrote {len(content)} characters to '{path_str}'."
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=True,
                    output=output,
                    outcome=ToolOutcome.HIGH_PROGRESS,
                    tokens_consumed=self.estimate_tokens(output),
                    execution_time_ms=duration_ms,
                    new_files=[path_str],
                )

            # Case 2: String replacement
            if not target_path.exists():
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"Error: Cannot edit '{path_str}' because file does not exist. Use 'content' argument to create it.",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message=f"File not found: '{path_str}'"
                )

            if old_text is None:
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output="Error: Either 'old_text' or 'content' must be provided.",
                    outcome=ToolOutcome.FAILURE,
                    error_message="Missing old_text/content"
                )

            with open(target_path, "r", encoding="utf-8") as f:
                current_content = f.read()

            if old_text not in current_content:
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"Target text was not found in '{path_str}'. Verify line endings, indentation, and exact wording.",
                    outcome=ToolOutcome.NO_PROGRESS,
                    execution_time_ms=duration_ms,
                    error_message="Target string not found in file."
                )

            occurrences = current_content.count(old_text)
            if occurrences > 1:
                # Replace only first instance or warn
                updated_content = current_content.replace(old_text, new_text, 1)
                warning = f" (Note: {occurrences} occurrences found; replaced the first occurrence)."
            else:
                updated_content = current_content.replace(old_text, new_text)
                warning = ""

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            duration_ms = int((time.time() - start_time) * 1000)
            output = f"Successfully edited '{path_str}'{warning}."

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=ToolOutcome.HIGH_PROGRESS,
                tokens_consumed=self.estimate_tokens(output),
                execution_time_ms=duration_ms,
                new_files=[path_str],
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error editing '{path_str}': {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )


class ApplyPatchTool(BaseTool):
    """Applies a unified patch/diff to repository files."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apply_patch",
            category=ToolCategory.MODIFICATION,
            description="Apply a unified diff / patch to the repository.",
            parameters={
                "patch": {"type": "string", "required": True, "description": "Unified diff / patch text"}
            },
            estimated_token_cost=900,
            estimated_time_ms=250,
            risk=0.15,
            capabilities=["patch-application", "batch-modification"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        patch_text = args.get("patch", "")

        if not patch_text.strip():
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: Empty patch provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Empty patch"
            )

        try:
            # Try git apply
            cmd = ["git", "apply", "--whitespace=nowarn", "-"]
            proc = subprocess.run(
                cmd,
                input=patch_text,
                text=True,
                capture_output=True,
                cwd=workspace_dir,
                timeout=security.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            if proc.returncode == 0:
                output = "Patch successfully applied."
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=True,
                    output=output,
                    outcome=ToolOutcome.HIGH_PROGRESS,
                    tokens_consumed=self.estimate_tokens(output),
                    execution_time_ms=duration_ms,
                )
            else:
                err_msg = proc.stderr.strip() or proc.stdout.strip()
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"Git apply failed: {err_msg}",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=duration_ms,
                    error_message=err_msg
                )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error applying patch: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )
