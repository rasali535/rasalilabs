"""Offline browser launch smoke: verifies that Chromium can render and capture."""
import asyncio

from playwright.async_api import async_playwright


async def smoke():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            await page.set_content(
                "<!doctype html><html><head><title>Offline Smoke</title></head>"
                "<body><h1>Browser QA is operational</h1>"
                "<img src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22%3E%3C/svg%3E'>"
                "</body></html>"
            )
            assert await page.title() == "Offline Smoke"
            assert await page.locator("h1").inner_text() == "Browser QA is operational"
            assert len(await page.screenshot(type="jpeg", quality=40)) > 200
        finally:
            await browser.close()


def test_offline_chromium_render_and_screenshot():
    asyncio.run(smoke())
