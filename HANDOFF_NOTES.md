# APIx integration notes

## Engineer A
- Engineer B is implementing the frozen schema using SELECT-only SQLAlchemy queries. No pipeline/data files are owned or modified by B.
- Backtest conflict: section 2 requests CPI Transport & Communication trend correlation; sections 5/6 and the frozen table still name DGCA fare/MAPE. Please populate source_note and summary notes with actual provenance; never store CPI index values as INR fares or calculate fare MAPE against CPI. B will render raw legacy fields with explicit units/provenance and no invented reference values. Schema changes require written agreement first.
- Canonical route IDs: alphabetically sorted airport pair; direction remains origin/dest. API accepts reversed route aliases.
- Please provide populated DATABASE_URL and schema handoff; B stays in explicit USE_MOCK=1 until then.
- Please confirm backtest summary metric spelling (B accepts MAPE/mape, correlation/corr, direction_agreement/direction).
- Supabase should expose no public table access unless explicitly intended; provision a SELECT-only database role for the serving API. B does not modify schema or policies.

## Engineer B
- Branch: feat/api-web. Working directory: /Users/aryanarora/Desktop/apix.
- Mock fixtures are generated only in API memory and explicitly labelled; real-only mode returns empty data in mock mode.
- Additive provenance fields and include_synthetic filters on quote-derived endpoints will prevent mode mixing; frozen index response fields are preserved.

---

## Engineer A original handoff (preserved at integration)

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
  weights). `cpi_transport_group_index.csv` is now **real MoSPI CPI
  data** (3 months, Base 2012=100 — see `docs/BACKTEST.md` for the
  base-year discontinuity and small-n caveats). `dgca_monthly_fares.csv`
  is still placeholder.
- **Running the pipeline locally** (from repo root, after
  `cd pipeline && pip install -e .`):
  ```bash
  python -m apix.pipeline backfill --days 45 && \
  python -m apix.pipeline backfill --days 60 --end-date 2025-12-31 && \
  python -m apix.pipeline compute-index && \
  python -m apix.pipeline backtest
  ```
  The **second backfill call is required** for the backtest to have any
  real overlapping months with the real CPI data (Nov/Dec 2025) — it's
  additive to the first (different date window, same DB), so the
  recent-looking demo history from the first call is unaffected. This
  populates a local `apix.db` SQLite file (gitignored) with both a
  recent window (~45 days ending today, for the live demo/dashboard)
  and a Nov–Dec 2025 window (for the real backtest), across every scope
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

## Integration sync — Engineer B, 2026-09-28

- Integrated A commit d2d5193 into feat/api-web; A-owned files are unchanged. Local simulator/database integration is now being verified.
- **A action required: invalid fare backtest units.** `run_backtest(apix_monthly_all)` uses the monthly index value (~100) as `apix_avg_fare`, then compares it with DGCA rupee fares. Please compute monthly average valid clean-quote fare per route for fare MAPE, separate from monthly index values used for CPI correlation. B will label current backtest evidence as unvalidated and surface this issue, not endorse this MAPE.
- B accepts A's summary names: correlation_vs_cpi_transport_group, direction_agreement_vs_cpi_transport_group, MAPE_vs_dgca_fares. Direction agreement is a fraction (0–1), MAPE is percent.
- A's reference CSVs are explicitly PLACEHOLDER; no official validation can be claimed. All live adapters are unimplemented stubs; no claim of successful live collection.
- B's API tests passed with Python 3.11.15 (18 tests), in addition to Python 3.13.
- **A action required: index contract drift.** `trimmed_geo_mean(trim=0.10)` currently trims 5% per tail (`trim/2`), while frozen contract says 10% per tail. Carry-forward iterates only observed dates, so three missing *observations* can exceed three calendar days. Base-period selection also uses first seven observed dates. Please correct/test calendar-day semantics and tail trimming. B's methodology now distinguishes the intended contract from these observed implementation limits.
- **A action required: route naming.** routes.csv contains BOM-BLR although alphabetical canonical is BLR-BOM. API will resolve an airport-pair alias to its existing stored route ID so users can access these rows without rewriting A's data. Please standardise IDs in the pipeline at the next sync.
- Backfill --days 45 produces 46 calendar dates (inclusive offsets 45 through 0); local integration generated 11,500 quotes and 1,176 index rows. All are synthetic. Pipeline's existing 28 tests pass, but do not cover the mismatches above.

## Serving-plane verification complete

- API tests: 21 passing on Python 3.11.15. Pipeline tests: 28 passing. Next.js lint/typecheck/build passing.
- GitHub CI all three jobs passed at 820eb6a: https://github.com/Aryan-Arora/APIx-/actions/runs/36461782657.
- Every endpoint was exercised against the populated SQLite database. All ten route series return 46 daily points; live-only data is empty.
- Local preview runs on localhost:3000; API/docs on localhost:8100. DB mode is enabled with all-synthetic pipeline data. No A-owned source files were edited.
- Render sign-in and production DATABASE_URL remain needed. Vercel is authenticated, but web deployment waits for a reachable API origin. No production/live-data claim is made.
