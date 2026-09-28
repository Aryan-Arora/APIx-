-- APIx reference schema (Postgres-flavored; SQLAlchemy models in apix/db.py
-- are the source of truth and also generate an equivalent schema for
-- SQLite locally / Postgres in prod via DATABASE_URL).

CREATE TABLE IF NOT EXISTS routes (
  route_id TEXT PRIMARY KEY,
  origin CHAR(3),
  dest CHAR(3),
  dgca_pax_share NUMERIC,
  active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS fare_quotes (
  id BIGSERIAL PRIMARY KEY,
  scraped_at TIMESTAMPTZ NOT NULL,
  source TEXT NOT NULL,
  source_type TEXT NOT NULL,              -- 'airline' | 'ota' | 'simulator'
  carrier TEXT,
  flight_no TEXT,
  route_id TEXT REFERENCES routes(route_id),
  origin CHAR(3),
  dest CHAR(3),
  depart_date DATE,
  depart_time TIME,
  lead_days INT,
  lead_bucket TEXT,                       -- 'T+1','T+7','T+15','T+30','T+45'
  fare_class TEXT,
  base_fare NUMERIC,
  taxes NUMERIC,
  udf NUMERIC,
  convenience_fee NUMERIC,
  total_fare NUMERIC NOT NULL,
  currency CHAR(3) DEFAULT 'INR',
  is_sold_out BOOLEAN DEFAULT false,
  is_synthetic BOOLEAN NOT NULL DEFAULT false,
  raw_hash TEXT
);

CREATE TABLE IF NOT EXISTS clean_quotes (
  id BIGSERIAL PRIMARY KEY,
  fare_quote_id BIGINT REFERENCES fare_quotes(id),
  scraped_at TIMESTAMPTZ NOT NULL,
  source TEXT NOT NULL,
  source_type TEXT NOT NULL,
  carrier TEXT,
  flight_no TEXT,
  route_id TEXT REFERENCES routes(route_id),
  origin CHAR(3),
  dest CHAR(3),
  depart_date DATE,
  depart_time TIME,
  lead_days INT,
  lead_bucket TEXT,
  fare_class TEXT,
  base_fare NUMERIC,
  taxes NUMERIC,
  udf NUMERIC,
  convenience_fee NUMERIC,
  total_fare NUMERIC NOT NULL,
  currency CHAR(3) DEFAULT 'INR',
  is_sold_out BOOLEAN DEFAULT false,
  is_synthetic BOOLEAN NOT NULL DEFAULT false,
  raw_hash TEXT,
  is_outlier BOOLEAN DEFAULT false,
  quality_flag TEXT DEFAULT 'ok'           -- 'ok','imputed','outlier','fee_estimated'
);

CREATE TABLE IF NOT EXISTS index_values (
  obs_date DATE,
  freq TEXT,
  scope TEXT,
  value NUMERIC,
  n_quotes INT,
  method_version TEXT,
  includes_synthetic BOOLEAN,
  PRIMARY KEY (obs_date, freq, scope, includes_synthetic)
);

CREATE TABLE IF NOT EXISTS backtest_results (
  id BIGSERIAL PRIMARY KEY,
  month DATE,
  route_id TEXT,
  apix_avg_fare NUMERIC,
  dgca_avg_fare NUMERIC,
  abs_pct_error NUMERIC,
  source_note TEXT
);

CREATE TABLE IF NOT EXISTS backtest_summary (
  id BIGSERIAL PRIMARY KEY,
  metric TEXT,
  value NUMERIC,
  note TEXT
);

CREATE TABLE IF NOT EXISTS scrape_runs (
  id BIGSERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  source TEXT,
  status TEXT,
  quotes_count INT DEFAULT 0,
  error_msg TEXT
);
