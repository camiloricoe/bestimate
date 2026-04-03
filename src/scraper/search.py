"""Phase 1: Search Zillow by address to find property ZPID and basic data."""

from __future__ import annotations

import logging
import re

from src.scraper.parser import PropertyData, parse_property, parse_search_results

logger = logging.getLogger(__name__)

ZILLOW_SEARCH_URL = "https://www.zillow.com/homes/for_sale/{query}_rb/"


def build_search_url(address: str, city: str, state: str, zip_code: str) -> str:
    """Build the Zillow search URL for an address.

    Format: https://www.zillow.com/homes/for_sale/4826-Locust-Ave-Kansas-city,-KS,-66106_rb/
    """
    # Address part: spaces to dashes
    addr_part = re.sub(r"\s+", "-", address.strip())

    # City, State, Zip with commas
    parts = [addr_part]
    if city:
        parts.append(re.sub(r"\s+", "-", city.strip()) + ",")
    if state:
        parts.append(state.strip() + ",")
    if zip_code:
        parts.append(zip_code.strip())

    query = "-".join(parts)
    return ZILLOW_SEARCH_URL.format(query=query)


def search_property(
    client: ZillowClient,
    address: str,
    city: str,
    state: str,
    zip_code: str,
) -> PropertyData | None:
    """Search Zillow for a property by address.

    Returns PropertyData if found, None otherwise.
    """
    url = build_search_url(address, city, state, zip_code)
    logger.info("Searching: %s", url)

    status, html = client.get_page_content(url)

    if status == 403:
        logger.warning("Blocked (403) on search for: %s", address)
        return None

    if status == 404:
        logger.info("No results (404) for: %s", address)
        return None

    if status != 200 or not html:
        logger.warning("Unexpected status %d for: %s", status, address)
        return None

    # Check if we were redirected to a detail page
    if "__NEXT_DATA__" in html:
        # Try as detail page first (direct match)
        prop = parse_property(html)
        if prop:
            return prop

        # Try as search results
        results = parse_search_results(html)
        if results:
            logger.info("Found %d search results for: %s", len(results), address)
            return results[0]

    logger.info("No usable results for: %s", address)
    return None
