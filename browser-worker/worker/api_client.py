import asyncio
from typing import Any, Dict, Optional

import httpx


class BackendApiClient:
    """Client used by the worker to claim tasks and save results through FastAPI."""

    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(20.0, connect=3.0),
        )

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = await self._client.request(method, path, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < 3:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"backend api request failed: {last_error}")

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/v1/browser-tasks/worker/tasks/{task_id}")

    async def update_task(
        self,
        task_id: str,
        status: str,
        *,
        result: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        log_path: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"status": status}
        if result is not None:
            payload["result"] = result
        if error_code is not None:
            payload["error_code"] = error_code
        if error_message is not None:
            payload["error_message"] = error_message
        if screenshot_path is not None:
            payload["screenshot_path"] = screenshot_path
        if log_path is not None:
            payload["log_path"] = log_path
        if started_at is not None:
            payload["started_at"] = started_at
        if finished_at is not None:
            payload["finished_at"] = finished_at
        return await self._request("POST", f"/api/v1/browser-tasks/{task_id}/result", payload)

    async def requeue(self, task_id: str) -> Dict[str, Any]:
        return await self._request("POST", f"/api/v1/browser-tasks/{task_id}/requeue")

    async def aclose(self) -> None:
        await self._client.aclose()
