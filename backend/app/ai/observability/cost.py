from typing import Optional

import yaml

from app.core.project_paths import config_path

CONFIG_PATH = config_path("ai", "cost_budgets.yaml")

RATES = {
    ("openai", "gpt-4o"): (2.5, 10.0),
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("gemini", None): (0.0, 0.0),
}


def _budgets() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    rate = RATES.get((provider, model)) or RATES.get((provider, None)) or (0.0, 0.0)
    return round(input_tokens / 1_000_000 * rate[0] + output_tokens / 1_000_000 * rate[1], 6)


def task_budget(task_type: str) -> Optional[float]:
    return _budgets().get("task_budgets", {}).get(task_type)
