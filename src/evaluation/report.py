"""Report generation and table formatting for evaluation benchmarks."""

from typing import List
from rich.console import Console
from rich.table import Table
from .metrics import EvaluationMetrics


class EvaluationReport:
    """Formats and displays evaluation benchmark results."""

    @staticmethod
    def render_markdown(metrics_list: List[EvaluationMetrics]) -> str:
        """Renders standard evaluation comparison markdown table matching PS Section 22."""
        header = "| Agent | Success | Tools | Tokens | Time (s) | Failed Calls | Repeated | Composite Eff |"
        sep = "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
        rows = [header, sep]

        for m in metrics_list:
            comp_eff = m.compute_composite_efficiency()
            row = (
                f"| {m.agent_name} | {m.success_rate * 100:.1f}% | {m.avg_tool_calls:.1f} | "
                f"{int(m.avg_tokens)} | {m.avg_time_seconds:.2f}s | {m.avg_failed_calls:.2f} | "
                f"{m.avg_repeated_actions:.2f} | **{comp_eff:.4f}** |"
            )
            rows.append(row)

        return "\n".join(rows)

    @staticmethod
    def print_terminal_table(metrics_list: List[EvaluationMetrics], title: str = "Benchmark Evaluation Results"):
        """Displays rich terminal table."""
        console = Console()
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Agent / Harness", style="bold")
        table.add_column("Success", justify="center")
        table.add_column("Tools", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Time", justify="right")
        table.add_column("Failed Calls", justify="right")
        table.add_column("Repeated", justify="right")
        table.add_column("Efficiency Score", justify="right", style="green bold")

        for m in metrics_list:
            comp_eff = m.compute_composite_efficiency()
            table.add_row(
                m.agent_name,
                f"{m.success_rate * 100:.1f}%",
                f"{m.avg_tool_calls:.1f}",
                f"{int(m.avg_tokens):,}",
                f"{m.avg_time_seconds:.1f}s",
                f"{m.avg_failed_calls:.1f}",
                f"{m.avg_repeated_actions:.1f}",
                f"{comp_eff:.4f}",
            )

        console.print(table)
