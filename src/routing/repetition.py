"""Repetition and stagnation detection with adaptive penalty calculation."""

from typing import Any, Dict, List, Optional
from ..agent.state import PlannerState
from ..tools.base import BaseTool, ToolOutcome


class RepetitionDetector:
    """Detects repeated low-progress tool executions and calculates R_repeat penalties."""

    def __init__(self, max_allowed_repetitions: int = 2):
        self.max_allowed = max_allowed_repetitions

    def compute_repetition_penalty(
        self,
        tool: BaseTool,
        state: PlannerState,
        candidate_args: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculates R_repeat(t) in [0.0, 3.0+].
        Penalizes repeated calls, especially if past calls resulted in NO_PROGRESS or FAILURE.
        """
        tool_name = tool.metadata.name
        recent = state.recent_actions(6)

        if not recent:
            return 0.0

        consecutive_count = 0
        consecutive_low_progress = 0

        for action in reversed(recent):
            if action.tool == tool_name:
                consecutive_count += 1
                if action.outcome in (ToolOutcome.NO_PROGRESS, ToolOutcome.FAILURE, ToolOutcome.LOW_PROGRESS):
                    consecutive_low_progress += 1
            else:
                break

        # Base penalty for consecutive runs of the exact same tool
        penalty = 0.0
        if consecutive_count >= 1:
            penalty += 0.4 * consecutive_count

        # Severe penalty if previous invocations produced no progress
        if consecutive_low_progress >= 1:
            penalty += 1.2 * consecutive_low_progress

        if consecutive_count >= self.max_allowed:
            penalty += 2.0  # Force diversification

        # Check for exact duplicate arguments if provided
        if candidate_args:
            arg_str = str(sorted(candidate_args.items()))
            for action in recent:
                if action.tool == tool_name and str(sorted(action.arguments.items())) == arg_str:
                    if action.outcome in (ToolOutcome.NO_PROGRESS, ToolOutcome.FAILURE):
                        penalty += 2.5
                        break

        return min(5.0, penalty)

    def is_stuck(self, state: PlannerState) -> bool:
        """Determines if the agent is stuck in an unproductive loop."""
        recent = state.recent_actions(4)
        if len(recent) < 3:
            return False

        unproductive_count = sum(
            1 for a in recent
            if a.outcome in (ToolOutcome.NO_PROGRESS, ToolOutcome.FAILURE, ToolOutcome.LOW_PROGRESS)
        )
        return unproductive_count >= 3

    def get_diversification_alternatives(self, failed_tool: str) -> List[str]:
        """Recommends alternative exploratory or understanding tools when one fails."""
        mapping = {
            "grep": ["symbol_search", "find_files", "read_file", "dependency_search"],
            "symbol_search": ["grep", "find_files", "read_file"],
            "find_files": ["grep", "list_files", "symbol_search"],
            "read_file": ["grep", "symbol_search", "git_status"],
            "edit_file": ["read_file", "git_diff", "call_graph"],
            "run_tests": ["read_file", "grep", "git_diff"],
        }
        return mapping.get(failed_tool, ["grep", "read_file", "git_status"])
