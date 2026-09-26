"""Tests for utility scoring, cost modeling, and router ranking (PS Section 12)."""

from pathlib import Path
from src.agent.state import PlannerState, TaskType
from src.routing.cost_model import CostModel
from src.routing.scorer import UtilityScorer
from src.tools.base import ToolOutcome
from src.tools.search import GrepTool, ListFilesTool, SymbolSearchTool


def test_cost_model_empirical_update():
    cm = CostModel()
    grep = GrepTool()
    init_tokens = cm.get_estimated_tokens(grep)
    assert init_tokens == grep.metadata.estimated_token_cost

    # Record 3 empirical runs with higher token usage
    cm.record_execution("grep", tokens=2500, duration_ms=200, outcome=ToolOutcome.HIGH_PROGRESS)
    cm.record_execution("grep", tokens=2500, duration_ms=200, outcome=ToolOutcome.HIGH_PROGRESS)
    cm.record_execution("grep", tokens=2500, duration_ms=200, outcome=ToolOutcome.HIGH_PROGRESS)

    updated_tokens = cm.get_estimated_tokens(grep)
    # Empirical average should pull the estimate upwards
    assert updated_tokens > init_tokens


def test_utility_scoring_components(tmp_path: Path):
    scorer = UtilityScorer()
    state = PlannerState(
        task_description="Fix bug in auth",
        workspace_dir=tmp_path,
        task_type=TaskType.BUG_FIX,
    )
    grep = GrepTool()
    scored = scorer.score_tool(grep, state)

    assert scored.p_progress > 0
    assert scored.v_progress > 0
    assert scored.c_tokens >= 0
    assert scored.affordable
    # Score should follow formula
    expected = (
        (scored.p_progress * scored.v_progress)
        - scored.c_tokens
        - (0.5 * scored.c_time)
        - scored.c_call
        - scored.r_failure
        - (2.0 * scored.r_repeat)
    )
    assert abs(scored.score - expected) < 1e-4


def test_ranking_prefers_relevant_tools(tmp_path: Path):
    scorer = UtilityScorer()
    state = PlannerState(
        task_description="Fix bug in login password verification",
        workspace_dir=tmp_path,
        task_type=TaskType.BUG_FIX,
        phase="exploration",
    )
    tools = [GrepTool(), SymbolSearchTool(), ListFilesTool()]
    ranked = scorer.rank_tools(tools, state)

    # Grep or Symbol search should rank higher than ListFiles for bug fix in exploration
    top_tool_names = [r.tool.metadata.name for r in ranked]
    assert top_tool_names[0] in ("grep", "symbol_search")
