"""Cost and risk model for candidate tools with adaptive online statistics."""

from dataclasses import dataclass
from typing import Dict

from ..tools.base import BaseTool, ToolOutcome


@dataclass
class ToolExecutionStats:
    total_calls: int = 0
    total_tokens: int = 0
    total_duration_ms: int = 0
    failed_calls: int = 0
    high_progress_calls: int = 0

    @property
    def avg_tokens(self) -> float:
        return self.total_tokens / max(1, self.total_calls)

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / max(1, self.total_calls)

    @property
    def failure_rate(self) -> float:
        return self.failed_calls / max(1, self.total_calls)

    @property
    def success_progress_rate(self) -> float:
        return self.high_progress_calls / max(1, self.total_calls)


class CostModel:
    """Estimates resource cost and failure risk for candidate tools."""

    def __init__(self):
        self.stats: Dict[str, ToolExecutionStats] = {}

    def record_execution(
        self,
        tool_name: str,
        tokens: int,
        duration_ms: int,
        outcome: ToolOutcome
    ):
        """Updates internal statistics with empirical observation."""
        if tool_name not in self.stats:
            self.stats[tool_name] = ToolExecutionStats()

        s = self.stats[tool_name]
        s.total_calls += 1
        s.total_tokens += tokens
        s.total_duration_ms += duration_ms

        if outcome in (ToolOutcome.FAILURE, ToolOutcome.BLOCKED):
            s.failed_calls += 1
        elif outcome in (ToolOutcome.HIGH_PROGRESS, ToolOutcome.VERIFICATION_SUCCESS):
            s.high_progress_calls += 1

    def get_estimated_tokens(self, tool: BaseTool) -> float:
        """Blends prior metadata with empirical execution average."""
        prior = float(tool.metadata.estimated_token_cost)
        if tool.metadata.name in self.stats and self.stats[tool.metadata.name].total_calls > 0:
            empirical = self.stats[tool.metadata.name].avg_tokens
            # Bayesian update: weight empirical with call count
            n = self.stats[tool.metadata.name].total_calls
            weight = min(0.8, n / (n + 3.0))
            return (1.0 - weight) * prior + weight * empirical
        return prior

    def get_estimated_time_ms(self, tool: BaseTool) -> float:
        prior = float(tool.metadata.estimated_time_ms)
        if tool.metadata.name in self.stats and self.stats[tool.metadata.name].total_calls > 0:
            empirical = self.stats[tool.metadata.name].avg_duration_ms
            n = self.stats[tool.metadata.name].total_calls
            weight = min(0.8, n / (n + 3.0))
            return (1.0 - weight) * prior + weight * empirical
        return prior

    def get_failure_risk(self, tool: BaseTool) -> float:
        prior = tool.metadata.risk
        if tool.metadata.name in self.stats and self.stats[tool.metadata.name].total_calls > 0:
            empirical = self.stats[tool.metadata.name].failure_rate
            n = self.stats[tool.metadata.name].total_calls
            weight = min(0.8, n / (n + 3.0))
            return (1.0 - weight) * prior + weight * empirical
        return prior

    def compute_cost_components(self, tool: BaseTool) -> Dict[str, float]:
        """Returns normalized cost features: C_tokens, C_time, C_call, R_failure."""
        est_tokens = self.get_estimated_tokens(tool)
        est_time_ms = self.get_estimated_time_ms(tool)
        risk = self.get_failure_risk(tool)

        # Normalization reference scales: 2000 tokens ~ 1.0, 5000 ms ~ 1.0
        c_tokens = min(2.0, est_tokens / 1500.0)
        c_time = min(2.0, (est_time_ms / 1000.0) / 4.0)
        c_call = 0.25  # Fixed marginal cost per tool invocation
        r_failure = risk

        return {
            "c_tokens": c_tokens,
            "c_time": c_time,
            "c_call": c_call,
            "r_failure": r_failure,
            "raw_tokens": est_tokens,
            "raw_time_ms": est_time_ms,
        }
