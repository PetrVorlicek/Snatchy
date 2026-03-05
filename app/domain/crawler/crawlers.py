from contextlib import asynccontextmanager
import os
import logging
import time
from urllib.parse import urlparse

from app.domain.crawler.engines import StealthPlaywrightEngine

URL = "https://www.bezrealitky.cz/vyhledat?estateType=BYT&location=exact&offerType=PRODEJ&osm_value=Hlavn%C3%AD+m%C4%9Bsto+Praha%2C+Praha%2C+%C4%8Cesko&regionOsmIds=R435514&currency=CZK&locale=CS"

logger = logging.getLogger(__name__)
BLOCK_PAGE_MARKERS = (
    "Něco nám brání v načtení stránky",
    "It seems the page failed to load correctly",
    "cmp.seznam.cz/js/cmp2/scmp-cw.js",
)
LISTING_PAGE_MARKERS = ("__NEXT_DATA__", "sreality.cz", "/hledani/")
DEFAULT_EUCONSENT_V2 = (
    "CQgfW0AQgfW0AD3ACQCSCUFsAP_gAEPgAATIJNQJgAFAAQAAqABkAEAAKAAZAA0ACSAEwAJwAWwAvwBhAGIAQEAggCEAEUAI4ATgAoQBxADuAIQAUgA04COgE2gKkAVkAtwBeYDGQGWAMuAf4BAcCMwEmgSrgKgAVABAADIAGgATAAxAB-AEIAI4ATgA7gCEAEWATaAqQBWQC3AF5gMsAZcBKsAA.IJVwKgAFAAQAAqABkAEAAKAAZAA0ACSAEwAJwAWwAvwBhAGIAPwAgIBBAEIAIoARwAnABQgDNAHEAO4AhABFgCkAGnAR0Am0BUgCsgFuALzAYyAywBlwD_AIDgRmAk0BKsAA.YAAAAAAAAWAA"
)
COOKIE_SELECTORS = (
    "button:has-text('Souhlasím')",
    "button:has-text('Přijmout vše')",
    "button:has-text('Přijmout všechny')",
    "button:has-text('Povolit vše')",
    "button:has-text('Accept all')",
    "button:has-text('I agree')",
    "#didomi-notice-agree-button",
    "button[id*='accept']",
    "button[class*='accept']",
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def is_block_page_html(html: str) -> bool:
    if not html:
        return False
    html_lower = html.lower()
    has_block_marker = any(marker.lower() in html_lower for marker in BLOCK_PAGE_MARKERS)
    has_listing_marker = any(
        marker.lower() in html_lower for marker in LISTING_PAGE_MARKERS
    )
    return has_block_marker and not has_listing_marker


def is_cmp_consent_error_page(html: str) -> bool:
    if not html:
        return False
    html_lower = html.lower()
    return (
        "nastavení souhlasu s personalizací" in html_lower
        or "setting consent for personalization" in html_lower
        or "id=\"scmp-cw\"" in html_lower
    ) and "cmp.seznam.cz/js/cmp2/scmp-cw.js" in html_lower


def is_cmp_page_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.netloc.endswith("cmp.seznam.cz")


async def _try_click_cookie_selector(target, selector: str) -> bool:
    try:
        locator = target.locator(selector)
        if await locator.count() == 0:
            return False
        await locator.first.click(timeout=1500)
        return True
    except Exception:
        return False


async def _try_accept_cookies_once(page) -> bool:
    # Try common consent buttons in main page and iframes.
    targets = [page]
    try:
        targets.extend(page.frames)
    except Exception:
        pass

    for target in targets:
        for selector in COOKIE_SELECTORS:
            if await _try_click_cookie_selector(target, selector):
                return True

    # Fallback: click visible buttons by text from DOM (including custom markup).
    try:
        clicked = await page.evaluate(
            """() => {
                const words = ['souhlas', 'přijmout', 'povolit', 'accept', 'agree', 'consent'];
                const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
                for (const node of nodes) {
                    const txt = (node.innerText || node.textContent || '').toLowerCase().trim();
                    if (!txt) continue;
                    if (!words.some(w => txt.includes(w))) continue;
                    const style = window.getComputedStyle(node);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    node.click();
                    return true;
                }
                return false;
            }"""
        )
        return bool(clicked)
    except Exception:
        return False


async def _click_cmp_shadow_dom_button(page) -> bool:
    try:
        clicked = await page.evaluate(
            """() => {
                const terms = ['souhlas', 'souhlasim', 'přijmout', 'prijmout', 'accept all', 'allow all', 'i agree'];
                const isVisible = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return false;
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                };
                const textMatches = (el) => {
                    const txt = (el.innerText || el.textContent || '').toLowerCase().trim();
                    if (!txt) return false;
                    return terms.some(t => txt.includes(t));
                };

                const queue = [document];
                while (queue.length) {
                    const root = queue.shift();
                    const nodes = root.querySelectorAll('button, [role="button"], a, input[type="button"], input[type="submit"]');
                    for (const node of nodes) {
                        if (!isVisible(node)) continue;
                        if (!textMatches(node)) continue;
                        node.click();
                        return true;
                    }
                    const all = root.querySelectorAll('*');
                    for (const el of all) {
                        if (el.shadowRoot) queue.push(el.shadowRoot);
                    }
                }
                return false;
            }"""
        )
        return bool(clicked)
    except Exception:
        return False


async def try_click_cmp_consent(page, max_wait_ms: int = 10000) -> bool:
    if not is_cmp_page_url(page.url):
        return False

    interval_ms = 500
    deadline = time.monotonic() + (max_wait_ms / 1000.0)
    while time.monotonic() < deadline:
        if await _try_accept_cookies_once(page):
            await page.wait_for_timeout(800)
            return True

        if await _click_cmp_shadow_dom_button(page):
            await page.wait_for_timeout(800)
            return True

        await page.wait_for_timeout(interval_ms)
    return False


async def try_accept_cookies(page, max_wait_ms: int = 8000, interval_ms: int = 500) -> bool:
    clicked_any = False
    deadline = time.monotonic() + (max_wait_ms / 1000.0)
    while time.monotonic() < deadline:
        clicked = await _try_accept_cookies_once(page)
        clicked_any = clicked_any or clicked
        await page.wait_for_timeout(interval_ms)
    return clicked_any


async def preseed_consent_cookies(
    page,
    url: str,
    *,
    enabled: bool,
    euconsent_v2: str,
    didomi_token: str,
) -> None:
    if "sreality.cz" not in url:
        return
    if not enabled:
        return

    cookies = [
        {"name": "euconsent-v2", "value": euconsent_v2, "domain": ".sreality.cz", "path": "/"},
        {"name": "euconsent-v2", "value": euconsent_v2, "domain": ".seznam.cz", "path": "/"},
        {"name": "didomi_token", "value": didomi_token, "domain": ".sreality.cz", "path": "/"},
    ]
    await page.context.add_cookies(cookies)


class Crawler:
    def __init__(self):
        self._url = None
        self._engine = None
        self._runtime_config: dict[str, object] = {}

    def set_engine(self, engine):
        if self._engine is not None:
            raise ValueError("Engine is already set")
        self._engine = engine

    def set_runtime_config(self, runtime_config: dict[str, object] | None):
        if self._runtime_config:
            raise ValueError("Runtime config is already set")
        self._runtime_config = runtime_config or {}

    def set_url(self, url):
        if self._url is not None:
            raise ValueError("URL is already set")
        self._url = url

    @property
    def is_ready(self):
        return self._engine is not None and self._url is not None

    @asynccontextmanager
    async def get_page(self):
        if not self.is_ready:
            raise ValueError(
                "Crawler is not ready. Please set engine, parser, and URL before using."
            )

        async with self._engine() as engine:
            async with engine.page() as page:
                rc = self._runtime_config
                max_attempts = max(
                    1, int(rc.get("max_attempts", int(os.getenv("SNATCHY_NAV_ATTEMPTS", "3"))))
                )
                retry_sleep_ms = int(
                    rc.get("retry_sleep_ms", int(os.getenv("SNATCHY_RETRY_SLEEP_MS", "1500")))
                )
                networkidle_timeout_ms = int(
                    rc.get(
                        "networkidle_timeout_ms",
                        int(os.getenv("SNATCHY_NETWORKIDLE_TIMEOUT_MS", "15000")),
                    )
                )
                cookie_wait_ms = int(
                    rc.get("cookie_wait_ms", int(os.getenv("SNATCHY_COOKIE_WAIT_MS", "8000")))
                )
                manual_wait_ms = int(
                    rc.get("manual_wait_ms", int(os.getenv("SNATCHY_MANUAL_WAIT_MS", "0")))
                )
                cmp_wait_ms = int(
                    rc.get("cmp_wait_ms", int(os.getenv("SNATCHY_CMP_WAIT_MS", "10000")))
                )
                preseed_consent = bool(
                    rc.get(
                        "preseed_consent",
                        _env_bool("SNATCHY_PRESEED_CONSENT", True),
                    )
                )
                euconsent_v2 = str(
                    rc.get(
                        "euconsent_v2",
                        os.getenv("SNATCHY_EUCONSENT_V2", DEFAULT_EUCONSENT_V2),
                    )
                )
                didomi_token = str(rc.get("didomi_token", os.getenv("SNATCHY_DIDOMI_TOKEN", "{}")))

                def on_request_failed(request):
                    if "cmp.seznam.cz/js/cmp2/scmp-cw.js" in request.url:
                        failure = request.failure
                        error_text = failure if isinstance(failure, str) else str(failure)
                        logger.warning(
                            f"CMP script request failed for {self._url}: {error_text}"
                        )

                page.on("requestfailed", on_request_failed)

                for attempt in range(1, max_attempts + 1):
                    await preseed_consent_cookies(
                        page,
                        self._url,
                        enabled=preseed_consent,
                        euconsent_v2=euconsent_v2,
                        didomi_token=didomi_token,
                    )
                    await page.goto(self._url, wait_until="domcontentloaded")

                    if await try_click_cmp_consent(page, max_wait_ms=cmp_wait_ms):
                        logger.info(f"CMP consent clicked on {self._url}")
                        try:
                            await page.wait_for_url("**sreality.cz/**", timeout=10000)
                        except Exception:
                            pass

                    if await try_accept_cookies(page, max_wait_ms=cookie_wait_ms):
                        logger.info(f"Cookie consent accepted on {self._url}")
                        await page.wait_for_timeout(1000)

                    if manual_wait_ms > 0:
                        logger.info(
                            f"Manual wait enabled for {manual_wait_ms} ms on {self._url}."
                        )
                        await page.wait_for_timeout(manual_wait_ms)
                        await try_accept_cookies(page, max_wait_ms=2000)

                    try:
                        await page.wait_for_load_state(
                            "networkidle", timeout=networkidle_timeout_ms
                        )
                    except Exception:
                        # Some pages never reach networkidle; continue with available HTML.
                        pass

                    html = await page.content()
                    if is_cmp_consent_error_page(html):
                        logger.warning(
                            f"CMP fallback page detected on attempt {attempt}/{max_attempts} for {self._url}."
                        )
                    if not is_block_page_html(html):
                        break

                    if attempt < max_attempts:
                        logger.warning(
                            f"Detected block page on attempt {attempt}/{max_attempts} for {self._url}. Retrying."
                        )
                        await page.wait_for_timeout(retry_sleep_ms)
                        continue

                    logger.warning(
                        f"Block page persisted after {max_attempts} attempts for {self._url}."
                    )

                try:
                    yield page
                finally:
                    print("Page context closed")


def build_crawler(
    url: str,
    *,
    engine_kwargs: dict[str, object] | None = None,
    runtime_config: dict[str, object] | None = None,
) -> Crawler:
    crawler = Crawler()
    crawler.set_url(url)
    if engine_kwargs:
        crawler.set_engine(lambda: StealthPlaywrightEngine(**engine_kwargs))
    else:
        crawler.set_engine(StealthPlaywrightEngine)
    crawler.set_runtime_config(runtime_config)
    return crawler
