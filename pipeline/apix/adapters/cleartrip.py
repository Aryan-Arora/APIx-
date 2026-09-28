"""Cleartrip OTA adapter — STUB. See docs/SCRAPING.md.

Same limitation as ixigo.py: needs Playwright-based browser automation
which is unavailable in this build environment.
"""
from __future__ import annotations

from datetime import date

from .base import BaseAdapter, FareQuote


class ClearTripAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "cleartrip"

    @property
    def source_type(self) -> str:
        return "ota"

    def fetch(self, route: dict, depart_date: date) -> list[FareQuote]:
        raise NotImplementedError(
            "cleartrip adapter requires Playwright-based browser automation, "
            "not available in this environment."
        )
