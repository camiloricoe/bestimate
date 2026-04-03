"""Parse Zillow property data from __NEXT_DATA__ JSON embedded in HTML."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Regex fallback for __NEXT_DATA__ extraction (faster than full HTML parse)
NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
    re.DOTALL,
)


@dataclass
class PropertyData:
    """Structured property data extracted from Zillow."""

    zpid: int
    zestimate: float | None = None
    price: float | None = None
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    beds: int | None = None
    baths: float | None = None
    sqft: int | None = None
    lot_size_sqft: float | None = None
    year_built: int | None = None
    property_type: str | None = None
    raw_data: dict | None = None

    @property
    def best_value(self) -> float | None:
        """Return zestimate if available, otherwise price."""
        return self.zestimate or self.price

    def to_dict(self) -> dict:
        return {
            "zpid": self.zpid,
            "zestimate": self.zestimate,
            "price": self.price,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "beds": self.beds,
            "baths": self.baths,
            "sqft": self.sqft,
            "lot_size_sqft": self.lot_size_sqft,
            "year_built": self.year_built,
            "property_type": self.property_type,
        }


def extract_next_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ JSON from Zillow HTML page."""
    # Try regex first (faster)
    match = NEXT_DATA_RE.search(html)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback to BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            return json.loads(script.string)
        except json.JSONDecodeError:
            pass

    return None


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _find_property_data(data: dict) -> dict | None:
    """Navigate the __NEXT_DATA__ JSON tree to find property data.

    Zillow's structure varies but property data is typically at:
    - props.pageProps.componentProps.gdpClientCache -> JSON string -> property
    - props.pageProps.initialData.building (for apartments)
    - queryState/searchResults for search pages
    """
    try:
        page_props = data.get("props", {}).get("pageProps", {})

        # Path 1: GDP client cache (most common for property detail pages)
        gdp_cache = page_props.get("componentProps", {}).get("gdpClientCache")
        if gdp_cache:
            if isinstance(gdp_cache, str):
                gdp_cache = json.loads(gdp_cache)
            # The cache is keyed by a query hash; get the first (usually only) entry
            for _key, value in gdp_cache.items():
                if isinstance(value, str):
                    value = json.loads(value)
                prop = value.get("property")
                if prop and "zpid" in prop:
                    return prop

        # Path 2: initialReduxState (alternative structure)
        redux = page_props.get("initialReduxState", {})
        gdp = redux.get("gdp", {})
        if "building" in gdp:
            return gdp["building"]
        if "property" in gdp:
            return gdp["property"]

        # Path 3: Direct property in pageProps
        if "property" in page_props and "zpid" in page_props.get("property", {}):
            return page_props["property"]

        # Path 4: componentProps.initialData
        initial = page_props.get("componentProps", {}).get("initialData", {})
        if "property" in initial:
            return initial["property"]

    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.warning("Failed to navigate __NEXT_DATA__: %s", e)

    return None


def _convert_lot_size(value, unit: str | None) -> float | None:
    """Convert lot size to square feet."""
    if value is None:
        return None
    val = _safe_float(value)
    if val is None:
        return None
    if unit and "acre" in unit.lower():
        return val * 43560
    return val


def parse_property(html: str) -> PropertyData | None:
    """Parse a Zillow property page HTML into structured data."""
    next_data = extract_next_data(html)
    if not next_data:
        logger.warning("No __NEXT_DATA__ found in HTML")
        return None

    prop = _find_property_data(next_data)
    if not prop:
        logger.warning("No property data found in __NEXT_DATA__")
        return None

    zpid = _safe_int(prop.get("zpid"))
    if not zpid:
        logger.warning("No zpid found in property data")
        return None

    # Address extraction
    addr_info = prop.get("address", {})
    if isinstance(addr_info, dict):
        address = addr_info.get("streetAddress", "")
        city = addr_info.get("city", "")
        state = addr_info.get("state", "")
        zip_code = str(addr_info.get("zipcode", ""))[:5]
    else:
        address = str(addr_info) if addr_info else ""
        city = ""
        state = ""
        zip_code = ""

    # Lot size
    lot_val = prop.get("lotAreaValue") or prop.get("lotSize")
    lot_unit = prop.get("lotAreaUnits", prop.get("lotAreaUnit", "sqft"))
    lot_size = _convert_lot_size(lot_val, lot_unit)

    return PropertyData(
        zpid=zpid,
        zestimate=_safe_float(prop.get("zestimate")),
        price=_safe_float(prop.get("price")),
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        beds=_safe_int(prop.get("bedrooms") or prop.get("beds")),
        baths=_safe_float(prop.get("bathrooms") or prop.get("baths")),
        sqft=_safe_int(prop.get("livingArea") or prop.get("livingAreaValue")),
        lot_size_sqft=lot_size,
        year_built=_safe_int(prop.get("yearBuilt")),
        property_type=prop.get("homeType") or prop.get("propertyType"),
        raw_data=prop,
    )


def parse_search_results(html: str) -> list[PropertyData]:
    """Parse Zillow search results page to extract property listings."""
    next_data = extract_next_data(html)
    if not next_data:
        return []

    results = []
    try:
        page_props = next_data.get("props", {}).get("pageProps", {})

        # Search results are in searchPageState.cat1.searchResults.listResults
        search_state = page_props.get("searchPageState", {})
        cat1 = search_state.get("cat1", {})
        search_results = cat1.get("searchResults", {})
        list_results = search_results.get("listResults", [])

        for item in list_results:
            zpid = _safe_int(item.get("zpid") or item.get("id"))
            if not zpid:
                continue

            # Address can be in different formats
            addr = item.get("address", "")
            addr_info = item.get("addressStreet", "")
            city = item.get("addressCity", "")
            state = item.get("addressState", "")
            zipcode = str(item.get("addressZipcode", ""))[:5]

            # Zestimate might be in hdpData
            hdp = item.get("hdpData", {}).get("homeInfo", {})

            results.append(PropertyData(
                zpid=zpid,
                zestimate=_safe_float(hdp.get("zestimate") or item.get("zestimate")),
                price=_safe_float(item.get("unformattedPrice") or item.get("price")),
                address=addr_info or addr,
                city=city,
                state=state,
                zip_code=zipcode,
                beds=_safe_int(item.get("beds") or hdp.get("bedrooms")),
                baths=_safe_float(item.get("baths") or hdp.get("bathrooms")),
                sqft=_safe_int(item.get("area") or hdp.get("livingArea")),
                lot_size_sqft=None,
                year_built=_safe_int(hdp.get("yearBuilt")),
                property_type=hdp.get("homeType"),
            ))
    except (AttributeError, TypeError) as e:
        logger.warning("Failed to parse search results: %s", e)

    return results
