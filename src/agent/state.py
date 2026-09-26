"""State representation for ACTP: PlannerState, BudgetTracker, and ActionRecords."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import time

from ..tools.base import ToolOutcome


class TaskType(str, Enum):
    BUG_FIX = "BUG_FIX"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    TEST_FAILURE = "TEST_FAILURE"
    REFACTORING = "REFACTORING"
    GENERAL = "GENERAL"


class VerificationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFIED_PASS = "VERIFIED_PASS"
    VERIFIED_FAIL = "VERIFIED_FAIL"


@dataclass
class ActionRecord:
    step: int
    tool: str
    arguments: Dict[str, Any]
    outcome: ToolOutcome
    tokens_consumed: int
    duration_ms: int
    reason: str
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    output_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "arguments_summary": str(self.arguments)[:80],
            "outcome": self.outcome.value,
            "tokens": self.tokens_consumed,
            "duration_ms": self.duration_ms,
            "reason": self.reason,
            "error": self.error,
        }


@dataclass
class BudgetTracker:
    max_tool_calls: int = 40
    max_tokens: int = 50000
    max_seconds: int = 300

    used_tool_calls: int = 0
    used_tokens: int = 0
    used_seconds: float = 0.0

    @property
    def remaining_tool_calls(self) -> int:
        return max(0, self.max_tool_calls - self.used_tool_calls)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.max_seconds - self.used_seconds)

    @property
    def is_exhausted(self) -> bool:
        return (
            self.remaining_tool_calls <= 0
            or self.remaining_tokens <= 0
            or self.remaining_seconds <= 0.0
        )

    def record_usage(self, tool_calls: int, tokens: int, seconds: float):
        self.used_tool_calls += tool_calls
        self.used_tokens += tokens
        self.used_seconds += seconds

    def can_afford(self, estimated_tokens: int, estimated_time_ms: int) -> bool:
        if self.remaining_tool_calls < 1:
            return False
        # Allow reasonable flexibility for the last tool call
        if self.remaining_tokens < (estimated_tokens // 2):
            return False
        if self.remaining_seconds < (estimated_time_ms / 1000.0 * 0.5):
            return False
        return True


@dataclass
class PlannerState:
    task_description: str
    workspace_dir: Path
    task_type: TaskType = TaskType.GENERAL
    current_goal: str = ""
    phase: str = "exploration"  # exploration, diagnosis, implementation, verification, finished
    explored_files: Set[str] = field(default_factory=set)
    discovered_symbols: Set[str] = field(default_factory=set)
    modified_files: Set[str] = field(default_factory=set)
    previous_actions: List[ActionRecord] = field(default_factory=list)
    failed_actions: List[ActionRecord] = field(default_factory=list)
    successful_actions: List[ActionRecord] = field(default_factory=list)
    budget: BudgetTracker = field(default_factory=BudgetTracker)
    verification_status: VerificationStatus = VerificationStatus.NOT_STARTED
    finished: bool = False
    termination_reason: Optional[str] = None
    step_counter: int = 0

    def record_action(
        self,
        tool: str,
        arguments: Dict[str, Any],
        outcome: ToolOutcome,
        tokens: int,
        duration_ms: int,
        reason: str,
        error: Optional[str] = None,
        output_summary: str = "",
        new_files: Optional[List[str]] = None,
        new_symbols: Optional[List[str]] = None,
    ) -> ActionRecord:
        self.step_counter += 1
        record = ActionRecord(
            step=self.step_counter,
            tool=tool,
            arguments=arguments,
            outcome=outcome,
            tokens_consumed=tokens,
            duration_ms=duration_ms,
            reason=reason,
            error=error,
            output_summary=output_summary,
        )

        self.previous_actions.append(record)
        if outcome in (ToolOutcome.FAILURE, ToolOutcome.BLOCKED, ToolOutcome.NO_PROGRESS):
            self.failed_actions.append(record)
        else:
            self.successful_actions.append(record)

        if new_files:
            self.explored_files.update(new_files)
        if new_symbols:
            self.discovered_symbols.update(new_symbols)

        # Update budget
        self.budget.record_usage(
            tool_calls=1,
            tokens=tokens,
            seconds=duration_ms / 1000.0,
        )

        # Check budget limits
        if self.budget.is_exhausted:
            self.finished = True
            self.termination_reason = "Budget limit exhausted."

        return record

    def recent_actions(self, count: int = 5) -> List[ActionRecord]:
        return self.previous_actions[-count:]

    def consecutive_same_tool_count(self, tool_name: str) -> int:
        count = 0
        for action in reversed(self.previous_actions):
            if action.tool == tool_name:
                count += 1
            else:
                break
        return count

    def get_repeated_action_count(self, tool_name: str, arguments: Dict[str, Any]) -> int:
        count = 0
        arg_str = str(sorted(arguments.items()))
        for action in self.previous_actions:
            if action.tool == tool_name and str(sorted(action.arguments.items())) == arg_str:
                count += 1
        return count

    def to_log_event(self, record: ActionRecord, estimated_cost: float) -> Dict[str, Any]:
        """Creates the structured JSON logging event matching PS Section 29."""
        return {
            "step": record.step,
            "tool": record.tool,
            "arguments_summary": str(record.arguments)[:100],
            "estimated_cost": round(estimated_cost, 4),
            "actual_tokens": record.tokens_consumed,
            "duration_ms": record.duration_ms,
            "outcome": record.outcome.value,
            "new_information": record.outcome in (ToolOutcome.HIGH_PROGRESS, ToolOutcome.MEDIUM_PROGRESS),
            "planner_reason": record.reason,
            "remaining_budget": {
                "tools": self.budget.remaining_tool_calls,
                "tokens": self.budget.remaining_tokens,
                "seconds": round(self.budget.remaining_seconds, 1),
            },
        }
