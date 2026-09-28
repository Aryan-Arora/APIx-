"""Raw fare_quotes -> clean_quotes transformation.

Steps: dedup by raw_hash, flag (but keep) sold-out rows, detect outliers
per (route, lead_bucket, day) using MAD on log(total_fare), impute
missing fee-component breakdowns from route+carrier medians, and
validate total ~= base+taxes+udf+fee.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

MAD_Z_THRESHOLD = 3.5  # standard robust-outlier threshold
FEE_TOLERANCE_PCT = 0.05  # 5% tolerance on total vs sum-of-parts


@dataclass
class CleanRow:
    fare_quote_id: int | None
    scraped_at: object
    source: str
    source_type: str
    carrier: str | None
    flight_no: str | None
    route_id: str | None
    origin: str | None
    dest: str | None
    depart_date: object
    depart_time: object
    lead_days: int | None
    lead_bucket: str | None
    fare_class: str | None
    base_fare: float | None
    taxes: float | None
    udf: float | None
    convenience_fee: float | None
    total_fare: float
    currency: str
    is_sold_out: bool
    is_synthetic: bool
    raw_hash: str | None
    is_outlier: bool = False
    quality_flag: str = "ok"


def dedup(rows: Iterable[dict]) -> list[dict]:
    """Dedup by raw_hash, keeping first occurrence (stable order)."""
    seen = set()
    out = []
    for r in rows:
        h = r.get("raw_hash")
        key = h if h else (r.get("source"), r.get("route_id"), r.get("depart_date"),
                            r.get("carrier"), r.get("flight_no"), r.get("scraped_at"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _mad_outlier_flags(values: list[float]) -> list[bool]:
    """Return a bool-per-value outlier flag using MAD on log(values)."""
    if len(values) < 4:
        return [False] * len(values)
    logs = [math.log(v) for v in values if v > 0]
    if len(logs) < 4:
        return [False] * len(values)
    med = statistics.median(logs)
    abs_devs = [abs(x - med) for x in logs]
    mad = statistics.median(abs_devs)
    if mad == 0:
        return [False] * len(values)
    # 0.6745 scales MAD to be comparable to a standard deviation for
    # normally distributed data.
    flags = []
    for v in values:
        if v <= 0:
            flags.append(True)
            continue
        z = 0.6745 * (math.log(v) - med) / mad
        flags.append(abs(z) > MAD_Z_THRESHOLD)
    return flags


def detect_outliers(rows: list[dict]) -> None:
    """Mutates rows in place, setting is_outlier per (route, lead_bucket,
    depart-day-of-observation) group, using non-sold-out rows only for
    determining the group statistics (sold-out rows are never flagged as
    price outliers here since we don't trust their price)."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("is_sold_out"):
            r["is_outlier"] = False
            continue
        key = (r.get("route_id"), r.get("lead_bucket"),
               str(r.get("scraped_at"))[:10])
        groups[key].append(r)

    for key, group_rows in groups.items():
        values = [r["total_fare"] for r in group_rows]
        flags = _mad_outlier_flags(values)
        for r, flag in zip(group_rows, flags):
            r["is_outlier"] = flag


def _route_carrier_medians(rows: list[dict]) -> dict[tuple, dict]:
    buckets: dict[tuple, dict[str, list[float]]] = defaultdict(
        lambda: {"base_fare": [], "taxes": [], "udf": [], "convenience_fee": []}
    )
    for r in rows:
        if r.get("base_fare") is None:
            continue
        key = (r.get("route_id"), r.get("carrier"))
        for field in ("base_fare", "taxes", "udf", "convenience_fee"):
            val = r.get(field)
            if val is not None:
                buckets[key][field].append(val)
    medians = {}
    for key, fields in buckets.items():
        medians[key] = {
            f: (statistics.median(vals) if vals else None)
            for f, vals in fields.items()
        }
    return medians


def impute_missing_fees(rows: list[dict]) -> None:
    """Fill missing base_fare/taxes/udf/convenience_fee from route+carrier
    medians, scaled to the row's actual total_fare, flagging
    quality_flag='fee_estimated' when imputation happened."""
    medians = _route_carrier_medians(rows)
    for r in rows:
        if r.get("total_fare") is None:
            continue
        missing = any(
            r.get(f) is None for f in ("base_fare", "taxes", "udf", "convenience_fee")
        )
        if not missing:
            continue
        key = (r.get("route_id"), r.get("carrier"))
        med = medians.get(key)
        if not med or any(v is None for v in med.values()):
            # fall back to a fixed split assumption
            total = r["total_fare"]
            r["base_fare"] = r.get("base_fare") or round(total * 0.75, 0)
            r["taxes"] = r.get("taxes") or round(total * 0.14, 0)
            r["udf"] = r.get("udf") or round(total * 0.06, 0)
            r["convenience_fee"] = r.get("convenience_fee") or round(total * 0.05, 0)
        else:
            med_total = sum(med.values())
            total = r["total_fare"]
            scale = (total / med_total) if med_total else 1.0
            r["base_fare"] = r.get("base_fare") or round(med["base_fare"] * scale, 0)
            r["taxes"] = r.get("taxes") or round(med["taxes"] * scale, 0)
            r["udf"] = r.get("udf") or round(med["udf"] * scale, 0)
            r["convenience_fee"] = r.get("convenience_fee") or round(
                med["convenience_fee"] * scale, 0
            )
        r["quality_flag"] = "fee_estimated"


def validate_totals(rows: list[dict]) -> None:
    """Sanity-check total ~= base+taxes+udf+fee within FEE_TOLERANCE_PCT;
    does not drop rows, just leaves quality_flag as-is (fee estimation
    already handles the missing-breakdown case)."""
    for r in rows:
        parts = [r.get("base_fare"), r.get("taxes"), r.get("udf"), r.get("convenience_fee")]
        if any(p is None for p in parts):
            continue
        total = r["total_fare"]
        summed = sum(parts)
        if total > 0 and abs(summed - total) / total > FEE_TOLERANCE_PCT:
            # doesn't invalidate the row, but worth flagging if not
            # already flagged otherwise
            if r.get("quality_flag") == "ok":
                r["quality_flag"] = "fee_estimated"


def clean(rows: list[dict]) -> list[dict]:
    """Full cleaning pipeline: dedup -> outlier detect -> impute fees ->
    validate totals. Returns a new list of clean-quote dicts (does not
    mutate the input list object, though row dicts are copied)."""
    rows = [dict(r) for r in dedup(rows)]
    for r in rows:
        r.setdefault("is_outlier", False)
        r.setdefault("quality_flag", "ok")
        if r.get("is_sold_out"):
            r["quality_flag"] = "ok"  # kept, but excluded from price calcs downstream

    detect_outliers(rows)
    for r in rows:
        if r.get("is_outlier"):
            r["quality_flag"] = "outlier"

    impute_missing_fees(rows)
    validate_totals(rows)
    return rows
