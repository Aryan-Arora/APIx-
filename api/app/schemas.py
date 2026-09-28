"""Validated public response contracts; additive fields carry provenance."""

from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IndexPoint(BaseModel):
    date: Date
    value: float
    n_quotes: int
    includes_synthetic: bool


class Latest(BaseModel):
    date: Date | None = None
    value: float | None = None
    n_quotes: int = 0
    includes_synthetic: bool
    change_day_pct: float | None = None
    change_week_pct: float | None = None
    change_month_pct: float | None = None


class Route(BaseModel):
    route_id: str
    origin: str
    dest: str
    dgca_pax_share: float
    active: bool


class HeatCell(BaseModel):
    route_id: str
    date: Date
    value: float
    includes_synthetic: bool


class LeadPoint(BaseModel):
    lead_bucket: str
    avg_fare: float
    relative_to_T45: float | None
    includes_synthetic: bool


class Carrier(BaseModel):
    carrier: str
    avg_fare: float
    index: float | None
    n_quotes: int
    includes_synthetic: bool


class Quote(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    scraped_at: datetime
    source: str
    route_id: str
    carrier: str | None = None
    lead_bucket: str
    total_fare: float
    is_synthetic: bool
    is_sold_out: bool
    is_outlier: bool | None = None
    quality_flag: str | None = None


class QuotePage(BaseModel):
    items: list[Quote]
    total: int
    limit: int
    offset: int


class Run(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    source: str
    status: str
    quotes_count: int
    error_msg: str | None


class BacktestRow(BaseModel):
    month: Date
    route_id: str
    apix_avg_fare: float | None
    dgca_avg_fare: float | None
    abs_pct_error: float | None
    source_note: str


class Summary(BaseModel):
    mape: float | None = None
    corr: float | None = None
    direction: float | None = None


class Backtest(BaseModel):
    summary: Summary
    rows: list[BacktestRow]
    notes: list[str]
    provenance: str


class Health(BaseModel):
    status: str
    db: str
    last_scrape_at: datetime | None
    version: str
    data_mode: Literal["mock", "database"]


class Methodology(BaseModel):
    title: str
    formula: str
    steps: list[str]
    limitations: list[str]
