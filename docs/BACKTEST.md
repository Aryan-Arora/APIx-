# Backtest — approach, scope, and caveats

## What this backtest is (and is not)

APIx is a novel, high-frequency airfare index. There's no pre-existing
"ground truth" airfare index to validate it against exactly, so the
backtest does two different, more modest things instead:

1. **Trend comparison against MoSPI's CPI "Transport and Communication"
   group index.** This is the honest, primary comparison. It is
   explicitly **not** a fare-for-fare comparison — the CPI Transport &
   Communication group covers rail, road transport, fuel, postal
   services, telecom, and more, not just domestic air travel. We only
   check whether APIx's *direction of movement* broadly agrees with that
   group index month over month, and compute a Pearson correlation
   between the two monthly series. Agreement or correlation here is weak
   supporting evidence that APIx is capturing real transport-cost
   dynamics — it is not proof of fare-level accuracy.

2. **Route-level comparison against DGCA average domestic fares**, where
   available, computing an absolute-percentage-error and MAPE between
   APIx's implied average fare and DGCA's published average fare per
   route per month. This is a more literal comparison, but only as good
   as the DGCA data behind it.

## Data status: CPI series is real, DGCA fares are still placeholder

- **`data/reference/cpi_transport_group_index.csv` is now real MoSPI
  data**, sourced directly from official MoSPI CPI monthly press
  releases (Annex-I and Annex-II), sub-group `6.1.03 "Transport and
  communication"`, Combined (rural+urban) area, Base Year 2012=100:
  - Dec 2024: index 171.0
  - Nov 2025: index 172.4 (Final)
  - Dec 2025: index 172.3 (Provisional), YoY inflation 0.76%

  **Base-year discontinuity caveat:** MoSPI's more recent releases
  (from around mid-2026 onward, e.g. the August 2026 press release)
  moved to a new Base Year 2024=100 series with a different group
  structure — the old combined "Transport and communication" sub-group
  was split into separate COICOP divisions (`07.1`–`07.4` Transport,
  `08.1`/`08.3` Communication) with no direct like-for-like row. This
  series therefore stops at Dec 2025 (last month under the old base);
  we did not attempt to splice the two bases together, since that would
  require rebasing math that isn't provided by MoSPI and would risk a
  fabricated join. Extending this series past Dec 2025 requires either
  (a) more historical old-base releases if MoSPI keeps publishing them
  in parallel, or (b) an explicit rebasing methodology using an overlap
  month in both series.

  **Sample size caveat:** only 3 real months exist, and only 2 of them
  (Nov 2025, Dec 2025) currently overlap with any APIx history (the
  pipeline additionally backfills a synthetic window ending
  `2025-12-31` via `--end-date`, specifically so there's a real month
  to compare against — see `HANDOFF_NOTES.md`). A correlation or
  direction-agreement computed from 2 overlapping months is
  **mathematically close to guaranteed to look "perfect" (±1.0 / 100%)
  and is not statistically meaningful** — `run_backtest` attaches an
  explicit note to that effect on any summary metric computed from
  fewer than 6 overlapping months. Treat these numbers as "the pipeline
  and real data are wired up correctly," not "APIx is validated."

- **`data/reference/dgca_monthly_fares.csv` is still placeholder DGCA
  average domestic fares.** Real DGCA airfare publications were not
  supplied; every row is marked `PLACEHOLDER` in `source_note` and
  `apix/backtest.py` logs a runtime warning on load. Until real DGCA
  figures are supplied, `MAPE_vs_dgca_fares` and any `backtest_results`
  rows should be treated as illustrative only, not evidence.

## What's computed

`pipeline/apix/backtest.py::run_backtest`, driven by
`python -m apix.pipeline backtest`:

- **`backtest_results`** (one row per route/month where DGCA data
  exists): `apix_avg_fare` vs `dgca_avg_fare` and `abs_pct_error`.
- **`backtest_summary`**:
  - `correlation_vs_cpi_transport_group` — Pearson correlation between
    APIx's monthly `all`-scope series and the CPI group index, over
    whatever months overlap between the two.
  - `direction_agreement_vs_cpi_transport_group` — fraction of
    consecutive months where both series moved the same direction.
  - `MAPE_vs_dgca_fares` — mean absolute percentage error across all
    route-months compared against DGCA figures.

If there's no month overlap between APIx's history and the reference
series, the summary metrics come back as `None` with a note explaining
why, rather than silently reporting a fabricated number. To guarantee
overlap with the real CPI months above, `python -m apix.pipeline
backfill` is run twice in this build: once with defaults (recent
history, for the live demo/dashboard) and once with `--days 60
--end-date 2025-12-31` (to cover Nov–Dec 2025, matching the real CPI
data). See `HANDOFF_NOTES.md` for the exact commands.

## Where this lives in code

- `pipeline/apix/backtest.py` — loading, metric computation.
- `pipeline/apix/pipeline.py::backtest_cmd` — CLI wiring, writes to
  `backtest_results` / `backtest_summary` tables.
