import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.integrations.base import ProviderRateLimited, ProviderTimeout
from app.integrations.shopify.exceptions import map_shopify_error
from app.integrations.shopify.graphql import CURRENT_BULK_OPERATION_QUERY

logger = logging.getLogger(__name__)


class ShopifyClient:
    """Shopify GraphQL Admin API client with adaptive pacing (read-only)."""

    def __init__(self):
        self._shop = settings.shopify_shop_domain.rstrip("/")
        self._token = settings.shopify_access_token
        self._version = settings.shopify_api_version
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0))

    def _url(self) -> str:
        return f"https://{self._shop}/admin/api/{self._version}/graphql.json"

    async def graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        try:
            response = await self._client.post(
                self._url(), json={"query": query, "variables": variables or {}}, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderTimeout(str(exc)) from exc
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "2") or 2)
            await asyncio.sleep(min(retry_after, 30))
            raise ProviderRateLimited(f"Shopify throttled (429) retry_after={retry_after}")
        if response.status_code in (401, 403):
            raise map_shopify_error(ValueError("unauthorized"))
        body = response.json()
        if body.get("errors"):
            raise map_shopify_error(ValueError(body["errors"][0].get("message", "graphql error")))
        extensions = body.get("extensions", {})
        throttle = extensions.get("cost", {}).get("throttleStatus", {})
        remaining = throttle.get("currentlyAvailable", 1000)
        if remaining < 100:
            await asyncio.sleep(1.0)
        return body.get("data", {})

    async def paginate_connection(
        self, query: str, path: List[str], variables: Optional[Dict[str, Any]] = None, max_pages: int = 200
    ) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(max_pages):
            data = await self.graphql(query, {**(variables or {}), "after": cursor})
            node = data
            for part in path:
                node = (node or {}).get(part, {})
            for edge in node.get("edges", []):
                nodes.append(edge.get("node"))
            page_info = node.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return nodes

    async def run_bulk_operation(self, query: str, poll_seconds: float = 5.0, max_wait: float = 1800) -> str:
        result = await self.graphql(query)
        bulk = (result.get("bulkOperationRunQuery") or {}).get("bulkOperation") or {}
        operation_id = bulk.get("id")
        if not operation_id:
            raise RuntimeError("bulk operation not created")
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            current = (await self.graphql(CURRENT_BULK_OPERATION_QUERY)).get("currentBulkOperation", {})
            status = current.get("status")
            if status == "COMPLETED":
                return current.get("url") or ""
            if status in ("FAILED", "CANCELED", "EXPIRED"):
                raise RuntimeError(f"bulk operation {status}: {current.get('errorCode')}")
            await asyncio.sleep(poll_seconds)
        raise ProviderTimeout("bulk operation timed out")

    async def stream_jsonl(self, url: str):
        async with self._client.stream("GET", url) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    yield __import__("json").loads(line)

    async def aclose(self) -> None:
        await self._client.aclose()
