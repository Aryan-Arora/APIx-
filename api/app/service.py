"""Read-side calculations and portable parameterized SQL."""

from datetime import date, timedelta

from fastapi import HTTPException

from .deps import Store


def canonical(route: str) -> str:
    """Accept both directions while preserving the canonical stored pair."""
    if route == "all":
        return route
    parts = route.upper().split("-")
    if len(parts) != 2 or any(len(p) != 3 or not p.isalpha() for p in parts):
        raise HTTPException(422, "Route must be an airport pair such as DEL-BOM")
    return "-".join(sorted(parts))


def resolve_route(store: Store, route: str) -> str:
    """Resolve bidirectional input to the actual stored ID without changing data."""
    normalized = canonical(route)
    if normalized == "all":
        return normalized
    identifiers = [r["route_id"] for r in store.rows("routes")]
    if route.upper() in identifiers:
        return route.upper()
    return next((r for r in identifiers if canonical(r) == normalized), normalized)


def scope_name(scope: str, store: Store) -> str:
    """Normalize route scopes without changing other scope identifiers."""
    return (
        "route:" + resolve_route(store, scope[6:])
        if scope.startswith("route:")
        else scope
    )


def bounds(start: date | None, end: date | None) -> None:
    """Reject inverted ranges."""
    if start and end and start > end:
        raise HTTPException(422, "from must be on or before to")


def index_rows(
    store: Store,
    freq: str,
    scope: str,
    synthetic: bool,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Read exactly one stored synthetic mode, never combine index series."""
    bounds(start, end)
    scope = scope_name(scope, store)
    if store.mock is not None:
        rows = [
            r
            for r in store.mock["index_values"]
            if r["freq"] == freq
            and r["scope"] == scope
            and r["includes_synthetic"] == synthetic
            and (not start or str(r["obs_date"]) >= str(start))
            and (not end or str(r["obs_date"]) <= str(end))
        ]
    else:
        conditions = ["freq=:freq", "scope=:scope", "includes_synthetic=:synthetic"]
        params = dict(freq=freq, scope=scope, synthetic=synthetic)
        if start:
            conditions.append("obs_date >= :start")
            params["start"] = start
        if end:
            conditions.append("obs_date <= :end")
            params["end"] = end
        rows = store.query(
            "SELECT obs_date, value, n_quotes, includes_synthetic FROM index_values WHERE "
            + " AND ".join(conditions)
            + " ORDER BY obs_date",
            params,
        )
    return [
        dict(
            date=str(r["obs_date"]),
            value=r["value"],
            n_quotes=r["n_quotes"],
            includes_synthetic=r["includes_synthetic"],
        )
        for r in sorted(rows, key=lambda x: str(x["obs_date"]))
    ]


def quote_filter(
    synthetic: bool,
    route: str,
    carrier: str | None,
    start: date | None,
    end: date | None,
    valid_only: bool,
) -> tuple[str, dict]:
    bounds(start, end)
    conditions, params = ["1=1"], {}
    if not synthetic:
        conditions.append("is_synthetic = :synthetic")
        params["synthetic"] = False
    if route != "all":
        conditions.append("route_id = :route")
        params["route"] = route
    if carrier:
        conditions.append("carrier = :carrier")
        params["carrier"] = carrier
    if start:
        conditions.append("scraped_at >= :start")
        params["start"] = str(start)
    if end:
        conditions.append("scraped_at < :end")
        params["end"] = str(end + timedelta(days=1))
    if valid_only:
        conditions.extend(
            [
                "is_sold_out = false",
                "(is_outlier = false OR is_outlier IS NULL)",
                "total_fare > 0",
            ]
        )
    return " AND ".join(conditions), params


def mock_quotes(
    store: Store,
    synthetic: bool,
    route: str = "all",
    carrier: str | None = None,
    start: date | None = None,
    end: date | None = None,
    valid_only: bool = True,
) -> list[dict]:
    bounds(start, end)
    route = resolve_route(store, route)
    return [
        r
        for r in store.mock["clean_quotes"]
        if (synthetic or not r["is_synthetic"])
        and (route == "all" or r["route_id"] == route)
        and (not carrier or r["carrier"] == carrier)
        and (not start or r["scraped_at"][:10] >= str(start))
        and (not end or r["scraped_at"][:10] <= str(end))
        and (
            not valid_only
            or (not r["is_sold_out"] and not r["is_outlier"] and r["total_fare"] > 0)
        )
    ]


def quote_groups(
    store: Store,
    group: str,
    synthetic: bool,
    route: str = "all",
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Aggregate valid quotes in SQL, retaining per-group synthetic provenance."""
    if group not in {"lead_bucket", "carrier", "route_id, CAST(scraped_at AS DATE)"}:
        raise ValueError("Unsupported aggregation")
    if store.mock is not None:
        groups = {}
        for row in mock_quotes(store, synthetic, route, start=start, end=end):
            key = (
                (row["route_id"], row["scraped_at"][:10])
                if group.startswith("route_id,")
                else (row[group],)
            )
            groups.setdefault(key, []).append(row)
        return [
            dict(
                **(dict(route_id=k[0], date=k[1]) if len(k) == 2 else {group: k[0]}),
                avg_fare=sum(r["total_fare"] for r in rows) / len(rows),
                n_quotes=len(rows),
                includes_synthetic=any(r["is_synthetic"] for r in rows),
            )
            for k, rows in groups.items()
        ]
    route = resolve_route(store, route)
    where, params = quote_filter(synthetic, route, None, start, end, True)
    date_expr = (
        "date(scraped_at)"
        if store.engine.dialect.name == "sqlite"
        else "CAST(scraped_at AS DATE)"
    )
    fields = (
        f"route_id, {date_expr} AS date" if group.startswith("route_id,") else group
    )
    grouping = f"route_id, {date_expr}" if group.startswith("route_id,") else group
    return store.query(
        f"SELECT {fields}, AVG(total_fare) AS avg_fare, COUNT(*) AS n_quotes, "
        f"MAX(CASE WHEN is_synthetic THEN 1 ELSE 0 END) AS includes_synthetic "
        f"FROM clean_quotes WHERE {where} GROUP BY {grouping}",
        params,
    )


def latest_quote_date(store: Store, synthetic: bool) -> date | None:
    if store.mock is not None:
        rows = mock_quotes(store, synthetic)
        value = max((r["scraped_at"][:10] for r in rows), default=None)
    else:
        where, params = quote_filter(synthetic, "all", None, None, None, True)
        value = store.query(
            f"SELECT MAX(scraped_at) AS latest FROM clean_quotes WHERE {where}", params
        )[0]["latest"]
    return date.fromisoformat(str(value)[:10]) if value else None
