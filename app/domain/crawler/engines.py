from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


class StealthPlaywrightEngine:
    launch_kwargs = {
        "headless": False,
        "args": ["--headless=new"],
    }

    async def __aenter__(self):
        self._stealth = Stealth().use_async(async_playwright())
        self._playwright = await self._stealth.__aenter__()
        self._browser = await self._playwright.chromium.launch(**self.launch_kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._stealth.__aexit__(exc_type, exc_val, exc_tb)

    @asynccontextmanager
    async def page(self):
        context = await self._browser.new_context()
        page = await context.new_page()
        try:
            yield page
        finally:
            await page.close()
