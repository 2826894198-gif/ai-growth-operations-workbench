import os

from playwright.async_api import Page


async def save_screenshot(
    page: Page,
    directory: str,
    name: str,
    full_page: bool = True,
) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{name}.png")
    await page.screenshot(path=path, full_page=full_page)
    return path
