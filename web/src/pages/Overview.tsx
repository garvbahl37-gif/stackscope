import { ArrowDownRight, ArrowUpRight, Maximize2, Minus, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { payHeatMapOption, spotlightOption, streamOption } from "../charts/bento";
import { ensureWorldMap } from "../charts/map";
import { quadrantOption } from "../charts/quadrant";
import { EChart } from "../components/EChart";
import { NAV } from "../components/Shell";
import { type Column, DownloadButton, ErrorState, Loading, PageHeader, Panel, Segmented, YearScrubber } from "../components/ui";
import { type Overview as OverviewData, useMeta, useOverview, usePayMap, useQuadrant, useTechProfile, useTrends } from "../lib/api";
import { compactNum, int, money, pct, pp, signedPct } from "../lib/format";
import { useTokens } from "../lib/theme";

const CATEGORIES = [
  { value: "language", label: "Languages" },
  { value: "database", label: "Databases" },
  { value: "cloud", label: "Cloud platforms" },
  { value: "webframe", label: "Web frameworks" },
];
const QUADRANTS = ["Leaders", "Challengers", "Visionaries", "Niche players"] as const;
const DATABASES = ["PostgreSQL", "MySQL", "SQLite", "MongoDB"];
const MAP_YEAR = 2025;

function formatFindingValue(label: string, value: number): string {
  if (/HHI/.test(label)) return int(value);
  if (/pay,|median pay/.test(label)) return money(value);
  if (/MAE/.test(label)) return `${value.toFixed(1)} pp`;
  if (/odds of trusting/.test(label)) return `${value.toFixed(2)}×`;
  if (/lead over/.test(label)) return pp(value * 100, 0);
  if (/premium/.test(label)) return signedPct(value, 1);
  if (/growth in odds|growth/.test(label)) return signedPct(value, 0);
  return pct(value, 0);
}

/** The outlined round button in a card's head: opens the full view. */
function OpenView({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className="icon-btn icon-btn--outline" aria-label={label} title={label}>
      <ArrowUpRight aria-hidden />
    </Link>
  );
}

function Leader({ color, label, value, muted }: { color: string; label: string; value: string; muted?: boolean }) {
  return (
    <li className={muted ? "is-muted" : undefined}>
      <span className="leaders__key" style={{ background: color }} aria-hidden />
      <span>{label}</span><span className="leaders__dots" aria-hidden /><span className="leaders__value">{value}</span>
    </li>
  );
}

// ------------------------------------------------------------------------------------------
// Gauge: AI tool use in the latest wave
// ------------------------------------------------------------------------------------------
const GAUGE = { cx: 100, cy: 100, r: 82, from: -135, sweep: 270 };

function arc(fromDeg: number, toDeg: number): string {
  const { cx, cy, r } = GAUGE;
  const pt = (deg: number) => {
    const a = (deg * Math.PI) / 180;
    return `${(cx + r * Math.sin(a)).toFixed(2)} ${(cy - r * Math.cos(a)).toFixed(2)}`;
  };
  return `M ${pt(fromDeg)} A ${r} ${r} 0 ${toDeg - fromDeg > 180 ? 1 : 0} 1 ${pt(toDeg)}`;
}

function AiGauge({ rows }: { rows: OverviewData["ai"] }) {
  const t = useTokens();
  const last = rows[rows.length - 1];
  const first = rows[0];
  const end = GAUGE.from + GAUGE.sweep * last.using_w;
  const columns: Column<OverviewData["ai"][number]>[] = [
    { key: "survey_year", label: "Year" },
    { key: "using_w", label: "Use AI tools", value: (r) => r.using_w },
    { key: "distrust_w", label: "Distrust AI output", value: (r) => r.distrust_w },
    { key: "trust_w", label: "Trust AI output", value: (r) => r.trust_w },
  ];
  return (
    <Panel className="span-6 panel--fill" title={`AI tools in ${last.survey_year}`}
           tools={<><OpenView to="/ai" label="Open AI adoption and trust" /><DownloadButton columns={columns} rows={rows} filename="ai_adoption_trust.csv" /></>}>
      <div className="gauge-card">
        <svg className="gauge" viewBox="0 0 200 176" role="img"
             aria-label={`${pct(last.using_w, 0)} of developers used AI tools in ${last.survey_year}`}>
          <defs>
            <linearGradient id="heat-arc" gradientUnits="userSpaceOnUse" x1="18" y1="0" x2="182" y2="0">
              <stop offset="0" stopColor={t.heat[0]} /><stop offset="0.45" stopColor={t.heat[1]} />
              <stop offset="0.75" stopColor={t.heat[2]} /><stop offset="1" stopColor={t.heat[3]} />
            </linearGradient>
          </defs>
          <path d={arc(GAUGE.from, GAUGE.from + GAUGE.sweep)} className="gauge__track" />
          <path d={arc(GAUGE.from, end)} stroke="url(#heat-arc)" className="gauge__value" />
          <text x="100" y="104" textAnchor="middle" className="gauge__figure">{pct(last.using_w, 0)}</text>
          <text x="100" y="128" textAnchor="middle" className="gauge__label">use AI tools</text>
        </svg>
        <ul className="leaders leaders--keyed">
          <Leader color={t.heat[3]} label="Use AI tools" value={pct(last.using_w, 0)} />
          <Leader color={t.heat[2]} label="Distrust the output" value={pct(last.distrust_w, 0)} />
          <Leader color={t.heat[0]} label="Trust the output" value={pct(last.trust_w, 0)} />
          <Leader color={t.mapNone} label={`Used AI tools in ${first.survey_year}`} value={pct(first.using_w, 0)} muted />
        </ul>
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------
// Map: median pay by country, with a pinned callout that follows the hovered country
// ------------------------------------------------------------------------------------------
function PayMap() {
  const t = useTokens();
  const pay = usePayMap(MAP_YEAR);
  const [ready, setReady] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  useEffect(() => { ensureWorldMap().then(() => setReady(true)); }, []);

  const rows = useMemo(() => (pay.data?.rows ?? [])
    .filter((r) => r.pay_n >= 30 && r.median_pay_usd != null)
    .map((r) => ({ id: String(r.iso_numeric), country: r.country, value: r.median_pay_usd as number, n: r.pay_n })), [pay.data]);
  const option = useMemo(() => (ready && rows.length ? payHeatMapOption(rows, t, zoom) : null), [ready, rows, t, zoom]);
  const byId = useMemo(() => new Map(rows.map((r) => [r.id, r])), [rows]);
  const largest = useMemo(() => [...rows].sort((a, b) => b.n - a.n)[0], [rows]);
  const shown = (hover && byId.get(hover.id)) || largest;
  const sorted = useMemo(() => rows.map((r) => r.value).sort((a, b) => a - b), [rows]);
  const q = (p: number) => sorted[Math.round(p * (sorted.length - 1))];
  const events = useMemo(() => ({
    mouseover: (p: { name?: string; event?: { offsetX: number; offsetY: number } }) =>
      p.name && p.event && setHover({ id: p.name, x: p.event.offsetX, y: p.event.offsetY }),
    mouseout: () => setHover(null),
  }), []);
  const columns: Column<(typeof rows)[number]>[] = [
    { key: "country", label: "Country" }, { key: "value", label: `Median pay ${MAP_YEAR} (USD)` }, { key: "n", label: "Salaries" },
  ];

  return (
    <Panel className="span-6" title="Median pay by country"
           tools={<><OpenView to="/pay" label="Open pay and skills" /><DownloadButton columns={columns} rows={rows} filename={`median_pay_${MAP_YEAR}.csv`} /></>}>
      <div className="map-card">
        {pay.isError ? <ErrorState error={pay.error} /> : option ? (
          <EChart option={option} height={262} renderer="canvas" events={events}
                  label={`World map of median developer pay, ${MAP_YEAR}`} />
        ) : <Loading height={262} />}
        {shown && (
          <div className="map-callout" aria-live="polite"
               style={hover ? { left: `min(${hover.x + 18}px, calc(100% - 180px))`, top: Math.max(hover.y - 70, 0) } : undefined}>
            <strong>{money(shown.value)}</strong>
            <span>{shown.country}</span>
          </div>
        )}
        <div className="map-zoom" role="group" aria-label="Map zoom">
          <button type="button" className="icon-btn icon-btn--outline" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(6, z * 1.4))}><Plus aria-hidden /></button>
          <button type="button" className="icon-btn icon-btn--outline" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(1, z / 1.4))}><Minus aria-hidden /></button>
          <button type="button" className="icon-btn icon-btn--outline" aria-label="Reset the map" onClick={() => setZoom(1)}><Maximize2 aria-hidden /></button>
        </div>
        {sorted.length > 0 && (
          <ul className="map-legend" aria-label="Colour key">
            <li><span style={{ background: t.heat[3] }} />{money(q(0.96), { compact: true })}+</li>
            <li><span style={{ background: t.heat[2] }} />{money(q(0.5), { compact: true })}</li>
            <li><span style={{ background: t.heat[0] }} />{money(q(0.04), { compact: true })}</li>
          </ul>
        )}
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------
// Stream: Rust's rise, use inside the wider want-to-use halo
// ------------------------------------------------------------------------------------------
const STREAM_MARKS = [2017, 2021, 2025];

function RustStream() {
  const t = useTokens();
  const profile = useTechProfile("Rust");
  const series = profile.data?.series ?? [];
  const points = series.filter((s) => s.share_wanted_w != null)
    .map((s) => ({ year: s.survey_year, core: s.share_used_w, halo: s.share_wanted_w as number }));
  const option = useMemo(() => (points.length > 1 ? streamOption(points, STREAM_MARKS, t) : null), [profile.data, t]); // eslint-disable-line react-hooks/exhaustive-deps
  const last = series[series.length - 1];
  const at = (y: number) => points.find((p) => p.year === y);
  const left = (y: number) => points.length ? `${((y - (points[0].year - 0.5)) / points.length) * 100}%` : "0";
  const columns: Column<(typeof series)[number]>[] = [
    { key: "survey_year", label: "Year" },
    { key: "share_used_w", label: "Use Rust", value: (r) => r.share_used_w },
    { key: "share_wanted_w", label: "Want to use Rust", value: (r) => r.share_wanted_w },
  ];

  return (
    <Panel className="span-6 panel--bleed" title="Rust, the fastest-rising language"
           tools={<><OpenView to="/trends" label="Open adoption and forecasts" /><DownloadButton columns={columns} rows={series} filename="rust_adoption.csv" /></>}>
      {!last || !option ? <Loading height={250} /> : (
        <>
          <div className="kpis">
            <div><strong>{pct(last.share_used_w, 1)}</strong><span>use it in {last.survey_year}</span></div>
            <div><strong>{pct(last.share_wanted_w, 0)}</strong><span>want to use it</span></div>
            <div><strong>{signedPct(profile.data?.trend?.odds_growth, 0)}</strong><span>odds of use, per year</span></div>
          </div>
          <div className="stream">
            <div className="stream__pills stream__pills--top">
              {STREAM_MARKS.map((y, i) => at(y) && (
                <span key={y} style={{ left: left(y) }} className={i === 1 ? "is-dark" : undefined}>{pct(at(y)!.halo, 0)}</span>
              ))}
            </div>
            <EChart option={option} height={112} label="Rust: share who use it and share who want to use it, 2017 to 2025" />
            <div className="stream__pills stream__pills--bottom">
              {STREAM_MARKS.map((y) => at(y) && <span key={y} style={{ left: left(y) }}>{pct(at(y)!.core, 0)}<small>{y}</small></span>)}
            </div>
          </div>
          <p className="panel__foot stream__key">Inner band: developers who use Rust. Outer band: developers who want to use it next year.</p>
        </>
      )}
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------
// Spotlight trend: PostgreSQL against the other large databases
// ------------------------------------------------------------------------------------------
function DatabaseTrend() {
  const t = useTokens();
  const trends = useTrends(DATABASES, "adoption");
  const option = useMemo(() => {
    if (!trends.data) return null;
    return spotlightOption(trends.data.series.map((s) => ({ name: s.tech, points: s.points.map((p) => ({ x: p.year, y: p.value })) })),
      "PostgreSQL", t, (v) => pct(v, 0), (d) => pp(d * 100, 1));
  }, [trends.data, t]);
  const flat = (trends.data?.series ?? []).flatMap((s) => s.points.map((p) => ({ tech: s.tech, year: p.year, value: p.value })));
  const columns: Column<(typeof flat)[number]>[] = [{ key: "tech", label: "Database" }, { key: "year", label: "Year" }, { key: "value", label: "Adoption" }];
  return (
    <Panel className="span-6" title="Database adoption trend"
           tools={<><OpenView to="/trends" label="Open adoption and forecasts" /><DownloadButton columns={columns} rows={flat} filename="database_adoption.csv" /></>}>
      {trends.isError ? <ErrorState error={trends.error} /> : option ? (
        <EChart option={option} height={262} label="Adoption of PostgreSQL, MySQL, SQLite and MongoDB, 2017 to 2025" />
      ) : <Loading height={262} />}
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------
// Market position: the quadrant and its companion list share one category and one year
// ------------------------------------------------------------------------------------------
function MarketPosition() {
  const t = useTokens();
  const [category, setCategory] = useState("language");
  const quad = useQuadrant(category);
  const years = quad.data?.years ?? [];
  const [year, setYear] = useState<number>(2025);
  const shownYear = years.includes(year) ? year : years[years.length - 1] ?? year;
  const option = useMemo(
    () => (quad.data ? quadrantOption(quad.data.points, shownYear, t, { compact: true }) : null),
    [quad.data, shownYear, t],
  );
  const groups = useMemo(() => {
    const current = (quad.data?.points ?? []).filter((p) => p.survey_year === shownYear);
    return QUADRANTS.map((q) => ({
      quadrant: q,
      techs: current.filter((p) => p.quadrant === q).sort((a, b) => b.adoption - a.adoption),
    }));
  }, [quad.data, shownYear]);

  return (
    <>
      <Panel hero className="span-8" stale={quad.isPlaceholderData} title="Market position"
             tools={<Segmented label="Technology category" options={CATEGORIES} value={category} onChange={setCategory} />}>
        {quad.isError ? <ErrorState error={quad.error} /> : option ? (
          <EChart option={option} height={470} label={`Market position quadrant for ${category}, ${shownYear}`} />
        ) : <Loading height={470} />}
        <div className="scrub-row">
          {years.length > 0 && <YearScrubber years={years} value={shownYear} onChange={setYear} />}
        </div>
      </Panel>
      <Panel className="span-4 positions" title={`Positions in ${shownYear}`}>
        <div className="positions__groups" aria-live="polite">
          {groups.map((g) => (
            <div key={g.quadrant}>
              <h3 className="positions__head">
                <span>{g.quadrant}</span><span className="leaders__dots" aria-hidden /><span className="count">{g.techs.length}</span>
              </h3>
              {g.techs.length ? (
                <ul className="positions__names">{g.techs.map((p) => <li key={p.tech}>{p.tech}</li>)}</ul>
              ) : <p className="small muted">None this year</p>}
            </div>
          ))}
        </div>
        <p className="panel__foot">
          Up means more developers use it. Right means it keeps its users, attracts new ones and grows faster than its
          category. Press play to watch 2017 to 2025, or <Link to="/landscape">explore every category</Link>.
        </p>
      </Panel>
    </>
  );
}

function Movers({ movers }: { movers: OverviewData["movers"] }) {
  const meta = useMeta();
  const [dir, setDir] = useState<"Rising" | "Declining">("Rising");
  const label = (id: string) => meta.data?.categories.find((c) => c.id === id)?.label ?? id;
  const rows = movers
    .filter((m) => m.trend === dir)
    .sort((a, b) => (dir === "Rising" ? b.odds_growth - a.odds_growth : a.odds_growth - b.odds_growth))
    .slice(0, 6);
  const Arrow = dir === "Rising" ? ArrowUpRight : ArrowDownRight;
  return (
    <Panel title="Fastest movers" caption="Change in the odds of use per year, for technologies with a clear trend over five or more surveys."
           tools={<Segmented label="Direction" value={dir} onChange={setDir}
                             options={[{ value: "Rising", label: "Rising" }, { value: "Declining", label: "Falling" }]} />}>
      <ol className="movers">
        {rows.map((m) => (
          <li key={`${m.category}-${m.tech}`}>
            <span className="movers__name">
              <strong>{m.tech}</strong>
              <span>{label(m.category)}, {pct(m.share_first, 0)} to {pct(m.share_last, 0)} since {m.first_year}</span>
            </span>
            <span className={`movers__rate movers__rate--${dir === "Rising" ? "up" : "down"}`}>
              <Arrow aria-hidden />{signedPct(m.odds_growth, 0)}
            </span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

function Foundation({ k }: { k: OverviewData["kpis"] }) {
  return (
    <Panel title="Data foundation">
      <ul className="leaders">
        <li><span>Countries and territories</span><span className="leaders__dots" aria-hidden /><span className="leaders__value">{k.countries}</span></li>
        <li><span>Technology usage observations</span><span className="leaders__dots" aria-hidden /><span className="leaders__value">{compactNum(k.tech_observations)}</span></li>
        <li><span>Validated salaries</span><span className="leaders__dots" aria-hidden /><span className="leaders__value">{compactNum(k.pay_records)}</span></li>
        <li><span>Quality checks passing</span><span className="leaders__dots" aria-hidden /><span className="leaders__value">{k.checks_passed}/{k.checks_total}</span></li>
      </ul>
      <p className="panel__foot">Salaries are full-time professionals, converted to USD, real USD and PPP. <Link to="/quality">See every check</Link>.</p>
    </Panel>
  );
}

function Explore() {
  const items = NAV.flatMap((g) => g.items).filter((i) => i.to !== "/");
  return (
    <Panel title="Explore the views">
      <ul className="explore">
        {items.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <Link to={to}><span className="explore__icon"><Icon aria-hidden /></span>{label}</Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export default function Overview() {
  const { data, isError, error } = useOverview();
  const k = data?.kpis;
  return (
    <>
      <PageHeader
        title="Technology market"
        lede="Stack Overflow Developer Survey, nine annual waves from 2017 to 2025"
        figures={[
          { value: k ? int(k.respondents) : "664,042", label: "Survey responses", chip: `${k?.waves ?? 9} waves` },
          { value: k ? int(k.technologies) : "309", label: "Technologies tracked", chip: `${k ? int(k.raw_labels) : "448"} labels` },
        ]}
      />
      <div className="grid">
        {data ? <AiGauge rows={data.ai} /> : <div className="span-6"><Loading height={300} /></div>}
        <PayMap />
        <RustStream />
        <DatabaseTrend />

        <MarketPosition />

        {isError ? <div className="span-12"><ErrorState error={error} /></div> : !data ? <div className="span-12"><Loading height={300} /></div> : (
          <>
            <Panel className="span-8" title="What the data says"
                   caption="Every figure is computed by the pipeline and recomputed by an independent audit. Select a finding to open the view behind it.">
              <div className="findings">
                {data.findings.map((f) => (
                  <Link key={f.finding_id} to={f.route} className="finding">
                    <span className="finding__theme">{f.theme}</span>
                    <span>
                      <span className="finding__headline">{f.headline}</span>
                      <p className="finding__detail">{f.detail}</p>
                    </span>
                    <span className="finding__value">{formatFindingValue(f.value_label, f.value)}<small>{f.value_label}</small></span>
                  </Link>
                ))}
              </div>
            </Panel>
            <div className="span-4 stack overview-aside">
              <Movers movers={data.movers} />
              <Foundation k={data.kpis} />
              <Explore />
            </div>
          </>
        )}
      </div>
    </>
  );
}
