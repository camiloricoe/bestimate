"""Humanized timing with jitter and exponential backoff."""

import asyncio
import random
import time

from src.config import settings


async def human_delay(multiplier: float = 1.0) -> None:
    """Wait a randomized, human-like interval between requests."""
    base = random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
    jitter = random.gauss(0, 0.5)
    delay = max(1.0, (base + jitter) * multiplier)
    await asyncio.sleep(delay)


async def backoff_delay(attempt: int) -> None:
    """Exponential backoff for retries: 10s -> 30s -> 60s."""
    delays = [10, 30, 60, 120]
    idx = min(attempt, len(delays) - 1)
    base = delays[idx]
    jitter = random.uniform(0, base * 0.3)
    await asyncio.sleep(base + jitter)


class CircuitBreaker:
    """Stops all scraping when block rate exceeds threshold."""

    def __init__(self, threshold: float = 0.20, window_size: int = 100, pause_seconds: int = 60):
        self.threshold = threshold
        self.window_size = window_size
        self.pause_seconds = pause_seconds
        self._results: list[bool] = []  # True = success, False = block
        self._paused_until: float = 0

    def record(self, success: bool) -> None:
        self._results.append(success)
        if len(self._results) > self.window_size:
            self._results = self._results[-self.window_size:]

    @property
    def block_rate(self) -> float:
        if len(self._results) < 10:
            return 0.0
        failures = sum(1 for r in self._results if not r)
        return failures / len(self._results)

    @property
    def is_open(self) -> bool:
        if time.time() < self._paused_until:
            return True
        if self.block_rate > self.threshold:
            self._paused_until = time.time() + self.pause_seconds
            return True
        return False

    async def wait_if_open(self) -> bool:
        """Wait if circuit is open. Returns True if we had to wait."""
        if not self.is_open:
            return False
        remaining = self._paused_until - time.time()
        if remaining > 0:
            await asyncio.sleep(remaining)
        return True
