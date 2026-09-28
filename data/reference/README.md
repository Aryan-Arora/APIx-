# Reference data

- **routes.csv** — the 10-route basket used by APIx. `dgca_pax_share` is an
  **ASSUMPTION**: real DGCA domestic sector-wise passenger-share figures were
  not available in this environment, so weights were estimated from route
  prominence/frequency (BOM-DEL and BLR-DEL are the busiest Indian trunk
  routes) and normalized to sum to 1.0. Replace with actual DGCA "Airport
  Pair" traffic data before production use.
- **lead_weights.json** — booking lead-time bucket weights, per the project
  spec (T+1..T+45), also an ASSUMPTION about the shape of the booking curve.
- **dgca_monthly_fares.csv** — placeholder for real DGCA average domestic
  fare data (not available). Marked PLACEHOLDER; used only to show the
  backtest wiring, not as a source of truth.
- **cpi_transport_group_index.csv** — placeholder for MoSPI CPI "Transport
  and Communication" group monthly index. Marked PLACEHOLDER. Real data
  must be supplied by a human (see BACKTEST.md).
