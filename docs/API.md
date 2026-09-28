# API reference

Base: `/api/v1`. OpenAPI explorer: `/docs`; machine schema: `/openapi.json`.

All data endpoints require `X-API-Key`. `/health` and `/methodology` are public; OpenAPI documentation is public. Configure comma-separated `API_KEYS`. Missing keys fail closed. Only GET is supported. The browser demo key is intentionally public and must not grant writes or privileged database access.

Errors have `{ "error": "...", "detail": "..." }`. Invalid input: 422; missing/wrong key: 401; rate limit: 429 plus Retry-After; unavailable/unconfigured DB: 503. Rate limit: 60 requests/minute per direct IP per process. CORS allows exact origins from `ALLOWED_ORIGINS`. No wildcard credentials.

All responses expose `X-Data-Mode: mock|database` and `Cache-Control: no-store`.

| Path | Query parameters | Response |
|---|---|---|
| `/health` | none | status, db, last_scrape_at, version, data_mode |
| `/index` | freq=daily/weekly/monthly, scope=all, from, to, include_synthetic=true | date, value, n_quotes, includes_synthetic array |
| `/index/latest` | scope=all, include_synthetic=true | latest point and change_day_pct, change_week_pct, change_month_pct |
| `/routes` | none | active route_id, origin, dest, dgca_pax_share, active |
| `/heatmap` | date OR from/to, metric=index/avg_fare, include_synthetic=true | route_id, date, value, includes_synthetic array |
| `/lead-curve` | route=all or airport pair, date, include_synthetic=true | lead_bucket, avg_fare, relative_to_T45, includes_synthetic array |
| `/carriers` | from, to, include_synthetic=true | carrier, avg_fare, index, n_quotes, includes_synthetic array |
| `/quotes` | route=all, carrier, from, to, limit=100 (1–500), offset=0, include_synthetic=true | items, total, limit, offset |
| `/backtest` | none | summary:{mape,corr,direction}, rows, notes, provenance |
| `/scrape-runs` | limit=25 (1–200) | most recent run records |
| `/methodology` | none | title, formula, steps, limitations |

Scope examples: `all`, `route:BOM-DEL`, `carrier:6E`, `lead:T+7`. URL-encode literal `+` as `%2B`. Route queries accept reversed aliases such as `DEL-BOM`. Unknown valid scopes return an empty series; malformed route syntax returns 422. Dates use YYYY-MM-DD and ranges are inclusive. No `date` defaults to latest valid quote date for lead curves; heatmaps return all available dates, with the UI showing the latest 14.

Latest percentage changes compare the exact preceding day, 7 days, and 30 days. They are null if that date is missing or the previous value is zero. No current point returns null date/value and zero quotes. `relative_to_T45` is a ratio, not a percentage; missing/zero T+45 means null.

```bash
curl 'http://localhost:8000/api/v1/index?freq=daily&include_synthetic=false' \
  -H 'X-API-Key: apix-local-demo'
curl 'http://localhost:8000/api/v1/quotes?route=DEL-BOM&limit=10&include_synthetic=true' \
  -H 'X-API-Key: apix-local-demo'
```

Backtest fields `apix_avg_fare` and `dgca_avg_fare` are inherited from the frozen schema. CPI indices must not be inserted as rupee fares. Metric units and interpretation must be in source_note/summary notes. The serving plane does not invent a reference or replace null scores with zero. A schema amendment for CPI index-specific results remains an integration question in HANDOFF_NOTES.md.

Integration with A's current summary names is supported. Placeholder-reference scores are withheld (null) with explanatory notes. `MAPE_vs_dgca_fares` is withheld because the integrated apix-v1 implementation currently compares index points with rupee fares; A must supply a corrected metric before it can be used. A fare-comparison chart renders only when every row explicitly identifies INR in source_note and no placeholder/unit-error warning remains.
