"""SQLAlchemy models + engine/session helpers for APIx.

Works against SQLite locally (default) and Postgres/Supabase in prod via
the same models, selected purely through the DATABASE_URL env var.
"""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Route(Base):
    __tablename__ = "routes"

    route_id = Column(String, primary_key=True)
    origin = Column(String(3))
    dest = Column(String(3))
    dgca_pax_share = Column(Float)
    active = Column(Boolean, default=True)


class FareQuote(Base):
    """Raw, append-only fare observations."""

    __tablename__ = "fare_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scraped_at = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # airline | ota | simulator
    carrier = Column(String)
    flight_no = Column(String)
    route_id = Column(String, ForeignKey("routes.route_id"))
    origin = Column(String(3))
    dest = Column(String(3))
    depart_date = Column(Date)
    depart_time = Column(Time)
    lead_days = Column(Integer)
    lead_bucket = Column(String)
    fare_class = Column(String)
    base_fare = Column(Float)
    taxes = Column(Float)
    udf = Column(Float)
    convenience_fee = Column(Float)
    total_fare = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    is_sold_out = Column(Boolean, default=False)
    is_synthetic = Column(Boolean, nullable=False, default=False)
    raw_hash = Column(String)


class CleanQuote(Base):
    """Cleaned view of fare_quotes with quality flags."""

    __tablename__ = "clean_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fare_quote_id = Column(Integer, ForeignKey("fare_quotes.id"))
    scraped_at = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    carrier = Column(String)
    flight_no = Column(String)
    route_id = Column(String, ForeignKey("routes.route_id"))
    origin = Column(String(3))
    dest = Column(String(3))
    depart_date = Column(Date)
    depart_time = Column(Time)
    lead_days = Column(Integer)
    lead_bucket = Column(String)
    fare_class = Column(String)
    base_fare = Column(Float)
    taxes = Column(Float)
    udf = Column(Float)
    convenience_fee = Column(Float)
    total_fare = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    is_sold_out = Column(Boolean, default=False)
    is_synthetic = Column(Boolean, nullable=False, default=False)
    raw_hash = Column(String)
    is_outlier = Column(Boolean, default=False)
    quality_flag = Column(String, default="ok")  # ok|imputed|outlier|fee_estimated


class IndexValue(Base):
    __tablename__ = "index_values"

    obs_date = Column(Date, primary_key=True)
    freq = Column(String, primary_key=True)  # daily|weekly|monthly
    scope = Column(String, primary_key=True)  # all|route:X|carrier:X|lead:X
    includes_synthetic = Column(Boolean, primary_key=True)
    value = Column(Float)
    n_quotes = Column(Integer)
    method_version = Column(String)


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(Date)
    route_id = Column(String)
    apix_avg_fare = Column(Float)
    dgca_avg_fare = Column(Float)
    abs_pct_error = Column(Float)
    source_note = Column(String)


class BacktestSummary(Base):
    __tablename__ = "backtest_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String)
    value = Column(Float)
    note = Column(String)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    source = Column(String)
    status = Column(String)  # ok|blocked|error
    quotes_count = Column(Integer, default=0)
    error_msg = Column(Text)


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///apix.db")


def get_engine(url: str | None = None):
    url = url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def get_session_factory(engine=None) -> sessionmaker:
    engine = engine or get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine=None) -> None:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)


def get_session(engine=None) -> Session:
    factory = get_session_factory(engine)
    return factory()
