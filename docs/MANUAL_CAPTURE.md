# Manual IndiGo fare capture

Live scraping is compliance-blocked for all four candidate sources —
IndiGo, ixigo, Cleartrip and EaseMyTrip all explicitly disallow their
flight-search/booking paths in `robots.txt` (see
[`docs/SCRAPING.md`](SCRAPING.md)). This project's own
`apix/compliance.py::is_allowed()` fails closed on that, so no
automated adapter runs against them.

What's still honestly possible: a **person** — not a script, not this
repo's automation — running an actual search on goindigo.in in their
own browser, then pasting the visible flight-result text through
`scripts/capture_indigo.py`, which parses it into real (`is_synthetic
= False`) `FareQuote` rows. Robots.txt binds automated agents; it does
not (and cannot) forbid a human from looking at a page they loaded
themselves. This is not a live feed — it's an occasional, manual
snapshot.

## One capture session, all 10 routes

The index needs 5 lead-time buckets per route (`T+1`, `T+7`, `T+15`,
`T+30`, `T+45`) to fill a cell — `lead_bucket` is only set when
`lead_days` lands on exactly one of those numbers
(`apix/adapters/indigo_cards.py`). The simplest way to hit that
exactly: pick one capture day, and for each route search flights
departing 1, 7, 15, 30, and 45 days out **from that same day**. That's
10 routes × 5 searches = 50 searches in one sitting.

Route basket (`data/reference/routes.csv`, canonical alphabetical IDs):

| route_id | origin | dest |
|---|---|---|
| AMD-DEL | AMD | DEL |
| BLR-BOM | BLR | BOM |
| BLR-DEL | BLR | DEL |
| BLR-HYD | BLR | HYD |
| BOM-DEL | BOM | DEL |
| BOM-HYD | BOM | HYD |
| BOM-MAA | BOM | MAA |
| CCU-DEL | CCU | DEL |
| DEL-HYD | DEL | HYD |
| DEL-MAA | DEL | MAA |

For each route above, on your capture day, search departure dates
`today+1`, `today+7`, `today+15`, `today+30`, `today+45` (one-way,
economy, 1 passenger). It's fine to do a lighter first pass — e.g.
just `T+1` and `T+7` across all 10 routes (20 searches) — to see
whether this is worth the ongoing effort before committing to the
full 50 each time.

## Per-search steps

1. Search `origin` → `dest` for the target departure date at
   goindigo.in.
2. On the results page, select and copy the text of each non-stop
   Economy flight card you want captured (the accessibility-tree text
   — screen-reader/inspector text works well; see
   `data/fixtures/indigo_card_excerpt.txt` for the expected shape).
   Multiple cards from the same search can be pasted together,
   separated by a line containing only `---`.
3. Run:
   ```bash
   cd pipeline
   python scripts/capture_indigo.py \
     --route BOM-DEL \
     --depart-date 2026-10-14 \
     --in /path/to/pasted_cards.txt
   ```
   (or pipe the pasted text via stdin instead of `--in`). This does no
   network I/O and writes nothing to the database — it appends parsed
   quotes to `data/manual_captures/<today>.jsonl`.
4. The script prints what it parsed (flight, time, lead bucket, fare)
   so you can sanity-check before moving to the next route/date.

## Landing captures in the database

Capturing to the JSONL log is separate from importing it — nothing
touches `fare_quotes` until you explicitly run:

```bash
cd pipeline
python -m apix.pipeline import-manual-captures data/manual_captures/2026-09-29.jsonl
python -m apix.pipeline compute-index
```

`import-manual-captures` is idempotent (dedups by `raw_hash`, so
re-running on the same or overlapping files is safe) and refuses rows
marked `is_synthetic=true`. It never runs as part of `run-daily` or
any other automation — real captures are always a deliberate, manual
step. `compute-index` then folds the new real quotes into the
`includes_synthetic=false` index series and the
`/api/v1/quotes?include_synthetic=false` endpoint the dashboard's
"Real observed fares" panel reads from.
