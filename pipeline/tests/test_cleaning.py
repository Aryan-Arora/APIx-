from datetime import date, datetime

from apix import cleaning


def _row(**kw):
    base = dict(
        scraped_at=datetime(2026, 1, 1),
        source="simulator",
        source_type="simulator",
        carrier="IndiGo",
        flight_no="6E123",
        route_id="BOM-DEL",
        origin="BOM",
        dest="DEL",
        depart_date=date(2026, 2, 1),
        depart_time=None,
        lead_days=30,
        lead_bucket="T+30",
        fare_class="Y",
        base_fare=4000.0,
        taxes=800.0,
        udf=200.0,
        convenience_fee=200.0,
        total_fare=5200.0,
        currency="INR",
        is_sold_out=False,
        is_synthetic=True,
        raw_hash="abc123",
    )
    base.update(kw)
    return base


def test_dedup_by_raw_hash():
    rows = [_row(raw_hash="h1"), _row(raw_hash="h1"), _row(raw_hash="h2")]
    out = cleaning.dedup(rows)
    assert len(out) == 2


def test_dedup_without_hash_uses_fallback_key():
    rows = [_row(raw_hash=None), _row(raw_hash=None)]
    out = cleaning.dedup(rows)
    assert len(out) == 1


def test_outlier_detection_flags_extreme_value():
    normal = [_row(raw_hash=f"h{i}", total_fare=5000 + i * 10) for i in range(10)]
    outlier = _row(raw_hash="hout", total_fare=50000)
    rows = normal + [outlier]
    cleaning.detect_outliers(rows)
    assert outlier["is_outlier"] is True
    assert all(not r["is_outlier"] for r in normal)


def test_sold_out_rows_never_flagged_as_price_outliers():
    rows = [_row(raw_hash="h1", total_fare=1.0, is_sold_out=True)]
    cleaning.detect_outliers(rows)
    assert rows[0]["is_outlier"] is False


def test_impute_missing_fees_from_route_carrier_median():
    known = [_row(raw_hash=f"h{i}", total_fare=5000) for i in range(5)]
    missing = _row(
        raw_hash="hmiss", total_fare=5000,
        base_fare=None, taxes=None, udf=None, convenience_fee=None,
    )
    rows = known + [missing]
    cleaning.impute_missing_fees(rows)
    assert missing["base_fare"] is not None
    assert missing["quality_flag"] == "fee_estimated"
    parts = [missing["base_fare"], missing["taxes"], missing["udf"], missing["convenience_fee"]]
    assert abs(sum(parts) - missing["total_fare"]) / missing["total_fare"] < 0.05


def test_full_clean_pipeline_runs_end_to_end():
    rows = [_row(raw_hash=f"h{i}", total_fare=5000 + i) for i in range(6)]
    rows.append(_row(raw_hash="hdup", total_fare=5200))
    rows.append(dict(rows[-1]))  # exact duplicate
    out = cleaning.clean(rows)
    assert len(out) == 7  # duplicate removed
    assert all("quality_flag" in r for r in out)
