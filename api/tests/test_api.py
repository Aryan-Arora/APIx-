"""Contract, provenance, authentication and real SQL integration tests."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.deps import Settings
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(
        create_app(Settings(use_mock=True, api_keys=("test-key",), rate_limit=1000))
    ) as c:
        c.headers["X-API-Key"] = "test-key"
        yield c


def test_auth_and_public_routes(client):
    client.headers.pop("X-API-Key")
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/methodology").status_code == 200
    assert client.get("/api/v1/index").status_code == 401
    assert (
        client.get("/api/v1/index", headers={"X-API-Key": "wrong"}).status_code == 401
    )


@pytest.mark.parametrize(
    "path",
    [
        "index",
        "index/latest",
        "routes",
        "heatmap",
        "lead-curve",
        "carriers",
        "quotes",
        "backtest",
        "scrape-runs",
    ],
)
def test_endpoints(client, path):
    response = client.get("/api/v1/" + path)
    assert response.status_code == 200, response.text
    assert response.headers["X-Data-Mode"] == "mock"


def test_mock_real_only_never_leaks(client):
    for path in ["index", "heatmap", "lead-curve", "carriers"]:
        assert (
            client.get("/api/v1/" + path, params={"include_synthetic": False}).json()
            == []
        )
    assert client.get("/api/v1/quotes?include_synthetic=false").json()["total"] == 0
    assert (
        client.get("/api/v1/index/latest?include_synthetic=false").json()["value"]
        is None
    )
    assert client.get("/api/v1/backtest").json()["summary"]["mape"] is None
    assert client.get("/api/v1/scrape-runs").json() == []


def test_filters_aliases_and_pagination(client):
    today = datetime.now(timezone.utc).date().isoformat()
    rows = client.get(
        "/api/v1/index", params={"scope": "route:DEL-BOM", "from": today, "to": today}
    ).json()
    assert len(rows) == 1
    page = client.get("/api/v1/quotes?route=DEL-BOM&carrier=6E&limit=2&offset=1").json()
    assert len(page["items"]) == 2
    assert all(
        r["route_id"] == "BOM-DEL" and r["carrier"] == "6E" for r in page["items"]
    )
    assert client.get("/api/v1/index?from=2026-09-02&to=2026-09-01").status_code == 422
    assert client.get("/api/v1/quotes?limit=501").status_code == 422
    assert (
        client.get("/api/v1/heatmap?date=2026-09-01&from=2026-09-01").status_code == 422
    )
    assert client.get("/api/v1/lead-curve?route=bad").status_code == 422


def test_rate_limit_and_cors():
    with TestClient(
        create_app(Settings(use_mock=True, api_keys=("key",), rate_limit=2))
    ) as c:
        for _ in range(2):
            assert (
                c.get("/api/v1/routes", headers={"X-API-Key": "key"}).status_code == 200
            )
        assert c.get("/api/v1/routes").status_code == 429
        assert c.get("/api/v1/health").status_code == 200
        response = c.options(
            "/api/v1/index",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )


@pytest.fixture
def sql_client():
    app = create_app(
        Settings(
            database_url="sqlite:///:memory:", api_keys=("test-key",), rate_limit=1000
        )
    )
    with app.state.store.engine.begin() as conn:
        # Fixture DDL belongs only to tests. Production repository never runs DDL.
        for statement in [
            "CREATE TABLE routes(route_id TEXT, origin TEXT, dest TEXT, dgca_pax_share NUMERIC, active BOOLEAN)",
            "CREATE TABLE index_values(obs_date DATE, freq TEXT, scope TEXT, value NUMERIC, n_quotes INT, method_version TEXT, includes_synthetic BOOLEAN)",
            "CREATE TABLE clean_quotes(id INT, scraped_at TIMESTAMP, source TEXT, route_id TEXT, carrier TEXT, lead_bucket TEXT, total_fare NUMERIC, is_synthetic BOOLEAN, is_sold_out BOOLEAN, is_outlier BOOLEAN, quality_flag TEXT)",
            "CREATE TABLE scrape_runs(id INT, started_at TIMESTAMP, finished_at TIMESTAMP, source TEXT, status TEXT, quotes_count INT, error_msg TEXT)",
            "CREATE TABLE backtest_results(month DATE, route_id TEXT, apix_avg_fare NUMERIC, dgca_avg_fare NUMERIC, abs_pct_error NUMERIC, source_note TEXT)",
            "CREATE TABLE backtest_summary(metric TEXT, value NUMERIC, note TEXT)",
        ]:
            conn.execute(text(statement))
        conn.execute(text("INSERT INTO routes VALUES ('BOM-DEL','BOM','DEL',1,1)"))
        for synthetic, value in [(False, 110), (True, 130)]:
            for offset, price in [(0, value), (1, 100), (7, 100), (30, 100)]:
                for scope in ["all", "route:BOM-DEL", "carrier:6E"]:
                    conn.execute(
                        text(
                            "INSERT INTO index_values VALUES (:d,'daily',:scope,:v,2,'v1',:s)"
                        ),
                        dict(
                            d=str(date(2026, 9, 28) - timedelta(days=offset)),
                            scope=scope,
                            v=price,
                            s=synthetic,
                        ),
                    )
        for id, price, synthetic, sold, outlier, lead, stamp in [
            (1, 1000, False, False, False, "T+45", "2026-09-28 12:00:00"),
            (2, 2000, False, False, False, "T+1", "2026-09-28 12:00:00"),
            (3, 9000, True, False, False, "T+1", "2026-09-28 12:00:00"),
            (4, 99999, False, True, False, "T+1", "2026-09-28 12:00:00"),
            (5, 99999, False, False, True, "T+1", "2026-09-28 12:00:00"),
            (6, 55555, False, False, False, "T+1", "2026-09-29 00:00:00"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO clean_quotes VALUES (:id,:stamp,'fixture','BOM-DEL','6E',:lead,:price,:s,:sold,:outlier,'ok')"
                ),
                dict(
                    id=id,
                    stamp=stamp,
                    lead=lead,
                    price=price,
                    s=synthetic,
                    sold=sold,
                    outlier=outlier,
                ),
            )
    with TestClient(app) as c:
        c.headers["X-API-Key"] = "test-key"
        yield c


def test_sql_provenance_and_exact_comparisons(sql_client):
    result = sql_client.get("/api/v1/index/latest?include_synthetic=false").json()
    assert result["value"] == 110
    assert result["change_day_pct"] == pytest.approx(10)
    assert result["change_week_pct"] == pytest.approx(10)
    assert result["change_month_pct"] == pytest.approx(10)
    assert (
        sql_client.get("/api/v1/index/latest?include_synthetic=true").json()["value"]
        == 130
    )
    assert sql_client.get("/api/v1/health").json()["db"] == "connected"


def test_sql_quote_aggregation_excludes_sold_out_outliers_and_next_day(sql_client):
    curve = sql_client.get(
        "/api/v1/lead-curve?route=DEL-BOM&date=2026-09-28&include_synthetic=false"
    ).json()
    assert curve[0]["avg_fare"] == 2000
    assert curve[0]["relative_to_T45"] == 2
    assert curve[1]["avg_fare"] == 1000
    cells = sql_client.get(
        "/api/v1/heatmap?metric=avg_fare&date=2026-09-28&include_synthetic=false"
    ).json()
    assert cells[0]["value"] == 1500
    assert not cells[0]["includes_synthetic"]
    page = sql_client.get(
        "/api/v1/quotes?from=2026-09-28&to=2026-09-28&include_synthetic=false"
    ).json()
    assert page["total"] == 4  # flagged rows retained for auditing
    assert all(not r["is_synthetic"] for r in page["items"])
    assert (
        sql_client.get("/api/v1/quotes?carrier=%27%20OR%201=1--").json()["total"] == 0
    )


def test_missing_database_fails_without_mock_fallback():
    with TestClient(create_app(Settings(api_keys=("key",)))) as c:
        result = c.get("/api/v1/index", headers={"X-API-Key": "key"})
        assert result.status_code == 503
        assert result.headers["X-Data-Mode"] == "database"


def test_error_envelopes(client):
    for response in [client.get("/api/v1/missing"), client.post("/api/v1/index")]:
        assert set(response.json()) == {"error", "detail"}


def test_sql_all_scopes_and_endpoints(sql_client):
    for path in [
        "routes",
        "heatmap?metric=index",
        "carriers",
        "scrape-runs",
        "backtest",
    ]:
        response = sql_client.get("/api/v1/" + path)
        assert response.status_code == 200, response.text
    result = sql_client.get(
        "/api/v1/carriers?from=2026-09-28&to=2026-09-28&include_synthetic=false"
    ).json()
    assert result[0]["avg_fare"] == 1500
    assert result[0]["index"] == 110


def test_noncanonical_stored_route_alias(sql_client):
    with sql_client.app.state.store.engine.begin() as conn:
        conn.execute(text("UPDATE routes SET route_id='DEL-BOM'"))
        conn.execute(text("UPDATE clean_quotes SET route_id='DEL-BOM'"))
        conn.execute(
            text(
                "UPDATE index_values SET scope='route:DEL-BOM' WHERE scope='route:BOM-DEL'"
            )
        )
    assert len(sql_client.get("/api/v1/index?scope=route:BOM-DEL").json()) == 4
    assert sql_client.get("/api/v1/quotes?route=BOM-DEL").json()["total"] == 6
    assert (
        len(sql_client.get("/api/v1/lead-curve?route=BOM-DEL&date=2026-09-28").json())
        == 2
    )


def test_pipeline_metric_aliases_and_placeholder_suppression(sql_client):
    with sql_client.app.state.store.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO backtest_summary VALUES ('correlation_vs_cpi_transport_group',0.8,'PLACEHOLDER inputs')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO backtest_summary VALUES ('MAPE_vs_dgca_fares',98,'Legacy comparison')"
            )
        )
    result = sql_client.get("/api/v1/backtest").json()
    assert result["summary"] == {"mape": None, "corr": None, "direction": None}
    assert any("index points" in n for n in result["notes"])
    assert any("PLACEHOLDER" in n for n in result["notes"])
    with sql_client.app.state.store.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE backtest_summary SET note='Verified CPI series' WHERE metric='correlation_vs_cpi_transport_group'"
            )
        )
    assert sql_client.get("/api/v1/backtest").json()["summary"]["corr"] == 0.8


def test_naive_pipeline_timestamps_are_utc(sql_client):
    quote = sql_client.get("/api/v1/quotes?limit=1").json()["items"][0]
    assert quote["scraped_at"].endswith("Z")
