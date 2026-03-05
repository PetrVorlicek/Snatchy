from contextlib import asynccontextmanager
import os

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class StealthPlaywrightEngine:
    def __init__(
        self,
        *,
        headless: bool | None = None,
        locale: str | None = None,
        timezone: str | None = None,
        user_data_dir: str | None = None,
        user_agent: str | None = None,
        nav_timeout_ms: int | None = None,
        channel: str | None = None,
    ):
        default_user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )
        self._headless = _env_bool("SNATCHY_HEADLESS", True) if headless is None else headless
        self._locale = locale or os.getenv("SNATCHY_LOCALE", "cs-CZ")
        self._timezone = timezone or os.getenv("SNATCHY_TIMEZONE", "Europe/Prague")
        self._user_data_dir = (
            os.getenv("SNATCHY_USER_DATA_DIR") if user_data_dir is None else user_data_dir
        )
        self._user_agent = user_agent or os.getenv("SNATCHY_USER_AGENT", default_user_agent)
        self._navigation_timeout_ms = (
            int(os.getenv("SNATCHY_NAV_TIMEOUT_MS", "60000"))
            if nav_timeout_ms is None
            else int(nav_timeout_ms)
        )
        self._channel = os.getenv("SNATCHY_PLAYWRIGHT_CHANNEL") if channel is None else channel

    async def __aenter__(self):
        self._stealth = Stealth().use_async(async_playwright())
        self._playwright = await self._stealth.__aenter__()

        common_launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]
        launch_kwargs = {
            "headless": self._headless,
            "args": common_launch_args,
        }
        if self._channel:
            launch_kwargs["channel"] = self._channel

        self._persistent_context = None
        if self._user_data_dir:
            persistent_kwargs = {
                "user_data_dir": self._user_data_dir,
                "headless": self._headless,
                "args": common_launch_args,
                "locale": self._locale,
                "timezone_id": self._timezone,
                "user_agent": self._user_agent,
                "viewport": {"width": 1366, "height": 768},
                "ignore_https_errors": True,
            }
            if self._channel:
                persistent_kwargs["channel"] = self._channel

            self._persistent_context = (
                await self._playwright.chromium.launch_persistent_context(
                    **persistent_kwargs
                )
            )
            await self._persistent_context.set_extra_http_headers(
                {
                    "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Upgrade-Insecure-Requests": "1",
                }
            )
            await self._persistent_context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            self._browser = None
            return self

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if getattr(self, "_persistent_context", None) is not None:
            await self._persistent_context.close()
        if hasattr(self, "_browser"):
            if self._browser is not None:
                await self._browser.close()
        await self._stealth.__aexit__(exc_type, exc_val, exc_tb)

    @asynccontextmanager
    async def page(self):
        if self._persistent_context is not None:
            context = self._persistent_context
            page = await context.new_page()
            page.set_default_timeout(self._navigation_timeout_ms)
            page.set_default_navigation_timeout(self._navigation_timeout_ms)
            try:
                yield page
            finally:
                await page.close()
            return

        context = await self._browser.new_context(
            locale=self._locale,
            timezone_id=self._timezone,
            user_agent=self._user_agent,
            viewport={"width": 1366, "height": 768},
            ignore_https_errors=True,
        )
        await context.set_extra_http_headers(
            {
                "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = await context.new_page()
        page.set_default_timeout(self._navigation_timeout_ms)
        page.set_default_navigation_timeout(self._navigation_timeout_ms)
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        try:
            yield page
        finally:
            await page.close()
            await context.close()
