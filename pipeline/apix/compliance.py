"""Scraping compliance helpers: robots.txt checks + a jittered rate limiter.

Used (or intended for use) by any live adapter before issuing requests.
The simulator adapter does not need these since it makes no network
calls.
"""
from __future__ import annotations

import os
import random
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

USER_AGENT = (
    "APIxResearchBot/0.1 (+https://github.com/; research prototype for "
    "SIH 2026 airfare price-index project; contact: project maintainers)"
)


def is_allowed(url: str, user_agent: str = USER_AGENT) -> bool:
    """Check a URL against the target site's robots.txt.

    Fails safe: if robots.txt cannot be fetched/parsed, returns False
    (treat as disallowed) rather than assuming permission.
    """
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        return False
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return False


class RateLimiter:
    """Simple jittered rate limiter.

    SCRAPE_MAX_RPS env var (default 0.5 requests/sec) controls the base
    delay between requests; each wait adds +/-20% jitter to avoid a
    predictable request cadence.
    """

    def __init__(self, max_rps: float | None = None):
        self.max_rps = max_rps if max_rps is not None else float(
            os.environ.get("SCRAPE_MAX_RPS", 0.5)
        )
        self._last_call: float | None = None

    def _base_delay(self) -> float:
        if self.max_rps <= 0:
            return 0.0
        return 1.0 / self.max_rps

    def wait(self) -> None:
        base = self._base_delay()
        if base == 0:
            return
        jitter = base * random.uniform(-0.2, 0.2)
        delay = max(0.0, base + jitter)
        if self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            remaining = delay - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()
