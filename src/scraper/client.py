"""Zillow scraper: Bridge API cookies + proxy sticky sessions.

Flow:
1. Create sticky proxy session (same IP ~10 min)
2. Get bridge cookies via that sticky session
3. Scrape properties via same sticky session + cookies
4. When PX blocks or session expires: new sticky session + new cookies
5. Repeat

Speed: ~3-5 sec/property | Cost: ~$1/GB PacketStream
"""

from __future__ import annotations

import logging
import random
import string
import time

from curl_cffi.requests import Session

from src.anti_detect.headers import generate_chrome_headers
from src.config import settings
from src.scraper.parser import PropertyData, parse_property

logger = logging.getLogger(__name__)

BRIDGE_URL = "https://www.zillow.com/bridge/api/v1/property/get"
AUTOCOMPLETE_URL = "https://www.zillowstatic.com/autocomplete/v3/suggestions"

MAX_PAGES_PER_SESSION = 50  # Conservative: new session every 50 pages
SESSION_TTL = 480  # 8 min (PacketStream sticky ~10 min)
MAX_RETRIES = 3
COOKIE_RETRY = 5


def _random_session_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


class ZillowScraper:
    """Zillow scraper with sticky sessions and bridge cookies."""

    def __init__(self):
        self._session: Session | None = None
        self._session_id: str = ""
        self._session_start: float = 0
        self._request_count: int = 0
        self._total_scraped: int = 0
        self._total_failed: int = 0
        self._total_no_zpid: int = 0

    def _sticky_proxy_url(self, session_id: str) -> str:
        password = f"{settings.proxy_pass}_session-{session_id}"
        return (
            f"http://{settings.proxy_user}:{password}"
            f"@{settings.proxy_host}:{settings.proxy_port}"
        )

    def _session_expired(self) -> bool:
        if self._session is None:
            return True
        if self._request_count >= MAX_PAGES_PER_SESSION:
            return True
        if (time.time() - self._session_start) > SESSION_TTL:
            return True
        return False

    def _new_session(self) -> Session:
        """Create sticky proxy session + get bridge cookies."""
        if self._session:
            self._session.close()

        headers = generate_chrome_headers()

        for attempt in range(COOKIE_RETRY):
            sid = _random_session_id()
            proxy = self._sticky_proxy_url(sid)

            self._session = Session(impersonate="chrome124")
            try:
                resp = self._session.get(
                    BRIDGE_URL, headers=headers, proxy=proxy, timeout=20,
                )
                if resp.status_code == 200 and self._session.cookies:
                    self._session_id = sid
                    self._session_start = time.time()
                    self._request_count = 0
                    logger.info("Session %s ready (%d cookies)", sid[:6], len(dict(self._session.cookies)))
                    return self._session
            except Exception as e:
                logger.debug("Cookie attempt %d: %s", attempt + 1, e)

            self._session.close()
            time.sleep(0.5)

        # Fallback
        self._session = Session(impersonate="chrome124")
        self._session_id = _random_session_id()
        self._session_start = time.time()
        self._request_count = 0
        logger.warning("Could not get cookies, proceeding anyway")
        return self._session

    def _ensure_session(self) -> Session:
        if not self._session_expired():
            return self._session  # type: ignore
        return self._new_session()

    def _proxy(self) -> str:
        return self._sticky_proxy_url(self._session_id)

    def lookup_zpid(self, address: str, city: str, state: str, zip_code: str) -> int | None:
        """Get zpid from autocomplete (no PX).

        Uses address + zip only (no city) because city in input data
        often doesn't match Zillow's city. Falls back to address + state.
        """
        session = self._ensure_session()

        # Try queries in order: most specific to least
        queries = [
            f"{address} {zip_code}",              # address + zip (best match)
            f"{address} {state} {zip_code}",      # with state
            f"{address} {city} {state} {zip_code}",  # full (sometimes works)
        ]

        for query in queries:
            for attempt in range(MAX_RETRIES):
                try:
                    resp = session.get(
                        AUTOCOMPLETE_URL,
                        params={"q": query, "resultTypes": "allAddress"},
                        headers=generate_chrome_headers(),
                        proxy=self._proxy(),
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        if results:
                            return results[0].get("metaData", {}).get("zpid")
                        break  # No results for this query, try next format
                except Exception as e:
                    logger.debug("Autocomplete retry %d: %s", attempt + 1, e)
                    time.sleep(0.5)
        return None

    def scrape_property(
        self, zpid: int, address: str = "", city: str = "", state: str = "", zip_code: str = ""
    ) -> PropertyData | None:
        """Scrape property via sticky proxy session."""
        session = self._ensure_session()
        slug = "-".join(f"{address} {city} {state} {zip_code}".split())
        url = f"https://www.zillow.com/homedetails/{slug}/{zpid}_zpid/"
        headers = generate_chrome_headers(referer="https://www.zillow.com/")

        for attempt in range(MAX_RETRIES):
            try:
                resp = session.get(url, headers=headers, proxy=self._proxy(), timeout=20)
                self._request_count += 1

                if resp.status_code == 200 and "__NEXT_DATA__" in resp.text:
                    prop = parse_property(resp.text)
                    if prop:
                        self._total_scraped += 1
                        return prop

                if resp.status_code == 403 or "px-captcha" in resp.text.lower():
                    logger.info("PX blocked, new session...")
                    self._new_session()
                    session = self._session  # type: ignore
                    continue

            except Exception as e:
                logger.debug("Scrape retry %d: %s", attempt + 1, e)
                time.sleep(1)
                self._new_session()
                session = self._session  # type: ignore

        self._total_failed += 1
        return None

    def search_property(
        self, address: str, city: str, state: str, zip_code: str
    ) -> PropertyData | None:
        zpid = self.lookup_zpid(address, city, state, zip_code)
        if not zpid:
            self._total_no_zpid += 1
            return None
        return self.scrape_property(zpid, address, city, state, zip_code)

    @property
    def stats(self) -> dict:
        total = self._total_scraped + self._total_failed + self._total_no_zpid
        return {
            "scraped": self._total_scraped,
            "failed": self._total_failed,
            "no_zpid": self._total_no_zpid,
            "success_rate": f"{self._total_scraped / total * 100:.0f}%" if total > 0 else "N/A",
            "session_reqs": self._request_count,
        }

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
