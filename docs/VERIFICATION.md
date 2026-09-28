# Serving-plane verification — 2026-09-28

## Automated checks

- 21 API tests passed under Python 3.11.15; cover auth, rate limiting, CORS, date/range validation, pagination, SQL injection parameter binding, synthetic isolation, aggregation exclusions, stored-route aliases, UTC timestamps, and withheld placeholder/invalid-unit metrics.
- Engineer A's existing 28 pipeline tests passed. These do not resolve the contract deviations identified in HANDOFF_NOTES.md.
- Web ESLint, TypeScript and optimized Next.js build passed.
- GitHub CI for commit 820eb6a passed API, pipeline and web jobs: https://github.com/Aryan-Arora/APIx-/actions/runs/36461782657.

## Populated-database integration

Executed A's backfill, cleaning/index computation and backtest locally, then exercised every API endpoint with `USE_MOCK=0` and the resulting SQLite database. All returned 200 with valid response models. Counts: 11,500 raw/clean quote rows; 1,176 stored index rows; 46 daily points in each route series; 460 heatmap cells; five carriers; five lead buckets; one simulator run. Zero live-only index/quote rows. Backtest had no overlapping reference months and no valid scores.

No A-owned files were modified during integration. A's simulator creates 46 dates for --days 45; this is documented as an issue, not disguised as exactly 45.

## Browser verification

Desktop: 1920×1080. Verified overview, combined/live-only toggle, index/average-fare heatmap, route selector and lead curve, carriers, missing-reference state, actual simulator run log, methodology and API directory. Saved screenshots in docs/img. Mobile viewport and error checks are recorded after completion below.

## Unverified / blocked

Public Render and Vercel deployment, Supabase Postgres connection and latency, real scraping, actual official reference comparison, and daily cron execution. Render is signed out; production DATABASE_URL and official reference data were not supplied. Pipeline method/backtest defects are assigned to Engineer A in handoff notes.

Mobile verification completed at 390×844: menu opens, selecting Overview closes it, the collapsed navigation is removed from keyboard/accessibility navigation, and the synthetic toggle retains its accessible name. Document width equals viewport width (390px), with no horizontal page overflow or Next.js error overlay. Browser page-error log was empty. Screenshot: docs/img/overview-mobile.png. Desktop heatmap and lead-curve screenshots were visually reviewed.
