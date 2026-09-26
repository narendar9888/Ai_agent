from pathlib import Path

from src.agent.state import BudgetTracker, PlannerState, TaskType
from src.routing.scorer import UtilityScorer
from src.tools.search import GrepTool


def test_budget_initialization():
    b = BudgetTracker(max_tool_calls=10, max_tokens=1000, max_seconds=60)
    assert b.remaining_tool_calls == 10
    assert b.remaining_tokens == 1000
    assert b.remaining_seconds == 60.0
    assert not b.is_exhausted


def test_budget_consumption_and_exhaustion():
    b = BudgetTracker(max_tool_calls=3, max_tokens=1000, max_seconds=10)
    b.record_usage(tool_calls=2, tokens=600, seconds=4.0)

    assert b.remaining_tool_calls == 1
    assert b.remaining_tokens == 400
    assert b.remaining_seconds == 6.0
    assert not b.is_exhausted

    # Exhaust tool calls
    b.record_usage(tool_calls=1, tokens=100, seconds=1.0)
    assert b.remaining_tool_calls == 0
    assert b.is_exhausted


def test_planner_state_budget_cutoff(tmp_path: Path):
    state = PlannerState(
        task_description="Test budget cutoff",
        workspace_dir=tmp_path,
        task_type=TaskType.BUG_FIX,
    )
    state.budget = BudgetTracker(max_tool_calls=2, max_tokens=1000, max_seconds=30)

    # First call
    from src.tools.base import ToolOutcome
    state.record_action("grep", {"query": "auth"}, ToolOutcome.HIGH_PROGRESS, tokens=200, duration_ms=100, reason="search")
    assert not state.finished

    # Second call hits limit
    state.record_action("read_file", {"path": "auth.py"}, ToolOutcome.HIGH_PROGRESS, tokens=300, duration_ms=150, reason="read")
    assert state.finished
    assert "Budget limit exhausted" in (state.termination_reason or "")


def test_scorer_budget_rejection():
    scorer = UtilityScorer(enable_budget_check=True)
    state = PlannerState(
        task_description="Test rejection",
        workspace_dir=Path("."),
    )
    # Give tiny budget
    state.budget = BudgetTracker(max_tool_calls=1, max_tokens=20, max_seconds=1)

    grep = GrepTool()
    scored = scorer.score_tool(grep, state)

    # Grep estimated tokens (500) exceeds tiny budget (20)
    assert not scored.affordable
    assert scored.score <= -500
    assert "Insufficient token budget" in (scored.rejection_reason or "")
