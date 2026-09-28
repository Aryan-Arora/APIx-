"""APIx CLI: python -m apix.pipeline <command>

Commands: backfill, compute-index, backtest, run-daily
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime

import click

from . import backtest as backtest_mod
from . import cleaning, db, index
from .adapters.base import FareQuote
from .adapters.cleartrip import ClearTripAdapter
from .adapters.easemytrip import EaseMyTripAdapter
from .adapters.indigo import IndiGoAdapter
from .adapters.ixigo import IxigoAdapter
from .adapters.simulator import LEAD_WEIGHTS_JSON, ROUTES_CSV, SimulatorAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("apix.pipeline")

STUB_ADAPTERS = [IxigoAdapter(), EaseMyTripAdapter(), ClearTripAdapter(), IndiGoAdapter()]


def load_route_weights() -> dict[str, float]:
    weights = {}
    with open(ROUTES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["active"].lower() == "true":
                weights[row["route_id"]] = float(row["dgca_pax_share"])
    return weights


def load_lead_weights() -> dict[str, float]:
    with open(LEAD_WEIGHTS_JSON) as f:
        return json.load(f)


def seed_routes(session) -> None:
    existing = {r.route_id for r in session.query(db.Route).all()}
    with open(ROUTES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["route_id"] in existing:
                continue
            session.add(db.Route(
                route_id=row["route_id"],
                origin=row["origin"],
                dest=row["dest"],
                dgca_pax_share=float(row["dgca_pax_share"]),
                active=row["active"].lower() == "true",
            ))
    session.commit()


def _fare_quote_to_row(fq: FareQuote) -> db.FareQuote:
    return db.FareQuote(
        scraped_at=fq.scraped_at,
        source=fq.source,
        source_type=fq.source_type,
        carrier=fq.carrier,
        flight_no=fq.flight_no,
        route_id=fq.route_id,
        origin=fq.origin,
        dest=fq.dest,
        depart_date=fq.depart_date,
        depart_time=fq.depart_time,
        lead_days=fq.lead_days,
        lead_bucket=fq.lead_bucket,
        fare_class=fq.fare_class,
        base_fare=fq.base_fare,
        taxes=fq.taxes,
        udf=fq.udf,
        convenience_fee=fq.convenience_fee,
        total_fare=fq.total_fare,
        currency=fq.currency,
        is_sold_out=fq.is_sold_out,
        is_synthetic=fq.is_synthetic,
        raw_hash=fq.raw_hash,
    )


@click.group()
def cli():
    """APIx data pipeline."""


@cli.command("backfill")
@click.option("--days", default=45, show_default=True, help="Days of synthetic history to generate.")
def backfill_cmd(days: int):
    engine = db.get_engine()
    db.init_db(engine)
    session = db.get_session(engine)
    seed_routes(session)

    sim = SimulatorAdapter()
    run = db.ScrapeRun(started_at=datetime.utcnow(), source="simulator", status="running")
    session.add(run)
    session.commit()

    quotes = sim.backfill(days=days)
    for fq in quotes:
        session.add(_fare_quote_to_row(fq))
    run.finished_at = datetime.utcnow()
    run.status = "ok"
    run.quotes_count = len(quotes)
    session.commit()
    logger.info("Backfilled %d synthetic fare quotes over %d days.", len(quotes), days)


def _fetch_clean_rows_for_index(session) -> list[dict]:
    """Read clean_quotes and shape them for index.py (adds obs_date)."""
    rows = []
    for cq in session.query(db.CleanQuote).all():
        rows.append({
            "route_id": cq.route_id,
            "lead_bucket": cq.lead_bucket,
            "carrier": cq.carrier,
            "total_fare": cq.total_fare,
            "is_sold_out": cq.is_sold_out,
            "is_outlier": cq.is_outlier,
            "is_synthetic": cq.is_synthetic,
            "obs_date": cq.scraped_at.date() if hasattr(cq.scraped_at, "date") else cq.scraped_at,
        })
    return rows


@cli.command("compute-index")
def compute_index_cmd():
    engine = db.get_engine()
    db.init_db(engine)
    session = db.get_session(engine)

    raw_rows = []
    for fq in session.query(db.FareQuote).all():
        raw_rows.append({
            "fare_quote_id": fq.id,
            "scraped_at": fq.scraped_at,
            "source": fq.source,
            "source_type": fq.source_type,
            "carrier": fq.carrier,
            "flight_no": fq.flight_no,
            "route_id": fq.route_id,
            "origin": fq.origin,
            "dest": fq.dest,
            "depart_date": fq.depart_date,
            "depart_time": fq.depart_time,
            "lead_days": fq.lead_days,
            "lead_bucket": fq.lead_bucket,
            "fare_class": fq.fare_class,
            "base_fare": fq.base_fare,
            "taxes": fq.taxes,
            "udf": fq.udf,
            "convenience_fee": fq.convenience_fee,
            "total_fare": fq.total_fare,
            "currency": fq.currency,
            "is_sold_out": fq.is_sold_out,
            "is_synthetic": fq.is_synthetic,
            "raw_hash": fq.raw_hash,
        })

    if not raw_rows:
        logger.warning("No fare_quotes found; run `backfill` first.")
        return

    cleaned = cleaning.clean(raw_rows)

    # Clear and rewrite clean_quotes (idempotent recompute)
    session.query(db.CleanQuote).delete()
    for r in cleaned:
        session.add(db.CleanQuote(
            fare_quote_id=r.get("fare_quote_id"),
            scraped_at=r["scraped_at"],
            source=r["source"],
            source_type=r["source_type"],
            carrier=r.get("carrier"),
            flight_no=r.get("flight_no"),
            route_id=r.get("route_id"),
            origin=r.get("origin"),
            dest=r.get("dest"),
            depart_date=r.get("depart_date"),
            depart_time=r.get("depart_time"),
            lead_days=r.get("lead_days"),
            lead_bucket=r.get("lead_bucket"),
            fare_class=r.get("fare_class"),
            base_fare=r.get("base_fare"),
            taxes=r.get("taxes"),
            udf=r.get("udf"),
            convenience_fee=r.get("convenience_fee"),
            total_fare=r["total_fare"],
            currency=r.get("currency", "INR"),
            is_sold_out=r.get("is_sold_out", False),
            is_synthetic=r.get("is_synthetic", False),
            raw_hash=r.get("raw_hash"),
            is_outlier=r.get("is_outlier", False),
            quality_flag=r.get("quality_flag", "ok"),
        ))
    session.commit()
    logger.info("Wrote %d clean_quotes rows.", len(cleaned))

    route_weights = load_route_weights()
    lead_weights = load_lead_weights()
    route_ids = list(route_weights.keys())
    carriers = sorted({r["carrier"] for r in cleaned if r.get("carrier")})
    lead_buckets = list(lead_weights.keys())
    scopes = index.all_scopes(route_ids, carriers, lead_buckets)

    session.query(db.IndexValue).delete()
    session.commit()

    n_written = 0
    for includes_synthetic in (True, False):
        rows_for_mode = cleaned if includes_synthetic else [r for r in cleaned if not r.get("is_synthetic")]
        rows_for_index = [
            {**r, "obs_date": (r["scraped_at"].date() if hasattr(r["scraped_at"], "date") else r["scraped_at"])}
            for r in rows_for_mode
        ]
        if not rows_for_index:
            continue
        for scope in scopes:
            daily = index.compute_scoped_daily_index(rows_for_index, scope, route_weights, lead_weights)
            if not daily:
                continue
            for d, info in daily.items():
                session.add(db.IndexValue(
                    obs_date=d, freq="daily", scope=scope,
                    includes_synthetic=includes_synthetic,
                    value=info["value"], n_quotes=info["n_quotes"],
                    method_version=index.METHOD_VERSION,
                ))
                n_written += 1
            weekly = index.aggregate_weekly(daily)
            for wk, info in weekly.items():
                session.add(db.IndexValue(
                    obs_date=info["obs_date"], freq="weekly", scope=scope,
                    includes_synthetic=includes_synthetic,
                    value=info["value"], n_quotes=info["n_quotes"],
                    method_version=index.METHOD_VERSION,
                ))
                n_written += 1
            monthly = index.aggregate_monthly(daily)
            for mo, info in monthly.items():
                session.add(db.IndexValue(
                    obs_date=info["obs_date"], freq="monthly", scope=scope,
                    includes_synthetic=includes_synthetic,
                    value=info["value"], n_quotes=info["n_quotes"],
                    method_version=index.METHOD_VERSION,
                ))
                n_written += 1
    session.commit()
    logger.info("Wrote %d index_values rows across scopes/frequencies/synthetic modes.", n_written)


@cli.command("backtest")
def backtest_cmd():
    engine = db.get_engine()
    db.init_db(engine)
    session = db.get_session(engine)

    monthly_all = session.query(db.IndexValue).filter_by(
        freq="monthly", scope="all", includes_synthetic=True
    ).all()
    apix_monthly = {}
    for row in monthly_all:
        month_key = f"{row.obs_date.year}-{row.obs_date.month:02d}"
        apix_monthly[month_key] = row.value

    if not apix_monthly:
        logger.warning("No monthly index_values found; run `compute-index` first.")

    results_rows, summary_rows = backtest_mod.run_backtest(apix_monthly)

    session.query(db.BacktestResult).delete()
    session.query(db.BacktestSummary).delete()
    for r in results_rows:
        session.add(db.BacktestResult(
            month=datetime.strptime(r["month"], "%Y-%m").date(),
            route_id=r["route_id"],
            apix_avg_fare=r["apix_avg_fare"],
            dgca_avg_fare=r["dgca_avg_fare"],
            abs_pct_error=r["abs_pct_error"],
            source_note=r["source_note"],
        ))
    for s in summary_rows:
        session.add(db.BacktestSummary(metric=s["metric"], value=s["value"], note=s["note"]))
    session.commit()
    logger.info("Backtest complete: %d result rows, %d summary metrics.",
                len(results_rows), len(summary_rows))
    for s in summary_rows:
        logger.info("  %s = %s (%s)", s["metric"], s["value"], s["note"])


@cli.command("run-daily")
def run_daily_cmd():
    """Scrape all adapters (incl. simulator) for today -> clean -> index."""
    engine = db.get_engine()
    db.init_db(engine)
    session = db.get_session(engine)
    seed_routes(session)

    route_weights = load_route_weights()
    routes = [{"route_id": rid} for rid in route_weights]
    with open(ROUTES_CSV, newline="") as f:
        route_rows = [r for r in csv.DictReader(f) if r["active"].lower() == "true"]

    lead_weights = load_lead_weights()
    from .adapters.simulator import LEAD_BUCKETS
    today = date.today()

    # 1) live/stub adapters: attempt and log blocked status honestly
    for adapter in STUB_ADAPTERS:
        run = db.ScrapeRun(started_at=datetime.utcnow(), source=adapter.name, status="running")
        session.add(run)
        session.commit()
        try:
            quotes = []
            for r in route_rows:
                quotes.extend(adapter.fetch(r, today))
            for fq in quotes:
                session.add(_fare_quote_to_row(fq))
            run.status = "ok"
            run.quotes_count = len(quotes)
        except NotImplementedError as e:
            run.status = "blocked"
            run.quotes_count = 0
            run.error_msg = str(e)
            logger.warning("Adapter %s blocked: %s", adapter.name, e)
        except Exception as e:  # pragma: no cover - defensive
            run.status = "error"
            run.error_msg = str(e)
            logger.exception("Adapter %s failed", adapter.name)
        finally:
            run.finished_at = datetime.utcnow()
            session.commit()

    # 2) simulator: always works, produces today's quotes for all lead buckets
    sim = SimulatorAdapter()
    run = db.ScrapeRun(started_at=datetime.utcnow(), source="simulator", status="running")
    session.add(run)
    session.commit()
    sim_quotes = []
    for r in route_rows:
        for bucket_lead in LEAD_BUCKETS.values():
            from datetime import timedelta
            depart_date = today + timedelta(days=bucket_lead)
            sim_quotes.extend(sim._quotes_for(r, depart_date, today, bucket_lead,
                                               scraped_at=datetime.combine(today, datetime.min.time())))
    for fq in sim_quotes:
        session.add(_fare_quote_to_row(fq))
    run.finished_at = datetime.utcnow()
    run.status = "ok"
    run.quotes_count = len(sim_quotes)
    session.commit()
    logger.info("run-daily: %d simulator quotes ingested for %s.", len(sim_quotes), today)

    # 3) re-clean + recompute index over full history
    compute_index_cmd.callback()


if __name__ == "__main__":
    cli()
