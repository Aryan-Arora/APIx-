"""Hand-computed tests for the APIx index formula: 2 routes x 2 lead buckets."""
import math
from datetime import date

from apix import index


def _q(route, bucket, day, fare):
    return {
        "route_id": route,
        "lead_bucket": bucket,
        "carrier": "TestAir",
        "total_fare": fare,
        "is_sold_out": False,
        "is_outlier": False,
        "is_synthetic": True,
        "obs_date": day,
    }


ROUTE_WEIGHTS = {"R1": 0.6, "R2": 0.4}
LEAD_WEIGHTS = {"B1": 0.7, "B2": 0.3}

DAY0 = date(2026, 1, 1)
DAY1 = date(2026, 1, 2)


def test_trimmed_geo_mean_single_value():
    assert abs(index.trimmed_geo_mean([100.0]) - 100.0) < 1e-9


def test_trimmed_geo_mean_trims_tails():
    # 10 values 1..10, trim 10% total (5% each tail) -> drop none since
    # floor(10*0.05)=0 -> geometric mean of all 10.
    vals = [float(v) for v in range(1, 11)]
    gm = index.trimmed_geo_mean(vals)
    expected = math.exp(sum(math.log(v) for v in vals) / len(vals))
    assert abs(gm - expected) < 1e-9


def test_two_route_two_bucket_hand_computed():
    quotes = [
        _q("R1", "B1", DAY0, 100),
        _q("R1", "B2", DAY0, 200),
        _q("R2", "B1", DAY0, 50),
        _q("R2", "B2", DAY0, 150),
        _q("R1", "B1", DAY1, 110),
        _q("R1", "B2", DAY1, 190),
        _q("R2", "B1", DAY1, 55),
        _q("R2", "B2", DAY1, 160),
    ]
    daily = index.compute_daily_index(
        quotes, ROUTE_WEIGHTS, LEAD_WEIGHTS, base_period_days=[DAY0]
    )

    assert abs(daily[DAY0]["value"] - 100.0) < 1e-9

    # Hand-computed expected value for DAY1 (see test docstring / PR notes):
    # weights: (R1,B1)=.42 (R1,B2)=.18 (R2,B1)=.28 (R2,B2)=.12
    w = {
        ("R1", "B1"): 0.6 * 0.7,
        ("R1", "B2"): 0.6 * 0.3,
        ("R2", "B1"): 0.4 * 0.7,
        ("R2", "B2"): 0.4 * 0.3,
    }
    p0 = {("R1", "B1"): 100, ("R1", "B2"): 200, ("R2", "B1"): 50, ("R2", "B2"): 150}
    p1 = {("R1", "B1"): 110, ("R1", "B2"): 190, ("R2", "B1"): 55, ("R2", "B2"): 160}
    log_sum = sum(w[k] * math.log(p1[k] / p0[k]) for k in w)
    expected = 100.0 * math.exp(log_sum)

    assert abs(daily[DAY1]["value"] - expected) < 1e-9
    assert 106.0 < daily[DAY1]["value"] < 107.5


def test_weekly_and_monthly_aggregation_is_plain_mean():
    daily = {
        DAY0: {"value": 100.0, "n_quotes": 4},
        DAY1: {"value": 110.0, "n_quotes": 4},
    }
    weekly = index.aggregate_weekly(daily)
    monthly = index.aggregate_monthly(daily)
    assert len(weekly) == 1
    assert len(monthly) == 1
    (wk_val,) = [v["value"] for v in weekly.values()]
    (mo_val,) = [v["value"] for v in monthly.values()]
    assert abs(wk_val - 105.0) < 1e-9
    assert abs(mo_val - 105.0) < 1e-9


def test_missing_cell_carried_forward_then_dropped():
    # R2 has no quotes at all after DAY0 for B2 -> should be carried
    # forward up to 3 days, and R1 continues normally.
    from datetime import timedelta

    days = [DAY0 + timedelta(days=i) for i in range(6)]
    quotes = []
    for d in days:
        quotes.append(_q("R1", "B1", d, 100))
        quotes.append(_q("R1", "B2", d, 200))
        quotes.append(_q("R2", "B1", d, 50))
    quotes.append(_q("R2", "B2", days[0], 150))  # only present on day 0

    daily = index.compute_daily_index(
        quotes, ROUTE_WEIGHTS, LEAD_WEIGHTS, base_period_days=[days[0]]
    )
    # all 6 days should have a value (carried forward for up to 3 days,
    # then cell dropped + renormalized for remaining days, but the
    # basket is never fully empty because R1/R2-B1 have full coverage)
    assert len(daily) == 6


def test_compute_scoped_daily_index_route_scope():
    quotes = [
        _q("R1", "B1", DAY0, 100),
        _q("R1", "B2", DAY0, 200),
        _q("R2", "B1", DAY0, 50),
        _q("R1", "B1", DAY1, 120),
        _q("R1", "B2", DAY1, 220),
    ]
    daily = index.compute_scoped_daily_index(
        quotes, "route:R1", ROUTE_WEIGHTS, LEAD_WEIGHTS, base_period_days=[DAY0]
    )
    assert abs(daily[DAY0]["value"] - 100.0) < 1e-9
    assert daily[DAY1]["value"] > 100.0  # both R1 cells rose


def test_sold_out_and_outlier_quotes_excluded_from_elementary_price():
    quotes = [
        _q("R1", "B1", DAY0, 100),
        {**_q("R1", "B1", DAY0, 99999), "is_outlier": True},
        {**_q("R1", "B1", DAY0, 1), "is_sold_out": True},
    ]
    elem = index.elementary_prices(quotes)
    assert abs(elem[("R1", "B1")][DAY0] - 100.0) < 1e-9
