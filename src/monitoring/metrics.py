"""Prometheus metrics for scraper monitoring."""

from prometheus_client import Counter, Gauge, Histogram

# Scraping metrics
REQUESTS_TOTAL = Counter(
    "scraper_requests_total",
    "Total HTTP requests to Zillow",
    ["phase"],  # search, detail
)

BLOCKS_TOTAL = Counter(
    "scraper_blocks_total",
    "Total blocked/failed requests",
)

SCRAPE_DURATION = Histogram(
    "scraper_duration_seconds",
    "Time per property scrape",
    ["phase"],  # search, detail, full
    buckets=[1, 2, 5, 10, 20, 30, 60],
)

# Progress metrics
PROPERTIES_COMPLETED = Counter(
    "scraper_properties_completed_total",
    "Total properties successfully scraped",
)

PROPERTIES_FAILED = Counter(
    "scraper_properties_failed_total",
    "Total properties that failed scraping",
)

# Queue metrics
QUEUE_PENDING = Gauge(
    "scraper_queue_pending",
    "Properties waiting to be scraped",
)

QUEUE_IN_PROGRESS = Gauge(
    "scraper_queue_in_progress",
    "Properties currently being scraped",
)

# Proxy metrics
PROXIES_ACTIVE = Gauge(
    "scraper_proxies_active",
    "Number of active proxies",
    ["tier"],
)

PROXY_SUCCESS_RATE = Gauge(
    "scraper_proxy_success_rate",
    "Proxy success rate",
    ["tier"],
)
