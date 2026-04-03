"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

celery_app = Celery(
    "property_collector",
    broker=settings.redis_url,
    backend=settings.redis_url.replace("/0", "/1"),
    include=["src.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Playwright needs 1 task at a time per worker (each worker has 1 browser)
    # Scale by running multiple worker processes, not concurrency
    worker_concurrency=1,
    task_default_rate_limit="4/m",  # ~15 sec per task with Playwright
    beat_schedule={
        "feed-queue": {
            "task": "src.worker.tasks.feed_queue",
            "schedule": 30.0,  # Every 30 seconds, feed pending addresses into queue
        },
    },
)
