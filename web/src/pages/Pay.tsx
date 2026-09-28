import { useEffect, useMemo, useState } from "react";
import { forestOption, rangeDotOption, stackedShareOption } from "../charts/bars";
import { lineOption } from "../charts/lines";
import { choroplethOption, ensureWorldMap } from "../charts/map";
import { EChart } from "../components/EChart";
import { type Column, DataTable, ErrorState, Legend, Loading, PageHeader, Panel, Segmented, Select } from "../components/ui";
import { type Benchmark, type CountryYear, type Premium, useBenchmarks, usePayMap, usePremium, useWorkforce } from "../lib/api";
import { int, money, pct, signedPct, significance } from "../lib/format";
import { useTokens } from "../lib/theme";

const CUTS = [
  { value: "role", label: "Role" }, { value: "experience", label: "Experience" }, { value: "org_size", label: "Company size" },
  { value: "remote", label: "Work arrangement" }, { value: "education", label: "Education" }, { value: "region", label: "Region" },
];
const EXP_ORDER = ["0-2", "3-5", "6-10", "11-20", "21+"];
const ORG_ORDER = ["<20", "20-99", "100-499", "500-999", "1,000-4,999", "5,000-9,999", "10,000+"];
const YEARS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017].map((y) => ({ value: y, label: String(y) }));
const PREMIUM_CATS = [
  { value: "all", label: "All" }, { value: "language", label: "Languages" }, { value: "database", label: "Databases" },
  { value: "cloud", label: "Cloud" }, { value: "webframe", label: "Frameworks" }, { value: "devops", label: "DevOps" },
];

const PREMIUM_COLUMNS: Column<Premium>[] = [
  { key: "tech", label: "Technology" },
  { key: "category", label: "Category" },
  { key: "premium", label: "Adjusted premium", numeric: true, render: (r) => signedPct(r.premium), value: (r) => r.premium },
  { key: "ci", label: "95% interval", numeric: true, render: (r) => `${signedPct(r.premium_lo)} to ${signedPct(r.premium_hi)}` },
  { key: "raw_premium", label: "Raw gap", numeric: true, render: (r) => signedPct(r.raw_premium, 0), value: (r) => r.raw_premium },
  { key: "q_value", label: "FDR", numeric: true, render: (r) => significance(r.q_value), value: (r) => r.q_value },
  { key: "n_users", label: "Users in sample", numeric: true, render: (r) => int(r.n_users) },
];

export default function Pay() {
  const t = useTokens();
  const [year, setYear] = useState(2025);
  const [basis, setBasis] = useState<"usd" | "ppp">("usd");
  const [cut, setCut] = useState("role");
  const [scope, setScope] = useState("Global");
  const [premiumCat, setPremiumCat] = useState("all");
  const [onlySig, setOnlySig] = useState(true);
  const bench = useBenchmarks(cut, year);
  const payMap = usePayMap(year);
  const premium = usePremium(scope);
  const workforce = useWorkforce();
  const [mapReady, setMapReady] = useState(false);
  useEffect(() => { ensureWorldMap().then(() => setMapReady(true)); }, []);

  const fmtMoney = (v: number) => money(v);
  const rangeOption = useMemo(() => {
    if (!bench.data) return null;
    let rows = bench.data.rows.filter((r) => r.segment !== "Unknown");
    const val = (r: Benchmark) => (basis === "usd"
      ? { lo: r.p25_usd, mid: r.median_usd, hi: r.p75_usd } : { lo: r.p25_ppp ?? NaN, mid: r.median_ppp ?? NaN, hi: r.p75_ppp ?? NaN });
    if (cut === "experience") rows = [...rows].sort((a, b) => EXP_ORDER.indexOf(a.segment) - EXP_ORDER.indexOf(b.segment));
    else if (cut === "org_size") rows = [...rows].sort((a, b) => ORG_ORDER.indexOf(a.segment) - ORG_ORDER.indexOf(b.segment));
    else rows = [...rows].sort((a, b) => val(b).mid - val(a).mid);
    const overall = bench.data.overall;
    return rangeDotOption(rows.map((r) => ({ label: r.label ?? r.segment, n: r.n, ...val(r) })).filter((r) => Number.isFinite(r.mid)), t, fmtMoney,
      overall ? { reference: { value: basis === "usd" ? overall.median_usd : overall.median_ppp, label: "All developers" } } : {});
  }, [bench.data, basis, cut, t]); // eslint-disable-line react-hooks/exhaustive-deps

  const mapOption = useMemo(() => {
    if (!payMap.data || !mapReady) return null;
    return choroplethOption(payMap.data.rows.filter((r) => r.pay_n >= 30).map((r) => ({
      iso_numeric: r.iso_numeric, country: r.country, n: r.pay_n,
      value: basis === "usd" ? r.median_pay_usd : r.median_pay_ppp,
      extra: r.top_language ? `most used language ${r.top_language}` : undefined,
    })), t, fmtMoney, basis === "usd" ? "Median pay (USD)" : "Median pay (PPP $)");
  }, [payMap.data, mapReady, basis, t]); // eslint-disable-line react-hooks/exhaustive-deps

  const premiumRows = useMemo(() => {
    const rows = (premium.data?.rows ?? []).filter((r) => (premiumCat === "all" || r.category === premiumCat) && (!onlySig || r.significant));
    return [...rows].sort((a, b) => b.premium - a.premium);
  }, [premium.data, premiumCat, onlySig]);
  const forest = useMemo(() => {
    if (!premiumRows.length) return null;
    const shown = premiumRows.length > 30 ? [...premiumRows.slice(0, 15), ...premiumRows.slice(-15)] : premiumRows;
    return forestOption(shown.map((r) => ({ label: r.tech, est: r.premium, lo: r.premium_lo, hi: r.premium_hi, compare: r.raw_premium, strong: r.significant, group: `${r.category}, ${int(r.n_users)} users, ${significance(r.q_value)}` })),
      t, { fmt: (v) => signedPct(v, 0), reference: 0, estLabel: "Adjusted premium", compareLabel: "Raw gap (no controls)" });
  }, [premiumRows, t]);

  const payTrend = useMemo(() => workforce.data ? lineOption([
    { name: "Fixed mix", color: t.series[0], points: workforce.data.real_pay.map((r) => ({ x: r.survey_year, y: r.fixed_mix_median_real })) },
    { name: "Raw median", color: t.series[1], points: workforce.data.real_pay.map((r) => ({ x: r.survey_year, y: r.raw_median_real })) },
  ], t, { yFormat: (v) => money(v), yMin: 50000, endLabels: true, height: 300 }) : null, [workforce.data, t]);

  const remoteMix = useMemo(() => {
    if (!workforce.data) return null;
    const years = [...new Set(workforce.data.remote.map((r) => r.survey_year))].sort();
    const seg = (cat: string) => years.map((y) => workforce.data!.remote.find((r) => r.survey_year === y && r.category === cat)?.share_w ?? null);
    // ordered scale (in-person -> hybrid -> remote): one-hue ordinal steps
    return stackedShareOption(years.map(String), [
      { name: "In-person", color: t.seq[1], values: seg("In-person") },
      { name: "Hybrid", color: t.seq[3], values: seg("Hybrid") },
      { name: "Remote", color: t.seq[5], values: seg("Remote") },
    ], t, { fmt: (v) => pct(v, 0) });
  }, [workforce.data, t]);

  const model = premium.data?.model;
  return (
    <>
      <PageHeader
        title="Pay and skills"
        lede="What developers earn and which skills move the number. Salaries are cleaned per market, deflated to 2025 dollars and, optionally, converted at purchasing-power parity so a salary in Bengaluru and one in Berlin can be compared on what they buy."
      />
      <div className="controls">
        <Select id="yr" label="Survey year" options={YEARS} value={year} onChange={setYear} />
        <Segmented label="Currency basis" options={[{ value: "usd", label: "US dollars" }, { value: "ppp", label: "Purchasing power (PPP)" }]} value={basis} onChange={setBasis} />
      </div>
      <div className="grid">
        <Panel className="span-12" stale={bench.isPlaceholderData}
               title={`Pay by ${CUTS.find((c) => c.value === cut)!.label.toLowerCase()}, ${year}`}
               caption="Full-time professional developers. The bar spans the middle 50% of salaries; the dot is the median."
               tools={<Select id="cut" label="" options={CUTS} value={cut} onChange={setCut} />}
               table={bench.data ? { columns: [
                 { key: "segment", label: "Segment", render: (r: Benchmark) => r.label ?? r.segment },
                 { key: "n", label: "Salaries", numeric: true, render: (r: Benchmark) => int(r.n) },
                 { key: "p25_usd", label: "P25 (USD)", numeric: true, render: (r: Benchmark) => money(r.p25_usd) },
                 { key: "median_usd", label: "Median (USD)", numeric: true, render: (r: Benchmark) => money(r.median_usd) },
                 { key: "p75_usd", label: "P75 (USD)", numeric: true, render: (r: Benchmark) => money(r.p75_usd) },
                 { key: "median_ppp", label: "Median (PPP)", numeric: true, render: (r: Benchmark) => money(r.median_ppp) },
               ], rows: bench.data.rows, filename: `pay_${cut}_${year}.csv` } : undefined}>
          {bench.isError ? <ErrorState error={bench.error} /> : rangeOption ? <EChart option={rangeOption} height={Math.max(320, (bench.data?.rows.length ?? 8) * 34 + 60)} label="Pay ranges" /> : <Loading height={360} />}
        </Panel>
        <Panel className="span-7" stale={payMap.isPlaceholderData} title={`Median pay by country, ${year}`}
               caption={basis === "usd" ? "Countries with at least 30 validated salaries. Switch to PPP to compare living standards." : "PPP dollars: what the salary buys locally, relative to the US."}
               table={payMap.data ? { columns: [
                 { key: "country", label: "Country" }, { key: "pay_n", label: "Salaries", numeric: true },
                 { key: "median_pay_usd", label: "Median USD", numeric: true, render: (r: { median_pay_usd: number | null }) => money(r.median_pay_usd) },
                 { key: "median_pay_ppp", label: "Median PPP", numeric: true, render: (r: { median_pay_ppp: number | null }) => money(r.median_pay_ppp) },
               ], rows: payMap.data.rows.filter((r) => r.pay_n >= 30), filename: `pay_by_country_${year}.csv` } : undefined}>
          {mapOption ? <EChart option={mapOption} height={340} renderer="canvas" label="World map of median pay" /> : <Loading height={340} />}
          {payMap.data && (
            <>
              <h3 className="panel__title" style={{ fontSize: 13.5, margin: "10px 0 6px" }}>Highest-paying markets</h3>
              <DataTable
                columns={[
                  { key: "country", label: "Country" },
                  { key: "pay", label: basis === "usd" ? "Median (USD)" : "Median (PPP)", numeric: true,
                    render: (r: CountryYear) => money(basis === "usd" ? r.median_pay_usd : r.median_pay_ppp) },
                  { key: "pay_n", label: "Salaries", numeric: true, render: (r: CountryYear) => int(r.pay_n) },
                ]}
                rows={[...payMap.data.rows].filter((r) => r.pay_n >= 100 && (basis === "usd" ? r.median_pay_usd : r.median_pay_ppp) != null)
                  .sort((a, b) => ((basis === "usd" ? b.median_pay_usd : b.median_pay_ppp) ?? 0) - ((basis === "usd" ? a.median_pay_usd : a.median_pay_ppp) ?? 0))
                  .slice(0, 10)}
                rowKey={(r) => r.iso3} maxHeight={330}
              />
              <p className="panel__foot">Markets with at least 100 validated salaries.</p>
            </>
          )}
        </Panel>

        <div className="span-5 stack">
          <Panel title="Real pay, two ways"
                 caption="Median pay in constant 2025 dollars. The raw median moves with who answered; holding the mix of 35 always-surveyed countries fixed shows the underlying trend."
                 table={workforce.data ? { columns: [
                   { key: "survey_year", label: "Year" },
                   { key: "fixed_mix_median_real", label: "Fixed mix", numeric: true, render: (r: { fixed_mix_median_real: number }) => money(r.fixed_mix_median_real) },
                   { key: "raw_median_real", label: "Raw", numeric: true, render: (r: { raw_median_real: number }) => money(r.raw_median_real) },
                 ], rows: workforce.data.real_pay, filename: "real_pay.csv" } : undefined}>
            {payTrend ? <EChart option={payTrend} height={300} label="Real pay trend" /> : <Loading height={300} />}
          </Panel>
          <Panel title="How developers work"
                 caption="Professional developers by work arrangement, composition-weighted. Not asked in 2018, 2020 or 2021.">
            <Legend items={[{ label: "In-person", color: t.seq[1] }, { label: "Hybrid", color: t.seq[3] }, { label: "Remote", color: t.seq[5] }]} shape="swatch" />
            {remoteMix ? <EChart option={remoteMix} height={280} label="Work arrangement mix by year" /> : <Loading height={280} />}
          </Panel>
        </div>

        <Panel className="span-12" stale={premium.isPlaceholderData}
               title="What is a skill worth?"
               caption={model ? `Pay premium associated with using each technology, holding country, experience, role, company size, education, industry, work arrangement and year constant. OLS on log real pay, ${int(model.n)} developers, 2023–2025, R² ${model.r2.toFixed(2)}, robust standard errors, false-discovery-rate controlled. Hollow markers show the raw gap before controls.` : undefined}
               table={{ columns: PREMIUM_COLUMNS, rows: premiumRows, filename: `skill_premium_${scope}.csv` }}
               foot="These are associations, not causal effects: a skill can stand in for seniority or sector that the controls miss.">
          <div className="controls" style={{ marginBottom: 8 }}>
            <Segmented label="Market" options={(premium.data?.scopes ?? ["Global", "United States", "India", "Western Europe"]).map((s) => ({ value: s, label: s }))} value={scope} onChange={setScope} />
            <Select id="pcat" label="Category" options={PREMIUM_CATS} value={premiumCat} onChange={setPremiumCat} />
            <label className="control"><input type="checkbox" checked={onlySig} onChange={(e) => setOnlySig(e.target.checked)} /> Significant only</label>
          </div>
          {forest ? <EChart option={forest} height={Math.max(300, Math.min(30, premiumRows.length) * 26 + 60)} label="Skill premium forest plot" />
            : premium.data ? <p className="state">No technologies match these filters.</p> : <Loading height={400} />}
        </Panel>

      </div>
    </>
  );
}
