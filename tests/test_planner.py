"""Tests for AdaptiveToolPlanner and outcome-aware replanning (PS Section 14 & 38)."""

from pathlib import Path
from src.agent.planner import AdaptiveToolPlanner
from src.agent.state import TaskType
from src.tools import get_default_tools
from src.tools.base import ToolOutcome


def test_task_classification_analysis(tmp_path: Path):
    planner = AdaptiveToolPlanner()

    state_bug = planner.analyze_task("Fix broken password hash comparison in api", tmp_path)
    assert state_bug.task_type == TaskType.BUG_FIX

    state_feat = planner.analyze_task("Add new pagination query parameter to get_users endpoint", tmp_path)
    assert state_feat.task_type == TaskType.FEATURE_REQUEST

    state_test = planner.analyze_task("Fix failing pytest assertion in test_models.py", tmp_path)
    assert state_test.task_type == TaskType.TEST_FAILURE


def test_outcome_aware_replanning_on_empty_grep(tmp_path: Path):
    planner = AdaptiveToolPlanner()
    state = planner.analyze_task("Fix authentication bug", tmp_path)
    tools = get_default_tools()

    # Simulate grep returning 0 matches
    state.record_action(
        tool="grep",
        arguments={"query": "authenticate"},
        outcome=ToolOutcome.NO_PROGRESS,
        tokens=150,
        duration_ms=40,
        reason="search for authenticate",
        output_summary="Grep found 0 matches for pattern 'authenticate'.",
    )

    action = planner.plan_next_action(state, tools)
    assert action.is_replan
    assert action.replan_diagnosis is not None
    assert "0 matches" in action.replan_diagnosis
    # Must NOT blindly repeat grep with same arguments
    assert not (action.tool_name == "grep" and action.arguments.get("query") == "authenticate")


def test_should_stop_conditions(tmp_path: Path):
    planner = AdaptiveToolPlanner()
    state = planner.analyze_task("Fix bug", tmp_path)

    assert not planner.should_stop(state)

    # Exhaust budget
    state.budget.used_tool_calls = state.budget.max_tool_calls
    assert planner.should_stop(state)
    assert "budget exhausted" in (state.termination_reason or "").lower()
