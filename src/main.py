"""Main entrypoint for ACTP: CLI & Interactive TUI interface."""

import argparse
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from .agent.agent import AutonomousCodingAgent
from .config.settings import ACTPSettings


def render_banner(console: Console):
    banner = (
        "[bold cyan]ACTP[/bold cyan] — [bold white]Adaptive Cost-Aware Tool Planning Harness[/bold white]\n"
        "[dim]Outcome-Aware Tool-Sequence Optimization for Autonomous Software Engineering[/dim]"
    )
    console.print(Panel(banner, border_style="cyan", padding=(1, 2)))


def print_step_event(console: Console, event: dict):
    step = event["step"]
    tool = event["tool"]
    outcome = event["outcome"]
    reason = event["planner_reason"]
    tokens = event["actual_tokens"]
    duration = event["duration_ms"]
    remaining = event["remaining_budget"]
    is_replan = event.get("is_replan", False)

    outcome_color = {
        "HIGH_PROGRESS": "green",
        "MEDIUM_PROGRESS": "blue",
        "LOW_PROGRESS": "yellow",
        "NO_PROGRESS": "yellow",
        "FAILURE": "red",
        "BLOCKED": "red",
        "VERIFICATION_SUCCESS": "bold green",
        "VERIFICATION_FAILURE": "bold red",
    }.get(outcome, "white")

    header = f"[bold cyan]Step {step}[/bold cyan] | Tool: [bold magenta]{tool}[/bold magenta]"
    if is_replan:
        header += " [bold yellow][REPLAN][/bold yellow]"

    details = (
        f"[dim]Planner Reason:[/dim] {reason}\n"
        f"[dim]Outcome:[/dim] [{outcome_color}]{outcome}[/{outcome_color}]  "
        f"[dim]Tokens:[/dim] {tokens}  [dim]Duration:[/dim] {duration}ms\n"
        f"[dim]Remaining Budget:[/dim] Tools: [bold]{remaining['tools']}[/bold] | "
        f"Tokens: [bold]{remaining['tokens']}[/bold] | Time: [bold]{remaining['seconds']}s[/bold]"
    )
    console.print(Panel(details, title=header, border_style="dim", padding=(0, 1)))


def main():
    parser = argparse.ArgumentParser(description="ACTP - Adaptive Cost-Aware Tool Planning Harness")
    parser.add_argument("--task", type=str, help="Software engineering task / issue description")
    parser.add_argument("--task-file", type=str, help="Path to file containing issue description")
    parser.add_argument("--repo", type=str, default=".", help="Target repository path (default: current dir)")
    parser.add_argument("--budget-calls", type=int, default=None, help="Maximum allowed tool calls")
    parser.add_argument("--budget-tokens", type=int, default=None, help="Maximum allowed tokens")
    parser.add_argument("--budget-seconds", type=int, default=None, help="Maximum allowed wall-clock seconds")
    parser.add_argument("--evaluate", action="store_true", help="Run benchmark evaluation suite")
    parser.add_argument("--log-file", type=str, default="logs/actp_run.json", help="Path to write structured event logs")

    args = parser.parse_args()
    console = Console()

    # Evaluation Mode
    if args.evaluate:
        render_banner(console)
        console.print("[bold green]Starting Benchmark Evaluation Suite...[/bold green]\n")
        from .evaluation.runner import main as run_eval_main
        run_eval_main()
        return

    render_banner(console)

    # Resolve task description
    task_desc = args.task
    if not task_desc and args.task_file:
        task_file_path = Path(args.task_file)
        if task_file_path.exists():
            with open(task_file_path, "r", encoding="utf-8") as f:
                task_desc = f.read().strip()
        else:
            console.print(f"[red]Error: Task file '{args.task_file}' not found.[/red]")
            sys.exit(1)

    # Interactive mode if no task given
    if not task_desc:
        console.print("[bold yellow]Interactive Mode[/bold yellow]")
        task_desc = Prompt.ask(
            "[bold white]Enter Issue / Task Description[/bold white]",
            default="Fix the authentication bug in the API: password validation fails for admin."
        )

    # Load settings and apply CLI overrides
    settings = ACTPSettings.load()
    if args.budget_calls:
        settings.budget.max_tool_calls = args.budget_calls
    if args.budget_tokens:
        settings.budget.max_tokens = args.budget_tokens
    if args.budget_seconds:
        settings.budget.max_seconds = args.budget_seconds

    repo_dir = Path(args.repo).resolve()
    settings.workspace_dir = repo_dir

    # Display Task & Initial Budget (PS Section 34 & 51)
    budget_table = Table(title="Execution Budget", show_header=True, header_style="bold cyan")
    budget_table.add_column("Resource", style="dim")
    budget_table.add_column("Allocated Budget", style="bold green")
    budget_table.add_row("Max Tool Calls", str(settings.budget.max_tool_calls))
    budget_table.add_row("Max Tokens", f"{settings.budget.max_tokens:,}")
    budget_table.add_row("Max Time", f"{settings.budget.max_seconds} seconds")
    console.print(budget_table)

    console.print(Panel(f"[bold white]{task_desc}[/bold white]", title="[bold]Target Software Issue[/bold]", border_style="blue"))

    # Check API key status (PS Section 32)
    api_key_set = bool(
        os.environ.get("AI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if api_key_set:
        console.print("[green]✔ AI_API_KEY detected in environment.[/green]\n")
    else:
        console.print(
            "[yellow]Notice: AI_API_KEY is not set. Operating in deterministic offline heuristic planning mode.\n"
            "To connect a live model, run: export AI_API_KEY=\"<your_key>\"[/yellow]\n"
        )

    agent = AutonomousCodingAgent(settings=settings)

    console.print("[bold cyan]Planner:[/bold cyan] Analyzing task and initializing state...\n")

    def on_step(event):
        print_step_event(console, event)

    result = agent.solve(
        issue_description=task_desc,
        workspace_dir=repo_dir,
        step_callback=on_step,
        log_file_path=args.log_file,
    )

    # Final Summary Table (PS Section 28 & 51)
    status_style = "bold green" if result.status == "VERIFIED" else "bold red"
    summary_table = Table(title="Task Resolution Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", style="cyan")

    summary_table.add_row("Final Verification Status", f"[{status_style}]{result.status}[/{status_style}]")
    summary_table.add_row("Tests Deterministically Passed", str(result.verification.tests_passed))
    summary_table.add_row("Build Deterministically Passed", str(result.verification.build_passed))
    summary_table.add_row("Changed Files", str(result.verification.changed_files))
    summary_table.add_row("Total Tool Calls", str(result.total_tool_calls))
    summary_table.add_row("Total Tokens Consumed", f"{result.total_tokens:,}")
    summary_table.add_row("Execution Time", f"{result.execution_seconds:.2f} seconds")
    summary_table.add_row("Failed Tool Calls", str(result.failed_tool_calls))
    summary_table.add_row("Repeated Actions Prevented", str(result.repeated_actions_count))
    summary_table.add_row("Termination Reason", result.state.termination_reason if result.state else "Complete")

    console.print("\n")
    console.print(summary_table)

    if result.verification.diff_summary:
        console.print(Panel(result.verification.diff_summary, title="[bold]Verification Git Diff[/bold]", border_style="dim"))

    if args.log_file:
        console.print(f"[dim]Structured execution log written to: {args.log_file}[/dim]\n")


if __name__ == "__main__":
    main()
