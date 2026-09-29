import json

from click.testing import CliRunner

from apix import db
from apix.pipeline import cli


def _write_capture(path, **overrides):
    row = {
        "scraped_at": "2026-09-29T11:00:00+00:00",
        "source": "indigo",
        "source_type": "airline",
        "route_id": "BOM-DEL",
        "origin": "BOM",
        "dest": "DEL",
        "depart_date": "2026-10-14",
        "total_fare": 6179.0,
        "carrier": "6E",
        "flight_no": "6E656",
        "depart_time": "05:00:00",
        "lead_days": 15,
        "lead_bucket": "T+15",
        "fare_class": "Economy starts-at",
        "base_fare": None,
        "taxes": None,
        "udf": None,
        "convenience_fee": None,
        "currency": "INR",
        "is_sold_out": False,
        "is_synthetic": False,
        "raw_hash": "testhash123",
    }
    row.update(overrides)
    path.write_text(json.dumps(row) + "\n")
    return path


def test_import_inserts_real_quote(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    capture = _write_capture(tmp_path / "capture.jsonl")

    result = CliRunner().invoke(cli, ["import-manual-captures", str(capture)])

    assert result.exit_code == 0, result.output
    engine = db.get_engine()
    session = db.get_session(engine)
    rows = session.query(db.FareQuote).all()
    assert len(rows) == 1
    assert rows[0].route_id == "BOM-DEL"
    assert rows[0].is_synthetic is False
    assert rows[0].total_fare == 6179.0


def test_import_is_idempotent_on_raw_hash(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    capture = _write_capture(tmp_path / "capture.jsonl")

    runner = CliRunner()
    runner.invoke(cli, ["import-manual-captures", str(capture)])
    result = runner.invoke(cli, ["import-manual-captures", str(capture)])

    assert result.exit_code == 0, result.output
    engine = db.get_engine()
    session = db.get_session(engine)
    assert session.query(db.FareQuote).count() == 1


def test_import_skips_rows_marked_synthetic(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    capture = _write_capture(tmp_path / "capture.jsonl", is_synthetic=True, raw_hash="synthetichash")

    result = CliRunner().invoke(cli, ["import-manual-captures", str(capture)])

    assert result.exit_code == 0, result.output
    engine = db.get_engine()
    session = db.get_session(engine)
    assert session.query(db.FareQuote).count() == 0
