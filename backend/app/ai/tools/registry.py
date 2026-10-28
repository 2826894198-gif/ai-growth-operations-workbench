import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.permissions import check_permission
from app.models.ai import AIToolAudit

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Awaitable[Dict[str, Any]]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: str
    allowed_agents: List[str]
    handler: ToolHandler
    timeout_seconds: int = 10
    requires_approval: bool = False
    version: str = "1"


class ToolPermissionDenied(Exception):
    pass


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level,
                "allowed_agents": t.allowed_agents,
                "timeout_seconds": t.timeout_seconds,
                "requires_approval": t.requires_approval,
                "version": t.version,
            }
            for t in self._tools.values()
        ]

    async def call(
        self,
        db: AsyncSession,
        *,
        agent_type: str,
        tool_name: str,
        run_id: Optional[str],
        step_id: Optional[str],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool = self.get(tool_name)
        if tool is None:
            raise ToolPermissionDenied(f"tool not registered: {tool_name}")
        if not check_permission(agent_type, tool_name):
            raise ToolPermissionDenied(f"agent {agent_type} cannot use tool {tool_name}")
        started = datetime.now(timezone.utc)
        safe_summary = json.dumps({k: _safe(v) for k, v in kwargs.items()}, ensure_ascii=False, default=str)[:2000]
        input_hash = hashlib.sha256(safe_summary.encode("utf-8")).hexdigest()
        try:
            result = await tool.handler(db, **kwargs)
            success, error_code = True, None
            output_ref = result.get("_output_ref", "memory")
        except Exception as exc:  # noqa: BLE001
            success, error_code = False, getattr(exc, "error_code", "TOOL_ERROR")
            output_ref = None
            logger.warning("tool call failed", extra={"event": "tool_failed", "tool": tool_name, "error": error_code})
            raise
        finally:
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            db.add(
                AIToolAudit(
                    run_id=run_id,
                    step_id=step_id,
                    agent_type=agent_type,
                    tool_name=tool_name,
                    risk_level=tool.risk_level,
                    input_hash=input_hash,
                    safe_input_summary=safe_summary,
                    output_ref=output_ref,
                    started_at=started,
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=duration_ms,
                    success=success,
                    error_code=error_code,
                )
            )
            await db.commit()
        return result


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items() if not _sensitive(k)}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    return value


def _sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(word in lowered for word in ("password", "token", "secret", "key", "authorization", "cookie"))


registry = ToolRegistry()
