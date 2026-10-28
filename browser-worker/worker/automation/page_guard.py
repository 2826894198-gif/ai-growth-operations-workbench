import asyncio
import ipaddress
import logging
import socket
from typing import List, Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PageGuard:
    """Protects the AdsPower-managed browser from risky navigation.

    Part 01 is read-only: only http(s) public URLs are allowed, navigation is
    time-boxed, and private/loopback hosts are rejected.
    """

    def __init__(
        self,
        allowed_hosts: Optional[List[str]] = None,
        navigation_timeout_ms: int = 45000,
        allow_private: bool = False,
    ):
        self.allowed_hosts = {h.lower() for h in (allowed_hosts or [])}
        self.navigation_timeout_ms = navigation_timeout_ms
        self.allow_private = allow_private

    async def validate_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("only http(s) URLs are allowed")
        if len(url) > 2048:
            raise ValueError("url too long")
        host = url.split("://", 1)[1].split("/", 1)[0].split("@")[-1].split(":")[0].strip("[]")
        if not host:
            raise ValueError("url has no host")
        if self.allowed_hosts and host.lower() not in self.allowed_hosts:
            raise ValueError(f"host {host} is not allowlisted")
        if not self.allow_private:
            await self._reject_private(host)
        return url

    async def _reject_private(self, host: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError:
            return  # DNS failure will surface as navigation error
        for info in infos[:8]:
            ip = info[4][0]
            try:
                parsed = ipaddress.ip_address(ip.split("%")[0])
            except ValueError:
                continue
            if parsed.is_private or parsed.is_loopback or parsed.is_link_local:
                raise ValueError(f"private/loopback host not allowed: {host} ({ip})")

    async def apply(self, page: Page) -> None:
        page.set_default_navigation_timeout(self.navigation_timeout_ms)

        async def block_bad_scheme(route):
            request_url = route.request.url
            if not request_url.startswith(("http://", "https://")):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", block_bad_scheme)
