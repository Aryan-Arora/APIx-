"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  BookOpen,
  ChevronRight,
  Code2,
  Database,
  Download,
  ArrowUpRight,
  CalendarDays,
  Grid2X2,
  Landmark,
  Menu,
  Plane,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const BASE = (
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1"
).replace(/\/$/, "");
const KEY = process.env.NEXT_PUBLIC_API_KEY || "";
const sections = [
  "Overview",
  "Sector heatmap",
  "Lead-time elasticity",
  "Carriers",
  "Reference backtest",
  "Data quality",
  "Methodology",
  "API access",
] as const;
type Section = (typeof sections)[number];
type Point = {
  date: string;
  value: number;
  n_quotes: number;
  includes_synthetic: boolean;
};
type Latest = Partial<Point> & {
  change_day_pct: number | null;
  change_week_pct: number | null;
  change_month_pct: number | null;
};
type Route = {
  route_id: string;
  origin: string;
  dest: string;
  dgca_pax_share: number;
};
type Heat = {
  route_id: string;
  date: string;
  value: number;
  includes_synthetic: boolean;
};
type Lead = {
  lead_bucket: string;
  avg_fare: number;
  relative_to_T45: number | null;
};
type Carrier = {
  carrier: string;
  avg_fare: number;
  index: number | null;
  n_quotes: number;
};
type Run = {
  id: number;
  source: string;
  status: string;
  quotes_count: number;
  started_at: string;
  error_msg: string | null;
};
type RealQuote = {
  id: number;
  scraped_at: string;
  source: string;
  route_id: string;
  carrier: string | null;
  lead_bucket: string;
  total_fare: number;
  depart_date?: string;
  flight_no?: string | null;
};
type QuotePage = {
  items: RealQuote[];
  total: number;
};
type Backtest = {
  summary: {
    mape: number | null;
    corr: number | null;
    direction: number | null;
  };
  rows: {
    month: string;
    route_id: string;
    apix_avg_fare: number | null;
    dgca_avg_fare: number | null;
    abs_pct_error: number | null;
    source_note: string;
  }[];
  notes: string[];
  provenance: string;
};
type Method = {
  title: string;
  formula: string;
  steps: string[];
  limitations: string[];
};
type Resource<T> = {
  data?: T;
  error?: string;
  loading: boolean;
  mode?: string;
};
const money = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
const num = (n: number | null | undefined, digits = 2) =>
  n == null
    ? "—"
    : n.toLocaleString("en-IN", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
const shortDate = (date: string) =>
  new Date(date.slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  });
const carrierNames: Record<string, string> = {
  "6E": "IndiGo",
  AI: "Air India",
  QP: "Akasa Air",
  IX: "Air India Express",
  SG: "SpiceJet",
};

function useApi<T>(path: string | null, refresh: number): Resource<T> {
  const [state, setState] = useState<
    Resource<T> & { path?: string; refresh?: number }
  >({
    loading: true,
  });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    fetch(BASE + path, {
      headers: { "X-API-Key": KEY },
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok)
          throw new Error(body.detail || `Request failed (${response.status})`);
        return {
          data: body as T,
          mode: response.headers.get("X-Data-Mode") || undefined,
        };
      })
      .then((result) => setState({ ...result, path, refresh, loading: false }))
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({ path, refresh, loading: false, error: error.message });
        else if (controller.signal.reason?.name === "AbortError")
          setState({
            path,
            refresh,
            loading: false,
            error:
              "Request timed out. The API may be waking up; retry in a moment.",
          });
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      clearTimeout(timeout);
      controller.abort("cancelled");
    };
  }, [path, refresh]);
  return state.path === path && state.refresh === refresh
    ? state
    : { loading: true };
}
function Status<T>({
  resource,
  empty = false,
  children,
}: {
  resource: Resource<T>;
  empty?: boolean;
  children: React.ReactNode;
}) {
  if (resource.loading)
    return (
      <div className="state loading" role="status">
        <RefreshCw size={20} className="spin" /> Loading observations…
      </div>
    );
  if (resource.error)
    return (
      <div className="state error" role="alert">
        <strong>Data could not be loaded</strong>
        <p>{resource.error}</p>
        <small>Check the API connection and use Refresh data.</small>
      </div>
    );
  if (empty)
    return (
      <div className="state">
        <Database size={28} />
        <strong>No observations for this selection</strong>
        <p>
          Live-only data appears after a successful collection run. Simulated
          history is available separately.
        </p>
      </div>
    );
  return children;
}
function Chart({
  data,
  kind = "index",
}: {
  data: (Point | Lead | Carrier)[];
  kind?: "index" | "lead" | "carrier";
}) {
  const common = { stroke: "#e7ecf2", vertical: false, strokeDasharray: "3 5" };
  const axis = {
    tick: { fontSize: 11, fill: "#718096" },
    axisLine: false,
    tickLine: false,
  };
  return (
    <div
      className="chart"
      role="img"
      aria-label={
        kind === "index"
          ? "Airfare price index over time, base 100"
          : "Average fare in rupees"
      }
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
        minWidth={1}
        minHeight={1}
      >
        {kind === "carrier" ? (
          <BarChart
            data={data}
            margin={{ top: 16, right: 15, left: 8, bottom: 0 }}
          >
            <CartesianGrid {...common} />
            <XAxis dataKey="carrier" {...axis} />
            <YAxis
              {...axis}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip formatter={(v) => money(Number(v))} />
            <Bar
              isAnimationActive={false}
              dataKey="avg_fare"
              name="Average fare"
              fill="#0b2a5b"
              radius={[5, 5, 0, 0]}
              maxBarSize={64}
            />
          </BarChart>
        ) : kind === "lead" ? (
          <LineChart
            data={data}
            margin={{ top: 16, right: 25, left: 8, bottom: 0 }}
          >
            <CartesianGrid {...common} />
            <XAxis dataKey="lead_bucket" {...axis} />
            <YAxis
              {...axis}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip formatter={(v) => money(Number(v))} />
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="avg_fare"
              name="Average fare"
              stroke="#0b2a5b"
              strokeWidth={3}
              dot={{ r: 5, fill: "#fff", strokeWidth: 3 }}
            />
          </LineChart>
        ) : (
          <AreaChart
            data={data}
            margin={{ top: 16, right: 16, left: -18, bottom: 0 }}
          >
            <defs>
              <linearGradient id="indexFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#466d9b" stopOpacity={0.16} />
                <stop offset="100%" stopColor="#466d9b" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid {...common} />
            <XAxis
              dataKey="date"
              {...axis}
              minTickGap={35}
              tickFormatter={shortDate}
            />
            <YAxis
              {...axis}
              domain={["auto", "auto"]}
              tickFormatter={(v) => Number(v).toFixed(0)}
            />
            <Tooltip
              labelFormatter={(v) => shortDate(String(v))}
              formatter={(v) => [num(Number(v)), "APIx"]}
            />
            <Area
              isAnimationActive={false}
              type="monotone"
              dataKey="value"
              stroke="#0b2a5b"
              strokeWidth={3}
              activeDot={{ r: 6, stroke: "#fff", strokeWidth: 3 }}
              fill="url(#indexFill)"
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
function FareReferenceChart({ rows }: { rows: Backtest["rows"] }) {
  return (
    <div
      className="chart"
      role="img"
      aria-label="Pipeline average airfare versus reference airfare in INR"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={rows.map((row) => ({
            ...row,
            period: `${row.month.slice(0, 7)} · ${row.route_id}`,
          }))}
          margin={{ top: 20, right: 25, left: 15, bottom: 10 }}
        >
          <CartesianGrid vertical={false} stroke="#e7ecf2" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis
            tickFormatter={(value) =>
              `₹${Number(value).toLocaleString("en-IN")}`
            }
            tick={{ fontSize: 11 }}
          />
          <Tooltip formatter={(value) => money(Number(value))} />
          <Line
            isAnimationActive={false}
            dataKey="apix_avg_fare"
            name="Pipeline average fare (INR)"
            stroke="#0b2a5b"
            strokeWidth={2}
          />
          <Line
            isAnimationActive={false}
            dataKey="dgca_avg_fare"
            name="Reference fare (INR)"
            stroke="#bd620d"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Delta({ value }: { value?: number | null }) {
  return (
    <span
      className={`delta ${value == null ? "neutral" : value < 0 ? "falling" : "rising"}`}
    >
      {value == null ? "—" : `${value >= 0 ? "+" : ""}${num(value)}%`}
    </span>
  );
}

export default function Dashboard() {
  const [section, setSection] = useState<Section>("Overview");
  const [synthetic, setSynthetic] = useState(true);
  const [freq, setFreq] = useState("daily");
  const [route, setRoute] = useState("all");
  const [metric, setMetric] = useState("index");
  const [windowDays, setWindowDays] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [mobileNav, setMobileNav] = useState(false);
  const modeQuery = `include_synthetic=${synthetic}`;
  const health = useApi<{
    data_mode: string;
    last_scrape_at: string | null;
    db: string;
  }>("/health", refresh);
  const latest = useApi<Latest>(`/index/latest?${modeQuery}`, refresh);
  const routes = useApi<Route[]>("/routes", refresh);
  const index = useApi<Point[]>(
    section === "Overview" ? `/index?freq=${freq}&${modeQuery}` : null,
    refresh,
  );
  const heat = useApi<Heat[]>(
    section === "Sector heatmap"
      ? `/heatmap?metric=${metric}&${modeQuery}`
      : null,
    refresh,
  );
  const lead = useApi<Lead[]>(
    section === "Lead-time elasticity"
      ? `/lead-curve?route=${route}&${modeQuery}`
      : null,
    refresh,
  );
  const carriers = useApi<Carrier[]>(
    section === "Carriers" ? `/carriers?${modeQuery}` : null,
    refresh,
  );
  const backtest = useApi<Backtest>(
    section === "Reference backtest" ? "/backtest" : null,
    refresh,
  );
  const runs = useApi<Run[]>(
    section === "Data quality" ? "/scrape-runs?limit=25" : null,
    refresh,
  );
  const method = useApi<Method>(
    section === "Methodology" ? "/methodology" : null,
    refresh,
  );
  const realQuotes = useApi<QuotePage>(
    section === "Overview" ? "/quotes?include_synthetic=false&limit=10" : null,
    refresh,
  );
  const mock = health.data?.data_mode === "mock" || latest.mode === "mock";
  const activeMode = mock
    ? "Mock API · illustrative fixtures"
    : health.data?.data_mode === "database"
      ? "Connected to shared database"
      : health.error
        ? "API connection unavailable"
        : "Checking data connection";
  const latestValue = latest.data?.value;
  const heatDates = Array.from(new Set(heat.data?.map((r) => r.date) || []))
    .sort()
    .slice(-14);
  const heatRoutes = Array.from(
    new Set(heat.data?.map((r) => r.route_id) || []),
  ).sort();
  const heatLookup = new Map(
    heat.data?.map((r) => [`${r.route_id}:${r.date}`, r.value]),
  );
  const firstLead = lead.data?.find((x) => x.lead_bucket === "T+1");
  const lastLead = lead.data?.find((x) => x.lead_bucket === "T+45");
  const saving =
    firstLead && lastLead && firstLead.avg_fare > 0
      ? (1 - lastLead.avg_fare / firstLead.avg_fare) * 100
      : null;
  const series = index.data || [];
  const lastDate = series.at(-1)?.date;
  const cutoff =
    lastDate && windowDays
      ? new Date(lastDate).getTime() - (windowDays - 1) * 86400000
      : null;
  const visibleSeries =
    cutoff == null
      ? series
      : series.filter((point) => new Date(point.date).getTime() >= cutoff);
  const rangeLow = visibleSeries.length
    ? Math.min(...visibleSeries.map((point) => point.value))
    : null;
  const rangeHigh = visibleSeries.length
    ? Math.max(...visibleSeries.map((point) => point.value))
    : null;
  function exportSeries() {
    const csv = [
      "date,index,quote_count,includes_synthetic,frequency",
      ...visibleSeries.map((point) =>
        [
          point.date,
          point.value,
          point.n_quotes,
          point.includes_synthetic,
          freq,
        ].join(","),
      ),
    ].join("\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `apix-${freq}-${synthetic ? "combined" : "observed"}.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  useEffect(() => {
    if (!mobileNav) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileNav(false);
        document.querySelector<HTMLButtonElement>(".mobile-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [mobileNav]);
  function navigate(value: Section) {
    setSection(value);
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  return (
    <div className="shell">
      <a href="#main" className="skip">
        Skip to content
      </a>
      {mobileNav && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside id="navigation" className={`sidebar ${mobileNav ? "open" : ""}`}>
        <Link className="brand" href="/" aria-label="APIx home">
          <span className="brand-icon">
            <Plane size={23} />
          </span>
          <span>
            API<span className="brand-x">x</span>
            <small>AIRFARE PRICE INDEX</small>
          </span>
        </Link>
        <div className="workspace-label">
          WORKSPACE <span>01</span>
        </div>
        <nav aria-label="Main navigation">
          {sections.map((name, i) => {
            const Icon = [
              Activity,
              Grid2X2,
              TrendingUp,
              Plane,
              Landmark,
              ShieldCheck,
              BookOpen,
              Code2,
            ][i];
            return (
              <button
                key={name}
                className={section === name ? "nav-item active" : "nav-item"}
                onClick={() => navigate(name)}
                aria-current={section === name ? "page" : undefined}
              >
                <Icon size={18} />
                <span>{name}</span>
                {section === name && <ChevronRight size={14} />}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="research-icon">
            <Landmark size={21} />
          </div>
          <strong>Built for better measurement.</strong>
          <p>A research prototype for India’s evolving air travel economy.</p>
          <span className="prototype">
            SIH 2026 <span>PS 26056</span>
          </span>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-toggle"
              aria-label={mobileNav ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileNav}
              aria-controls="navigation"
              onClick={() => setMobileNav(!mobileNav)}
            >
              {mobileNav ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>Observatory</span>
            <ChevronRight size={13} />
            <strong>{section}</strong>
          </div>
          <div className="topbar-right">
            <span
              className={`connection-dot ${health.error ? "offline" : ""}`}
            />
            <span>{activeMode}</span>
            <span className="country">IN</span>
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-line" /> INDIA AIRFARE OBSERVATORY
              </div>
              <h1>
                {section === "Overview" ? (
                  <>
                    A clearer view of <br className="hero-break" />
                    <span className="heading-accent">
                      India’s airfare economy.
                    </span>
                  </>
                ) : (
                  section
                )}
              </h1>
              <p>
                {section === "Overview"
                  ? "Track price movements across India’s representative domestic routes."
                  : (
                      {
                        "Sector heatmap":
                          "See how airfare prices move across routes and observation dates.",
                        "Lead-time elasticity":
                          "Explore the relationship between booking horizon and ticket price.",
                        Carriers:
                          "Compare observed average fares and stored carrier indices.",
                        "Reference backtest":
                          "Evaluate evidence, with reference provenance kept in view.",
                        "Data quality":
                          "Collection activity and source health, directly from the pipeline.",
                        Methodology:
                          "Understand how observations become a fixed-basket price index.",
                        "API access":
                          "Bring transparent airfare indicators into your own tools.",
                      } as Record<string, string>
                    )[section]}
              </p>
            </div>
            <button
              className="button secondary refresh"
              aria-label="Refresh data"
              onClick={() => setRefresh((x) => x + 1)}
            >
              <RefreshCw size={15} className={health.loading ? "spin" : ""} />
              {health.loading ? "Refreshing…" : "Refresh data"}
            </button>
          </div>
          <div className="provenance-bar">
            <div>
              <span className="provenance-mark">
                <Database size={16} />
              </span>
              <strong>
                {synthetic
                  ? "Includes simulated history"
                  : "Live observations only"}
              </strong>
              <span className="provenance-detail">
                {mock
                  ? "Mock fixtures · not measured fares"
                  : synthetic
                    ? "Synthetic rows are included and labelled."
                    : "Synthetic quotes are excluded."}
              </span>
            </div>
            <label className="toggle-label">
              <span>Include simulated history</span>
              <input
                type="checkbox"
                aria-label="Include simulated history"
                checked={synthetic}
                onChange={(e) => setSynthetic(e.target.checked)}
              />
              <span className="switch" aria-hidden="true" />
            </label>
          </div>

          {section === "Overview" && (
            <>
              <div className="stats-grid">
                <article className="stat-card headline">
                  <div className="stat-label">
                    ALL-INDIA AIRFARE PRICE INDEX <Activity size={16} />
                  </div>
                  <div className="headline-number">
                    {latest.loading ? "…" : num(latestValue)}
                    <span>APIx</span>
                  </div>
                  <div className="stat-foot">
                    <Delta value={latest.data?.change_day_pct} />
                    <span>vs previous day</span>
                  </div>
                  <span className="base-note">Base period = 100</span>
                </article>
                <article className="stat-card">
                  <div className="stat-label">
                    7-DAY CHANGE <TrendingUp size={16} />
                  </div>
                  <div className="stat-number">
                    <Delta value={latest.data?.change_week_pct} />
                  </div>
                  <p>Compared with 7 days earlier</p>
                  <div className="stat-bottom">
                    Same basket. Same data mode.
                  </div>
                </article>
                <article className="stat-card">
                  <div className="stat-label">
                    30-DAY CHANGE <TrendingUp size={16} />
                  </div>
                  <div className="stat-number">
                    <Delta value={latest.data?.change_month_pct} />
                  </div>
                  <p>Compared with 30 days earlier</p>
                  <div className="stat-bottom">Not official CPI inflation</div>
                </article>
                <article className="stat-card">
                  <div className="stat-label">
                    LATEST OBSERVATIONS <Database size={16} />
                  </div>
                  <div className="stat-number">
                    {latest.data?.n_quotes?.toLocaleString("en-IN") ?? "—"}
                    <span>quotes</span>
                  </div>
                  <p>
                    {latest.data?.date
                      ? `Index date · ${shortDate(latest.data.date)}`
                      : "No index observation available"}
                  </p>
                  <div className="stat-bottom">
                    {routes.data?.length ?? "—"} routes · 5 booking horizons
                  </div>
                </article>
              </div>
              {latest.error && (
                <div className="inline-error" role="alert">
                  Headline unavailable: {latest.error}
                </div>
              )}
              <article className="panel trend-panel">
                <div className="panel-header">
                  <div>
                    <h2>Airfare price movement</h2>
                    <p>
                      A consistent view of how the fixed basket changes over
                      time
                    </p>
                  </div>
                  <div className="segments" aria-label="Index frequency">
                    {["daily", "weekly", "monthly"].map((f) => (
                      <button
                        aria-pressed={freq === f}
                        className={freq === f ? "selected" : ""}
                        key={f}
                        onClick={() => setFreq(f)}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="chart-meta">
                  <span>
                    <i className="legend-line" />
                    All-India APIx
                  </span>
                  <span className="badge">
                    {synthetic ? "SIMULATED HISTORY INCLUDED" : "LIVE ONLY"}
                  </span>
                </div>
                <div className="chart-toolbar">
                  <div className="range-controls" aria-label="Chart time range">
                    <CalendarDays size={15} aria-hidden="true" />
                    {[
                      [14, "2 weeks"],
                      [30, "1 month"],
                      [0, "All history"],
                    ].map(([days, label]) => (
                      <button
                        key={days}
                        className={windowDays === days ? "selected" : ""}
                        aria-pressed={windowDays === days}
                        onClick={() => setWindowDays(Number(days))}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <button
                    className="export-button"
                    disabled={!visibleSeries.length || index.loading}
                    onClick={exportSeries}
                  >
                    <Download size={14} /> Export CSV
                  </button>
                </div>
                <Status resource={index} empty={!visibleSeries.length}>
                  <Chart data={visibleSeries} />
                </Status>
                <div className="panel-footer">
                  <span className="chart-range">
                    Range{" "}
                    <strong>
                      {num(rangeLow)} — {num(rangeHigh)}
                    </strong>
                    <span> · base 100</span>
                  </span>
                  <span>
                    {visibleSeries.length
                      ? `${shortDate(visibleSeries[0].date)} — ${shortDate(visibleSeries[visibleSeries.length - 1].date)}`
                      : "Awaiting observations"}
                  </span>
                </div>
              </article>
              <div className="basket-strip">
                <div>
                  <span className="basket-icon">
                    <Plane size={19} />
                  </span>
                  <span>
                    <strong>The domestic basket</strong>
                    <small>Representative routes · fixed weights</small>
                  </span>
                </div>
                <div className="route-chips">
                  {routes.data?.slice(0, 4).map((item) => (
                    <span key={item.route_id}>
                      {item.origin}
                      <i>↔</i>
                      {item.dest}
                    </span>
                  ))}
                </div>
                <button onClick={() => navigate("Sector heatmap")}>
                  Explore {routes.data?.length || "all"} routes{" "}
                  <ArrowUpRight size={16} />
                </button>
              </div>
              <article className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Real observed fares</h2>
                    <p>
                      Manually captured, non-synthetic quotes — never a live
                      feed. See{" "}
                      <a
                        href="https://github.com/Aryan-Arora/APIx-/blob/main/docs/MANUAL_CAPTURE.md"
                        target="_blank"
                        rel="noreferrer"
                      >
                        the capture runbook
                      </a>
                      .
                    </p>
                  </div>
                  <span className="badge">
                    {realQuotes.loading
                      ? "…"
                      : `${realQuotes.data?.total ?? 0} CAPTURED`}
                  </span>
                </div>
                {realQuotes.loading ? (
                  <div className="state loading" role="status">
                    <RefreshCw size={20} className="spin" /> Loading
                    observations…
                  </div>
                ) : realQuotes.error ? (
                  <div className="state error" role="alert">
                    <strong>Data could not be loaded</strong>
                    <p>{realQuotes.error}</p>
                  </div>
                ) : !realQuotes.data?.items.length ? (
                  <div className="state">
                    <Plane size={28} />
                    <strong>No real observations captured yet</strong>
                    <p>
                      Live scraping is compliance-blocked (see Methodology).
                      Real quotes come from a person running an actual search
                      and pasting the results through{" "}
                      <code>scripts/capture_indigo.py</code> — see the
                      capture runbook linked above.
                    </p>
                  </div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>ROUTE</th>
                          <th>FLIGHT</th>
                          <th>LEAD BUCKET</th>
                          <th>FARE</th>
                          <th>CAPTURED</th>
                        </tr>
                      </thead>
                      <tbody>
                        {realQuotes.data.items.map((q) => (
                          <tr key={q.id}>
                            <td>{q.route_id}</td>
                            <td>{q.flight_no || "—"}</td>
                            <td>{q.lead_bucket}</td>
                            <td>{money(q.total_fare)}</td>
                            <td>{shortDate(q.scraped_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </article>
              <div className="overview-bottom">
                <article className="panel explore-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Go beyond the headline</h2>
                      <p>Understand where and when prices change.</p>
                    </div>
                  </div>
                  <div className="explore-grid">
                    <button onClick={() => navigate("Sector heatmap")}>
                      <span className="explore-icon">
                        <Grid2X2 size={23} />
                      </span>
                      <h3>
                        Across routes <ArrowRight size={17} />
                      </h3>
                      <p>Find pockets of price pressure in the route basket.</p>
                    </button>
                    <button onClick={() => navigate("Lead-time elasticity")}>
                      <span className="explore-icon green">
                        <TrendingUp size={23} />
                      </span>
                      <h3>
                        Across booking horizons <ArrowRight size={17} />
                      </h3>
                      <p>See the fare difference between T+1 and T+45.</p>
                    </button>
                  </div>
                </article>
                <article className="method-note">
                  <div className="eyebrow">
                    <ShieldCheck size={15} /> TRANSPARENCY BY DESIGN
                  </div>
                  <h2>Every number needs context.</h2>
                  <p>
                    {mock
                      ? "You are viewing illustrative API fixtures. These are not live collections or a validated historical backtest."
                      : "Synthetic and observed fares remain distinct. This index is a research prototype, not an official government statistic."}
                  </p>
                  <button onClick={() => navigate("Methodology")}>
                    Read the methodology <ArrowRight size={15} />
                  </button>
                </article>
              </div>
            </>
          )}

          {section === "Sector heatmap" && (
            <article className="panel">
              <div className="panel-header">
                <div>
                  <h2>Route price matrix</h2>
                  <p>
                    Latest 14 available dates · hover or focus a cell for its
                    value
                  </p>
                </div>
                <label className="select-label">
                  Measure
                  <select
                    value={metric}
                    onChange={(e) => setMetric(e.target.value)}
                  >
                    <option value="index">Price index</option>
                    <option value="avg_fare">Average fare (INR)</option>
                  </select>
                </label>
              </div>
              <Status resource={heat} empty={!heat.data?.length}>
                <div className="table-scroll heatmap">
                  <table>
                    <thead>
                      <tr>
                        <th>ROUTE</th>
                        {heatDates.map((d) => (
                          <th key={d}>{shortDate(d)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {heatRoutes.map((r) => (
                        <tr key={r}>
                          <th>{r.replace("-", " ↔ ")}</th>
                          {heatDates.map((d) => {
                            const value = heatLookup.get(`${r}:${d}`);
                            const intensity =
                              value == null
                                ? 0
                                : Math.min(
                                    0.85,
                                    Math.max(
                                      0.08,
                                      metric === "index"
                                        ? (value - 92) / 28
                                        : (value - 2500) / 10000,
                                    ),
                                  );
                            return (
                              <td key={d}>
                                <span
                                  tabIndex={0}
                                  title={`${r} · ${d}: ${value == null ? "missing" : metric === "index" ? num(value) : money(value)}`}
                                  style={{
                                    background: `rgba(11,42,91,${intensity})`,
                                    color: intensity >= 0.64 ? "#fff" : "#000",
                                  }}
                                >
                                  {value == null
                                    ? "—"
                                    : metric === "index"
                                      ? num(value, 1)
                                      : money(value)}
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="panel-footer">
                  <span>Canonical airport pairs · both directions</span>
                  <span>
                    Lower <i className="scale" /> Higher
                  </span>
                </div>
              </Status>
            </article>
          )}

          {section === "Lead-time elasticity" && (
            <article className="panel">
              <div className="panel-header">
                <div>
                  <h2>The booking-horizon curve</h2>
                  <p>
                    Latest available observation date · average valid total fare
                  </p>
                </div>
                <label className="select-label">
                  Route
                  <select
                    value={route}
                    onChange={(e) => setRoute(e.target.value)}
                  >
                    <option value="all">All routes</option>
                    {routes.data?.map((r) => (
                      <option key={r.route_id}>{r.route_id}</option>
                    ))}
                  </select>
                </label>
              </div>
              <Status resource={lead} empty={!lead.data?.length}>
                <Chart data={lead.data || []} kind="lead" />
                {saving != null && (
                  <div className="insight">
                    <ArrowDownRight size={25} />
                    <div>
                      <strong>
                        {num(Math.abs(saving), 1)}%{" "}
                        {saving >= 0 ? "lower" : "higher"} average fare at T+45
                      </strong>
                      <p>
                        Compared with T+1 for this selection. A cross-sectional
                        comparison, not a prediction or a causal saving
                        estimate.
                      </p>
                    </div>
                  </div>
                )}
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>ADVANCE PURCHASE</th>
                        <th>AVERAGE FARE</th>
                        <th>RELATIVE TO T+45</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lead.data?.map((r) => (
                        <tr key={r.lead_bucket}>
                          <td>{r.lead_bucket}</td>
                          <td>{money(r.avg_fare)}</td>
                          <td>{num(r.relative_to_T45)}×</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Status>
            </article>
          )}

          {section === "Carriers" && (
            <article className="panel">
              <div className="panel-header">
                <div>
                  <h2>Carrier comparison</h2>
                  <p>
                    All available observations in the selected data mode · route
                    mixes may differ
                  </p>
                </div>
              </div>
              <Status resource={carriers} empty={!carriers.data?.length}>
                <Chart data={carriers.data || []} kind="carrier" />
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>CARRIER</th>
                        <th>AVERAGE FARE</th>
                        <th>MEAN DAILY INDEX</th>
                        <th>QUOTES</th>
                      </tr>
                    </thead>
                    <tbody>
                      {carriers.data?.map((r) => (
                        <tr key={r.carrier}>
                          <td>
                            {carrierNames[r.carrier] || r.carrier}{" "}
                            {carrierNames[r.carrier] && (
                              <small>{r.carrier}</small>
                            )}
                          </td>
                          <td>{money(r.avg_fare)}</td>
                          <td>{num(r.index)}</td>
                          <td>{r.n_quotes.toLocaleString("en-IN")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Status>
            </article>
          )}

          {section === "Reference backtest" && (
            <Status resource={backtest}>
              <div className="notice">
                <Landmark size={21} />
                <div>
                  <strong>Reference validation has a different scope.</strong>
                  <p>
                    The CPI Transport &amp; Communication group includes rail,
                    road and telecom as well as air travel. Compare trend and
                    direction; CPI index points cannot be compared with rupee
                    fares. This panel shows the pipeline’s reference results and
                    is independent of the live-only toggle.
                  </p>
                </div>
              </div>
              <div className="stats-grid three">
                {[
                  ["MAPE", backtest.data?.summary.mape, "%"],
                  ["Correlation", backtest.data?.summary.corr, ""],
                  [
                    "Direction agreement (fraction)",
                    backtest.data?.summary.direction,
                    "",
                  ],
                ].map(([label, value, unit]) => (
                  <article className="stat-card" key={String(label)}>
                    <div className="stat-label">{label}</div>
                    <div className="stat-number">
                      {num(value as number | null)}
                      {value != null ? unit : ""}
                    </div>
                    <p>
                      {value == null
                        ? "Not available · no claim made"
                        : "See pipeline provenance below"}
                    </p>
                  </article>
                ))}
              </div>
              <article className="panel">
                <div className="panel-header">
                  <div>
                    <h2>Reference evidence</h2>
                    <p>{backtest.data?.provenance}</p>
                  </div>
                </div>
                {backtest.data?.notes.map((note, i) => (
                  <p className="reference-note" key={i}>
                    {note}
                  </p>
                ))}
                {backtest.data &&
                  backtest.data.rows.length > 0 &&
                  !backtest.data.notes.some((note) =>
                    /placeholder|index points/i.test(note),
                  ) &&
                  backtest.data.rows.every(
                    (row) =>
                      row.apix_avg_fare != null &&
                      row.dgca_avg_fare != null &&
                      /INR/i.test(row.source_note) &&
                      !/placeholder/i.test(row.source_note),
                  ) && <FareReferenceChart rows={backtest.data.rows} />}
                {!backtest.data?.rows.length ? (
                  <div className="state">
                    <Landmark size={28} />
                    <strong>Awaiting a verified reference series</strong>
                    <p>
                      No valid overlapping reference results are available.
                      Placeholder inputs do not establish accuracy; consult the
                      pipeline notes above.
                    </p>
                  </div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>MONTH</th>
                          <th>ROUTE</th>
                          <th>APIx VALUE*</th>
                          <th>REFERENCE VALUE*</th>
                          <th>SOURCE / UNITS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtest.data.rows.map((r, i) => (
                          <tr key={i}>
                            <td>{r.month}</td>
                            <td>{r.route_id}</td>
                            <td>{num(r.apix_avg_fare)}</td>
                            <td>{num(r.dgca_avg_fare)}</td>
                            <td>{r.source_note}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="reference-note">
                      *Legacy schema field names imply fares. Confirm units from
                      the source note before interpretation; unlike units are
                      not charted together.
                    </p>
                  </div>
                )}
              </article>
            </Status>
          )}

          {section === "Data quality" && (
            <article className="panel">
              <div className="panel-header">
                <div>
                  <h2>Source collection log</h2>
                  <p>
                    Recorded pipeline runs · failures are retained, not hidden
                  </p>
                </div>
                <span className="badge">
                  {mock ? "MOCK MODE" : "DATABASE RUN LOG"}
                </span>
              </div>
              <Status resource={runs}>
                {!runs.data?.length ? (
                  <div className="state">
                    <ShieldCheck size={28} />
                    <strong>No scraper runs recorded</strong>
                    <p>
                      {mock
                        ? "Mock mode does not fabricate successful live collection runs."
                        : "Run history will appear after Engineer A executes the pipeline."}
                    </p>
                  </div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>SOURCE</th>
                          <th>STATUS</th>
                          <th>QUOTES</th>
                          <th>STARTED (UTC)</th>
                          <th>DETAIL</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.data.map((r) => (
                          <tr key={r.id}>
                            <td>{r.source}</td>
                            <td>
                              <span className={`run-status ${r.status}`}>
                                {r.status}
                              </span>
                            </td>
                            <td>{r.quotes_count}</td>
                            <td>
                              {new Date(r.started_at)
                                .toISOString()
                                .replace("T", " ")
                                .slice(0, 19)}
                            </td>
                            <td>{r.error_msg || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Status>
              <div className="panel-footer">
                Sold-out and outlier quotes remain auditable in /quotes; they
                are excluded from fare aggregates.
              </div>
            </article>
          )}

          {section === "Methodology" && (
            <Status resource={method}>
              <article className="panel prose">
                <div className="eyebrow">JEVONS-TYPE GEOMETRIC INDEX</div>
                <h2>{method.data?.title}</h2>
                <p>
                  The index tracks relative price movement across a
                  representative basket of routes and booking horizons. An index
                  of 110 means the weighted basket is 10% above its base level.
                </p>
                <div className="formula">{method.data?.formula}</div>
                <ol>
                  {method.data?.steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
                <h2>Interpretation &amp; limitations</h2>
                <ul>
                  {method.data?.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article className="panel prose">
                <h2>Route basket &amp; weights</h2>
                <p>
                  Canonical airport pairs combine both travel directions. These
                  are assumption weights until replaced with verified traffic
                  shares.
                </p>
                <Status resource={routes} empty={!routes.data?.length}>
                  <div className="route-weights">
                    {routes.data?.map((r) => (
                      <span key={r.route_id}>
                        {r.route_id}
                        <strong>{num(r.dgca_pax_share * 100, 1)}%</strong>
                      </span>
                    ))}
                  </div>
                </Status>
              </article>
            </Status>
          )}

          {section === "API access" && (
            <>
              <article className="panel prose">
                <div className="eyebrow">READ-ONLY · JSON · OPENAPI</div>
                <h2>Built to be used beyond the dashboard.</h2>
                <p>
                  Send the public demo key in the X-API-Key header. This key is
                  visible in the browser and grants read access only. The
                  prototype limits requests to 60 per minute per direct client
                  IP and process.
                </p>
                <a
                  className="button primary"
                  href={BASE.replace(/\/api\/v1$/, "") + "/docs"}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open interactive API docs <ArrowRight size={16} />
                </a>
                <h3>Get the live-only daily index</h3>
                <pre>
                  <code>{`curl '${BASE}/index?freq=daily&include_synthetic=false' \\\n  -H 'X-API-Key: ${KEY || "<configure public demo key>"}'`}</code>
                </pre>
                <p>
                  Data mode is reported in the X-Data-Mode response header. An
                  empty live-only series means no live index observations are
                  available.
                </p>
              </article>
              <article className="panel">
                <div className="panel-header">
                  <h2>Endpoint directory</h2>
                  <span className="badge">/api/v1</span>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>METHOD</th>
                        <th>ENDPOINT</th>
                        <th>RETURNS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ["/health", "Database readiness, mode and last scrape"],
                        ["/index", "Daily, weekly or monthly index series"],
                        ["/index/latest", "Headline and 1/7/30-day changes"],
                        ["/routes", "Canonical route basket and weights"],
                        ["/heatmap", "Route × date indices or average fares"],
                        [
                          "/lead-curve",
                          "Booking horizon fares and T+45 ratios",
                        ],
                        ["/carriers", "Carrier fares and mean daily indices"],
                        [
                          "/quotes",
                          "Paginated cleaned quotes and quality flags",
                        ],
                        ["/backtest", "Reference results, notes and metrics"],
                        ["/scrape-runs", "Source collection run history"],
                        ["/methodology", "Formula, steps and limitations"],
                      ].map(([path, description]) => (
                        <tr key={path}>
                          <td>
                            <span className="get">GET</span>
                          </td>
                          <td>
                            <code>{path}</code>
                          </td>
                          <td>{description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </>
          )}
          <footer>
            <span>
              <strong>APIx</strong> Prototype · SIH 2026 · PS 26056
            </span>
            <span>
              Research use only. Not an official government statistic.
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
