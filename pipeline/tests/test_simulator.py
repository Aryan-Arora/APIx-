from datetime import date, timedelta

from apix.adapters.simulator import SimulatorAdapter, load_routes


def test_same_seed_same_output_backfill():
    sim1 = SimulatorAdapter(seed=42)
    sim2 = SimulatorAdapter(seed=42)
    q1 = sim1.backfill(days=3)
    q2 = sim2.backfill(days=3)
    assert len(q1) == len(q2)
    fares1 = [q.total_fare for q in q1]
    fares2 = [q.total_fare for q in q2]
    assert fares1 == fares2
    hashes1 = [q.raw_hash for q in q1]
    hashes2 = [q.raw_hash for q in q2]
    assert hashes1 == hashes2


def test_different_seed_different_output():
    sim1 = SimulatorAdapter(seed=1)
    sim2 = SimulatorAdapter(seed=2)
    q1 = sim1.backfill(days=2)
    q2 = sim2.backfill(days=2)
    fares1 = [q.total_fare for q in q1]
    fares2 = [q.total_fare for q in q2]
    assert fares1 != fares2


def test_backfill_covers_all_routes_and_lead_buckets():
    sim = SimulatorAdapter(seed=42)
    quotes = sim.backfill(days=2)
    routes = load_routes()
    route_ids = {r["route_id"] for r in routes}
    seen_routes = {q.route_id for q in quotes}
    seen_buckets = {q.lead_bucket for q in quotes}
    assert seen_routes == route_ids
    assert seen_buckets == {"T+1", "T+7", "T+15", "T+30", "T+45"}


def test_all_quotes_marked_synthetic_and_simulator_source():
    sim = SimulatorAdapter(seed=42)
    quotes = sim.backfill(days=1)
    assert all(q.is_synthetic for q in quotes)
    assert all(q.source == "simulator" for q in quotes)
    assert all(q.source_type == "simulator" for q in quotes)


def test_total_fare_always_positive():
    sim = SimulatorAdapter(seed=42)
    quotes = sim.backfill(days=5)
    assert all(q.total_fare > 0 for q in quotes)


def test_fetch_future_date_returns_quotes():
    sim = SimulatorAdapter(seed=42)
    routes = load_routes()
    depart_date = date.today() + timedelta(days=10)
    quotes = sim.fetch(routes[0], depart_date)
    assert len(quotes) == 5  # one per carrier


def test_fetch_past_date_returns_empty():
    sim = SimulatorAdapter(seed=42)
    routes = load_routes()
    depart_date = date.today() - timedelta(days=1)
    quotes = sim.fetch(routes[0], depart_date)
    assert quotes == []
