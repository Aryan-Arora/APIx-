# APIx — Handoff Notes

Cross-engineer coordination notes for the SIH 2026 APIx (Real-time Airfare
Price Index for India) project. Two engineers are building this monorepo
in parallel:

- **Engineer A** (data plane): `pipeline/`, `data/`, `.github/workflows/daily-scrape.yml`,
  `docs/SCRAPING.md`, `docs/METHODOLOGY.md`, `docs/BACKTEST.md`.
- **Engineer B** (API + web): `api/`, `web/`, and anything else not listed above.

## For Engineer B

- **DB schema**: see `pipeline/schema.sql` for the raw Postgres-flavored
  schema, and `pipeline/apix/db.py` for the SQLAlchemy models that are the
  actual source of truth (works against SQLite locally, Postgres/Supabase
  in prod via the `DATABASE_URL` env var — same models, same table names).
  Key tables your API will likely read from: `index_values` (the computed
  APIx series, all scopes/frequencies/synthetic-modes), `routes`,
  `clean_quotes` (if you need quote-level detail), `backtest_results` /
  `backtest_summary`.
- **Seed / reference data**: `data/reference/` — `routes.csv` (the 10-route
  basket + weights), `lead_weights.json` (booking lead-time bucket
  weights), plus placeholder DGCA/CPI reference files used by the
  backtest (see `docs/BACKTEST.md` for caveats on those).
- **Running the pipeline locally** (from repo root, after
  `cd pipeline && pip install -e .`):
  ```bash
  python -m apix.pipeline backfill --days 45 && \
  python -m apix.pipeline compute-index && \
  python -m apix.pipeline backtest
  ```
  This populates a local `apix.db` SQLite file (gitignored) with ~45 days
  of synthetic-but-realistic index history across every scope
  (`all`, `route:*`, `carrier:*`, `lead:*`) x frequency (`daily`,
  `weekly`, `monthly`) x `includes_synthetic` (`true`/`false`). Point
  `DATABASE_URL` at Postgres/Supabase to use the same commands against a
  shared DB.
- **Live scraping status**: honest heads-up — the OTA/airline adapters
  (`ixigo`, `easemytrip`, `cleartrip`, `indigo`) are stubs that raise
  `NotImplementedError` (Playwright/browser automation wasn't available
  in this build environment). The demo runs entirely on the
  `simulator` adapter, which is deterministic, fully documented, and
  produces the full 45-day/10-route/5-lead-bucket/5-carrier dataset. See
  `docs/SCRAPING.md` for details — this is expected/acceptable per the
  original spec ("if zero live sources work, stop — the demo uses the
  simulator").
- **`.env.example`** at repo root lists the pipeline-relevant env vars
  (`DATABASE_URL`, `SIMULATOR_SEED`, `SCRAPE_MAX_RPS`, `PROXY_URL`). Add
  your own API/web vars alongside them as needed.

## For Engineer A (me / future reference)

- Index formula, cleaning steps, and scoping are documented in
  `docs/METHODOLOGY.md`.
- Backtest scope + placeholder-data caveats are documented in
  `docs/BACKTEST.md` — real MoSPI CPI and DGCA fare data still need to be
  supplied by a human before those comparisons carry real weight.
