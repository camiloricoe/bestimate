"""Proxy rotation manager with health tracking and tiered fallback."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Minimum seconds between uses of the same proxy
PROXY_COOLDOWN = 10
# Disable proxy after this many consecutive blocks
MAX_CONSECUTIVE_BLOCKS = 3
# Re-enable after this many seconds
BLOCK_COOLDOWN = 1800  # 30 minutes


@dataclass
class ProxyInfo:
    url: str
    tier: int = 1
    is_rotating: bool = False  # Rotating proxies get a new IP per request (no cooldown needed)
    total_requests: int = 0
    successes: int = 0
    blocks: int = 0
    consecutive_blocks: int = 0
    last_used: float = 0
    last_blocked: float = 0
    is_active: bool = True

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successes / self.total_requests

    def record_success(self) -> None:
        self.total_requests += 1
        self.successes += 1
        self.consecutive_blocks = 0
        self.last_used = time.time()

    def record_block(self) -> None:
        self.total_requests += 1
        self.blocks += 1
        self.consecutive_blocks += 1
        self.last_used = time.time()
        self.last_blocked = time.time()
        if self.consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
            self.is_active = False
            logger.warning("Proxy disabled after %d consecutive blocks: %s", self.consecutive_blocks, self.url)


@dataclass
class ProxyManager:
    """Manages a pool of proxies with tiered selection and health tracking."""

    proxies: list[ProxyInfo] = field(default_factory=list)

    def add_proxy(self, url: str, tier: int = 1) -> None:
        if any(p.url == url for p in self.proxies):
            return
        self.proxies.append(ProxyInfo(url=url, tier=tier))

    def add_rotating_proxy(self, base_url: str, tier: int = 1) -> None:
        """Add a rotating proxy URL (each request gets a different IP from the provider).

        Rotating proxies skip the per-IP cooldown since the provider
        assigns a new IP for every request automatically.
        """
        if any(p.url == base_url for p in self.proxies):
            return
        self.proxies.append(ProxyInfo(url=base_url, tier=tier, is_rotating=True))

    def get_proxy(self, tier: int | None = None) -> str | None:
        """Select the best available proxy.

        Selection criteria:
        1. Must be active
        2. Must have cooled down since last use
        3. Prefer specified tier, fallback to higher tiers
        4. Among candidates: prefer least recently used + highest success rate
        """
        now = time.time()

        # Re-enable proxies past their block cooldown
        for p in self.proxies:
            if not p.is_active and p.last_blocked and (now - p.last_blocked) > BLOCK_COOLDOWN:
                p.is_active = True
                p.consecutive_blocks = 0
                logger.info("Re-enabled proxy after cooldown: %s", p.url)

        candidates = [
            p for p in self.proxies
            if p.is_active and (p.is_rotating or (now - p.last_used) >= PROXY_COOLDOWN)
        ]

        if tier is not None:
            tier_candidates = [p for p in candidates if p.tier == tier]
            if tier_candidates:
                candidates = tier_candidates

        if not candidates:
            # Relax cooldown constraint
            candidates = [p for p in self.proxies if p.is_active]

        if not candidates:
            logger.error("No proxies available!")
            return None

        # Sort by: least recently used first, then by success rate (descending)
        candidates.sort(key=lambda p: (p.last_used, -p.success_rate))

        # Pick from top 3 with some randomness
        top = candidates[:3]
        selected = random.choice(top)
        selected.last_used = now
        return selected.url

    def record_result(self, proxy_url: str, success: bool) -> None:
        """Record the result of a request through a proxy."""
        for p in self.proxies:
            if p.url == proxy_url:
                if success:
                    p.record_success()
                else:
                    p.record_block()
                return

    @property
    def active_count(self) -> int:
        return sum(1 for p in self.proxies if p.is_active)

    @property
    def stats(self) -> dict:
        """Return summary statistics."""
        by_tier: dict[int, dict] = {}
        for p in self.proxies:
            tier = p.tier
            if tier not in by_tier:
                by_tier[tier] = {"total": 0, "active": 0, "avg_success_rate": 0.0}
            by_tier[tier]["total"] += 1
            if p.is_active:
                by_tier[tier]["active"] += 1
            by_tier[tier]["avg_success_rate"] += p.success_rate

        for tier, data in by_tier.items():
            if data["total"] > 0:
                data["avg_success_rate"] /= data["total"]

        return {
            "total_proxies": len(self.proxies),
            "active_proxies": self.active_count,
            "by_tier": by_tier,
        }
