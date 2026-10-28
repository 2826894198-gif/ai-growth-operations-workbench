"""Dev-only mock of the AdsPower Local API.

It launches a real Chromium (from the Playwright cache) with a CDP endpoint so
the whole Part 01 pipeline (backend -> Redis -> worker -> Playwright/CDP) can
be exercised end-to-end without AdsPower Desktop.

Run:  python scripts/dev/mock_adspower.py
"""

import os
import shutil
import socket
import subprocess
import time
import uuid
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI(title="Mock AdsPower Local API")

CHROMIUM_CANDIDATES = [
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell"
    ),
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-mac/headless_shell"
    ),
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-1223/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    ),
]

running: Dict[str, Dict] = {}
created_profiles: set = set()


def _ok(data=None) -> JSONResponse:
    return JSONResponse({"code": 0, "msg": "success", "data": data if data is not None else {}})


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _find_chromium() -> Optional[str]:
    for path in CHROMIUM_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _wait_for_cdp(port: int, timeout: float = 30.0) -> Optional[str]:
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            version = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=2).json()
            ws = version.get("webSocketDebuggerUrl")
            if ws:
                return ws
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    return None


@app.post("/api/v2/browser-profile/start")
async def start_browser(request: Request):
    body = await request.json()
    profile_id = body.get("profile_id")
    chromium = _find_chromium()
    if chromium is None:
        return JSONResponse({"code": 5001, "msg": "mock chromium not found"}, status_code=500)
    port = _free_port()
    user_data = f"/tmp/mock-adspower-{profile_id}-{uuid.uuid4().hex[:6]}"
    proc = subprocess.Popen(
        [
            chromium,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    ws = _wait_for_cdp(port)
    if ws is None:
        proc.terminate()
        return JSONResponse({"code": 5001, "msg": "chromium cdp did not come up"}, status_code=500)
    running[profile_id] = {"process": proc, "port": port, "user_data": user_data}
    return _ok(
        {
            "debug_port": str(port),
            "ws": {"selenium": ws, "puppeteer": ws},
            "webdriver": f"http://127.0.0.1:{port}",
        }
    )


@app.post("/api/v2/browser-profile/stop")
async def stop_browser(request: Request):
    body = await request.json()
    profile_id = body.get("profile_id")
    entry = running.pop(profile_id, None)
    if entry:
        entry["process"].terminate()
        try:
            entry["process"].wait(timeout=5)
        except subprocess.TimeoutExpired:
            entry["process"].kill()
        shutil.rmtree(entry["user_data"], ignore_errors=True)
    return _ok()


@app.post("/api/v2/browser-profile/create")
async def create_profile(request: Request):
    profile_id = f"mock-{uuid.uuid4().hex[:8]}"
    created_profiles.add(profile_id)
    return _ok({"profile_id": profile_id, "msg": "success"})


@app.post("/api/v2/browser-profile/delete")
async def delete_profile(request: Request):
    body = await request.json()
    for profile_id in body.get("profile_ids") or []:
        entry = running.pop(profile_id, None)
        if entry:
            entry["process"].terminate()
        created_profiles.discard(profile_id)
    return _ok()


@app.post("/api/v2/browser-profile/list")
async def list_profiles(request: Request):
    profiles = [
        {
            "profile_id": "mock-0001",
            "name": "Test-US-East",
            "group_name": "TEST",
            "domain_name": "general",
            "user_proxy_config": {},
            "fingerprint_config": {"country": "US", "language": ["en-US", "en"]},
        }
    ]
    for profile_id in sorted(created_profiles):
        profiles.append(
            {
                "profile_id": profile_id,
                "name": f"Mock-{profile_id}",
                "group_name": "TEST",
                "domain_name": "general",
                "user_proxy_config": {},
                "fingerprint_config": {},
            }
        )
    return _ok({"list": profiles, "page": 1, "page_size": 100, "total": len(profiles)})


@app.get("/diag.json")
async def diag():
    return JSONResponse(
        {
            "ip": "198.51.100.77",
            "country": "US",
            "region": "New York",
            "city": "New York",
            "timezone": "America/New_York",
        }
    )


@app.get("/page")
async def page():
    return Response(
        "<html><head><title>Mock Page</title></head><body><h1>Part 01 E2E</h1></body></html>",
        media_type="text/html",
    )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=50325, log_level="warning")
