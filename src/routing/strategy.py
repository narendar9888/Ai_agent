"""Strategic priors, task classification, and outcome-aware recovery policies."""

from typing import Dict

from ..agent.state import TaskType, PlannerState
from ..tools.base import ToolOutcome


class TaskClassifier:
    """Classifies natural language issues into standardized task types."""

    @staticmethod
    def classify(issue_text: str) -> TaskType:
        text = issue_text.lower()
        if any(w in text for w in ["test", "failing", "assert", "fail", "broken test", "regression"]):
            return TaskType.TEST_FAILURE
        if any(w in text for w in ["bug", "fix", "error", "exception", "crash", "incorrect", "wrong", "nullpointer"]):
            return TaskType.BUG_FIX
        if any(w in text for w in ["refactor", "deprecat", "cleanup", "modernize", "rename", "restructure"]):
            return TaskType.REFACTORING
        if any(w in text for w in ["add", "feature", "support", "implement", "extend", "endpoint", "new"]):
            return TaskType.FEATURE_REQUEST
        return TaskType.GENERAL


class StrategyAdvisor:
    """Guides tool selection with task-type priors and dynamic phase transitions."""

    # Prior relevance boosts for tools by task type
    TASK_PRIORS: Dict[TaskType, Dict[str, float]] = {
        TaskType.BUG_FIX: {
            "grep": 1.4,
            "read_file": 1.3,
            "call_graph": 1.2,
            "edit_file": 1.3,
            "run_tests": 1.4,
            "symbol_search": 1.1,
            "git_diff": 1.1,
        },
        TaskType.FEATURE_REQUEST: {
            "find_files": 1.3,
            "grep": 1.1,
            "read_file": 1.3,
            "dependency_search": 1.2,
            "edit_file": 1.4,
            "run_tests": 1.3,
            "run_build": 1.1,
        },
        TaskType.TEST_FAILURE: {
            "run_tests": 1.6,
            "read_file": 1.4,
            "grep": 1.2,
            "edit_file": 1.3,
            "git_diff": 1.2,
        },
        TaskType.REFACTORING: {
            "grep": 1.3,
            "symbol_search": 1.4,
            "dependency_search": 1.3,
            "call_graph": 1.2,
            "edit_file": 1.3,
            "run_tests": 1.4,
        },
        TaskType.GENERAL: {
            "list_files": 1.1,
            "grep": 1.2,
            "read_file": 1.2,
            "edit_file": 1.2,
            "run_tests": 1.2,
        },
    }

    @staticmethod
    def get_phase_guidance(state: PlannerState) -> str:
        """Determines the current execution phase based on actions taken."""
        if state.verification_status.value.startswith("VERIFIED_PASS"):
            return "finished"

        has_edits = any(a.tool in ("edit_file", "apply_patch") and a.outcome == ToolOutcome.HIGH_PROGRESS for a in state.previous_actions)
        has_read = any(a.tool == "read_file" and a.outcome == ToolOutcome.HIGH_PROGRESS for a in state.previous_actions)
        has_search = any(a.tool in ("grep", "find_files", "list_files", "symbol_search") for a in state.previous_actions)

        if has_edits:
            return "verification"
        elif has_read:
            return "implementation"
        elif has_search:
            return "diagnosis"
        else:
            return "exploration"

    @classmethod
    def get_prior_boost(cls, task_type: TaskType, tool_name: str, phase: str) -> float:
        """Returns heuristic utility weight multiplier."""
        priors = cls.TASK_PRIORS.get(task_type, cls.TASK_PRIORS[TaskType.GENERAL])
        base_boost = priors.get(tool_name, 1.0)

        # Phase alignment adjustments
        if phase == "exploration":
            if tool_name in ("list_files", "find_files", "grep"):
                base_boost *= 1.3
            elif tool_name in ("edit_file", "apply_patch"):
                base_boost *= 0.4  # Discourage premature editing before exploration
        elif phase == "diagnosis":
            if tool_name in ("read_file", "symbol_search", "call_graph", "dependency_search"):
                base_boost *= 1.3
        elif phase == "implementation":
            if tool_name in ("edit_file", "apply_patch", "git_diff"):
                base_boost *= 1.4
            elif tool_name in ("list_files", "find_files"):
                base_boost *= 0.5
        elif phase == "verification":
            if tool_name in ("run_tests", "run_build", "git_diff"):
                base_boost *= 1.5

        return base_boost
