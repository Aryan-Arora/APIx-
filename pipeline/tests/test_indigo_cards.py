from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from apix.adapters.indigo_cards import parse_cards

CARD = (
    Path(__file__).resolve().parents[2] / "data/fixtures/indigo_card_excerpt.txt"
).read_text()
ROUTE = {"origin": "BOM", "dest": "DEL"}
OBSERVED = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
DEPARTURE = date(2026, 10, 14)


def test_actual_card_selects_economy_not_business():
    (quote,) = parse_cards([CARD], ROUTE, DEPARTURE, OBSERVED)
    assert quote.total_fare == 6179
    assert quote.flight_no == "6E656"
    assert quote.route_id == "BOM-DEL"
    assert quote.lead_bucket == "T+15"
    assert not quote.is_synthetic
    assert quote.base_fare is None and quote.taxes is None


@pytest.mark.parametrize(
    "card",
    [
        CARD.replace("BOM, T2", "NMI"),
        CARD.replace("DEL, T1", "HDO"),
        CARD.replace("Non-stop", "1 stops"),
        CARD.replace("6E\n656", "6E\n656\n6E\n100"),
        CARD.replace("Economy Starts at", "Unavailable"),
        CARD.replace("05:00", "99:99"),
    ],
)
def test_rejects_nearby_connecting_and_incomplete_cards(card):
    assert parse_cards([card], ROUTE, DEPARTURE, OBSERVED) == []


def test_deduplicates_and_requires_capture_timezone():
    assert len(parse_cards([CARD, CARD], ROUTE, DEPARTURE, OBSERVED)) == 1
    with pytest.raises(ValueError):
        parse_cards([CARD], ROUTE, DEPARTURE, OBSERVED.replace(tzinfo=None))
