import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { axisStyle, base, tooltip, ttEnd, ttRow, ttTitle } from "../charts/base";
import { lineOption } from "../charts/lines";
import { quadrantOption } from "../charts/quadrant";
import { EChart } from "../components/EChart";
import { type Column, DataTable, DownloadButton, ErrorState, Legend, Loading, PageHeader, Panel, Select, YearScrubber } from "../components/ui";
import { type QuadrantPoint, useConcentration, useMeta, useQuadrant, useTechProfile } from "../lib/api";
import { fixed, int, pct, signedPct, significance } from "../lib/format";
import { type Tokens, useTokens } from "../lib/theme";

function Profile({ tech }: { tech: string | null }) {
  const t = useTokens();
  const { data, isLoading } = useTechProfile(tech);
  const spark = useMemo(() => {
    if (!data) return null;
    return lineOption([{
      name: "Adoption", color: t.series[0],
      points: data.series.map((s) => ({ x: s.survey_year, y: s.share_used_w, lo: s.share_used_w_lo, hi: s.share_used_w_hi })),
    }], t, { yFormat: (v) => pct(v, 0), yMin: 0, bands: true, compact: true });
  }, [data, t]);

  if (!tech) return <Panel title="Select a technology" caption="Click any dot in the quadrant to see its full profile."><p className="small muted">The profile shows adoption with 95% intervals, retention, where its leavers go and what it is paired with.</p></Panel>;
  if (isLoading || !data) return <Panel title={tech}><Loading height={420} /></Panel>;
  const last = data.series[data.series.length - 1];
  const global = data.premium.find((p) => p.scope === "Global");
  return (
    <Panel title={data.info.tech} caption={`${data.info.category_label}, surveyed ${data.info.first_year}–${data.info.last_year}`}>
      {spark && <EChart option={spark} height={130} label={`${tech} adoption over time`} />}
      <dl className="kv" style={{ marginTop: 10 }}>
        <dt>Adoption {last.survey_year}</dt><dd>{pct(last.share_used_w)} <span className="muted">({pct(last.share_used_w_lo)}–{pct(last.share_used_w_hi)})</span></dd>
        <dt>Retention</dt><dd>{pct(last.retention_w, 0)}</dd>
        <dt>Attraction</dt><dd>{pct(last.attraction_w, 0)}</dd>
        <dt>Rank in category</dt><dd>#{last.rank_in_category}</dd>
        {data.trend?.odds_growth != null && <>
          <dt>Odds of use, per year</dt>
          <dd>{signedPct(data.trend.odds_growth, 0)} <span className="muted">({data.trend.trend.toLowerCase()}, {significance(data.trend.q_value)})</span></dd>
        </>}
        {global && <><dt>Pay premium (global)</dt><dd>{signedPct(global.premium)} <span className="muted">{global.significant ? "significant" : "not significant"}</span></dd></>}
      </dl>
      {data.info.note && <p className="callout small" style={{ marginTop: 12 }}>{data.info.note}</p>}
      {data.leaving_to.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <h3 className="panel__title" style={{ fontSize: 13.5 }}>Where its leavers want to go</h3>
          <p className="small muted">{data.leaving_to.slice(0, 4).map((d) => `${d.to_tech} ${pct(d.share_of_churners, 0)}`).join(", ")}</p>
        </div>
      )}
      {data.paired_with.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <h3 className="panel__title" style={{ fontSize: 13.5 }}>Most often paired with</h3>
          <p className="small muted">{data.paired_with.slice(0, 6).map((d) => `${d.tech} (${pct(d.confidence, 0)})`).join(", ")}</p>
        </div>
      )}
    </Panel>
  );
}

function mindshareOption(shares: { survey_year: number; tech: string; mindshare: number }[], t: Tokens): { option: EChartsOption; legend: { label: string; color: string }[] } {
  const years = [...new Set(shares.map((s) => s.survey_year))].sort();
  const techs = [...new Set(shares.map((s) => s.tech))].filter((x) => x !== "Others");
  const order = [...techs, ...(shares.some((s) => s.tech === "Others") ? ["Others"] : [])];
  const color = (tech: string, i: number) => (tech === "Others" ? t.deemph : t.series[i % 8]);
  const ax = axisStyle(t);
  const series = order.map((tech, i) => ({
    id: tech, name: tech, type: "bar" as const, stack: "m", barWidth: 22,
    data: years.map((y) => shares.find((s) => s.survey_year === y && s.tech === tech)?.mindshare ?? 0),
    itemStyle: { color: color(tech, i), borderColor: t.surface, borderWidth: 1 },
    emphasis: { focus: "series" as const },
  }));
  return {
    legend: order.map((tech, i) => ({ label: tech, color: color(tech, i) })),
    option: {
      ...base(t),
      grid: { left: 8, right: 12, top: 8, bottom: 24, containLabel: true },
      tooltip: tooltip(t, {
        trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: "rgba(15,42,51,0.04)" } },
        formatter: (params: { dataIndex: number }[]) => {
          const i = params[0].dataIndex;
          return ttTitle(String(years[i])) + order.map((tech, k) => ttRow(color(tech, k), tech, pct(series[k].data[i], 1), "rect")).reverse().join("") + ttEnd;
        },
      }),
      xAxis: { type: "category", data: years.map(String), ...ax, splitLine: { show: false } },
      yAxis: { type: "value", max: 1, ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, 0) } },
      series,
    } as EChartsOption,
  };
}

const COLUMNS: Column<QuadrantPoint>[] = [
  { key: "tech", label: "Technology" },
  { key: "quadrant", label: "Position" },
  { key: "adoption", label: "Adoption", numeric: true, render: (r) => pct(r.adoption), value: (r) => r.adoption },
  { key: "ci", label: "95% interval", numeric: true, render: (r) => `${pct(r.adoption_lo)}–${pct(r.adoption_hi)}`, value: (r) => `${r.adoption_lo}-${r.adoption_hi}` },
  { key: "momentum", label: "Momentum (σ)", numeric: true, render: (r) => fixed(r.momentum), value: (r) => r.momentum },
  { key: "retention", label: "Retention", numeric: true, render: (r) => pct(r.retention, 0), value: (r) => r.retention },
  { key: "attraction", label: "Attraction", numeric: true, render: (r) => pct(r.attraction, 0), value: (r) => r.attraction },
  { key: "base_n", label: "Answered", numeric: true, render: (r) => int(r.base_n) },
];

export default function Landscape() {
  const t = useTokens();
  const meta = useMeta();
  const [category, setCategory] = useState("language");
  const quad = useQuadrant(category);
  const conc = useConcentration(category);
  const years = quad.data?.years ?? [];
  const [year, setYear] = useState(2025);
  const shownYear = years.includes(year) ? year : years[years.length - 1] ?? year;
  const [selected, setSelected] = useState<string | null>("Python");

  const option = useMemo(
    () => (quad.data ? quadrantOption(quad.data.points, shownYear, t, { selected }) : null),
    [quad.data, shownYear, t, selected],
  );
  const events = useMemo(() => ({ click: (p: { seriesId?: string; name?: string }) => p.seriesId === "techs" && p.name && setSelected(p.name) }), []);
  const rows = useMemo(() => (quad.data?.points ?? []).filter((p) => p.survey_year === shownYear).sort((a, b) => b.adoption - a.adoption), [quad.data, shownYear]);
  const hhi = useMemo(() => conc.data ? lineOption([{
    name: "HHI", color: t.series[0], points: conc.data.hhi.map((h) => ({ x: h.survey_year, y: h.hhi })),
  }], t, { yFormat: (v) => int(v), yMin: 0, compact: false }) : null, [conc.data, t]);
  const mind = useMemo(() => (conc.data ? mindshareOption(conc.data.shares, t) : null), [conc.data, t]);
  const categories = (meta.data?.categories ?? []).map((c) => ({ value: c.id, label: c.label }));
  const lastHhi = conc.data?.hhi[conc.data.hhi.length - 1];

  return (
    <>
      <PageHeader
        title="Market landscape"
        lede="A data-driven position for every technology: adoption on one axis, momentum on the other. Momentum blends how many users stay, how many non-users want in, and how fast adoption is changing, each scored against the rest of its category."
      />
      <div className="controls">
        {categories.length > 0 && <Select id="cat" label="Category" options={categories} value={category} onChange={(c) => { setCategory(c); setSelected(null); }} />}
        {years.length > 0 && <YearScrubber years={years} value={shownYear} onChange={setYear} />}
      </div>
      <div className="grid">
        <Panel className="span-8" stale={quad.isPlaceholderData}
               title={`Positions in ${shownYear}`}
               caption="Adoption uses a log scale so niche and mainstream technologies are both readable. The horizontal guide is the category median; the vertical guide is average momentum."
               table={{ columns: COLUMNS, rows, filename: `quadrant_${category}_${shownYear}.csv` }}>
          {quad.isError ? <ErrorState error={quad.error} /> : option ? (
            <EChart option={option} height={560} events={events} label={`Market position quadrant, ${category}, ${shownYear}`} />
          ) : <Loading height={560} />}
        </Panel>
        <div className="span-4"><Profile tech={selected} /></div>

        <Panel className="span-12" title="All positions" caption="Click a row to trace that technology's path through the years."
               tools={<DownloadButton columns={COLUMNS} rows={rows} filename={`positions_${category}_${shownYear}.csv`} />}>
          <DataTable columns={COLUMNS} rows={rows} rowKey={(r) => r.tech} selectedKey={selected} onRowClick={(r) => setSelected(r.tech)} maxHeight={360} />
        </Panel>

        <Panel className="span-5" title="Is the market concentrating?"
               caption={lastHhi ? `Herfindahl-Hirschman Index of mindshare. ${lastHhi.survey_year}: ${int(lastHhi.hhi)}, ${lastHhi.structure.toLowerCase()}, equivalent to ${fixed(lastHhi.effective_competitors, 1)} equal-sized competitors.` : undefined}
               table={conc.data ? { columns: [
                 { key: "survey_year", label: "Year" }, { key: "hhi", label: "HHI", numeric: true, render: (r) => int(r.hhi) },
                 { key: "cr3", label: "Top-3 share", numeric: true, render: (r) => pct(r.cr3) }, { key: "leader", label: "Leader" },
                 { key: "leader_share", label: "Leader share", numeric: true, render: (r) => pct(r.leader_share) }, { key: "structure", label: "Structure" },
               ] as Column<NonNullable<typeof conc.data>["hhi"][number]>[], rows: conc.data.hhi, filename: `concentration_${category}.csv` } : undefined}
               foot="Below 1,500 is competitive, 1,500–2,500 moderately concentrated, above 2,500 highly concentrated (US DoJ guidelines). Mindshare is share of usage mentions, not revenue.">
          {hhi ? <EChart option={hhi} height={240} label="HHI over time" /> : <Loading height={240} />}
        </Panel>
        <Panel className="span-7" title="Share of mindshare" caption="Each technology's share of all usage mentions in the category; the seven largest are named.">
          {mind ? <><Legend items={mind.legend} shape="swatch" /><EChart option={mind.option} height={250} label="Mindshare by year" /></> : <Loading height={260} />}
        </Panel>
      </div>
    </>
  );
}
