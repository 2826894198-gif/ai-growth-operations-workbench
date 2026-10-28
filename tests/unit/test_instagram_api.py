from app.core.config import settings
from app.main import app
from fastapi.testclient import TestClient


def test_instagram_demo_api_is_explicit_and_read_only():
    old_demo_mode = settings.instagram_demo_mode
    settings.instagram_demo_mode = True
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/instagram/overview?workspace_id=ws_api")
            assert response.status_code == 200
            body = response.json()
            assert body["workspace_id"] == "ws_api"
            assert body["source"]["mode"] == "DEMO"
            assert body["source"]["is_live"] is False

            content = client.get("/api/v1/instagram/content?media_type=REELS")
            assert content.status_code == 200
            assert content.json()["total"] == 1
    finally:
        settings.instagram_demo_mode = old_demo_mode


def test_instagram_api_does_not_claim_live_when_demo_mode_is_disabled_without_live_preflight():
    old_demo_mode = settings.instagram_demo_mode
    settings.instagram_demo_mode = False
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/instagram/overview")
            assert response.status_code == 503
            assert "Live mode is not enabled" in response.json()["detail"]
    finally:
        settings.instagram_demo_mode = old_demo_mode
