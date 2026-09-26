"""Utility scoring engine: Utility(t|s) with cost penalties, risk, and repetition damping."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..agent.state import PlannerState
from ..config.settings import CostWeights
from ..tools.base import BaseTool, ToolCategory
from .cost_model import CostModel
from .repetition import RepetitionDetector
from .strategy import StrategyAdvisor


@dataclass
class ScoredTool:
    tool: BaseTool
    score: float
    p_progress: float
    v_progress: float
    c_tokens: float
    c_time: float
    c_call: float
    r_failure: float
    r_repeat: float
    affordable: bool
    rejection_reason: Optional[str] = None

    def breakdown_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool.metadata.name,
            "utility_score": round(self.score, 4),
            "expected_progress": round(self.p_progress * self.v_progress, 4),
            "cost_tokens": round(self.c_tokens, 4),
            "cost_time": round(self.c_time, 4),
            "cost_call": round(self.c_call, 4),
            "failure_risk": round(self.r_failure, 4),
            "repetition_penalty": round(self.r_repeat, 4),
            "affordable": self.affordable,
            "rejection_reason": self.rejection_reason,
        }


class UtilityScorer:
    """Calculates expected utility U(t|s) for tool candidates according to PS Section 12."""

    def __init__(
        self,
        cost_weights: Optional[CostWeights] = None,
        cost_model: Optional[CostModel] = None,
        repetition_detector: Optional[RepetitionDetector] = None,
        enable_budget_check: bool = True,
        enable_repetition_penalty: bool = True,
        enable_cost_model: bool = True,
        enable_task_prior: bool = True,
    ):
        self.weights = cost_weights or CostWeights()
        self.cost_model = cost_model or CostModel()
        self.repetition_detector = repetition_detector or RepetitionDetector()
        self.enable_budget_check = enable_budget_check
        self.enable_repetition_penalty = enable_repetition_penalty
        self.enable_cost_model = enable_cost_model
        self.enable_task_prior = enable_task_prior

    def estimate_progress_probability(self, tool: BaseTool, state: PlannerState) -> Tuple[float, float]:
        """
        Estimates P(progress|t,s) and V(progress).
        Reflects current phase and previous outcomes.
        """
        phase = state.phase
        tool_name = tool.metadata.name

        base_p = 0.5
        # High-progress history boost
        if tool_name in self.cost_model.stats:
            empirical_rate = self.cost_model.stats[tool_name].success_progress_rate
            base_p = 0.3 + 0.5 * empirical_rate

        # Task type prior boost
        if self.enable_task_prior:
            prior_boost = StrategyAdvisor.get_prior_boost(state.task_type, tool_name, phase)
            base_p *= prior_boost

        # Cap probability in [0.05, 0.95]
        p_progress = max(0.05, min(0.95, base_p))

        # Value of progress depends on tool category
        if tool.metadata.category == ToolCategory.VERIFICATION:
            v_progress = 2.5
        elif tool.metadata.category == ToolCategory.MODIFICATION:
            v_progress = 2.2
        elif tool.metadata.category == ToolCategory.UNDERSTANDING:
            v_progress = 1.8
        else:
            v_progress = 1.4

        return p_progress, v_progress

    def score_tool(
        self,
        tool: BaseTool,
        state: PlannerState,
        candidate_args: Optional[Dict[str, Any]] = None,
    ) -> ScoredTool:
        """
        U(t|s) = P(progress|t,s)*V(progress) - alpha*C_tokens - beta*C_time - gamma*C_call - delta*R_failure - lambda*R_repeat
        """
        # 1. Budget Feasibility Check
        est_tokens = self.cost_model.get_estimated_tokens(tool)
        est_time_ms = self.cost_model.get_estimated_time_ms(tool)

        affordable = True
        rejection_reason = None

        if self.enable_budget_check:
            if state.budget.remaining_tool_calls < 1:
                affordable = False
                rejection_reason = "Tool call budget exhausted."
            elif state.budget.remaining_tokens < est_tokens * 0.4:
                affordable = False
                rejection_reason = f"Insufficient token budget (needs ~{int(est_tokens)}, remaining {state.budget.remaining_tokens})."
            elif state.budget.remaining_seconds < (est_time_ms / 1000.0) * 0.4:
                affordable = False
                rejection_reason = f"Insufficient time budget (needs ~{est_time_ms/1000:.1f}s, remaining {state.budget.remaining_seconds:.1f}s)."

        # 2. Progress and Value
        p_progress, v_progress = self.estimate_progress_probability(tool, state)

        # 3. Cost components
        if self.enable_cost_model:
            costs = self.cost_model.compute_cost_components(tool)
            c_tokens = costs["c_tokens"]
            c_time = costs["c_time"]
            c_call = costs["c_call"]
            r_failure = costs["r_failure"]
        else:
            c_tokens = 0.0
            c_time = 0.0
            c_call = 0.0
            r_failure = 0.0

        # 4. Repetition penalty
        if self.enable_repetition_penalty:
            r_repeat = self.repetition_detector.compute_repetition_penalty(tool, state, candidate_args)
        else:
            r_repeat = 0.0

        # 5. Calculate Score with Adaptive Token Pressure
        if not affordable and self.enable_budget_check:
            score = -999.0
        else:
            budget_ratio = (state.budget.used_tokens / max(1, state.budget.max_tokens)) if self.enable_budget_check else 0.0
            eff_token_weight = self.weights.token_weight * (1.0 + 1.5 * budget_ratio)
            score = (
                (p_progress * v_progress)
                - (eff_token_weight * c_tokens)
                - (self.weights.time_weight * c_time)
                - (self.weights.call_weight * c_call)
                - (self.weights.failure_weight * r_failure)
                - (self.weights.repetition_weight * r_repeat)
            )

        return ScoredTool(
            tool=tool,
            score=score,
            p_progress=p_progress,
            v_progress=v_progress,
            c_tokens=c_tokens,
            c_time=c_time,
            c_call=c_call,
            r_failure=r_failure,
            r_repeat=r_repeat,
            affordable=affordable,
            rejection_reason=rejection_reason,
        )

    def rank_tools(
        self,
        tools: Sequence[BaseTool],
        state: PlannerState,
    ) -> List[ScoredTool]:
        """Ranks all candidate tools in descending order of utility score."""
        scored = [self.score_tool(t, state) for t in tools]
        return sorted(scored, key=lambda x: x.score, reverse=True)
