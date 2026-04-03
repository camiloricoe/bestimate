"""Solve PerimeterX challenge using real Chrome (headed) via Playwright.

Zillow uses PerimeterX (HUMAN) anti-bot. Headless browsers get detected.
The solution: launch REAL Chrome in headed mode (uses Xvfb on servers),
let PX auto-resolve, extract cookies, and use them with curl_cffi.

Cookie lifecycle:
1. Launch real Chrome -> visit zillow.com -> PX auto-resolves -> extract cookies
2. Inject cookies into curl_cffi sessions for fast HTTP scraping
3. Cookies last ~30 min. When they expire, repeat step 1.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

ZILLOW_HOME = "https://www.zillow.com/"


@dataclass
class PXCookies:
    """Holds PerimeterX cookies with expiration tracking."""

    cookies: dict[str, str] = field(default_factory=dict)
    obtained_at: float = 0
    max_age: int = 1800  # 30 minutes

    @property
    def is_expired(self) -> bool:
        if not self.cookies:
            return True
        return (time.time() - self.obtained_at) > self.max_age

    @property
    def age_minutes(self) -> float:
        return (time.time() - self.obtained_at) / 60


def solve_px_challenge(
    proxy_url: str | None = None,
    timeout_ms: int = 30000,
) -> PXCookies:
    """Launch real Chrome, visit Zillow, let PX auto-resolve, return cookies.

    Uses channel='chrome' (real Chrome, not Chromium) in headed mode.
    On servers, run with Xvfb for virtual display.
    """
    logger.info("Solving PX challenge with real Chrome...")

    proxy_config = None
    if proxy_url:
        proxy_config = {"server": proxy_url}

    all_cookies: dict[str, str] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = browser.new_context(
            proxy=proxy_config,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )

        # Remove automation markers
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
        """)

        page = context.new_page()

        try:
            resp = page.goto(ZILLOW_HOME, wait_until="domcontentloaded", timeout=timeout_ms)
            logger.info("Zillow homepage: HTTP %d", resp.status if resp else 0)

            # Wait for PX to auto-resolve
            page.wait_for_timeout(8000)

            # Check if page loaded successfully
            content = page.content()
            if "__NEXT_DATA__" not in content:
                logger.warning("__NEXT_DATA__ not found after initial wait, waiting longer...")
                page.wait_for_timeout(10000)

            # Extract all cookies from zillow.com domain
            browser_cookies = context.cookies()
            for cookie in browser_cookies:
                domain = cookie.get("domain", "")
                if "zillow" in domain or domain == ".zillow.com":
                    all_cookies[cookie["name"]] = cookie["value"]

            logger.info(
                "PX solved: %d cookies, including: %s",
                len(all_cookies),
                [k for k in all_cookies if k.startswith("_px") or k in ("JSESSIONID", "zguid", "zgsession")],
            )

        except Exception as e:
            logger.error("PX solve failed: %s", e)
            return PXCookies()
        finally:
            browser.close()

    if not all_cookies:
        logger.warning("No cookies obtained")
        return PXCookies()

    return PXCookies(cookies=all_cookies, obtained_at=time.time())


class PXCookieManager:
    """Manages PX cookie lifecycle: solve, cache, refresh.

    Usage:
        manager = PXCookieManager(proxy_url="http://user:pass@host:port")
        cookies = manager.get_cookies()  # Solves PX if needed
        # ... use cookies in curl_cffi requests ...
        # Auto-refreshes when expired
    """

    def __init__(self, proxy_url: str | None = None, max_age: int = 1800):
        self.proxy_url = proxy_url
        self.max_age = max_age
        self._current: PXCookies | None = None
        self._solve_count = 0

    def get_cookies(self) -> dict[str, str]:
        """Get valid PX cookies, solving challenge if needed."""
        if self._current and not self._current.is_expired:
            return self._current.cookies

        logger.info(
            "PX cookies %s, solving...",
            "expired" if self._current else "needed",
        )
        self._current = solve_px_challenge(
            proxy_url=self.proxy_url,
            timeout_ms=30000,
        )
        self._current.max_age = self.max_age
        self._solve_count += 1

        if not self._current.cookies:
            logger.error("Failed to obtain PX cookies (attempt #%d)", self._solve_count)

        return self._current.cookies

    def invalidate(self) -> None:
        """Force cookie refresh on next call."""
        self._current = None

    @property
    def solve_count(self) -> int:
        return self._solve_count
