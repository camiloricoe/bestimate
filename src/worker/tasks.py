"""Celery tasks for Zillow scraping using Playwright."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from src.celery_app import celery_app
from src.config import settings
from src.db.models import Property, Result
from src.db.session import SyncSessionLocal
from src.scraper.client import ZillowClient
from src.scraper.detail import fetch_property_detail
from src.scraper.search import search_property
from src.monitoring.metrics import (
    BLOCKS_TOTAL,
    PROPERTIES_COMPLETED,
    PROPERTIES_FAILED,
    REQUESTS_TOTAL,
    SCRAPE_DURATION,
)

logger = logging.getLogger(__name__)

# One browser per worker process (reused across tasks)
_client: ZillowClient | None = None


def get_client() -> ZillowClient:
    """Get or create the shared Playwright browser client."""
    global _client
    if _client is None:
        _client = ZillowClient()
    return _client


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def scrape_property(self, property_id: int) -> dict:
    """Scrape a single property from Zillow.

    1. Search by address -> get zpid + basic data
    2. If search gave partial data, fetch detail page for full data
    3. Save result to DB
    """
    start = time.time()
    client = get_client()

    with SyncSessionLocal() as session:
        prop = session.get(Property, property_id)
        if not prop:
            return {"status": "error", "message": "Property not found"}

        if prop.status == "completed":
            return {"status": "skipped", "message": "Already completed"}

        prop.status = "in_progress"
        prop.attempts += 1
        prop.last_attempt_at = datetime.now(timezone.utc)
        session.commit()

        try:
            # Phase 1: Search
            REQUESTS_TOTAL.labels(phase="search").inc()
            result = search_property(
                client, prop.address, prop.city, prop.state, prop.zip_code,
            )

            if result is None:
                BLOCKS_TOTAL.inc()
                prop.status = "blocked" if prop.attempts >= settings.max_retries else "pending"
                prop.error_message = "Search returned no results or was blocked"
                session.commit()
                PROPERTIES_FAILED.inc()
                return {"status": "blocked", "property_id": property_id}

            prop.zpid = result.zpid

            # Phase 2: Detail (if search didn't give full data)
            needs_detail = result.zestimate is None and result.sqft is None
            if needs_detail and result.zpid:
                REQUESTS_TOTAL.labels(phase="detail").inc()

                # Human-like delay between search and detail
                time.sleep(3)

                detail_result = fetch_property_detail(
                    client, result.zpid,
                    result.address, result.city, result.state, result.zip_code,
                )
                if detail_result:
                    result = detail_result

            # Save result
            db_result = Result(
                property_id=prop.id,
                zpid=result.zpid,
                zestimate=result.zestimate,
                price=result.price,
                beds=result.beds,
                baths=result.baths,
                sqft=result.sqft,
                lot_size_sqft=result.lot_size_sqft,
                year_built=result.year_built,
                property_type=result.property_type,
                address=result.address,
                city=result.city,
                state=result.state,
                zip_code=result.zip_code,
                raw_data=result.raw_data,
            )
            session.add(db_result)
            prop.status = "completed"
            prop.error_message = None
            session.commit()

            PROPERTIES_COMPLETED.inc()
            duration = time.time() - start
            SCRAPE_DURATION.labels(phase="full").observe(duration)

            logger.info(
                "Scraped zpid=%d zestimate=%s beds=%s sqft=%s in %.1fs",
                result.zpid, result.zestimate, result.beds, result.sqft, duration,
            )
            return {
                "status": "success",
                "zpid": result.zpid,
                "zestimate": result.zestimate,
            }

        except Exception as e:
            logger.exception("Error scraping property %d: %s", property_id, e)
            prop.status = "failed" if prop.attempts >= settings.max_retries else "pending"
            prop.error_message = str(e)[:500]
            session.commit()
            PROPERTIES_FAILED.inc()
            return {"status": "error", "message": str(e)}


@celery_app.task
def feed_queue(batch_size: int = 10) -> dict:
    """Feed pending addresses into the scraping queue.

    Called periodically by Celery Beat. Smaller batches since
    Playwright is slower than HTTP-only scraping.
    """
    with SyncSessionLocal() as session:
        stmt = (
            select(Property)
            .where(Property.status == "pending")
            .order_by(Property.created_at)
            .limit(batch_size)
        )
        properties = session.scalars(stmt).all()

        queued = 0
        for prop in properties:
            prop.status = "queued"
            session.commit()
            scrape_property.delay(prop.id)
            queued += 1

        logger.info("Fed %d properties into queue", queued)
        return {"queued": queued}
