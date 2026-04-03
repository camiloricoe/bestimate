"""Proxy provider configurations.

Each provider returns rotating residential proxy URLs.
Configure credentials in .env and call load_proxies() to populate the manager.
"""

from __future__ import annotations

import logging

from src.config import settings
from src.proxy.manager import ProxyManager

logger = logging.getLogger(__name__)


def build_proxy_url(user: str, password: str, host: str, port: int) -> str:
    """Build proxy URL from components."""
    return f"http://{user}:{password}@{host}:{port}"


def load_proxies(manager: ProxyManager) -> None:
    """Load proxies from configuration into the manager.

    For rotating residential proxies, a single URL is sufficient -
    the provider assigns a different IP for each request.
    """
    if not settings.proxy_host:
        logger.warning("No proxy configured. Scraping will use direct connection.")
        return

    url = build_proxy_url(
        settings.proxy_user,
        settings.proxy_pass,
        settings.proxy_host,
        settings.proxy_port,
    )
    manager.add_rotating_proxy(url, tier=1)
    logger.info(
        "Loaded rotating proxy: %s@%s:%d (tier 1)",
        settings.proxy_user,
        settings.proxy_host,
        settings.proxy_port,
    )
