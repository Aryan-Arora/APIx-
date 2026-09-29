"""Manual IndiGo fare-card capture — NOT an automated scraper.

A human runs an actual search at goindigo.in in their own browser (not
this script — robots.txt disallows automating that flow, see
docs/SCRAPING.md), selects the visible flight-result cards' text, and
pastes it through this script. This script does no network I/O; it
only parses text the human already has on screen and appends the
result to a dated capture log. Nothing here touches the live database
— that's a separate, explicit step (`import-manual-captures`).

Usage:
    python scripts/capture_indigo.py --route BOM-DEL --depart-date 2026-10-14 < paste.txt
    python scripts/capture_indigo.py --route BOM-DEL --depart-date 2026-10-14 --in paste.txt

Input format: one or more cards, each the raw text of a single flight
result as copied from the page (see data/fixtures/indigo_card_excerpt.txt
for the shape), separated by a line containing only `---`.

Output: appends one JSON object per captured quote to
data/manual_captures/<UTC-date-of-capture>.jsonl (created if absent).
Re-running with the same input is safe to do — duplicates are only
resolved later, at import time, by raw_hash.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apix.adapters.indigo_cards import parse_cards  # noqa: E402

ROUTES_CSV = REPO_ROOT / "data" / "reference" / "routes.csv"
CAPTURES_DIR = REPO_ROOT / "data" / "manual_captures"


def load_route(route_id: str) -> dict:
    with open(ROUTES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["route_id"] == route_id:
                return {"origin": row["origin"], "dest": row["dest"]}
    raise SystemExit(
        f"Unknown route_id {route_id!r} — must be one of the basket's "
        f"canonical (alphabetically-sorted) IDs in {ROUTES_CSV}."
    )


def split_cards(raw: str) -> list[str]:
    parts = [p.strip("\n") for p in raw.split("\n---\n")]
    return [p for p in parts if p.strip()]


def quote_to_jsonable(fq) -> dict:
    d = asdict(fq)
    d["scraped_at"] = fq.scraped_at.isoformat()
    d["depart_date"] = fq.depart_date.isoformat()
    if fq.depart_time is not None:
        d["depart_time"] = fq.depart_time.isoformat()
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--route", required=True, help="Canonical route_id, e.g. BOM-DEL (see data/reference/routes.csv).")
    ap.add_argument("--depart-date", required=True, help="YYYY-MM-DD departure date as searched.")
    ap.add_argument("--observed-at", default=None, help="ISO8601 UTC capture timestamp; defaults to now.")
    ap.add_argument("--in", dest="infile", default=None, help="Path to pasted card text; defaults to stdin.")
    ap.add_argument("--out", default=None, help="Capture log path; defaults to data/manual_captures/<today>.jsonl.")
    args = ap.parse_args()

    route = load_route(args.route)
    depart_date = date.fromisoformat(args.depart_date)
    observed_at = (
        datetime.fromisoformat(args.observed_at)
        if args.observed_at
        else datetime.now(timezone.utc)
    )
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    raw = Path(args.infile).read_text() if args.infile else sys.stdin.read()
    cards = split_cards(raw)
    if not cards:
        raise SystemExit("No cards found in input (expected non-empty text, cards separated by a lone '---' line).")

    quotes = parse_cards(cards, route, depart_date, observed_at)

    out_path = Path(args.out) if args.out else CAPTURES_DIR / f"{observed_at.date().isoformat()}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a") as f:
        for q in quotes:
            f.write(json.dumps(quote_to_jsonable(q)) + "\n")

    print(
        f"{args.route} depart={depart_date} observed={observed_at.isoformat()}: "
        f"{len(quotes)}/{len(cards)} card(s) parsed -> {out_path}"
    )
    if not quotes:
        print("  (0 quotes — check the pasted text matches the expected card shape; nothing written beyond this run)")
    for q in quotes:
        print(f"  {q.flight_no} {q.depart_time} lead={q.lead_bucket} fare=₹{q.total_fare:.0f}")


if __name__ == "__main__":
    main()
