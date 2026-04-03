"""Scrape a batch of properties using the ZillowScraper and save to CSV."""

import csv
import logging
import random
import sys
import time

# Allow running from project root
sys.path.insert(0, ".")

from src.scraper.client import ZillowScraper
from src.scraper.parser import PropertyData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PROPERTIES = [
    ("212 GREENBRIAR DR", "33403", "WEST PALM BEACH", "FL"),
    ("1000 OCEAN DR", "33426", "BOYNTON BEACH", "FL"),
    ("5600 WILEY ST", "33023", "HOLLYWOOD", "FL"),
    ("804 S J ST", "33460", "LAKE WORTH BEACH", "FL"),
    ("6720 NW 27TH ST", "33313", "SUNRISE", "FL"),
    ("1130 NE 24TH ST", "33064", "POMPANO BEACH", "FL"),
    ("5200 WILEY ST", "33021", "HOLLYWOOD", "FL"),
    ("7651 HOPE ST", "33024", "HOLLYWOOD", "FL"),
    ("5637 NE 6TH AVE", "33334", "FORT LAUDERDALE", "FL"),
]

CSV_COLUMNS = [
    "input_address", "input_zip", "input_city", "input_state",
    "zpid", "zestimate", "price", "address", "city", "state", "zip_code",
    "beds", "baths", "sqft", "lot_size_sqft", "year_built", "property_type",
]

OUTPUT_FILE = "results_batch.csv"


def main():
    scraper = ZillowScraper()
    results: list[dict] = []

    try:
        for i, (addr, zipcode, city, state) in enumerate(PROPERTIES, 1):
            logger.info("=== [%d/%d] %s, %s, %s %s ===", i, len(PROPERTIES), addr, city, state, zipcode)

            prop = scraper.search_property(addr, city, state, zipcode)

            row = {
                "input_address": addr,
                "input_zip": zipcode,
                "input_city": city,
                "input_state": state,
            }

            if prop:
                d = prop.to_dict()
                for col in CSV_COLUMNS:
                    if col not in row:
                        row[col] = d.get(col, "")
                logger.info("  -> Found: zpid=%s zestimate=%s beds=%s baths=%s sqft=%s",
                            prop.zpid, prop.zestimate, prop.beds, prop.baths, prop.sqft)
            else:
                logger.warning("  -> NOT FOUND")
                for col in CSV_COLUMNS:
                    if col not in row:
                        row[col] = ""

            results.append(row)

            # Delay between requests to be polite
            if i < len(PROPERTIES):
                delay = random.uniform(4, 8)
                logger.info("  Waiting %.1fs before next...", delay)
                time.sleep(delay)

        # Write CSV
        with open(OUTPUT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(results)

        logger.info("Saved %d rows to %s", len(results), OUTPUT_FILE)
        logger.info("Stats: %s", scraper.stats)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
