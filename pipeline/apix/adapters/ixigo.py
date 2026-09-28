"""Ixigo OTA adapter — STUB.

Live scraping was not implemented: ixigo's search results are rendered
client-side via JavaScript and require browser automation (Playwright) to
retrieve, which is out of scope for this automated build environment (no
headless browser available here). See docs/SCRAPING.md for details and
next steps for a human/CI environment with Playwright installed.
"""
from __future__ import annotations

from datetime import date

from .base import BaseAdapter, FareQuote


class IxigoAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "ixigo"

    @property
    def source_type(self) -> str:
        return "ota"

    def fetch(self, route: dict, depart_date: date) -> list[FareQuote]:
        # Returns no quotes; caller should log a scrape_runs row with
        # status='blocked' and this explanation.
        raise NotImplementedError(
            "ixigo adapter requires Playwright-based browser automation, "
            "not available in this environment."
        )
