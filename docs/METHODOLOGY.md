# APIx Methodology

## In plain English

APIx tracks how expensive domestic Indian airfares are *right now*,
relative to a fixed starting point (the "base period", set to 100). It
covers a basket of 10 major Indian routes, weighted by how much traffic
each route carries, and within each route it looks at fares across five
different booking-lead-time windows (booking 1, 7, 15, 30, or 45 days
before departure), because a fare booked tomorrow behaves very
differently from one booked six weeks out.

Every day, for every (route, lead-time-bucket) combination, we take all
the fresh fare quotes we collected, throw out the extreme 10% (5% off
each end) to avoid a handful of freak prices skewing things, and average
the rest using a *geometric* mean (appropriate for price ratios/indices).
That gives one "elementary price" per cell per day. We compare each
cell's price today to its price in the base period, take the log of that
ratio, weight it by how important that route/lead-bucket combination is,
sum everything up, and exponentiate back — this is the same
weighted-geometric-mean approach used by real-world price indices like
the CPI, applied to airfares. The result is a single number: 100 means
"same as the base period", 110 means "10% pricier on average", 90 means
"10% cheaper".

We also publish the same index restricted to a single route, a single
carrier, or a single lead-time bucket, so someone can ask "how has the
BOM-DEL route specifically moved?" or "is IndiGo cheaper today relative
to its own baseline?" — each of those "scoped" indices reuses the exact
same formula, just with the weights renormalized over whatever's left in
scope.

## The formula

1. **Elementary price**, per route `r`, lead bucket `b`, day `t`:
   ```
   P[r,b,t] = TrimmedGeoMean(total_fare for clean, non-sold-out,
                              non-outlier quotes in that cell on day t;
                              trim 10% total, 5% off each tail)
   ```

2. **Base price**, `P0[r,b]` = mean of `P[r,b,t]` over the first 7 days
   of the base period. The index equals 100 in the base period by
   construction.

3. **Cell weight**:
   ```
   w[r,b] = route_weight[r] * lead_weight[b]
   ```
   `route_weight` comes from `data/reference/routes.csv`
   (`dgca_pax_share`, an ASSUMPTION where real DGCA traffic-share data
   wasn't available — see that file's accompanying README). `lead_weight`
   comes from `data/reference/lead_weights.json` (also an assumption
   about the shape of the booking curve):
   `{"T+1":0.10,"T+7":0.25,"T+15":0.30,"T+30":0.25,"T+45":0.10}`.

4. **APIx**, at day `t`:
   ```
   APIx(t) = 100 * exp( Σ_{r,b} w[r,b] * ln( P[r,b,t] / P0[r,b] ) )
   ```
   This is a weighted geometric-mean-of-relatives formula (the same
   family as the Törnqvist/Laspeyres-style indices used for official
   price statistics), implemented in `pipeline/apix/index.py::compute_daily_index`.

5. **Weekly / monthly aggregation**: the weekly value for an ISO week is
   the plain mean of that week's daily values; the monthly value for a
   calendar month is the plain mean of that month's daily values.
   (`aggregate_weekly` / `aggregate_monthly`.)

6. **Scoped indices** (`compute_scoped_daily_index`): `route:<id>`,
   `carrier:<name>`, and `lead:<bucket>` scopes restrict the input quotes
   to that scope and use the same formula with weights renormalized to
   sum to 1 over whatever cells remain (e.g. a `route:BOM-DEL` scope only
   has the 5 lead-bucket cells for that route, weighted by
   `lead_weight` alone).

7. **Missing data handling**: if a cell has no fresh quotes on a given
   day, its last known elementary price is carried forward for up to 3
   days (and that day's index computation is flagged as using imputed
   data for that cell); beyond 3 consecutive missing days the cell is
   dropped from that day's basket entirely and the remaining weights are
   renormalized so they still sum to 1.

8. **Synthetic-inclusive vs. real-only**: every index value is computed
   twice, once including simulator-generated (`is_synthetic=True`) quotes
   and once excluding them (`includes_synthetic` column in
   `index_values`). Since live scraping is currently stubbed (see
   `SCRAPING.md`), the `includes_synthetic=false` series will typically
   be empty or very sparse until real adapters are implemented — this is
   expected and is exactly why the flag exists.

## Where this lives in code

- `pipeline/apix/index.py` — the formula itself, plus unit tests in
  `pipeline/tests/test_index.py` with a fully hand-computed 2-route x
  2-lead-bucket example you can check by hand.
- `pipeline/apix/cleaning.py` — the step that turns raw `fare_quotes`
  into `clean_quotes` (dedup, outlier flagging, fee imputation) that
  feeds the elementary-price step.
- `pipeline/apix/pipeline.py::compute_index_cmd` — orchestrates cleaning
  + index computation + writing `index_values` for every
  scope/frequency/synthetic-mode combination.
