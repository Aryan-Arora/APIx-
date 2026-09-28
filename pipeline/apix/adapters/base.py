"""Common interface every fare-source adapter implements."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


@dataclass
class FareQuote:
    """A single fare observation, shaped to match the fare_quotes table."""

    scraped_at: datetime
    source: str
    source_type: str  # 'airline' | 'ota' | 'simulator'
    route_id: str
    origin: str
    dest: str
    depart_date: date
    total_fare: float
    carrier: Optional[str] = None
    flight_no: Optional[str] = None
    depart_time: Optional[time] = None
    lead_days: Optional[int] = None
    lead_bucket: Optional[str] = None
    fare_class: Optional[str] = None
    base_fare: Optional[float] = None
    taxes: Optional[float] = None
    udf: Optional[float] = None
    convenience_fee: Optional[float] = None
    currency: str = "INR"
    is_sold_out: bool = False
    is_synthetic: bool = False
    raw_hash: Optional[str] = None


class BaseAdapter(abc.ABC):
    """Abstract base class for a fare source adapter."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short source identifier, e.g. 'ixigo', 'simulator'."""

    @property
    @abc.abstractmethod
    def source_type(self) -> str:
        """'airline' | 'ota' | 'simulator'."""

    @abc.abstractmethod
    def fetch(self, route: dict, depart_date: date) -> list[FareQuote]:
        """Fetch fare quotes for a route on a given departure date.

        `route` is a dict with at least route_id/origin/dest keys.
        Implementations should raise NotImplementedError, or return an
        empty list and log to scrape_runs with status='blocked', when the
        underlying live scrape cannot be performed in this environment.
        """
        raise NotImplementedError
