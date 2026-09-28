"""IndiGo direct-airline adapter — STUB. See docs/SCRAPING.md.

IndiGo's own booking site also renders fares via JS/XHR calls that are
not stable or documented publicly, and scraping it directly raises
additional ToS considerations beyond an OTA aggregator. Not implemented
in this build; would need Playwright plus careful compliance review
(robots.txt, rate limiting — see apix/compliance.py) before use.
"""
from __future__ import annotations

from datetime import date

from .base import BaseAdapter, FareQuote


class IndiGoAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "indigo"

    @property
    def source_type(self) -> str:
        return "airline"

    def fetch(self, route: dict, depart_date: date) -> list[FareQuote]:
        raise NotImplementedError(
            "indigo adapter requires Playwright-based browser automation, "
            "not available in this environment."
        )
