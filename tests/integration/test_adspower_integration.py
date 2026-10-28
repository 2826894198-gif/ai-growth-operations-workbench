import os
import uuid

import pytest

from app.integrations.adspower.client import AdsPowerClient

pytestmark = pytest.mark.integration


def _env_or_skip():
    base = os.getenv("ADSPOWER_BASE_URL")
    key = os.getenv("ADSPOWER_API_KEY")
    if not base or not key:
        pytest.skip("ADSPOWER_BASE_URL / ADSPOWER_API_KEY not set")
    return base, key


@pytest.mark.asyncio
async def test_full_browser_smoke_lifecycle():
    """Create test profile -> list -> start -> CDP connect -> page -> screenshot -> stop -> delete."""
    base, key = _env_or_skip()
    client = AdsPowerClient(base_url=base, api_key=key, max_concurrency=1, requests_per_second=1.0)
    name = f"codex-it-{uuid.uuid4().hex[:8]}"
    profile_id = None
    try:
        created = await client.create_profile({"name": name, "group_name": "TEST"})
        profile_id = created.profile_id
        assert profile_id, "create_profile returned no profile_id"

        listed = await client.list_profiles()
        assert any(item.profile_id == profile_id for item in listed.list)

        started = await client.start_browser(profile_id)
        ws = (started.ws.puppeteer if started.ws else None) or (started.ws.selenium if started.ws else None)
        assert ws, "start_browser returned no CDP websocket"

        from worker.automation.playwright_adapter import PlaywrightAdapter

        async with PlaywrightAdapter(ws) as adapter:
            response = await adapter.page.goto("https://example.com", wait_until="domcontentloaded")
            assert response is not None and response.status == 200
            title = await adapter.page.title()
            assert title == "Example Domain"

        await client.stop_browser(profile_id)
    finally:
        if profile_id:
            try:
                await client.delete_profile(profile_id)
            except Exception:  # noqa: BLE001, S110 - cleanup best effort
                pass
        await client.aclose()
