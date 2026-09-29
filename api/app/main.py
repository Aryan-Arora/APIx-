"""APIx read-only HTTP service. Run with uvicorn app.main:app."""

from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import schemas as s
from .deps import RateLimiter, Settings, Store, authorize, get_store
from .service import (
    bounds,
    canonical,
    index_rows,
    latest_quote_date,
    mock_quotes,
    quote_filter,
    quote_groups,
    resolve_route,
)

StoreDep = Annotated[Store, Depends(get_store)]
From = Annotated[Date | None, Query(alias="from")]
To = Annotated[Date | None, Query(alias="to")]
METHOD = dict(
    title="A fixed basket. A consistent measure.",
    formula="APIx(t) = 100 × exp(Σ w[r,b] × ln(P[r,b,t] / P0[r,b]))",
    steps=[
        "For each route and lead bucket, trim 10% of valid quotes from each tail, then take their geometric mean.",
        "The base price is the arithmetic mean of available elementary prices in the first seven calendar days. Base index is 100.",
        "Multiply route passenger-share weights by advance-purchase weights; combine price relatives geometrically.",
        "Carry missing cells forward for at most three calendar days, then drop the cell and renormalise weights.",
        "Weekly and monthly indices are arithmetic means of daily indices. Scoped indices renormalise the restricted basket.",
        "Live-only and combined-history indices are computed separately. Average fare charts use valid quote arithmetic means, not index values.",
    ],
    limitations=[
        "Research prototype, not an official MoSPI, NSO, DGCA or RBI statistic.",
        "Mock fixtures are illustrative. Synthetic history is not historical observation. Basket and lead weights are assumptions until verified.",
        "CPI Transport & Communication covers more than air travel. Compare monthly trend/direction only; never treat CPI index points as INR fares.",
        "No validated reference series means no defensible accuracy score.",
    ],
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct an isolated application, useful for tests and deployment."""
    config = settings or Settings.from_env()
    store = Store(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if store.engine is not None:
            store.engine.dispose()

    app = FastAPI(
        title="APIx · Airfare Price Index", version="0.1.0", lifespan=lifespan
    )
    app.state.settings = config
    app.state.store = store
    app.state.limiter = RateLimiter(config.rate_limit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_methods=["GET"],
        allow_headers=["X-API-Key"],
        expose_headers=["X-Data-Mode"],
    )

    @app.middleware("http")
    async def metadata(request: Request, call_next):
        if (
            request.url.path.startswith("/api/v1")
            and request.url.path not in {"/api/v1/health", "/api/v1/methodology"}
            and request.method != "OPTIONS"
        ):
            try:
                app.state.limiter.check(
                    request.client.host if request.client else "unknown"
                )
            except HTTPException as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"error": "rate_limited", "detail": exc.detail},
                    headers=exc.headers,
                )
        response = await call_next(request)
        response.headers["X-Data-Mode"] = "mock" if config.use_mock else "database"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(exc.status_code), "detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422, content={"error": "validation_error", "detail": str(exc)}
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "database_unavailable",
                "detail": "Database unavailable or schema not ready. No mock fallback was used.",
            },
        )

    @app.get("/api/v1/health", response_model=s.Health)
    def health(store: StoreDep):
        last = None
        if store.mock is not None:
            db = "mock"
        else:
            store.query("SELECT 1")
            last = store.query("SELECT MAX(finished_at) AS last FROM scrape_runs")[0][
                "last"
            ]
            db = "connected"
        return dict(
            status="ok",
            db=db,
            last_scrape_at=last,
            version="0.1.0",
            data_mode="mock" if config.use_mock else "database",
        )

    @app.get("/api/v1/methodology", response_model=s.Methodology)
    def methodology():
        return METHOD

    auth = [Depends(authorize)]

    @app.get("/api/v1/index", response_model=list[s.IndexPoint], dependencies=auth)
    def index(
        store: StoreDep,
        freq: Literal["daily", "weekly", "monthly"] = "daily",
        scope: str = "all",
        from_: From = None,
        to: To = None,
        include_synthetic: bool = True,
    ):
        return index_rows(store, freq, scope, include_synthetic, from_, to)

    @app.get("/api/v1/index/latest", response_model=s.Latest, dependencies=auth)
    def latest(store: StoreDep, scope: str = "all", include_synthetic: bool = True):
        rows = index_rows(store, "daily", scope, include_synthetic)
        if not rows:
            return dict(includes_synthetic=include_synthetic)
        current = rows[-1]
        d = Date.fromisoformat(str(current["date"]))
        by_date = {str(r["date"]): float(r["value"]) for r in rows}

        def change(days: int):
            previous = by_date.get(str(d - timedelta(days=days)))
            return (float(current["value"]) / previous - 1) * 100 if previous else None

        return dict(
            **current,
            change_day_pct=change(1),
            change_week_pct=change(7),
            change_month_pct=change(30),
        )

    @app.get("/api/v1/routes", response_model=list[s.Route], dependencies=auth)
    def routes(store: StoreDep):
        return sorted(
            [r for r in store.rows("routes") if r["active"]],
            key=lambda r: r["route_id"],
        )

    @app.get("/api/v1/heatmap", response_model=list[s.HeatCell], dependencies=auth)
    def heatmap(
        store: StoreDep,
        date: Date | None = None,
        from_: From = None,
        to: To = None,
        metric: Literal["index", "avg_fare"] = "index",
        include_synthetic: bool = True,
    ):
        if date and (from_ or to):
            raise HTTPException(422, "Use date or from/to, not both")
        start, end = (date, date) if date else (from_, to)
        bounds(start, end)
        if metric == "avg_fare":
            return [
                dict(
                    route_id=r["route_id"],
                    date=str(r["date"]),
                    value=r["avg_fare"],
                    includes_synthetic=r["includes_synthetic"],
                )
                for r in quote_groups(
                    store,
                    "route_id, CAST(scraped_at AS DATE)",
                    include_synthetic,
                    start=start,
                    end=end,
                )
            ]
        results = []
        for route in store.rows("routes"):
            if route["active"]:
                results.extend(
                    dict(
                        route_id=route["route_id"],
                        **{k: v for k, v in r.items() if k != "n_quotes"},
                    )
                    for r in index_rows(
                        store,
                        "daily",
                        "route:" + route["route_id"],
                        include_synthetic,
                        start,
                        end,
                    )
                )
        return results

    @app.get("/api/v1/lead-curve", response_model=list[s.LeadPoint], dependencies=auth)
    def lead_curve(
        store: StoreDep,
        route: str = "all",
        date: Date | None = None,
        include_synthetic: bool = True,
    ):
        canonical(route)
        day = date or latest_quote_date(store, include_synthetic)
        if day is None:
            return []
        rows = quote_groups(store, "lead_bucket", include_synthetic, route, day, day)
        baseline = next(
            (float(r["avg_fare"]) for r in rows if r["lead_bucket"] == "T+45"), None
        )
        return [
            dict(
                lead_bucket=r["lead_bucket"],
                avg_fare=r["avg_fare"],
                includes_synthetic=r["includes_synthetic"],
                relative_to_T45=float(r["avg_fare"]) / baseline if baseline else None,
            )
            for r in sorted(rows, key=lambda r: int(r["lead_bucket"][2:]))
        ]

    @app.get("/api/v1/carriers", response_model=list[s.Carrier], dependencies=auth)
    def carriers(
        store: StoreDep,
        from_: From = None,
        to: To = None,
        include_synthetic: bool = True,
    ):
        rows = quote_groups(store, "carrier", include_synthetic, start=from_, end=to)
        result = []
        for row in rows:
            if row["carrier"] is None:
                continue
            points = index_rows(
                store,
                "daily",
                "carrier:" + row["carrier"],
                include_synthetic,
                from_,
                to,
            )
            result.append(
                dict(
                    **row,
                    index=(
                        sum(float(p["value"]) for p in points) / len(points)
                        if points
                        else None
                    ),
                )
            )
        return sorted(result, key=lambda r: r["carrier"])

    @app.get("/api/v1/quotes", response_model=s.QuotePage, dependencies=auth)
    def quotes(
        store: StoreDep,
        route: str = "all",
        carrier: str | None = None,
        from_: From = None,
        to: To = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
        include_synthetic: bool = True,
    ):
        route = resolve_route(store, route)
        where, params = quote_filter(
            include_synthetic, route, carrier, from_, to, False
        )
        if store.mock is not None:
            rows = sorted(
                mock_quotes(store, include_synthetic, route, carrier, from_, to, False),
                key=lambda r: (r["scraped_at"], r["id"]),
                reverse=True,
            )
            items, total = rows[offset : offset + limit], len(rows)
        else:
            total = store.query(
                f"SELECT COUNT(*) AS n FROM clean_quotes WHERE {where}", params
            )[0]["n"]
            items = store.query(
                f"SELECT * FROM clean_quotes WHERE {where} ORDER BY scraped_at DESC, id DESC LIMIT :limit OFFSET :offset",
                dict(**params, limit=limit, offset=offset),
            )
        return dict(items=items, total=total, limit=limit, offset=offset)

    @app.get("/api/v1/backtest", response_model=s.Backtest, dependencies=auth)
    def backtest(store: StoreDep):
        rows = store.rows("backtest_results")
        summary_rows = store.rows("backtest_summary")
        metrics = {r["metric"].lower(): r["value"] for r in summary_rows}
        notes = [r["note"] for r in summary_rows if r.get("note")]
        if not rows:
            notes.append(
                "Reference results unavailable. No accuracy score can be claimed."
            )
        aliases = {
            "mape": ("mape", "mape_vs_dgca_fares"),
            "corr": ("correlation", "corr", "correlation_vs_cpi_transport_group"),
            "direction": (
                "direction_agreement",
                "direction",
                "direction_agreement_vs_cpi_transport_group",
            ),
        }
        summary = {
            key: next((metrics[name] for name in names if name in metrics), None)
            for key, names in aliases.items()
        }
        placeholder = any(
            "placeholder" in str(r.get("source_note", "")).lower() for r in rows
        ) or any("placeholder" in n.lower() for n in notes)
        if placeholder:
            notes.insert(
                0,
                "PLACEHOLDER reference inputs: calculated metrics are illustrative and are not published as validation scores.",
            )
            summary = dict(mape=None, corr=None, direction=None)
        if "mape_vs_dgca_fares" in metrics:
            summary["mape"] = None
            notes.insert(
                0,
                "Current pipeline fare MAPE is withheld: apix-v1 compares index points with INR fares. Engineer A must correct the units before validation.",
            )
        return dict(
            summary=summary,
            rows=rows,
            notes=notes,
            provenance=(
                "Mock mode: no reference comparison"
                if store.mock is not None
                else "Pipeline reference results; inspect source_note and summary notes for provenance and units."
            ),
        )

    @app.get("/api/v1/scrape-runs", response_model=list[s.Run], dependencies=auth)
    def runs(store: StoreDep, limit: Annotated[int, Query(ge=1, le=200)] = 25):
        if store.mock is not None:
            return sorted(
                store.rows("scrape_runs"),
                key=lambda r: str(r["started_at"]),
                reverse=True,
            )[:limit]
        return store.query(
            "SELECT id, started_at, finished_at, source, status, quotes_count, error_msg FROM scrape_runs ORDER BY started_at DESC LIMIT :limit",
            {"limit": limit},
        )

    return app


app = create_app()
