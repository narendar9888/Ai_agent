"""Autonomous Coding Agent harness driving the execution loop and verification."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json
import time

from ..config.settings import ACTPSettings
from ..llm.client import LLMClient
from ..tools import get_default_tools
from ..tools.base import BaseTool, SecurityManager
from .planner import AdaptiveToolPlanner, PlannedAction
from .state import PlannerState
from .verifier import DeterministicVerifier, VerificationResult


@dataclass
class AgentRunResult:
    task_description: str
    status: str  # "VERIFIED" or "FAILED"
    verification: VerificationResult
    total_tool_calls: int
    total_tokens: int
    execution_seconds: float
    failed_tool_calls: int
    repeated_actions_count: int
    events: List[Dict[str, Any]] = field(default_factory=list)
    state: Optional[PlannerState] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task_description,
            "status": self.status,
            "tests_passed": self.verification.tests_passed,
            "build_passed": self.verification.build_passed,
            "changed_files": self.verification.changed_files,
            "tool_calls": self.total_tool_calls,
            "tokens": self.total_tokens,
            "execution_seconds": round(self.execution_seconds, 2),
            "failed_calls": self.failed_tool_calls,
            "repeated_actions": self.repeated_actions_count,
            "termination_reason": self.state.termination_reason if self.state else "Complete",
        }


class AutonomousCodingAgent:
    """
    Main ACTP Autonomous Coding Agent harness.
    Orchestrates planning, safe tool execution, outcome observation, and deterministic verification.
    """

    def __init__(
        self,
        settings: Optional[ACTPSettings] = None,
        planner: Optional[AdaptiveToolPlanner] = None,
        verifier: Optional[DeterministicVerifier] = None,
        llm_client: Optional[LLMClient] = None,
        tools: Optional[Dict[str, BaseTool]] = None,
    ):
        self.settings = settings or ACTPSettings()
        self.planner = planner or AdaptiveToolPlanner(settings=self.settings)
        self.verifier = verifier or DeterministicVerifier(
            run_tests=self.settings.verification.run_tests,
            run_build=self.settings.verification.run_build,
        )
        self.llm_client = llm_client or LLMClient(self.settings.llm)
        self.tools = tools if tools is not None else get_default_tools()
        self.security = SecurityManager(
            workspace_dir=self.settings.workspace_dir,
            allowed_commands=self.settings.security.allowed_commands,
            forbidden_patterns=self.settings.security.forbidden_patterns,
            max_output_chars=self.settings.security.max_output_chars,
            timeout_seconds=self.settings.security.command_timeout_seconds,
        )

    def solve(
        self,
        issue_description: str,
        workspace_dir: Optional[Path] = None,
        step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        log_file_path: Optional[str] = None,
    ) -> AgentRunResult:
        """Solves a software-engineering task according to PS Section 38."""
        ws = (workspace_dir or self.settings.workspace_dir).resolve()
        self.security.workspace_dir = ws

        state = self.planner.analyze_task(issue_description, ws)
        start_time = time.time()
        events: List[Dict[str, Any]] = []

        while not state.finished:
            # 1. Stop condition check
            if self.planner.should_stop(state):
                break

            # 2. Plan next action using utility model and outcome history
            action: PlannedAction = self.planner.plan_next_action(state, self.tools, self.llm_client)

            chosen_tool = self.tools.get(action.tool_name)
            if not chosen_tool:
                break

            # 3. Execute tool within security sandbox
            result = chosen_tool.execute(action.arguments, ws, self.security)

            # 4. Update online cost & progress statistics
            self.planner.cost_model.record_execution(
                action.tool_name,
                result.tokens_consumed,
                result.execution_time_ms,
                result.outcome,
            )

            # 5. Record action in state
            record = state.record_action(
                tool=action.tool_name,
                arguments=action.arguments,
                outcome=result.outcome,
                tokens=result.tokens_consumed,
                duration_ms=result.execution_time_ms,
                reason=action.reason,
                error=result.error_message,
                output_summary=result.output[:300],
                new_files=result.new_files,
                new_symbols=result.new_symbols,
            )

            if action.tool_name in ("edit_file", "apply_patch") and result.success:
                for f in result.new_files:
                    state.modified_files.add(f)

            # 6. Structured JSON event logging (PS Section 29)
            event = state.to_log_event(record, estimated_cost=action.expected_cost)
            event["is_replan"] = action.is_replan
            events.append(event)

            if step_callback:
                step_callback(event)

            # 7. Check if deterministic verification should run
            if self.planner.should_verify(state):
                verification = self.verifier.verify(state, self.tools, self.security)
                if verification.status == "VERIFIED":
                    state.finished = True
                    state.termination_reason = "Deterministic verification confirmed task success."
                    break

        # Final verification attempt if not already verified
        verification_final = self.verifier.verify(state, self.tools, self.security)
        elapsed_time = time.time() - start_time

        repeated_count = sum(
            1 for a in state.previous_actions
            if state.get_repeated_action_count(a.tool, a.arguments) > 1
        )

        run_result = AgentRunResult(
            task_description=issue_description,
            status=verification_final.status,
            verification=verification_final,
            total_tool_calls=state.step_counter,
            total_tokens=state.budget.used_tokens,
            execution_seconds=elapsed_time,
            failed_tool_calls=len(state.failed_actions),
            repeated_actions_count=repeated_count,
            events=events,
            state=state,
        )

        # Write log file if requested
        if log_file_path:
            try:
                Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file_path, "w", encoding="utf-8") as f:
                    json.dump([e for e in events], f, indent=2)
            except Exception:
                pass

        return run_result
