"""Tests for repetition and stagnation detection (PS Section 15)."""

from pathlib import Path
from src.agent.state import PlannerState
from src.routing.repetition import RepetitionDetector
from src.tools.base import ToolOutcome
from src.tools.search import GrepTool


def test_repetition_zero_history(tmp_path: Path):
    detector = RepetitionDetector(max_allowed_repetitions=2)
    state = PlannerState(task_description="Search issue", workspace_dir=tmp_path)
    tool = GrepTool()

    penalty = detector.compute_repetition_penalty(tool, state)
    assert penalty == 0.0


def test_repetition_penalty_escalation(tmp_path: Path):
    detector = RepetitionDetector(max_allowed_repetitions=2)
    state = PlannerState(task_description="Search issue", workspace_dir=tmp_path)
    tool = GrepTool()

    # Step 1: grep with NO_PROGRESS
    state.record_action("grep", {"query": "auth"}, ToolOutcome.NO_PROGRESS, tokens=100, duration_ms=50, reason="1st")
    penalty_1 = detector.compute_repetition_penalty(tool, state, candidate_args={"query": "auth"})
    assert penalty_1 > 0.0

    # Step 2: grep again with NO_PROGRESS
    state.record_action("grep", {"query": "auth"}, ToolOutcome.NO_PROGRESS, tokens=100, duration_ms=50, reason="2nd")
    penalty_2 = detector.compute_repetition_penalty(tool, state, candidate_args={"query": "auth"})
    assert penalty_2 > penalty_1


def test_stuck_detection(tmp_path: Path):
    detector = RepetitionDetector()
    state = PlannerState(task_description="Search issue", workspace_dir=tmp_path)

    # 3 consecutive failures
    state.record_action("grep", {"query": "foo"}, ToolOutcome.NO_PROGRESS, 100, 50, "test")
    state.record_action("grep", {"query": "bar"}, ToolOutcome.NO_PROGRESS, 100, 50, "test")
    state.record_action("grep", {"query": "baz"}, ToolOutcome.NO_PROGRESS, 100, 50, "test")

    assert detector.is_stuck(state)


def test_diversification_recommendations():
    detector = RepetitionDetector()
    alts = detector.get_diversification_alternatives("grep")
    assert "symbol_search" in alts
    assert "find_files" in alts
