"""File inspection and reading tool."""

import time
from pathlib import Path
from typing import Any, Dict

from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager


class ReadFileTool(BaseTool):
    """Reads specific line ranges or sections of a file with line numbering."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="read_file",
            category=ToolCategory.UNDERSTANDING,
            description="Read content from a file, optionally specifying start_line and end_line (1-indexed).",
            parameters={
                "path": {"type": "string", "required": True, "description": "Relative path to file"},
                "start_line": {"type": "integer", "default": 1, "description": "Start line (1-indexed)"},
                "end_line": {"type": "integer", "default": 50, "description": "End line (1-indexed)"},
            },
            estimated_token_cost=250,
            estimated_time_ms=70,
            risk=0.01,
            capabilities=["code-inspection", "context-gathering"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        path_str = args.get("path", "")
        start_line = max(1, int(args.get("start_line", 1)))
        end_line = int(args.get("end_line", start_line + 49 if "start_line" in args else 50))

        if not path_str:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: No file path provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Missing path"
            )

        try:
            file_path = security.validate_path(path_str)
            if not file_path.exists():
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"File not found: '{path_str}'",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message=f"File '{path_str}' does not exist."
                )

            if file_path.is_dir():
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"Error: '{path_str}' is a directory, not a file.",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Path is a directory."
                )

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            end_line = min(end_line, total_lines)

            if start_line > total_lines:
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=True,
                    output=f"File '{path_str}' has {total_lines} lines. Requested start_line {start_line} is beyond EOF.",
                    outcome=ToolOutcome.LOW_PROGRESS,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            selected_lines = lines[start_line - 1 : end_line]
            formatted_lines = [
                f"{line_idx}: {line.rstrip()}"
                for line_idx, line in enumerate(selected_lines, start=start_line)
            ]

            output = (
                f"File: {path_str} (Lines {start_line}-{end_line} of {total_lines}):\n"
                + "\n".join(formatted_lines)
            )
            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)
            duration_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=ToolOutcome.HIGH_PROGRESS,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                new_files=[path_str],
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error reading file '{path_str}': {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )
