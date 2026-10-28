from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class PlaywrightAdapter:
    """Connects Playwright to an AdsPower-managed browser via CDP.

    Never launches its own Chromium; the browser lifecycle belongs to AdsPower.
    """

    def __init__(self, ws_endpoint: str):
        self._ws_endpoint = ws_endpoint
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def __aenter__(self) -> "PlaywrightAdapter":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self._ws_endpoint)
        if self._browser is None:
            raise RuntimeError("failed to connect over CDP")
        context: BrowserContext
        if self._browser.contexts:
            context = self._browser.contexts[0]
        else:
            context = await self._browser.new_context()
        if context.pages:
            self.page = context.pages[0]
        else:
            self.page = await context.new_page()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._playwright is not None:
            await self._playwright.stop()
        self.page = None
        self._browser = None
        self._playwright = None
