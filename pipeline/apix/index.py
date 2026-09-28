"""APIx index computation engine.

Formula (per spec):
  1. Elementary price P[r,b,t] = 10%-trimmed geometric mean of total_fare
     over clean, non-sold-out, non-outlier quotes for route r, lead
     bucket b, day t.
  2. Base price P0[r,b] = mean of elementary prices over the first 7 days
     of the base period (index = 100 there).
  3. Cell weight w[r,b] = route_weight[r] * lead_weight[b].
  4. APIx(t) = 100 * exp( sum_rb w[r,b] * ln(P[r,b,t] / P0[r,b]) )
  5. Weekly = mean of daily values in an ISO week; Monthly = mean of
     daily values in a calendar month.
  6. Scoped indices (per route / carrier / lead bucket) reuse the same
     formula restricted to that scope, with weights renormalized over
     the cells that remain in scope.
  7. A missing cell on a given day is carried forward from its last
     known value for up to 3 days (flagged imputed); beyond that the
     cell is dropped from that day's basket and weights renormalized.
  8. Both includes_synthetic={true,false} variants are computed.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

METHOD_VERSION = "apix-v1"
TRIM_FRACTION = 0.10
CARRY_FORWARD_MAX_DAYS = 3


def trimmed_geo_mean(values: list[float], trim: float = TRIM_FRACTION) -> float | None:
    """Geometric mean trimming `trim` fraction off EACH tail (per spec:
    "trim 10% each tail" -> trim=0.10 removes 10% from the low end and
    10% from the high end, 20% total)."""
    vals = sorted(v for v in values if v and v > 0)
    n = len(vals)
    if n == 0:
        return None
    k = int(math.floor(n * trim))
    trimmed = vals[k: n - k] if n - 2 * k > 0 else vals
    if not trimmed:
        return None
    log_sum = sum(math.log(v) for v in trimmed)
    return math.exp(log_sum / len(trimmed))


def elementary_prices(clean_quotes: list[dict]) -> dict[tuple, dict[date, float]]:
    """Group clean, priceable quotes -> elementary price per (route_id,
    lead_bucket) per day. `clean_quotes` rows must have keys: route_id,
    lead_bucket, depart_date-independent "obs_date" (the day the quote
    was observed, i.e. scraped_at date), total_fare, is_sold_out,
    is_outlier, carrier, is_synthetic."""
    groups: dict[tuple, dict[date, list[float]]] = defaultdict(lambda: defaultdict(list))
    for q in clean_quotes:
        if q.get("is_sold_out") or q.get("is_outlier"):
            continue
        key = (q["route_id"], q["lead_bucket"])
        groups[key][q["obs_date"]].append(q["total_fare"])

    result: dict[tuple, dict[date, float]] = {}
    for key, by_day in groups.items():
        result[key] = {}
        for day, vals in by_day.items():
            p = trimmed_geo_mean(vals)
            if p is not None:
                result[key][day] = p
    return result


def base_prices(elem: dict[tuple, dict[date, float]], base_period_days: list[date]) -> dict[tuple, float]:
    """P0[r,b] = mean of elementary prices over the first 7 days of the
    base period that have data."""
    p0 = {}
    for key, by_day in elem.items():
        vals = [by_day[d] for d in base_period_days if d in by_day]
        if vals:
            p0[key] = sum(vals) / len(vals)
    return p0


def _carry_forward(elem: dict[tuple, dict[date, float]], all_days: list[date]) -> dict[tuple, dict[date, float]]:
    """Fill gaps of up to CARRY_FORWARD_MAX_DAYS using the last known
    value; longer gaps are left missing (cell dropped that day)."""
    filled: dict[tuple, dict[date, float]] = {}
    for key, by_day in elem.items():
        filled[key] = {}
        last_val = None
        gap = 0
        for d in all_days:
            if d in by_day:
                last_val = by_day[d]
                gap = 0
                filled[key][d] = last_val
            elif last_val is not None and gap < CARRY_FORWARD_MAX_DAYS:
                gap += 1
                filled[key][d] = last_val
            else:
                gap += 1
    return filled


def compute_cell_weights(cell_keys: list[tuple], route_weights: dict[str, float],
                          lead_weights: dict[str, float]) -> dict[tuple, float]:
    raw = {}
    for (route_id, bucket) in cell_keys:
        rw = route_weights.get(route_id, 0.0)
        lw = lead_weights.get(bucket, 0.0)
        raw[(route_id, bucket)] = rw * lw
    total = sum(raw.values())
    if total <= 0:
        return {k: 0.0 for k in raw}
    return {k: v / total for k, v in raw.items()}


def compute_daily_index(clean_quotes: list[dict], route_weights: dict[str, float],
                         lead_weights: dict[str, float],
                         base_period_days: list[date] | None = None) -> dict[date, dict]:
    """Compute the daily APIx series (scope='all') over all days present
    in clean_quotes. Returns {day: {"value": v, "n_quotes": n}}.
    """
    if not clean_quotes:
        return {}
    obs_days = {q["obs_date"] for q in clean_quotes}
    start, end = min(obs_days), max(obs_days)
    all_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if base_period_days is None:
        base_period_days = all_days[:7]

    elem = elementary_prices(clean_quotes)
    elem_filled = _carry_forward(elem, all_days)
    p0 = base_prices(elem, base_period_days)

    cell_keys = list(p0.keys())
    counts_by_day: dict[date, int] = defaultdict(int)
    for q in clean_quotes:
        if not (q.get("is_sold_out") or q.get("is_outlier")):
            counts_by_day[q["obs_date"]] += 1

    out = {}
    for d in all_days:
        available = [k for k in cell_keys if elem_filled.get(k, {}).get(d) is not None]
        if not available:
            continue
        weights = compute_cell_weights(available, route_weights, lead_weights)
        log_sum = 0.0
        for k in available:
            p = elem_filled[k][d]
            log_sum += weights[k] * math.log(p / p0[k])
        value = 100.0 * math.exp(log_sum)
        out[d] = {"value": value, "n_quotes": counts_by_day.get(d, 0)}
    return out


def aggregate_weekly(daily: dict[date, dict]) -> dict[str, dict]:
    """ISO-week aggregation: key 'YYYY-Www'."""
    buckets: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    rep_day: dict[str, date] = {}
    for d, info in daily.items():
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        buckets[key].append(info["value"])
        counts[key] += info["n_quotes"]
        if key not in rep_day or d < rep_day[key]:
            rep_day[key] = d
    return {
        k: {"value": sum(v) / len(v), "n_quotes": counts[k], "obs_date": rep_day[k]}
        for k, v in buckets.items()
    }


def aggregate_monthly(daily: dict[date, dict]) -> dict[str, dict]:
    buckets: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    rep_day: dict[str, date] = {}
    for d, info in daily.items():
        key = f"{d.year}-{d.month:02d}"
        buckets[key].append(info["value"])
        counts[key] += info["n_quotes"]
        if key not in rep_day or d < rep_day[key]:
            rep_day[key] = d
    return {
        k: {"value": sum(v) / len(v), "n_quotes": counts[k], "obs_date": rep_day[k]}
        for k, v in buckets.items()
    }


def compute_scoped_daily_index(clean_quotes: list[dict], scope: str,
                                route_weights: dict[str, float],
                                lead_weights: dict[str, float],
                                base_period_days: list[date] | None = None) -> dict[date, dict]:
    """scope is one of 'all', 'route:<id>', 'carrier:<name>', 'lead:<bucket>'."""
    if scope == "all":
        filtered = clean_quotes
        rw, lw = route_weights, lead_weights
    elif scope.startswith("route:"):
        route_id = scope.split(":", 1)[1]
        filtered = [q for q in clean_quotes if q["route_id"] == route_id]
        rw = {route_id: 1.0}
        lw = lead_weights
    elif scope.startswith("carrier:"):
        carrier = scope.split(":", 1)[1]
        filtered = [q for q in clean_quotes if q.get("carrier") == carrier]
        rw, lw = route_weights, lead_weights
    elif scope.startswith("lead:"):
        bucket = scope.split(":", 1)[1]
        filtered = [q for q in clean_quotes if q["lead_bucket"] == bucket]
        rw = route_weights
        lw = {bucket: 1.0}
    else:
        raise ValueError(f"unknown scope: {scope}")

    return compute_daily_index(filtered, rw, lw, base_period_days)


def all_scopes(route_ids: list[str], carriers: list[str], lead_buckets: list[str]) -> list[str]:
    scopes = ["all"]
    scopes += [f"route:{r}" for r in route_ids]
    scopes += [f"carrier:{c}" for c in carriers]
    scopes += [f"lead:{b}" for b in lead_buckets]
    return scopes
