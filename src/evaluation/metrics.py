"""Evaluation metrics computation and composite efficiency scoring."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class EvaluationMetrics:
    agent_name: str
    total_tasks: int = 0
    successful_tasks: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    total_execution_seconds: float = 0.0
    total_failed_calls: int = 0
    total_repeated_actions: int = 0
    total_verification_attempts: int = 0

    @property
    def success_rate(self) -> float:
        return (self.successful_tasks / self.total_tasks) if self.total_tasks > 0 else 0.0

    @property
    def avg_tool_calls(self) -> float:
        return (self.total_tool_calls / self.total_tasks) if self.total_tasks > 0 else 0.0

    @property
    def avg_tokens(self) -> float:
        return (self.total_tokens / self.total_tasks) if self.total_tasks > 0 else 0.0

    @property
    def avg_time_seconds(self) -> float:
        return (self.total_execution_seconds / self.total_tasks) if self.total_tasks > 0 else 0.0

    @property
    def avg_failed_calls(self) -> float:
        return (self.total_failed_calls / self.total_tasks) if self.total_tasks > 0 else 0.0

    @property
    def avg_repeated_actions(self) -> float:
        return (self.total_repeated_actions / self.total_tasks) if self.total_tasks > 0 else 0.0

    def compute_composite_efficiency(
        self,
        ref_tokens: float = 20000.0,
        ref_tool_calls: float = 20.0,
        ref_time_seconds: float = 60.0,
        alpha: float = 1.0,
        beta: float = 1.0,
        gamma: float = 0.5,
    ) -> float:
        """
        Calculates composite efficiency per PS Section 21:
        Efficiency = SuccessRate / (1 + alpha*NormTokens + beta*NormCalls + gamma*NormTime)
        """
        norm_tokens = self.avg_tokens / max(1.0, ref_tokens)
        norm_calls = self.avg_tool_calls / max(1.0, ref_tool_calls)
        norm_time = self.avg_time_seconds / max(1.0, ref_time_seconds)

        denominator = 1.0 + (alpha * norm_tokens) + (beta * norm_calls) + (gamma * norm_time)
        return self.success_rate / denominator

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "tasks": self.total_tasks,
            "success_rate": f"{self.success_rate * 100:.1f}%",
            "avg_tools": round(self.avg_tool_calls, 1),
            "avg_tokens": int(self.avg_tokens),
            "avg_time_sec": round(self.avg_time_seconds, 2),
            "avg_failed_calls": round(self.avg_failed_calls, 2),
            "avg_repeated_actions": round(self.avg_repeated_actions, 2),
            "composite_efficiency": round(self.compute_composite_efficiency(), 4),
        }
