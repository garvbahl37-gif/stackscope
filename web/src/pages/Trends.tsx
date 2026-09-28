import { useMemo, useState } from "react";
import { divergingBarOption } from "../charts/bars";
import { type LineSeries, lineOption } from "../charts/lines";
import { EChart } from "../components/EChart";
import { TechPicker, useColorSlots } from "../components/TechPicker";
import { type Column, DataTable, DownloadButton, ErrorState, Loading, PageHeader, Panel, Segmented, Select } from "../components/ui";
import { type Backtest, type Trajectory, useForecast, useMeta, useMovers, useSelection, useTrajectories, useTrends } from "../lib/api";
import { fixed, pct, pp, signedPct, significance } from "../lib/format";
import { useTokens } from "../lib/theme";

type Metric = "adoption" | "desire" | "retention" | "attraction";
const METRICS: { value: Metric; label: string; caption: string }[] = [
  { value: "adoption", label: "Adoption", caption: "Share of respondents who used it in the past year, among those shown the question." },
  { value: "desire", label: "Desire", caption: "Share who want to work with it next year." },
  { value: "retention", label: "Retention", caption: "Share of current users who want to keep using it (the inverse of churn)." },
  { value: "attraction", label: "Attraction", caption: "Share of non-users who want to start using it." },
];

const TRAJ_COLUMNS: Column<Trajectory>[] = [
  { key: "tech", label: "Technology" },
  { key: "span", label: "Years", render: (r) => `${r.first_year}–${r.last_year}` },
  { key: "share_first", label: "First", numeric: true, render: (r) => pct(r.share_first), value: (r) => r.share_first },
  { key: "share_last", label: "Latest", numeric: true, render: (r) => pct(r.share_last), value: (r) => r.share_last },
  { key: "change_pp", label: "Change", numeric: true, render: (r) => pp(r.change_pp), value: (r) => r.change_pp },
  { key: "odds_growth", label: "Odds growth / yr", numeric: true, render: (r) => signedPct(r.odds_growth, 1), value: (r) => r.odds_growth },
  { key: "ci", label: "95% interval", numeric: true, render: (r) => r.odds_growth_lo == null ? "–" : `${signedPct(r.odds_growth_lo, 0)} to ${signedPct(r.odds_growth_hi, 0)}` },
  { key: "q_value", label: "FDR", numeric: true, render: (r) => significance(r.q_value), value: (r) => r.q_value },
  { key: "trend", label: "Verdict" },
];

const BT_COLUMNS: Column<Backtest>[] = [
  { key: "model", label: "Model", render: (r) => (r.selected ? `${r.model} (selected)` : r.model) },
  { key: "horizon", label: "Horizon", numeric: true, render: (r) => `${r.horizon} yr` },
  { key: "n", label: "Forecasts", numeric: true },
  { key: "mae_pp", label: "MAE", numeric: true, render: (r) => `${fixed(r.mae_pp, 2)} pp` },
  { key: "rmse_pp", label: "RMSE", numeric: true, render: (r) => `${fixed(r.rmse_pp, 2)} pp` },
  { key: "skill_vs_naive", label: "Skill vs naive", numeric: true, render: (r) => signedPct(r.skill_vs_naive, 1) },
];

export default function Trends() {
  const t = useTokens();
  const meta = useMeta();
  const { selected, slots, add, remove } = useColorSlots(["Python", "TypeScript", "Rust", "Go", "Java", "PHP"]);
  const [metric, setMetric] = useState<Metric>("adoption");
  const [weighted, setWeighted] = useState(true);
  const [showForecast, setShowForecast] = useState(true);
  const [moversCat, setMoversCat] = useState("language");
  const apiMetric = metric === "adoption" && !weighted ? "adoption_raw" : metric;
  const trends = useTrends(selected, apiMetric);
  const fc = useForecast(selected);
  const movers = useMovers(moversCat);
  const traj = useTrajectories();
  const selection = useSelection(moversCat);
  const picks = selection.data?.rows ?? [];
  const pick24 = picks.find((r) => r.survey_year === 2024)?.mean_picks;
  const pick25 = picks.find((r) => r.survey_year === 2025)?.mean_picks;
  const colorOf = (tech: string) => t.series[slots[tech] ?? 0];
  const fmt = (v: number) => pct(v, metric === "adoption" ? 1 : 0);

  const option = useMemo(() => {
    if (!trends.data) return null;
    const withForecast = metric === "adoption" && weighted && showForecast && fc.data;
    const series: LineSeries[] = trends.data.series.map((s) => {
      const points = s.points.filter((p) => p.value != null).map((p) => ({ x: p.year, y: p.value, lo: p.lo, hi: p.hi }));
      const f = withForecast ? fc.data!.series.find((x) => x.tech === s.tech) : undefined;
      const last = points[points.length - 1]?.x;
      if (f && last) {
        f.points.filter((p) => p.kind === "forecast").forEach((p) => points.push({ x: p.survey_year, y: p.share, lo: p.lo80, hi: p.hi80 }));
      }
      return { name: s.tech, color: colorOf(s.tech), points, forecastFrom: f ? last : undefined };
    });
    const notes = new Map(trends.data.notes.map((n) => [n.tech, n.note]));
    return lineOption(series, t, {
      yFormat: (v) => pct(v, 0), valueFormat: fmt, yMin: 0, bands: metric === "adoption", endLabels: series.length <= 6,
      note: (x) => (x > 2025 ? "2026–2027 are projections with an 80% interval learned from backtest errors." :
        [...notes.entries()].length ? `Series notes: ${[...notes.keys()].join(", ")} (see below)` : null),
    });
  }, [trends.data, fc.data, metric, weighted, showForecast, t, slots]); // eslint-disable-line react-hooks/exhaustive-deps

  const moversOption = useMemo(() => {
    if (!movers.data) return null;
    const sig = movers.data.rows.filter((r) => r.significant);
    const rows = [...sig.slice(0, 8), ...sig.slice(-8)].filter((r, i, arr) => arr.indexOf(r) === i).sort((a, b) => b.delta_pp - a.delta_pp);
    return divergingBarOption(rows.map((r) => ({ label: r.tech, value: r.delta_pp, note: `${pct(r.prev_share_used_w)} to ${pct(r.share_used_w)}, ${significance(r.q_value)}` })), t,
      (v) => pp(v, 1));
  }, [movers.data, t]);

  const trajRows = (traj.data?.rows ?? []).filter((r) => selected.includes(r.tech));
  const categories = (meta.data?.categories ?? []).map((c) => ({ value: c.id, label: c.label }));
  const selectedBacktest = fc.data?.backtest.find((b) => b.selected && b.horizon === 1);

  return (
    <>
      <PageHeader
        title="Adoption and forecasts"
        lede="How each technology's share of developers has moved since 2017, with 95% intervals, composition-weighted so a change in who answered the survey is not mistaken for a change in what developers use."
      />
      <div className="controls">
        <Segmented label="Metric" options={METRICS.map((m) => ({ value: m.value, label: m.label }))} value={metric} onChange={setMetric} />
        {metric === "adoption" && (
          <Segmented label="Weighting" options={[{ value: "w", label: "Composition-weighted" }, { value: "raw", label: "Raw sample" }]}
                     value={weighted ? "w" : "raw"} onChange={(v) => setWeighted(v === "w")} />
        )}
        {metric === "adoption" && weighted && (
          <label className="control"><input type="checkbox" checked={showForecast} onChange={(e) => setShowForecast(e.target.checked)} /> Show 2026–2027 projection</label>
        )}
      </div>
      <Panel hero stale={trends.isPlaceholderData}
             title={METRICS.find((m) => m.value === metric)!.label}
             caption={METRICS.find((m) => m.value === metric)!.caption}
             table={trends.data ? {
               columns: [{ key: "tech", label: "Technology" }, { key: "year", label: "Year" },
                         { key: "value", label: "Value", numeric: true, render: (r: { value: number | null }) => fmt(r.value ?? NaN), value: (r: { value: number | null }) => r.value },
                         { key: "lo", label: "Low", numeric: true, render: (r: { lo: number | null }) => (r.lo == null ? "–" : fmt(r.lo)) },
                         { key: "hi", label: "High", numeric: true, render: (r: { hi: number | null }) => (r.hi == null ? "–" : fmt(r.hi)) },
                         { key: "n", label: "Answered", numeric: true }],
               rows: trends.data.series.flatMap((s) => s.points.map((p) => ({ tech: s.tech, ...p }))),
               filename: `trends_${apiMetric}.csv`,
             } : undefined}>
        {meta.data && <TechPicker all={meta.data.technologies} selected={selected} colorOf={colorOf} onAdd={add} onRemove={remove} />}
        <div style={{ marginTop: 14 }}>
          {trends.isError ? <ErrorState error={trends.error} /> : option ? (
            <EChart option={option} height={440} label={`${metric} trends`} />
          ) : <Loading height={440} />}
        </div>
        {trends.data && trends.data.notes.length > 0 && (
          <ul className="notes">
            {trends.data.notes.map((n) => <li key={n.tech}><strong>{n.tech}:</strong> {n.note}</li>)}
          </ul>
        )}
      </Panel>

      <div className="grid" style={{ marginTop: 18 }}>
        <Panel className="span-12" title="Is the trend real?"
               caption="Inverse-variance weighted logistic trend over all waves: the annual growth in the odds of using each technology, with Benjamini-Hochberg false-discovery control across 300+ technologies."
               tools={<DownloadButton columns={TRAJ_COLUMNS} rows={trajRows} filename="trajectories.csv" />}>
          <DataTable columns={TRAJ_COLUMNS} rows={trajRows} rowKey={(r) => r.tech} />
        </Panel>
        <Panel className="span-6" title="Significant movers, 2024 to 2025" stale={movers.isPlaceholderData}
               caption="Change in adoption where the two-proportion test survives FDR correction (q < 0.05)."
               tools={categories.length ? <Select id="mv" label="" options={categories} value={moversCat} onChange={setMoversCat} /> : undefined}
               foot={pick24 && pick25 && pick25 / pick24 > 1.05 ? `Read with care: 2025 respondents ticked ${fixed(pick25, 1)} options in this category on average versus ${fixed(pick24, 1)} in 2024 (+${fixed((pick25 / pick24 - 1) * 100, 0)}%), a questionnaire effect that lifts many shares at once. Share of mentions on the Market landscape page is robust to it.` : undefined}>
          {moversOption ? <EChart option={moversOption} height={440} label="Significant movers" /> : <Loading height={440} />}
        </Panel>
        <Panel className="span-6" title="How good are the forecasts?"
               caption={selectedBacktest ? `Five models were backtested from rolling origins 2020–2024. None beat the naive forecast (next year looks like this year): its one-year error is ${fixed(selectedBacktest.mae_pp, 1)} percentage points on average, so projections are shown as calibrated ranges rather than extrapolated trends.` : undefined}
               table={fc.data ? { columns: BT_COLUMNS, rows: fc.data.backtest, filename: "forecast_backtest.csv" } : undefined}>
          {fc.data ? <DataTable columns={BT_COLUMNS} rows={fc.data.backtest} rowKey={(r) => `${r.model}${r.horizon}`} maxHeight={340} /> : <Loading height={200} />}
          {fc.data && (
            <p className="panel__foot">
              The leading-indicator model regresses next year's change on today's desire gap, retention, attraction and recent momentum
              (robust Huber fit): {fc.data.indicator.map((i) => `${i.feature} ${fixed(i.coefficient, 3)}`).join(", ")}. Retention and momentum carry signal,
              but not enough to beat the naive baseline out of sample.
            </p>
          )}
        </Panel>
      </div>
    </>
  );
}
