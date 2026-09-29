"""Parse observed IndiGo accessibility cards; no network or database writes.

Callers must verify the displayed search date and capture timestamp. This
parser is not an unattended collector and does not establish source permission.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time

from .base import FareQuote


def parse_cards(
    cards: list[str],
    route: dict,
    depart_date: date,
    observed_at: datetime,
) -> list[FareQuote]:
    """Return exact-airport, nonstop Economy 'starts at' observations.

    Nearby airports, connections and incomplete cards are excluded. Unknown
    fee components remain null. Repeated copies of a card are deduplicated.
    The observed_at timestamp must be timezone-aware; never substitute the
    import time for a historical capture time.
    """
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    origin, dest = route["origin"], route["dest"]
    if (
        not re.fullmatch(r"[A-Z]{3}", origin)
        or not re.fullmatch(r"[A-Z]{3}", dest)
        or origin == dest
    ):
        raise ValueError("Expected distinct three-letter airport codes")
    lead_days = (depart_date - observed_at.date()).days
    if lead_days < 0:
        raise ValueError("Departure precedes observation date")
    quotes: list[FareQuote] = []
    seen: set[str] = set()
    for card in cards:
        if "Non-stop" not in card:
            continue
        airports = re.findall(r"^([A-Z]{3})(?:, T\d+)?\s*$", card, re.MULTILINE)
        if airports != [origin, dest]:
            continue
        flights = re.findall(r"^6E\s*\n(\d{1,4})\s*$", card, re.MULTILINE)
        fare = re.search(r"Economy Starts at ₹([\d,]+(?:\.\d{1,2})?)", card)
        departure = re.search(r"^(\d{2}):(\d{2})\s*$", card, re.MULTILINE)
        if len(flights) != 1 or not fare or not departure:
            continue
        amount = float(fare.group(1).replace(",", ""))
        if amount <= 0:
            continue
        try:
            depart_time = time(int(departure.group(1)), int(departure.group(2)))
        except ValueError:
            continue
        identity = f"indigo|{origin}|{dest}|{depart_date}|6E{flights[0]}|{depart_time}|{amount}|{observed_at.isoformat()}"
        digest = hashlib.sha256(identity.encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        quotes.append(
            FareQuote(
                scraped_at=observed_at,
                source="indigo",
                source_type="airline",
                route_id="-".join(sorted((origin, dest))),
                origin=origin,
                dest=dest,
                depart_date=depart_date,
                total_fare=amount,
                carrier="6E",
                flight_no=f"6E{flights[0]}",
                depart_time=depart_time,
                lead_days=lead_days,
                lead_bucket=(
                    f"T+{lead_days}" if lead_days in {1, 7, 15, 30, 45} else None
                ),
                fare_class="Economy starts-at",
                is_synthetic=False,
                raw_hash=digest,
            )
        )
    return quotes
