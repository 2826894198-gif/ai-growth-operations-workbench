import pytest
import respx

from app.integrations.adspower.client import AdsPowerClient
from app.integrations.adspower.exceptions import (
    AdsPowerApiError,
    AdsPowerAuthFailed,
    ProfileNotFound,
)

BASE = "http://localhost:50325"


@pytest.fixture
def client() -> AdsPowerClient:
    return AdsPowerClient(base_url=BASE, api_key="test-key", max_concurrency=2, requests_per_second=100.0)


@pytest.mark.asyncio
@respx.mock
async def test_list_profiles_sends_bearer_auth(client):
    route = respx.post(f"{BASE}/api/v2/browser-profile/list").mock(
        return_value=respx.MockResponse(
            200,
            json={"code": 0, "msg": "success", "data": {"list": [], "page": 1, "page_size": 100, "total": 0}},
        )
    )
    data = await client.list_profiles()
    assert data.total == 0
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
@respx.mock
async def test_query_retries_transient_errors(client):
    respx.post(f"{BASE}/api/v2/browser-profile/list").mock(
        side_effect=[
            respx.MockResponse(500, json={"code": -1, "msg": "boom"}),
            respx.MockResponse(500, json={"code": -1, "msg": "boom"}),
            respx.MockResponse(200, json={"code": 0, "msg": "success", "data": {"list": [], "total": 0}}),
        ]
    )
    data = await client.list_profiles()
    assert data.total == 0


@pytest.mark.asyncio
@respx.mock
async def test_write_op_does_not_retry(client):
    route = respx.post(f"{BASE}/api/v2/browser-profile/create").mock(
        return_value=respx.MockResponse(500, json={"code": -1, "msg": "boom"})
    )
    with pytest.raises(AdsPowerApiError):
        await client.create_profile({"name": "x"})
    assert len(route.calls) == 1


@pytest.mark.asyncio
@respx.mock
async def test_error_mapping(client):
    respx.post(f"{BASE}/api/v2/browser-profile/list").mock(
        return_value=respx.MockResponse(200, json={"code": 5002, "msg": "auth fail"})
    )
    with pytest.raises(AdsPowerAuthFailed):
        await client.list_profiles()

    respx.post(f"{BASE}/api/v2/browser-profile/start").mock(
        return_value=respx.MockResponse(200, json={"code": 5004, "msg": "profile does not exist"})
    )
    with pytest.raises(ProfileNotFound):
        await client.start_browser("missing")


@pytest.mark.asyncio
@respx.mock
async def test_start_browser_parses_cdp_endpoint(client):
    respx.post(f"{BASE}/api/v2/browser-profile/start").mock(
        return_value=respx.MockResponse(
            200,
            json={
                "code": 0,
                "msg": "success",
                "data": {
                    "debug_port": "12345",
                    "ws": {"selenium": "ws://127.0.0.1:12345/devtools/browser/x", "puppeteer": "ws://127.0.0.1:12345/devtools/browser/y"},
                    "webdriver": "http://127.0.0.1:12345",
                },
            },
        )
    )
    data = await client.start_browser("ap-1")
    assert data.debug_port == "12345"
    assert data.ws.puppeteer is not None
