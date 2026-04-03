"""Phase 2: Fetch full property details from Zillow detail page."""

from __future__ import annotations

import logging
import re

from src.scraper.client import ZillowClient
from src.scraper.parser import PropertyData, parse_property

logger = logging.getLogger(__name__)

ZILLOW_DETAIL_URL = "https://www.zillow.com/homedetails/{slug}/{zpid}_zpid/"


def build_detail_url(
    zpid: int, address: str = "", city: str = "", state: str = "", zip_code: str = ""
) -> str:
    """Build the Zillow detail page URL."""
    slug_parts = []
    if address:
        slug_parts.append(address)
    if city:
        slug_parts.append(city)
    if state:
        slug_parts.append(state)
    if zip_code:
        slug_parts.append(zip_code)

    if slug_parts:
        slug = "-".join(" ".join(slug_parts).split())
        slug = re.sub(r"[^\w\-]", "", slug)
    else:
        slug = "property"

    return ZILLOW_DETAIL_URL.format(slug=slug, zpid=zpid)


def fetch_property_detail(
    client: ZillowClient,
    zpid: int,
    address: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
) -> PropertyData | None:
    """Fetch full property details from Zillow detail page."""
    url = build_detail_url(zpid, address, city, state, zip_code)
    logger.info("Fetching detail: %s", url)

    status, html = client.get_page_content(url)

    if status == 403:
        logger.warning("Blocked (403) on detail for zpid: %d", zpid)
        return None

    if status == 404:
        logger.info("Property not found (404) for zpid: %d", zpid)
        return None

    if status != 200 or not html:
        logger.warning("Unexpected status %d for zpid: %d", status, zpid)
        return None

    return parse_property(html)
