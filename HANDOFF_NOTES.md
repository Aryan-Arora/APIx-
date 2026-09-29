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

### Live scraping handoff (2026-09-29, Engineer A -> Engineer B)

Deployment (Fly.io API + Vercel dashboard) and the real-CPI backtest are
both done and live — see the "Deployment status" section below. The one
remaining item from the original problem statement is **live scraping**
(currently all 4 adapters in `pipeline/apix/adapters/` are stubs that
raise `NotImplementedError`). Handing this to B since it needs a real
browser + DevTools on the human's laptop, which A (running in a cloud
container with all airline/OTA domains blocked at the network policy
level) cannot do directly — only relay through pasted screenshots, which
is slow.

**What's been tried on IndiGo (goindigo.in), findings so far:**
- A recon script exists at `pipeline/scripts/explore_indigo.py` (one-off
  tool, not part of the pipeline CLI) — opens the site in headless
  Playwright, captures every XHR/fetch response, flags likely
  fare-related JSON. Run: `python3 scripts/explore_indigo.py --origin
  BOM --dest DEL`.
- **Deep-linking directly to a search URL does not work** — IndiGo's
  booking flow keeps search state client-side (redux/session storage),
  not in URL query params. A guessed URL
  (`goindigo.in/booking/book-flight?origin=...&destination=...`)
  produced a generic "Something went wrong" error page from their own
  app, not a bot-block. The real results page after a manual search is
  a static URL (`goindigo.in/book/flight-select.html`) with no params.
- **The site is NOT simply bot-blocked** — a manual search in a real
  browser works fine and returns real results ("Choose your preferred
  flight from Mumbai to Delhi").
- **IndiGo obfuscates its XHR request names** — Safari DevTools Network
  tab (filtered to XHR/Fetch) on a real search shows request names like
  `0HJ2g`, `params`, `0mPB8P`, `491e0abc-8e11-...` — no human-readable
  names like `/search` or `/fares`. This looks like deliberate scraping
  resistance (obfuscated + possibly encrypted payloads), not just
  minification. One clearly-identifiable request,
  `/C7h-Z3JfVaizxXM.../...`, is almost certainly anti-bot telemetry
  (PerimeterX/Akamai-style bot-detection sensor), not fare data — skip
  it.
- **Not yet confirmed:** whether the `params` or `0HJ2g` responses
  (2-2.5 KB each, the largest payloads) actually contain fare data in
  plaintext JSON, or whether they're encrypted/obfuscated blobs. This is
  the next thing to check — click into one of those responses in
  DevTools and look at the Preview/Response tab.

**Recommended next steps for B** (with real laptop + DevTools access):
1. Check the `params` and `0HJ2g` response bodies directly — if
   readable JSON with fare/price fields, the adapter is close: replicate
   the request (headers, cookies, CSRF token — note the domain prefix
   `csrf.min.56934e461ff6c4...` on the Initiator column, suggesting a
   CSRF token is required) via `httpx`/`requests` or keep it
   browser-driven via Playwright (`page.on("response")` intercepting
   the specific obfuscated URL pattern, since the random names likely
   change per-session/per-load).
2. If those payloads are encrypted (not plaintext), that's a strong
   signal to deprioritize IndiGo and instead try an OTA (Ixigo,
   EaseMyTrip, Cleartrip per SCRAPING.md's original preference order) or
   another airline's direct site — one of them may have simpler/less
   obfuscated APIs.
3. Whatever adapter gets built should live in
   `pipeline/apix/adapters/{indigo,ixigo,easemytrip,cleartrip}.py`,
   replacing the relevant stub, following `BaseAdapter`'s interface
   (`fetch(route, depart_date) -> list[FareQuote]`). Real fetched rows
   should get `is_synthetic=False`.
4. If nothing pans out within reasonable time, it's fine to leave this
   stubbed and documented (already the case in `docs/SCRAPING.md`) —
   this was always the plan's accepted fallback. Don't sink excessive
   time into anti-bot reverse-engineering at the expense of anything
   else still open.

### Deployment status (2026-09-29)
- API: live at https://apix-api.fly.dev (Fly.io, Postgres via
  `apix-db` Fly Postgres cluster, region `sin`). `fly.toml` in `api/`.
- Dashboard: live at https://apix-dashboard-sigma.vercel.app (Vercel).
- DB seeded with two backfill windows: recent (~45 days ending "today")
  for the live demo, and Nov-Dec 2025 (`--end-date 2025-12-31`) to
  overlap the real MoSPI CPI reference months for the backtest.
- `ALLOWED_ORIGINS` on the Fly API is set to the Vercel dashboard's
  origin (was CORS-blocked before this).
- `daily-scrape.yml` GitHub Action is green (was silently failing on
  every run before — `DATABASE_URL` resolves to `""` not unset in CI
  when the repo secret isn't configured, and `get_database_url()`
  wasn't falling back to SQLite for an empty string; fixed in
  `pipeline/apix/db.py`).

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
