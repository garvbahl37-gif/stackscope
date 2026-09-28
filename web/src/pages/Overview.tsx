import { useMemo, useState } from "react";
import { Link } from "react-router";
import { lineOption } from "../charts/lines";
import { quadrantOption } from "../charts/quadrant";
import { EChart } from "../components/EChart";
import { ErrorState, Loading, PageHeader, Panel, Segmented, YearScrubber } from "../components/ui";
import { useOverview, useQuadrant } from "../lib/api";
import { compactNum, int, money, pct, pp, signedPct } from "../lib/format";
import { useTokens } from "../lib/theme";

const CATEGORIES = [
  { value: "language", label: "Languages" },
  { value: "database", label: "Databases" },
  { value: "cloud", label: "Cloud platforms" },
  { value: "webframe", label: "Web frameworks" },
];
const QUADRANTS = ["Leaders", "Challengers", "Visionaries", "Niche players"] as const;

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

function Hero() {
  const t = useTokens();
  const [category, setCategory] = useState("language");
  const quad = useQuadrant(category);
  const years = quad.data?.years ?? [];
  const [year, setYear] = useState<number>(2017);
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
    <Panel hero stale={quad.isPlaceholderData}>
      <div className="controls" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <Segmented label="Technology category" options={CATEGORIES} value={category} onChange={setCategory} />
        {years.length > 0 && <YearScrubber years={years} value={shownYear} onChange={setYear} autoplay />}
      </div>
      <div className="hero-grid">
        <div>
          {quad.isError ? <ErrorState error={quad.error} /> : option ? (
            <EChart option={option} height={500} label={`Market position quadrant for ${category}, ${shownYear}`} />
          ) : <Loading height={500} />}
        </div>
        <aside className="hero-aside" aria-label={`Positions in ${shownYear}`}>
          {groups.map((g) => (
            <div key={g.quadrant} className="hero-aside__group">
              <h3>{g.quadrant} <span className="muted">{g.techs.length}</span></h3>
              <p>{g.techs.length ? g.techs.map((p) => p.tech).join(", ") : "None this year"}</p>
            </div>
          ))}
          <p className="small muted">
            Up means more developers use it. Right means it keeps its users, attracts new ones and grows faster than its
            category. <Link to="/landscape">Explore every category</Link>.
          </p>
        </aside>
      </div>
    </Panel>
  );
}

function Minis() {
  const t = useTokens();
  const { data } = useOverview();
  const options = useMemo(() => {
    if (!data) return null;
    const ai = lineOption([
      { name: "Use AI tools", color: t.series[0], points: data.ai.map((r) => ({ x: r.survey_year, y: r.using_w })) },
      { name: "Distrust output", color: t.series[1], points: data.ai.map((r) => ({ x: r.survey_year, y: r.distrust_w })) },
      { name: "Trust output", color: t.series[2], points: data.ai.map((r) => ({ x: r.survey_year, y: r.trust_w })) },
    ], t, { yFormat: (v) => pct(v, 0), yMin: 0, yMax: 1, yInterval: 0.25, compact: true, endLabels: true, height: 190 });
    const remote = lineOption([
      { name: "Fully remote", color: t.series[0], points: data.remote.map((r) => ({ x: r.survey_year, y: r.share_w })) },
    ], t, { yFormat: (v) => pct(v, 0), yMin: 0, compact: true });
    const pay = lineOption([
      { name: "Median real pay", color: t.series[0], points: data.real_pay.map((r) => ({ x: r.survey_year, y: r.fixed_mix_median_real })) },
    ], t, { yFormat: (v) => money(v), yMin: Math.floor(Math.min(...data.real_pay.map((r) => r.fixed_mix_median_real)) / 5000) * 5000, compact: true });
    return { ai, remote, pay };
  }, [data, t]);
  if (!options || !data) return null;
  return (
    <div className="grid" style={{ marginTop: 18 }}>
      <Panel className="span-4" title="GenAI: adoption up, trust down" caption="Share of developers, composition-weighted, 2023–2025.">
        <EChart option={options.ai} height={190} label="AI adoption versus trust" />
      </Panel>
      <Panel className="span-4" title="The remote-work peak has passed" caption="Professional developers working fully remote (asked in 6 waves).">
        <EChart option={options.remote} height={190} label="Fully remote share by year" />
      </Panel>
      <Panel className="span-4" title="Real pay, fixed country mix" caption="Median pay in constant 2025 USD across 35 countries surveyed every year.">
        <EChart option={options.pay} height={190} label="Fixed-mix median real pay" />
      </Panel>
    </div>
  );
}

export default function Overview() {
  const { data, isError, error } = useOverview();
  const k = data?.kpis;
  return (
    <>
      <PageHeader
        title="The developer technology market, 2017–2025"
        lede={<>Nine annual waves of the Stack Overflow Developer Survey, {k ? int(k.respondents) : "664,042"} responses and
          {" "}{k ? int(k.raw_labels) : "2,842"} raw answer labels, harmonised into one warehouse and read the way an industry
          analyst would: who leads, who is gaining, what skills pay, and how far to trust each number.</>}
      />
      <Hero />

      <div className="stats" style={{ marginTop: 18 }}>
        <div className="stat"><div className="stat__label">Survey responses</div><div className="stat__value">{k ? compactNum(k.respondents) : "–"}</div><div className="stat__note">{k?.waves ?? 9} annual waves, 2017–2025</div></div>
        <div className="stat"><div className="stat__label">Countries and territories</div><div className="stat__value">{k?.countries ?? "–"}</div><div className="stat__note">ISO-resolved into 10 analysis regions</div></div>
        <div className="stat"><div className="stat__label">Technologies tracked</div><div className="stat__value">{k?.technologies ?? "–"}</div><div className="stat__note">{k ? compactNum(k.tech_observations) : "–"} usage observations</div></div>
        <div className="stat"><div className="stat__label">Validated salaries</div><div className="stat__value">{k ? compactNum(k.pay_records) : "–"}</div><div className="stat__note">full-time professionals, in USD, real USD and PPP</div></div>
        <div className="stat"><div className="stat__label">Quality checks</div><div className="stat__value">{k ? `${k.checks_passed}/${k.checks_total}` : "–"}</div><div className="stat__note">passing on the latest build</div></div>
      </div>

      <h2 className="section-title">What the data says</h2>
      {isError ? <ErrorState error={error} /> : !data ? <Loading height={300} /> : (
        <div className="panel" style={{ paddingTop: 4, paddingBottom: 4 }}>
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
        </div>
      )}
      <Minis />
    </>
  );
}
