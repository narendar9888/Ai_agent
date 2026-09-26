"""Configuration settings and environment variable management for ACTP."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class BudgetConfig:
    max_tool_calls: int = 40
    max_tokens: int = 50000
    max_seconds: int = 300


@dataclass
class CostWeights:
    token_weight: float = 1.0        # alpha
    time_weight: float = 0.5         # beta
    call_weight: float = 1.0         # gamma
    failure_weight: float = 1.0      # delta
    repetition_weight: float = 2.0   # lambda


@dataclass
class ReplanningConfig:
    enabled: bool = True
    max_repeated_action: int = 2
    diversification_bonus: float = 1.5


@dataclass
class VerificationConfig:
    run_tests: bool = True
    run_build: bool = True
    timeout_seconds: int = 60


@dataclass
class SecurityConfig:
    allowed_commands: list = field(default_factory=lambda: [
        "pytest", "python", "python3", "git", "cat", "ls", "grep",
        "find", "head", "tail", "cargo", "npm", "node", "make"
    ])
    forbidden_patterns: list = field(default_factory=lambda: [
        "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "chmod -R 777 /",
        "> /dev/sda", "shutdown", "reboot"
    ])
    max_output_chars: int = 15000
    command_timeout_seconds: int = 45


@dataclass
class LLMConfig:
    api_key: Optional[str] = None
    model_name: str = "gpt-4o"
    base_url: Optional[str] = None
    temperature: float = 0.1
    timeout: int = 60


@dataclass
class ACTPSettings:
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    cost: CostWeights = field(default_factory=CostWeights)
    replanning: ReplanningConfig = field(default_factory=ReplanningConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    workspace_dir: Path = field(default_factory=lambda: Path.cwd())

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "ACTPSettings":
        settings = cls()

        # Load from config file if exists
        file_to_load = None
        if config_path and Path(config_path).exists():
            file_to_load = Path(config_path)
        elif Path("config/default_config.yaml").exists():
            file_to_load = Path("config/default_config.yaml")

        if file_to_load:
            try:
                with open(file_to_load, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if "budget" in data:
                    b = data["budget"]
                    settings.budget = BudgetConfig(
                        max_tool_calls=b.get("max_tool_calls", settings.budget.max_tool_calls),
                        max_tokens=b.get("max_tokens", settings.budget.max_tokens),
                        max_seconds=b.get("max_seconds", settings.budget.max_seconds),
                    )
                if "cost" in data:
                    c = data["cost"]
                    settings.cost = CostWeights(
                        token_weight=float(c.get("token_weight", settings.cost.token_weight)),
                        time_weight=float(c.get("time_weight", settings.cost.time_weight)),
                        call_weight=float(c.get("call_weight", settings.cost.call_weight)),
                        failure_weight=float(c.get("failure_weight", settings.cost.failure_weight)),
                        repetition_weight=float(c.get("repetition_weight", settings.cost.repetition_weight)),
                    )
                if "replanning" in data:
                    r = data["replanning"]
                    settings.replanning = ReplanningConfig(
                        enabled=r.get("enabled", settings.replanning.enabled),
                        max_repeated_action=r.get("max_repeated_action", settings.replanning.max_repeated_action),
                    )
            except Exception:
                pass

        # Environment variable overrides
        # PS Section 32: AI_API_KEY required / primary
        api_key = (
            os.environ.get("AI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        base_url = os.environ.get("AI_API_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        model_name = os.environ.get("AI_MODEL_NAME", "gpt-4o")

        settings.llm = LLMConfig(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
        )

        return settings
