# Architecture

The serving plane consumes Engineer A's frozen schema through SQLAlchemy and exposes FastAPI read-only endpoints. Next.js App Router renders a responsive dashboard; Recharts renders time series and comparisons. CSS uses the prescribed navy, saffron and green palette, with Tailwind available through its PostCSS integration.

## Boundaries

- Engineer A: schema, source adapters, simulator, cleaning, index and backtest computation, pipeline scheduling.
- Engineer B: `api/`, `web/`, CI, serving/deployment/user documentation.
- `HANDOFF_NOTES.md`: shared integration issues, especially CPI versus fare backtest units.

API production code only executes SELECT statements. Tests create an isolated SQLite fixture schema. Mock mode generates an in-memory, deterministic illustrative dataset for the 45 UTC calendar days ending today. Its price curves are UI fixtures, not the validated index engine or a calibrated historical model. No rows are written to the shared database.

## Provenance

`USE_MOCK=1` selects mock fixtures and sets `X-Data-Mode: mock`. All mock quotes are synthetic, and live-only mode returns no observations. `USE_MOCK=0` uses the configured database and sets `X-Data-Mode: database`; database errors return 503 without fixture substitution.

`includes_synthetic` on stored index rows selects one complete index series. For quote-derived endpoints, `include_synthetic=false` excludes synthetic rows; true admits both kinds. Aggregate provenance records whether a group actually contains synthetic quotes. The dashboard's combined-mode badge describes the selected mode even if a particular cell happens to contain only real quotes.

Backtest and scraper-health panels describe pipeline evidence independently of the global quote/index mode. Neither manufactures evidence to fill an empty state.

## Read calculations

Index values are read from the pipeline, never recomputed in the serving plane. Latest changes use exact date offsets of 1, 7 and 30 days; a missing comparison day yields null, not a substitute date. Monthly comparison means 30-day change and is labelled accordingly.

Average fares exclude sold-out, flagged outlier and nonpositive quotes. Quote listings retain quality flags and excluded rows for audit. Lead curves default to the latest valid quote date for the selected mode; explicit `date` supports reproducible queries. Carrier indices are means of stored daily carrier indices in the selected range.

Date filters are inclusive calendar dates; quote queries implement an exclusive next-day upper bound. Route aliases canonicalise airport codes alphabetically. Quote pagination is stable by scraped_at descending, then id descending. All user filters use bound parameters.

## Deployment and operational limits

One API process has its own rolling-minute rate limiter. Proxy headers are not trusted by default; behind Render, direct IPs may collapse to a shared upstream address. Configure a trusted proxy only after verifying the provider's forwarding behavior. Use a distributed limiter for multiple workers or replicas.

Database connections use a small SQLAlchemy pool (three persistent plus two overflow). Use the Supabase session pooler for persistent IPv4 backends. The browser never receives DATABASE_URL or a Supabase service-role key. It does receive the explicitly public read-only demo API key.

No API response cache is enabled in v1, so provenance toggles cannot accidentally serve stale cross-mode data. Larger histories require bounded queries, batching heatmap scopes, and authenticated cache/rate-limit infrastructure.

## First integration result

A's branch at d2d5193 has been merged without edits to A-owned files. API route aliases resolve against the stored route table, including the non-alphabetical BOM-BLR entry. Naive pipeline timestamps are serialized as UTC. All endpoints were exercised against the generated SQLite DB: 46 daily observations, ten route series, 460 heatmap cells, five carriers, five lead buckets. Live-only series/quotes are empty because the dataset is entirely synthetic. At the subsequent sync, A commit 479be55 corrected the trim/calendar-day deviations and the BLR-BOM identifier. Methodology text now reflects the corrected engine.
