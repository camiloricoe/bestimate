"""Cookie session management for Zillow scraping."""

from __future__ import annotations

import logging
import random

from curl_cffi.requests import Session

from src.anti_detect.headers import generate_chrome_headers

logger = logging.getLogger(__name__)

ZILLOW_HOME = "https://www.zillow.com/"


class CookieSession:
    """Manages a cookie session that mimics a real browser visit.

    Each session:
    1. Visits zillow.com homepage to collect cookies
    2. Reuses those cookies for N requests
    3. Gets rotated after N requests or on block
    """

    def __init__(self, session: Session, max_requests: int = 7):
        self.session = session
        self.max_requests = max_requests + random.randint(-2, 2)
        self.request_count = 0
        self.is_warmed = False

    def warm_up(self, proxy: str | None = None) -> bool:
        """Visit zillow.com homepage to collect initial cookies."""
        try:
            headers = generate_chrome_headers()
            resp = self.session.get(
                ZILLOW_HOME,
                headers=headers,
                proxy=proxy,
                timeout=15,
            )
            self.is_warmed = resp.status_code == 200
            if self.is_warmed:
                logger.debug("Cookie warm-up successful, got %d cookies", len(self.session.cookies))
            return self.is_warmed
        except Exception as e:
            logger.warning("Cookie warm-up failed: %s", e)
            return False

    @property
    def needs_rotation(self) -> bool:
        return self.request_count >= self.max_requests

    def increment(self) -> None:
        self.request_count += 1


def create_session(impersonate: str = "chrome124") -> Session:
    """Create a new curl_cffi session with Chrome TLS fingerprint."""
    return Session(impersonate=impersonate)
