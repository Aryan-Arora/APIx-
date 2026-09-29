# Known limitations and acceptance boundaries

1. This serving-plane delivery does not establish that real scraping, backfill, pipeline CI or live deployment succeeded. Those must be verified separately. Mock data is generated solely for interface development and clearly labelled.
2. No authoritative reference CSV was supplied with the brief. Backtest metrics remain absent until Engineer A supplies reference results. A fabricated MAPE/correlation is never substituted.
3. The handoff conflicts: its revised reference is CPI Transport & Communication but its frozen schema and older instructions use DGCA rupee fares. The UI therefore shows provenance-aware evidence tables and avoids plotting unlike units together. A verified same-unit fare dataset can support a comparison chart; a CPI comparison needs an agreed index-specific contract. This open issue is written in HANDOFF_NOTES.md.
4. The 45-day mock series is not an implementation of the mandated index engine, calibration model or historical backtest. Engineer A must compute and test the real method. All mock quotes are synthetic. Mock source runs are empty.
5. Basket and lead weights are assumptions until replaced with sourced passenger-share and booking-distribution evidence. Labels state this limitation.
6. One minute of requests is limited per direct client IP per API process. Proxy trust and distributed rate limiting are production follow-ups. The public demo key is not a confidentiality boundary.
7. Next.js public variables are build-time values. Changing the API URL/key requires a rebuild. Render free-tier cold starts can exceed three seconds; the dashboard handles delayed/error responses, but this is not a latency guarantee.
8. Local API tests now pass on Python 3.11.15 as well as 3.13. CI and the Docker image target 3.11; production Postgres remains unverified until credentials are supplied.
9. Reference summaries are pipeline-wide and do not support synthetic-mode filtering in the frozen contract. That independence is explicit in the UI.
10. Database filters assume UTC observation timestamps. Database role permissions, RLS, TLS certificate verification, live table size, pool capacity and reference units require production review with the actual deployment.

Future work: verified traffic weights; longer observed history; approved source integrations; index-specific CPI backtest schema; cell-level imputation/coverage reports; distributed limits; persistent filter URLs; bounded/cached aggregate endpoints; production performance measurement.

## Integrated pipeline issues awaiting Engineer A

Engineer A fixed tail trimming (10% per tail), calendar-day carry-forward/base-period selection and BLR-BOM canonical naming in commit 479be55, now integrated. Backfill --days 45 still generates 46 dates. Fare MAPE still compares index points with rupee fares and remains withheld by the serving API for A’s current metric name. Placeholder-reference metrics are also withheld. See HANDOFF_NOTES.md for correction requests and sync status.
