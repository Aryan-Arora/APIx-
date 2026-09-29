import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from capture_indigo import split_cards, quote_to_jsonable  # noqa: E402
from apix.adapters.indigo_cards import parse_cards
from datetime import date, datetime, timezone

CARD = (
    Path(__file__).resolve().parents[2] / "data/fixtures/indigo_card_excerpt.txt"
).read_text()


def test_split_cards_single_card_no_delimiter():
    assert split_cards(CARD) == [CARD.strip("\n")]


def test_split_cards_multiple_cards_and_blank_entries():
    raw = f"{CARD}\n---\n\n---\n{CARD}\n"
    cards = split_cards(raw)
    assert len(cards) == 2
    assert cards[0].strip() == CARD.strip()
    assert cards[1].strip() == CARD.strip()


def test_split_cards_empty_input():
    assert split_cards("") == []
    assert split_cards("   \n  \n") == []


def test_quote_to_jsonable_round_trips_dates_and_times():
    route = {"origin": "BOM", "dest": "DEL"}
    observed = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
    departure = date(2026, 10, 14)
    (quote,) = parse_cards([CARD], route, departure, observed)

    d = quote_to_jsonable(quote)

    assert d["scraped_at"] == "2026-09-29T11:00:00+00:00"
    assert d["depart_date"] == "2026-10-14"
    assert d["depart_time"] == "05:00:00"
    assert d["route_id"] == "BOM-DEL"
    assert d["is_synthetic"] is False
