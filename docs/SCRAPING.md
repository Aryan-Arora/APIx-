# Scraping — sources, status, and compliance stance

## Honest status summary

**No live scraping is functional in this build.** The four planned live
sources — three OTAs (ixigo, EaseMyTrip, Cleartrip) and one direct
airline site (IndiGo) — are implemented as **stub adapters** that raise
`NotImplementedError`. They exist to define the interface
(`pipeline/apix/adapters/base.py::BaseAdapter`) and to be filled in later
by someone with a Playwright-capable environment. The demo and all index
computation run entirely on the **simulator adapter**
(`pipeline/apix/adapters/simulator.py`), which is deterministic and
produces a full, plausible dataset without any network access.

This matches the project's own contingency plan: *"if zero live sources
work, stop — the demo uses the simulator... documented blocked attempts
is acceptable."*

## Per-source notes

### ixigo (`apix/adapters/ixigo.py`)
- Type: OTA aggregator.
- Status: **blocked**. ixigo's flight search results are rendered
  client-side (JS-driven XHR calls after the initial page load); no
  headless browser (Playwright/Puppeteer) was available in this build
  environment to drive that flow.
- What it would need: Playwright with a real browser context, careful
  selector/JSON-shape reverse engineering of their search API, and
  compliance review (see below).

### EaseMyTrip (`apix/adapters/easemytrip.py`)
- Type: OTA aggregator.
- Status: **blocked**, same reason as ixigo.

### Cleartrip (`apix/adapters/cleartrip.py`)
- Type: OTA aggregator.
- Status: **blocked**, same reason as ixigo.

### IndiGo (`apix/adapters/indigo.py`)
- Type: direct airline site.
- Status: **blocked**, same technical reason, plus an extra compliance
  flag: scraping an airline's own booking flow directly (rather than an
  aggregator) usually carries stricter Terms of Service language and
  deserves a dedicated legal/compliance read before attempting it, even
  once Playwright is available.

### simulator (`apix/adapters/simulator.py`)
- Type: synthetic data generator (`source_type='simulator'`).
- Status: **fully functional**. Deterministic given `SIMULATOR_SEED`
  (default 42). Models route base fares, day-of-week and seasonal
  effects, festival demand spikes (Diwali/Durga Puja/Holi, approximate
  2025-2026 dates), booking lead-time curves, per-carrier pricing
  differences (IndiGo/Air India/Air India Express/Akasa/SpiceJet), a
  fee-component split (base/taxes/UDF/convenience fee), occasional
  sold-out flights, and occasional injected outliers (to exercise the
  cleaner). All quotes are flagged `is_synthetic=True`. See the module
  docstring for the specific ASSUMPTION values used and why.

## Compliance stance (`apix/compliance.py`)

Even though no live scraper runs today, the compliance scaffolding is in
place for whoever implements one:

- `is_allowed(url)` checks the target site's `robots.txt` via
  `urllib.robotparser`, and **fails closed** (returns `False`, i.e.
  "not allowed") if robots.txt cannot be fetched or parsed — we never
  assume permission by default.
- `RateLimiter` enforces a maximum request rate (`SCRAPE_MAX_RPS` env
  var, default 0.5 req/s = one request every 2 seconds) with ±20%
  jitter, so a live adapter never hammers a target site or scrapes at a
  suspiciously constant cadence.
- A dedicated, identifying User-Agent string
  (`APIxResearchBot/0.1 (+https://github.com/; research prototype for
  SIH 2026 airfare price-index project; contact: project maintainers)`)
  is defined for any future live requests, rather than spoofing a
  browser UA.

Any future live adapter implementation should call `is_allowed()` before
its first request to a new host and route every request through
`RateLimiter.wait()`.

## `scrape_runs` logging

Every adapter invocation — live or simulator — writes a row to the
`scrape_runs` table (`started_at`, `finished_at`, `source`, `status`,
`quotes_count`, `error_msg`). The stub adapters' `NotImplementedError` is
caught by `apix/pipeline.py::run_daily_cmd` and logged with
`status='blocked'` and the adapter's explanatory message, rather than
silently failing or pretending success.

## Laptop investigation — 2026-09-29

Engineer B inspected the existing Safari flight-results session under the explicit handoff. `params` contained a sensor URL and the inspected `0HJ2g` response contained only `success: true`. Neither is a fare payload; no claim of encrypted fare data is justified from these responses.

The rendered cards expose readable Economy starting fares, flight numbers, times and airports. `apix.adapters.indigo_cards.parse_cards` now parses supplied card text, retaining exact airport pairs and nonstop Economy only. It leaves unknown fee components null and requires a timezone-aware capture time. `data/fixtures/indigo_card_excerpt.md` documents the observed test fixture. It is NOT a fresh collection and is not imported into the demo DB.

Unattended collection remains blocked: automated IndiGo navigation returned the site's generic error and robots retrieval timed out; Ixigo robots retrieval returned 403. Cleartrip robots disallows flight search and API paths, and EaseMyTrip disallows its flight-search listing. This investigation did not bypass these restrictions. Existing live adapters remain disabled; the parser alone is not live-source completion. A permitted source/feed or a reproducible approved browser collection flow is still required.

## Re-verification and outcome — 2026-09-29

`robots.txt` was re-fetched directly (not a proxy/relayed check) for all four candidate sources, resolving the earlier inconclusive/timed-out results:

- **IndiGo**: `Disallow: /book/*`, `/booking/*`, `/search.html`, `/book-flight.html`
- **ixigo**: `Disallow: /flights/search`, `/search/result/`
- **Cleartrip**: `Disallow: /flights/search*`, `/api/`
- **EaseMyTrip**: `Disallow: /flight-search/listing*`

Every source explicitly disallows the exact path an automated fetch would need. `apix/compliance.py::is_allowed()` fails closed on this by design, so this is a conclusive result, not a temporary gap: **no automated live adapter will be implemented against these four sources.** This isn't a shortfall relative to the project's plan — it's the documented, accepted fallback ("if zero live sources work, stop — the demo uses the simulator").

Two real, non-synthetic data paths remain available and are both implemented:

1. **Manual capture** (`pipeline/scripts/capture_indigo.py`, `docs/MANUAL_CAPTURE.md`): a person — not automation — runs an actual IndiGo search in their own browser and pastes the visible result text through the parser. Robots.txt binds automated agents, not a human reading a page they loaded themselves. This produces occasional real snapshots, never a continuous feed, and is never invoked by `run-daily` or any other automation — landing a capture in the database is always a deliberate, separate step (`python -m apix.pipeline import-manual-captures`).
2. **A licensed/authorized data provider** (e.g. a flight-data API with an actual terms-of-service grant) remains the correct path to a real automated feed, if one is set up later. Amadeus's free self-service tier — the obvious first candidate — was decommissioned in July 2026 in favor of an enterprise-sales-only access model, which ruled it out for this project's timeline; this wasn't re-attempted for the same date range.
