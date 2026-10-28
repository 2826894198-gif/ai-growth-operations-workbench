"""Capture light-theme variant previews (command center + accounts)."""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "themes"

THEMES = [
    ("deepseek", "DeepSeek 蓝"),
    ("vercel", "Vercel 极简"),
    ("linear", "Linear 蓝紫"),
    ("notion", "Notion 纸感"),
    ("stripe", "Stripe 质感"),
]
PAGES = [("command-center", "/command-center", None), ("accounts", "/accounts", None)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        for theme_id, theme_label in THEMES:
            for page_name, path, click_text in PAGES:
                page.goto(f"{BASE}{path}", wait_until="networkidle")
                if click_text:
                    page.get_by_text(click_text, exact=True).first.click()
                    page.wait_for_timeout(400)
                page.evaluate(
                    """(theme) => {
                        document.documentElement.dataset.theme = theme;
                        localStorage.setItem("growth_theme", theme);
                    }""",
                    theme_id,
                )
                page.wait_for_timeout(900)
                page.screenshot(path=str(OUT / f"theme-{theme_id}-{page_name}.png"))
                print("saved", theme_id, page_name)
        # DeepSeek table-view proof: accounts page in table mode
        page.goto(f"{BASE}/accounts", wait_until="networkidle")
        page.get_by_text("表格视图", exact=True).first.click()
        page.wait_for_timeout(400)
        page.evaluate("() => document.documentElement.dataset.theme = 'deepseek'")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "theme-deepseek-accounts-table.png"))
        print("saved deepseek accounts-table")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
