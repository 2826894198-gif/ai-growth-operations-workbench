"""Backend-enforced execution permissions (PART 06 §AA, §145-§146).

The project has no user auth service yet, so V1 uses an explicit
`X-Execution-Permission` header checked by every write endpoint. The demo
bypass (`EXECUTION_DEMO_PERMISSIONS=true`) is for local development only and
must be disabled in production.
"""

from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings

PERMISSIONS = {
    "EXECUTION_APPROVE",
    "EXECUTION_HIGH_RISK_APPROVE",
    "EXECUTION_COMPENSATE",
    "EXECUTION_POLICY_ADMIN",
    "EXECUTION_KILL_SWITCH",
}


def require_permission(permission: str):
    async def dependency(x_execution_permission: Optional[str] = Header(default=None)) -> None:
        if settings.execution_demo_permissions:
            return
        granted = {p.strip() for p in (x_execution_permission or "").split(",") if p.strip()}
        if permission not in granted:
            raise HTTPException(status_code=403, detail=f"missing execution permission: {permission}")

    return dependency
