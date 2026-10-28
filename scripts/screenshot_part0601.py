"""Capture PART 06-01 UI screenshots against the local dev server."""

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000/api/v1"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def get_json(path: str):
    with urllib.request.urlopen(f"{API}{path}") as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    accounts = get_json("/accounts?workspace_id=ws_main")
    account_id = accounts[0]["id"]
    assets = get_json("/content?workspace_id=ws_main")["rows"]
    asset_id = assets[0]["id"]
    recs = get_json("/recommendations")
    rec_id = recs[0]["id"] if recs else None

    pages = [
        ("part0601-command-center", "/command-center"),
        ("part0601-accounts", "/accounts"),
        ("part0601-account-detail", f"/accounts/{account_id}"),
        ("part0601-content", "/content"),
        ("part0601-content-detail", f"/content/assets/{asset_id}"),
        ("part0601-focus", "/focus"),
        ("part0601-connections", "/connections"),
        ("part0601-recommendation-case", f"/recommendations/{rec_id}" if rec_id else "/recommendations"),
        ("part0601-approval-queue", "/execution/approvals"),
        ("part0601-execution-queue", "/execution/queue"),
        ("part0601-kill-switch", "/execution/kill-switch"),
    ]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        for name, path in pages:
            page.goto(f"{BASE}{path}", wait_until="networkidle")
            page.wait_for_timeout(1800)
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
            print("saved", name)
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
