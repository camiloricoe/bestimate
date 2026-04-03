"""Rate-limited scheduler for feeding addresses into the scraping queue."""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from src.db.models import Property
from src.db.session import SyncSessionLocal

logger = logging.getLogger(__name__)


def get_queue_stats() -> dict:
    """Get current queue statistics."""
    with SyncSessionLocal() as session:
        counts = {}
        for status in ["pending", "queued", "in_progress", "completed", "failed", "blocked"]:
            count = session.scalar(
                select(func.count(Property.id)).where(Property.status == status)
            )
            counts[status] = count or 0

        counts["total"] = session.scalar(select(func.count(Property.id))) or 0
        return counts


def reset_stuck_properties(timeout_minutes: int = 30) -> int:
    """Reset properties stuck in 'in_progress' or 'queued' for too long."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    with SyncSessionLocal() as session:
        from sqlalchemy import update

        result = session.execute(
            update(Property)
            .where(
                Property.status.in_(["in_progress", "queued"]),
                Property.updated_at < cutoff,
            )
            .values(status="pending")
        )
        session.commit()
        count = result.rowcount  # type: ignore[assignment]
        if count:
            logger.info("Reset %d stuck properties to pending", count)
        return count
