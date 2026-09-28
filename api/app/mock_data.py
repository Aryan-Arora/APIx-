"""Deterministic illustrative serving fixtures, never empirical observations."""

import math
from datetime import date, datetime, timedelta, timezone


def build_mock() -> dict[str, list[dict]]:
    """Produce 45 days of labelled fixtures without touching shared tables."""
    pairs = [
        "DEL-BOM",
        "DEL-BLR",
        "BOM-BLR",
        "DEL-CCU",
        "BLR-HYD",
        "MAA-DEL",
        "DEL-HYD",
        "BOM-HYD",
        "BOM-MAA",
        "DEL-AMD",
    ]
    routes = []
    for pair in pairs:
        origin, dest = sorted(pair.split("-"))
        routes.append(
            dict(
                route_id=f"{origin}-{dest}",
                origin=origin,
                dest=dest,
                dgca_pax_share=0.1,
                active=True,
            )
        )
    quotes, indices = [], []
    today = datetime.now(timezone.utc).date()
    for day in range(45):
        obs = today - timedelta(days=44 - day)
        for r, route in enumerate(routes):
            value = round(100 + day * 0.19 + 2.5 * math.sin(day / 5 + r / 3), 2)
            indices.append(
                dict(
                    obs_date=obs.isoformat(),
                    freq="daily",
                    scope="route:" + route["route_id"],
                    value=value,
                    n_quotes=15,
                    includes_synthetic=True,
                    method_version="mock-fixture",
                )
            )
            for b, lead in enumerate([1, 7, 15, 30, 45]):
                for c, carrier in enumerate(["6E", "AI", "QP"]):
                    fare = round(
                        (3800 + r * 190)
                        * (1.65 - b * 0.15)
                        * value
                        / 100
                        * (1 + c * 0.07),
                        2,
                    )
                    quotes.append(
                        dict(
                            id=len(quotes) + 1,
                            scraped_at=f"{obs}T06:00:00+00:00",
                            source="mock_fixture",
                            source_type="simulator",
                            carrier=carrier,
                            flight_no=f"{carrier}{100+r}",
                            route_id=route["route_id"],
                            origin=route["origin"],
                            dest=route["dest"],
                            depart_date=(obs + timedelta(days=lead)).isoformat(),
                            depart_time="12:00:00",
                            lead_days=lead,
                            lead_bucket=f"T+{lead}",
                            fare_class="Economy",
                            base_fare=round(fare * 0.75, 2),
                            taxes=round(fare * 0.20, 2),
                            udf=round(fare * 0.03, 2),
                            convenience_fee=round(fare * 0.02, 2),
                            total_fare=fare,
                            currency="INR",
                            is_sold_out=False,
                            is_synthetic=True,
                            is_outlier=False,
                            quality_flag="ok",
                            raw_hash=f"mock-{day}-{r}-{b}-{c}",
                        )
                    )
        day_values = [
            x["value"]
            for x in indices
            if x["obs_date"] == obs.isoformat() and x["scope"].startswith("route:")
        ]
        overall = round(sum(day_values) / len(day_values), 2)
        for scope in [
            "all",
            "carrier:6E",
            "carrier:AI",
            "carrier:QP",
            *[f"lead:T+{x}" for x in [1, 7, 15, 30, 45]],
        ]:
            indices.append(
                dict(
                    obs_date=obs.isoformat(),
                    freq="daily",
                    scope=scope,
                    value=overall,
                    n_quotes=150 if scope == "all" else 30,
                    includes_synthetic=True,
                    method_version="mock-fixture",
                )
            )
    daily = list(indices)
    for freq in ["weekly", "monthly"]:
        grouped = {}
        for row in daily:
            d = date.fromisoformat(row["obs_date"])
            anchor = (
                d - timedelta(days=d.weekday())
                if freq == "weekly"
                else d.replace(day=1)
            )
            grouped.setdefault((anchor.isoformat(), row["scope"]), []).append(row)
        for (obs, scope), rows in grouped.items():
            indices.append(
                dict(
                    obs_date=obs,
                    freq=freq,
                    scope=scope,
                    value=round(sum(r["value"] for r in rows) / len(rows), 2),
                    n_quotes=sum(r["n_quotes"] for r in rows),
                    includes_synthetic=True,
                    method_version="mock-fixture",
                )
            )
    return dict(
        routes=routes,
        clean_quotes=quotes,
        index_values=indices,
        scrape_runs=[],
        backtest_results=[],
        backtest_summary=[],
    )
