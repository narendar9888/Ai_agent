"""Base tool definitions, metadata, outcome classification, and security enforcement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import re
import shlex


class ToolCategory(str, Enum):
    EXPLORATION = "exploration"
    UNDERSTANDING = "understanding"
    MODIFICATION = "modification"
    EXECUTION = "execution"
    VERIFICATION = "verification"


class ToolOutcome(str, Enum):
    HIGH_PROGRESS = "HIGH_PROGRESS"
    MEDIUM_PROGRESS = "MEDIUM_PROGRESS"
    LOW_PROGRESS = "LOW_PROGRESS"
    NO_PROGRESS = "NO_PROGRESS"
    FAILURE = "FAILURE"
    BLOCKED = "BLOCKED"
    VERIFICATION_SUCCESS = "VERIFICATION_SUCCESS"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"


@dataclass
class ToolMetadata:
    name: str
    category: ToolCategory
    description: str
    parameters: Dict[str, Any]
    estimated_token_cost: int
    estimated_time_ms: int
    risk: float = 0.05
    capabilities: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: str
    outcome: ToolOutcome = ToolOutcome.NO_PROGRESS
    tokens_consumed: int = 0
    execution_time_ms: int = 0
    new_files: List[str] = field(default_factory=list)
    new_symbols: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    confidence_delta: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool_name,
            "success": self.success,
            "outcome": self.outcome.value,
            "tokens": self.tokens_consumed,
            "time_ms": self.execution_time_ms,
            "new_files_count": len(self.new_files),
            "new_symbols_count": len(self.new_symbols),
            "error": self.error_message,
        }


class SecurityError(Exception):
    """Raised when an operation violates security policy."""
    pass


class SecurityManager:
    """Enforces sandbox boundary, path traversal limits, and command safety."""

    def __init__(
        self,
        workspace_dir: Path,
        allowed_commands: Optional[List[str]] = None,
        forbidden_patterns: Optional[List[str]] = None,
        max_output_chars: int = 15000,
        timeout_seconds: int = 45,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.allowed_commands = allowed_commands or [
            "pytest", "python", "python3", "git", "cat", "ls", "grep",
            "find", "head", "tail", "cargo", "npm", "node", "make", "echo"
        ]
        self.forbidden_patterns = forbidden_patterns or [
            "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "chmod -R 777 /",
            "> /dev/sda", "shutdown", "reboot", "curl | bash", "wget | bash"
        ]
        self.max_output_chars = max_output_chars
        self.timeout_seconds = timeout_seconds

    def validate_path(self, path_str: str) -> Path:
        """Validates that a path stays inside the workspace boundary."""
        target = (self.workspace_dir / path_str).resolve()
        try:
            target.relative_to(self.workspace_dir)
        except ValueError:
            raise SecurityError(
                f"Path traversal blocked: '{path_str}' is outside workspace boundary '{self.workspace_dir}'"
            )
        return target

    def validate_command(self, cmd_str: str) -> List[str]:
        """Validates shell command safety against allowlist and forbidden patterns."""
        for pattern in self.forbidden_patterns:
            if pattern in cmd_str:
                raise SecurityError(f"Command contains forbidden pattern: '{pattern}'")

        parts = shlex.split(cmd_str)
        if not parts:
            raise SecurityError("Empty command string.")

        base_bin = Path(parts[0]).name
        if base_bin not in self.allowed_commands:
            raise SecurityError(
                f"Binary '{base_bin}' is not in the allowed command list: {self.allowed_commands}"
            )
        return parts

    def truncate_output(self, text: str) -> str:
        """Truncates excessive output to keep token consumption and context manageable."""
        if len(text) > self.max_output_chars:
            omitted = len(text) - self.max_output_chars
            return text[:self.max_output_chars] + f"\n... [Truncated {omitted} characters for context conservation]"
        return text


class BaseTool(ABC):
    """Abstract base class for all repository and execution tools."""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        pass

    @abstractmethod
    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        pass

    def estimate_tokens(self, output: str) -> int:
        """Rough estimation: ~4 chars per token."""
        return max(1, len(output) // 4)
