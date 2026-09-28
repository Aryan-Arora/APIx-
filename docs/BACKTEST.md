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

## Placeholder data caveat — READ THIS

**Neither reference dataset used by this backtest is real, official
data.** Both were unavailable in this build environment:

- `data/reference/cpi_transport_group_index.csv` — placeholder monthly
  MoSPI CPI Transport & Communication group index values. Every row is
  marked `PLACEHOLDER` in its `source_note` column. `apix/backtest.py`
  logs a runtime warning every time this file is loaded, precisely so
  nobody mistakes it for real data.
- `data/reference/dgca_monthly_fares.csv` — placeholder DGCA average
  domestic fares for a couple of routes/months. Also marked
  `PLACEHOLDER`, also logged as a warning on load.

**A human needs to supply the real series** (from MoSPI's monthly CPI
press releases and DGCA's domestic airfare publications respectively)
before any correlation, direction-agreement, or MAPE number produced by
this backtest should be treated as meaningful evidence. Until then, the
backtest exists to prove the *pipeline* — the shapes, the write path to
`backtest_results`/`backtest_summary`, the metrics computed — works
correctly, not to make a real accuracy claim.

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

If there's no month overlap between APIx's history and the (placeholder)
reference series — which will normally be the case, since the simulator
generates recent dates and the placeholder CPI rows are dated 2025 —
the summary metrics come back as `None` with a note explaining why,
rather than silently reporting a fabricated number.

## Where this lives in code

- `pipeline/apix/backtest.py` — loading, metric computation.
- `pipeline/apix/pipeline.py::backtest_cmd` — CLI wiring, writes to
  `backtest_results` / `backtest_summary` tables.
