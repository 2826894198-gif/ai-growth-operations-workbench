from typing import Any, Dict, List

import yaml

from app.core.project_paths import config_path

CONFIG_PATH = config_path("ai", "tool_permissions.yaml")


def _matrix() -> Dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def allowed_tools(agent_type: str) -> List[str]:
    return list((_matrix().get("agents", {})).get(agent_type, {}).get("tools", []))


def check_permission(agent_type: str, tool_name: str) -> bool:
    return tool_name in allowed_tools(agent_type)
