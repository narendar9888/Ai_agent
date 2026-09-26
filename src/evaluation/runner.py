"""Evaluation runner executing baselines and ablation studies on benchmark tasks."""

import copy
import tempfile
from pathlib import Path
from typing import List, Optional

from ..agent.agent import AutonomousCodingAgent, AgentRunResult
from ..agent.planner import AdaptiveToolPlanner
from ..config.settings import ACTPSettings
from ..routing.scorer import UtilityScorer
from .metrics import EvaluationMetrics
from .report import EvaluationReport


class BaselineReActPlanner(AdaptiveToolPlanner):
    """
    Baseline A: Naive ReAct.
    Sees all tools, chooses tool without cost weights, budget gating, or repetition penalties.
    """
    def __init__(self, settings: ACTPSettings):
        super().__init__(settings=settings)
        # Disable all cost penalties, repetition penalties, and budget gates
        self.scorer = UtilityScorer(
            enable_budget_check=False,
            enable_repetition_penalty=False,
            enable_cost_model=False,
            enable_task_prior=False,
        )


class BaselineFixedOrderPlanner(AdaptiveToolPlanner):
    """
    Baseline B: Fixed Tool Order.
    Executes a rigid deterministic pipeline: find_files -> grep -> read_file -> edit_file -> run_tests.
    """
    FIXED_SEQUENCE = ["find_files", "grep", "read_file", "edit_file", "run_tests"]

    def plan_next_action(self, state, tools, llm_client=None):
        idx = min(len(state.previous_actions), len(self.FIXED_SEQUENCE) - 1)
        tool_name = self.FIXED_SEQUENCE[idx]
        tool = tools.get(tool_name) or list(tools.values())[0]

        args = self._formulate_arguments(tool, state, None, llm_client)
        from ..agent.planner import PlannedAction
        return PlannedAction(
            tool_name=tool.metadata.name,
            arguments=args,
            reason=f"Fixed Order step {idx + 1}: {tool.metadata.name}",
            utility_score=1.0,
            expected_cost=1.0,
        )


class BaselineStaticRouterPlanner(AdaptiveToolPlanner):
    """
    Baseline C: Static Router.
    Routes based on initial task classification, but never adapts or replans based on outcomes.
    """
    def __init__(self, settings: ACTPSettings):
        super().__init__(settings=settings)
        self.scorer = UtilityScorer(
            enable_budget_check=False,
            enable_repetition_penalty=False,  # No outcome adaptation
            enable_cost_model=True,
            enable_task_prior=True,
        )

    def diagnose_outcome(self, last_action, result):
        # Static router ignores outcome feedback
        return None


def run_single_task(
    agent: AutonomousCodingAgent,
    task_desc: str,
    task_repo_setup: Optional[callable] = None,
) -> AgentRunResult:
    """Runs an agent on a test workspace."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Setup minimal target repository files for testing
        if task_repo_setup:
            task_repo_setup(temp_path)
        else:
            # Default mock repo setup
            (temp_path / "src").mkdir(parents=True)
            (temp_path / "tests").mkdir(parents=True)
            with open(temp_path / "src" / "auth.py", "w") as f:
                f.write("def authenticate(username, password):\n    # TODO\n    return False\n")
            with open(temp_path / "tests" / "test_auth.py", "w") as f:
                f.write("from src.auth import authenticate\ndef test_auth():\n    assert authenticate('admin', 'secret') == True\n")

        # Initialize git repo in sandbox
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=temp_path)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_path)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_path)
        subprocess.run(["git", "add", "."], cwd=temp_path)
        subprocess.run(["git", "commit", "-m", "Initial commit", "-q"], cwd=temp_path)

        return agent.solve(task_desc, workspace_dir=temp_path)


class EvaluationRunner:
    """Orchestrates comprehensive benchmark experiments across baselines and ablations."""

    def __init__(self, settings: Optional[ACTPSettings] = None):
        self.settings = settings or ACTPSettings()

    def evaluate_all(self, tasks: Optional[List[str]] = None) -> List[EvaluationMetrics]:
        if not tasks:
            tasks = [
                "Fix authentication bug: password validation fails for valid admin credential.",
                "Feature Request: Add pagination support to users list API endpoint.",
                "Test failure: Fix failing test_auth assertion.",
                "Refactor: Replace deprecated token verification with modern handler.",
            ]

        results = []

        # 1. Baseline A: Naive ReAct
        m_react = self._evaluate_agent_variant(
            name="Baseline A (ReAct)",
            planner_factory=lambda s: BaselineReActPlanner(s),
            tasks=tasks,
        )
        results.append(m_react)

        # 2. Baseline B: Fixed Order
        m_fixed = self._evaluate_agent_variant(
            name="Baseline B (Fixed Order)",
            planner_factory=lambda s: BaselineFixedOrderPlanner(s),
            tasks=tasks,
        )
        results.append(m_fixed)

        # 3. Baseline C: Static Router
        m_static = self._evaluate_agent_variant(
            name="Baseline C (Static Router)",
            planner_factory=lambda s: BaselineStaticRouterPlanner(s),
            tasks=tasks,
        )
        results.append(m_static)

        # 4. Proposed: Full ACTP
        m_actp = self._evaluate_agent_variant(
            name="ACTP (Full System)",
            planner_factory=lambda s: AdaptiveToolPlanner(settings=s),
            tasks=tasks,
        )
        results.append(m_actp)

        return results

    def evaluate_ablations(self, tasks: Optional[List[str]] = None) -> List[EvaluationMetrics]:
        """Ablation experiments according to PS Section 23."""
        if not tasks:
            tasks = [
                "Fix authentication bug in auth.py: password validation fails.",
                "Add pagination to users list API.",
            ]

        ablations = [
            ("Ablation 1 (No Budget)", {"enable_budget_check": False}),
            ("Ablation 2 (No Outcome History)", {"repetition_penalty": False}),
            ("Ablation 3 (No Repetition Penalty)", {"enable_repetition_penalty": False}),
            ("Ablation 4 (No Cost Estimates)", {"enable_cost_model": False}),
            ("Ablation 5 (No Task Prior)", {"enable_task_prior": False}),
            ("Full ACTP", {}),
        ]

        results = []
        for name, config_overrides in ablations:
            def make_planner(s, overrides=config_overrides):
                scorer = UtilityScorer(
                    cost_weights=s.cost,
                    enable_budget_check=overrides.get("enable_budget_check", True),
                    enable_repetition_penalty=overrides.get("enable_repetition_penalty", True),
                    enable_cost_model=overrides.get("enable_cost_model", True),
                    enable_task_prior=overrides.get("enable_task_prior", True),
                )
                return AdaptiveToolPlanner(settings=s, scorer=scorer)

            m = self._evaluate_agent_variant(name, make_planner, tasks)
            results.append(m)

        return results

    def _evaluate_agent_variant(
        self,
        name: str,
        planner_factory: callable,
        tasks: List[str]
    ) -> EvaluationMetrics:
        metrics = EvaluationMetrics(agent_name=name)

        for task in tasks:
            metrics.total_tasks += 1
            settings = copy.deepcopy(self.settings)
            planner = planner_factory(settings)
            agent = AutonomousCodingAgent(settings=settings, planner=planner)

            # Define task setup with bug to fix
            def task_setup(repo_path: Path):
                src_dir = repo_path / "src"
                src_dir.mkdir(parents=True, exist_ok=True)
                auth_file = src_dir / "auth.py"
                with open(auth_file, "w") as f:
                    f.write(
                        "def authenticate(username, password):\n"
                        "    # Buggy password check\n"
                        "    if username == 'admin' and password == 'wrong_secret':\n"
                        "        return True\n"
                        "    return False\n"
                    )

                tests_dir = repo_path / "tests"
                tests_dir.mkdir(parents=True, exist_ok=True)
                test_file = tests_dir / "test_auth.py"
                with open(test_file, "w") as f:
                    f.write(
                        "from src.auth import authenticate\n"
                        "def test_authenticate():\n"
                        "    assert authenticate('admin', 'secret') is True\n"
                    )

            try:
                run_res = run_single_task(agent, task, task_repo_setup=task_setup)
                metrics.total_tool_calls += run_res.total_tool_calls
                metrics.total_tokens += run_res.total_tokens
                metrics.total_execution_seconds += run_res.execution_seconds
                metrics.total_failed_calls += run_res.failed_tool_calls
                metrics.total_repeated_actions += run_res.repeated_actions_count
                if run_res.status == "VERIFIED":
                    metrics.successful_tasks += 1
            except Exception:
                metrics.total_failed_calls += 1

        return metrics


def main():
    """Runs baseline and ablation benchmarks and outputs report tables."""
    runner = EvaluationRunner()
    print("\nRunning Baseline Benchmark Suite (ReAct vs Fixed vs Static vs ACTP)...")
    baseline_metrics = runner.evaluate_all()
    EvaluationReport.print_terminal_table(baseline_metrics, title="Baseline Comparisons (PS Section 18 & 22)")

    print("\nRunning Ablation Studies (PS Section 23)...")
    ablation_metrics = runner.evaluate_ablations()
    EvaluationReport.print_terminal_table(ablation_metrics, title="Ablation Studies (PS Section 23)")

    # Save to evaluation/results/
    out_dir = Path("evaluation/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_md = "# Evaluation Benchmark Results\n\n## Baselines\n\n"
    report_md += EvaluationReport.render_markdown(baseline_metrics)
    report_md += "\n\n## Ablations\n\n"
    report_md += EvaluationReport.render_markdown(ablation_metrics)

    with open(out_dir / "benchmark_report.md", "w") as f:
        f.write(report_md)
    print(f"\nSaved benchmark report to {out_dir / 'benchmark_report.md'}")


if __name__ == "__main__":
    main()
