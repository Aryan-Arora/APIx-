"""Deterministic synthetic fare generator.

This is the PRIORITY data source for the hackathon demo: no live scraper
is required to produce a full, plausible, testable index. Given the same
SIMULATOR_SEED, `backfill()` always produces the same fare history.

ASSUMPTION: `ROUTE_BASE` fares below (₹4000-9000) are rough, publicly
plausible averages for each route's approximate distance band (e.g.
short intra-metro hops like BLR-HYD are cheaper than long-haul BOM-DEL /
CCU-DEL). They are NOT sourced from any live pricing feed and must be
recalibrated against real data when it becomes available.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .base import BaseAdapter, FareQuote

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES_CSV = REPO_ROOT / "data" / "reference" / "routes.csv"
LEAD_WEIGHTS_JSON = REPO_ROOT / "data" / "reference" / "lead_weights.json"

LEAD_BUCKETS = {"T+1": 1, "T+7": 7, "T+15": 15, "T+30": 30, "T+45": 45}

# ASSUMPTION: plausible average one-way economy fares (INR) per route,
# calibrated loosely to route distance/popularity. See module docstring.
ROUTE_BASE = {
    "BOM-DEL": 6200,
    "BLR-DEL": 6400,
    "BLR-BOM": 4600,
    "CCU-DEL": 6800,
    "BLR-HYD": 4100,
    "DEL-MAA": 7200,
    "DEL-HYD": 5800,
    "BOM-HYD": 4400,
    "BOM-MAA": 5200,
    "AMD-DEL": 4900,
}

CARRIERS = {
    "IndiGo": {"code": "6E", "factor": 0.96},
    "Air India": {"code": "AI", "factor": 1.08},
    "Air India Express": {"code": "IX", "factor": 0.90},
    "Akasa Air": {"code": "QP", "factor": 0.98},
    "SpiceJet": {"code": "SG", "factor": 1.00},
}

# ASSUMPTION: approximate 2025/2026 Indian festival dates used to model
# demand spikes in the fare curve (±3 days around each).
FESTIVAL_DATES_2025_2026 = [
    date(2025, 10, 2),   # Durga Puja / Gandhi Jayanti window
    date(2025, 10, 20),  # Diwali 2025
    date(2026, 3, 4),    # Holi 2026
    date(2026, 10, 9),   # Durga Puja / Diwali window 2026 (approx)
]


def _seasonality(d: date) -> float:
    """Festival spikes + mild annual seasonality (summer/winter peaks)."""
    factor = 1.0
    for fd in FESTIVAL_DATES_2025_2026:
        delta = abs((d - fd).days)
        if delta <= 3:
            factor *= 1.35 - 0.05 * delta  # peak on the day, decaying
    # mild summer (Apr-Jun) and winter-holiday (Dec) seasonal bump
    month = d.month
    if month in (4, 5, 6):
        factor *= 1.08
    if month == 12:
        factor *= 1.10
    return factor


def _dow_factor(d: date) -> float:
    # Friday/Sunday pricier (weekend travel), midweek cheaper.
    dow = d.weekday()  # Mon=0..Sun=6
    table = {0: 1.00, 1: 0.96, 2: 0.95, 3: 1.02, 4: 1.12, 5: 1.05, 6: 1.10}
    return table[dow]


def _lead_factor(lead_days: int) -> float:
    # Closer to departure => pricier, roughly, with a last-minute spike.
    if lead_days <= 1:
        return 1.30
    if lead_days <= 7:
        return 1.15
    if lead_days <= 15:
        return 1.05
    if lead_days <= 30:
        return 0.95
    return 0.88


def _fuel_drift(today: date, d: date) -> float:
    """Mild fuel-surcharge-style linear drift over time (few % over 90d)."""
    days_ago = (today - d).days
    return 1.0 - 0.0006 * days_ago  # slightly cheaper further in the past


def _lead_bucket_for_days(lead_days: int) -> str:
    # nearest bucket
    return min(LEAD_BUCKETS, key=lambda b: abs(LEAD_BUCKETS[b] - lead_days))


def load_routes() -> list[dict]:
    routes = []
    with open(ROUTES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["active"].lower() == "true":
                routes.append(row)
    return routes


def _raw_hash(source: str, route_id: str, depart_date: date, carrier: str,
              flight_no: str, scraped_at: datetime) -> str:
    key = f"{source}|{route_id}|{depart_date}|{carrier}|{flight_no}|{scraped_at.date()}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


class SimulatorAdapter(BaseAdapter):
    """Synthetic fare source, deterministic given SIMULATOR_SEED."""

    def __init__(self, seed: int | None = None):
        self.seed = seed if seed is not None else int(os.environ.get("SIMULATOR_SEED", 42))

    @property
    def name(self) -> str:
        return "simulator"

    @property
    def source_type(self) -> str:
        return "simulator"

    def _rng_for(self, *parts) -> random.Random:
        key = f"{self.seed}|" + "|".join(str(p) for p in parts)
        h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        return random.Random(h)

    def fetch(self, route: dict, depart_date: date) -> list[FareQuote]:
        """Generate quotes for one route/departure-date across carriers
        and lead buckets, as of "today" (used by run-daily)."""
        today = date.today()
        lead_days = (depart_date - today).days
        if lead_days < 0:
            return []
        return self._quotes_for(route, depart_date, today, lead_days,
                                 scraped_at=datetime.utcnow())

    def _quotes_for(self, route: dict, depart_date: date, today: date,
                     lead_days: int, scraped_at: datetime) -> list[FareQuote]:
        route_id = route["route_id"]
        base = ROUTE_BASE.get(route_id, 5500)
        quotes: list[FareQuote] = []
        lead_bucket = _lead_bucket_for_days(max(lead_days, 0))

        for carrier_name, meta in CARRIERS.items():
            rng = self._rng_for(route_id, depart_date, carrier_name, "flight")
            flight_no = f"{meta['code']}{rng.randint(100, 999)}"

            mult = (
                _seasonality(depart_date)
                * _dow_factor(depart_date)
                * _lead_factor(max(lead_days, 1))
                * meta["factor"]
                * _fuel_drift(today, depart_date)
            )
            noise_rng = self._rng_for(route_id, depart_date, carrier_name, "noise", scraped_at.date())
            # lognormal noise, mean ~1, small sigma
            noise = math.exp(noise_rng.gauss(0, 0.06))
            total = round(base * mult * noise, -1)  # round to nearest 10

            is_sold_out = False
            is_outlier_row = False
            flag_rng = self._rng_for(route_id, depart_date, carrier_name, "flags", scraped_at.date())
            r = flag_rng.random()
            if r < 0.03:
                is_sold_out = True
            elif r < 0.05:
                # inject an outlier to exercise the cleaner
                is_outlier_row = True
                total = total * flag_rng.choice([3.5, 0.25])

            base_fare = round(total * flag_rng.uniform(0.70, 0.80), 0)
            remaining = total - base_fare
            taxes = round(remaining * 0.55, 0)
            udf = round(remaining * 0.25, 0)
            convenience_fee = round(remaining - taxes - udf, 0)

            quotes.append(
                FareQuote(
                    scraped_at=scraped_at,
                    source=self.name,
                    source_type=self.source_type,
                    route_id=route_id,
                    origin=route["origin"],
                    dest=route["dest"],
                    depart_date=depart_date,
                    total_fare=float(total),
                    carrier=carrier_name,
                    flight_no=flight_no,
                    lead_days=lead_days,
                    lead_bucket=lead_bucket,
                    fare_class="Y",
                    base_fare=float(base_fare),
                    taxes=float(taxes),
                    udf=float(udf),
                    convenience_fee=float(convenience_fee),
                    is_sold_out=is_sold_out,
                    is_synthetic=True,
                    raw_hash=_raw_hash(self.name, route_id, depart_date, carrier_name,
                                       flight_no, scraped_at),
                )
            )
        return quotes

    def backfill(self, days: int = 45, end_date: date | None = None) -> list[FareQuote]:
        """Generate `days` days of history (scraped_at) for all active
        routes x all 5 lead buckets x all carriers, ending on `end_date`
        (default: today).

        For each historical "as-of" day, we simulate what would have been
        quoted for departures at each of the 5 lead-time offsets from
        that day, so the resulting index has full route/lead-bucket
        coverage on every day of history.
        """
        routes = load_routes()
        end = end_date or date.today()
        all_quotes: list[FareQuote] = []
        for day_offset in range(days, -1, -1):
            as_of = end - timedelta(days=day_offset)
            for route in routes:
                for bucket_name, bucket_lead in LEAD_BUCKETS.items():
                    depart_date = as_of + timedelta(days=bucket_lead)
                    scraped_at = datetime.combine(as_of, datetime.min.time())
                    quotes = self._quotes_for(
                        route, depart_date, as_of, bucket_lead, scraped_at
                    )
                    all_quotes.extend(quotes)
        return all_quotes
