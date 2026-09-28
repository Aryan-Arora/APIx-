"""Backtest APIx against external reference series.

IMPORTANT SCOPE NOTE (see docs/BACKTEST.md): the MoSPI CPI "Transport and
Communication" group index covers far more than domestic air travel
(rail, road, fuel, postal, telecom, ...), so we do NOT claim fare-level
agreement with it. We only compare *trend* — correlation and
month-over-month direction agreement between APIx and that group index.
Route-level fare comparisons against DGCA average fares (where available)
are a separate, more literal comparison in `backtest_results`.
"""
from __future__ import annotations

import csv
import logging
import statistics
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CPI_CSV = REPO_ROOT / "data" / "reference" / "cpi_transport_group_index.csv"
DGCA_FARES_CSV = REPO_ROOT / "data" / "reference" / "dgca_monthly_fares.csv"


def _read_csv_skip_comments(path: Path) -> list[dict]:
    if not path.exists():
        logger.warning("Reference file missing: %s — backtest will run with no rows from it.", path)
        return []
    with open(path, newline="") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def load_cpi_series() -> list[dict]:
    rows = _read_csv_skip_comments(CPI_CSV)
    if rows and any(r.get("source_note") == "PLACEHOLDER" for r in rows):
        logger.warning(
            "cpi_transport_group_index.csv is PLACEHOLDER data — real MoSPI "
            "CPI Transport & Communication group figures must be supplied "
            "by a human before this backtest's trend comparison is meaningful."
        )
    return rows


def load_dgca_fares() -> list[dict]:
    rows = _read_csv_skip_comments(DGCA_FARES_CSV)
    if rows and any(r.get("source_note") == "PLACEHOLDER" for r in rows):
        logger.warning(
            "dgca_monthly_fares.csv is PLACEHOLDER data — real DGCA "
            "average domestic fare figures must be supplied by a human "
            "before route-level backtest results are meaningful."
        )
    return rows


def monthly_apix_from_index_values(monthly_rows: list[dict]) -> dict[str, float]:
    """monthly_rows: list of {"obs_date"/"month": 'YYYY-MM', "value": v}
    for scope='all', freq='monthly'. Returns {month: value}."""
    out = {}
    for r in monthly_rows:
        month = r.get("month") or r.get("obs_date")
        out[str(month)[:7]] = r["value"]
    return out


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        return None


def direction_agreement(xs: list[float], ys: list[float]) -> float | None:
    """% of consecutive month-over-month moves where sign(delta x) ==
    sign(delta y)."""
    if len(xs) < 2:
        return None
    agree = 0
    total = 0
    for i in range(1, len(xs)):
        dx = xs[i] - xs[i - 1]
        dy = ys[i] - ys[i - 1]
        if dx == 0 or dy == 0:
            continue
        total += 1
        if (dx > 0) == (dy > 0):
            agree += 1
    if total == 0:
        return None
    return agree / total


def mape(apix_vals: list[float], dgca_vals: list[float]) -> float | None:
    errs = []
    for a, d in zip(apix_vals, dgca_vals):
        if d:
            errs.append(abs(a - d) / d)
    if not errs:
        return None
    return sum(errs) / len(errs) * 100.0


def run_backtest(apix_monthly_all: dict[str, float]) -> tuple[list[dict], list[dict]]:
    """Compute backtest_results (route-level vs DGCA placeholder) and
    backtest_summary (trend vs CPI group index) rows.

    `apix_monthly_all` is {month_str: apix_value} for the 'all' scope.
    Returns (backtest_results_rows, backtest_summary_rows).
    """
    cpi_rows = load_cpi_series()
    dgca_rows = load_dgca_fares()

    results_rows: list[dict] = []
    for row in dgca_rows:
        month = row["month"]
        route_id = row["route_id"]
        dgca_avg = float(row["avg_fare"])
        apix_val = apix_monthly_all.get(month)
        if apix_val is None:
            continue
        abs_pct_err = abs(apix_val - dgca_avg) / dgca_avg * 100.0 if dgca_avg else None
        results_rows.append({
            "month": month,
            "route_id": route_id,
            "apix_avg_fare": apix_val,
            "dgca_avg_fare": dgca_avg,
            "abs_pct_error": abs_pct_err,
            "source_note": "DGCA figure is PLACEHOLDER data; comparison illustrative only",
        })

    summary_rows: list[dict] = []
    common_months = sorted(set(apix_monthly_all) & {r["month"] for r in cpi_rows})
    if common_months:
        apix_vals = [apix_monthly_all[m] for m in common_months]
        cpi_by_month = {r["month"]: float(r["index_value"]) for r in cpi_rows}
        cpi_vals = [cpi_by_month[m] for m in common_months]

        corr = correlation(apix_vals, cpi_vals)
        dir_agree = direction_agreement(apix_vals, cpi_vals)

        summary_rows.append({
            "metric": "correlation_vs_cpi_transport_group",
            "value": corr,
            "note": "Pearson correlation, APIx monthly vs MoSPI CPI Transport & "
                    "Communication group index (PLACEHOLDER data — see BACKTEST.md)",
        })
        summary_rows.append({
            "metric": "direction_agreement_vs_cpi_transport_group",
            "value": dir_agree,
            "note": "Fraction of months where APIx and CPI group index moved "
                    "the same direction month-over-month (PLACEHOLDER data)",
        })
    else:
        summary_rows.append({
            "metric": "correlation_vs_cpi_transport_group",
            "value": None,
            "note": "No overlapping months between APIx history and CPI reference series",
        })

    if results_rows:
        route_mape = mape(
            [r["apix_avg_fare"] for r in results_rows],
            [r["dgca_avg_fare"] for r in results_rows],
        )
        summary_rows.append({
            "metric": "MAPE_vs_dgca_fares",
            "value": route_mape,
            "note": "Mean absolute % error, APIx vs DGCA monthly avg fare "
                    "(PLACEHOLDER DGCA data — illustrative only)",
        })

    return results_rows, summary_rows
