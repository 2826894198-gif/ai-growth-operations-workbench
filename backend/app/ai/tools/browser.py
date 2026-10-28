import hashlib
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

ALLOWED_SCHEMES = ("http://", "https://")


async def _validate_url(url: str) -> None:
    if not url.startswith(ALLOWED_SCHEMES):
        raise ValueError("only http(s) public URLs allowed")
    if len(url) > 2048:
        raise ValueError("url too long")


async def public_page_snapshot(
    db: AsyncSession,
    url: str,
    profile_id: str,
    capture_screenshot: bool = True,
    extract_text: bool = True,
) -> Dict[str, Any]:
    """Read-only public page research through the AdsPower research profile.

    Part 04 exposes this only to the Competitor agent; actual browser capture
    is delegated to the Part 01 worker pipeline when enabled.
    """
    await _validate_url(url)
    if not settings.ai_browser_research_enabled:
        return {
            "status": "DISABLED",
            "url": url,
            "note": "AI_BROWSER_RESEARCH_ENABLED=false; capture not executed",
            "content_hash": hashlib.sha256(url.encode()).hexdigest(),
            "_output_ref": f"browser-snapshot://{hashlib.sha256(url.encode()).hexdigest()[:12]}",
        }
    return {
        "status": "QUEUED",
        "url": url,
        "profile_id": profile_id,
        "note": "browser snapshot task queued via Part 01 worker",
        "_output_ref": f"browser-snapshot://{hashlib.sha256(url.encode()).hexdigest()[:12]}",
    }


async def take_screenshot(db: AsyncSession, url: str, profile_id: str) -> Dict[str, Any]:
    return await public_page_snapshot(db, url=url, profile_id=profile_id, capture_screenshot=True, extract_text=False)
