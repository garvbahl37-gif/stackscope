import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { forestOption, stackedShareOption } from "../charts/bars";
import { axisStyle, base, tooltip, ttEnd, ttRow, ttTitle } from "../charts/base";
import { lineOption } from "../charts/lines";
import { EChart } from "../components/EChart";
import { ErrorState, Legend, Loading, PageHeader, Panel, Segmented } from "../components/ui";
import { type AiPulse, useAi } from "../lib/api";
import { fixed, pct, significance } from "../lib/format";
import { type Tokens, useTokens } from "../lib/theme";

const TRUST = ["Highly distrust", "Somewhat distrust", "Neither trust nor distrust", "Somewhat trust", "Highly trust"];
const SENTIMENT = ["Very unfavorable", "Unfavorable", "Indifferent", "Favorable", "Very favorable"];
const DIMENSIONS = [
  { value: "experience", label: "Experience" }, { value: "role", label: "Role" }, { value: "age", label: "Age" },
  { value: "org_size", label: "Company size" }, { value: "region", label: "Region" },
];
const EXP_ORDER = ["0-2", "3-5", "6-10", "11-20", "21+"];
const AGE_ORDER = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"];
const ORG_ORDER = ["<20", "20-99", "100-499", "500-999", "1,000-4,999", "5,000-9,999", "10,000+"];

function divergingColors(t: Tokens) {
  return [t.div.neg2, t.div.neg1, t.div.mid, t.div.pos1, t.div.pos2];
}

/** Dumbbell: two measures per segment on one percentage axis, joined by a hairline. */
function dumbbellOption(rows: { label: string; a: number; b: number }[], t: Tokens, names: [string, string]): EChartsOption {
  const ax = axisStyle(t);
  return {
    ...base(t),
    grid: { left: 8, right: 24, top: 8, bottom: 24, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: "rgba(15,42,51,0.04)" } },
      formatter: (params: { dataIndex: number }[]) => {
        const r = rows[params[0].dataIndex];
        return ttTitle(r.label) + ttRow(t.series[0], names[0], pct(r.a, 0), "dot") + ttRow(t.series[1], names[1], pct(r.b, 0), "dot") +
          ttRow(null, "Gap", `${fixed((r.a - r.b) * 100, 0)} pp`) + ttEnd;
      },
    }),
    xAxis: { type: "value", min: 0, max: 1, ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, 0) } },
    yAxis: { type: "category", data: rows.map((r) => r.label), inverse: true, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
    series: [
      {
        id: "gap", type: "custom", silent: true, data: rows.map((_, i) => [i]), encode: { y: 0 },
        renderItem: (_: unknown, api: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
          const i = api.value(0);
          const p1 = api.coord([rows[i].a, i]);
          const p2 = api.coord([rows[i].b, i]);
          return { type: "line", shape: { x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1] }, style: { stroke: t.axis, lineWidth: 2 } };
        },
      },
      { id: "a", name: names[0], type: "scatter", data: rows.map((r) => r.a), symbolSize: 11, itemStyle: { color: t.series[0], borderColor: t.surface, borderWidth: 2 }, z: 3 },
      { id: "b", name: names[1], type: "scatter", data: rows.map((r) => r.b), symbolSize: 11, itemStyle: { color: t.series[1], borderColor: t.surface, borderWidth: 2 }, z: 3 },
    ],
  } as EChartsOption;
}

function likertSegments(data: AiPulse, question: string, order: string[], colors: string[]) {
  const years = [...new Set(data.likert.filter((l) => l.question === question).map((l) => l.survey_year))].sort();
  return {
    years,
    segments: order.map((answer, i) => ({
      name: answer, color: colors[i],
      values: years.map((y) => {
        const rows = data.likert.filter((l) => l.question === question && l.survey_year === y && order.includes(l.answer));
        const total = rows.reduce((s, r) => s + r.share_w, 0);
        const hit = rows.find((r) => r.answer === answer);
        return hit && total ? hit.share_w / total : 0;
      }),
    })),
  };
}

export default function Ai() {
  const t = useTokens();
  const { data, isError, error } = useAi();
  const [dimension, setDimension] = useState("experience");
  const [model, setModel] = useState<"adoption" | "trust">("trust");

  const charts = useMemo(() => {
    if (!data) return null;
    const paradox = lineOption([
      { name: "Use AI tools", color: t.series[0], points: data.years.map((y) => ({ x: y.survey_year, y: y.using_w })) },
      { name: "Favourable", color: t.series[1], points: data.years.map((y) => ({ x: y.survey_year, y: y.favorable_w })) },
      { name: "Trust accuracy", color: t.series[2], points: data.years.map((y) => ({ x: y.survey_year, y: y.trust_w })) },
      { name: "Distrust accuracy", color: t.series[3], points: data.years.map((y) => ({ x: y.survey_year, y: y.distrust_w })) },
    ], t, { yFormat: (v) => pct(v, 0), yMin: 0, yMax: 1, yInterval: 0.25, endLabels: true });

    const trust = likertSegments(data, "ai_trust", TRUST, divergingColors(t));
    const sentiment = likertSegments(data, "ai_sentiment", SENTIMENT, divergingColors(t));
    const trustChart = stackedShareOption(trust.years.map(String), trust.segments, t, { horizontal: true, fmt: (v) => pct(v, 0), labelMin: 0.07 });
    const sentimentChart = stackedShareOption(sentiment.years.map(String), sentiment.segments, t, { horizontal: true, fmt: (v) => pct(v, 0), labelMin: 0.07 });

    const tasks = [...new Set(data.tasks.map((r) => r.task))];
    const latest = Math.max(...data.tasks.map((r) => r.survey_year));
    const taskOrder = tasks.sort((a, b) => (data.tasks.find((r) => r.task === b && r.survey_year === latest)?.share_w ?? 0) -
                                          (data.tasks.find((r) => r.task === a && r.survey_year === latest)?.share_w ?? 0));
    const years = [...new Set(data.tasks.map((r) => r.survey_year))].sort();
    const ramp = [t.seq[2], t.seq[4], t.seq[6]];
    const ax = axisStyle(t);
    const tasksChart: EChartsOption = {
      ...base(t),
      grid: { left: 8, right: 36, top: 8, bottom: 24, containLabel: true },
      tooltip: tooltip(t, { trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: "rgba(15,42,51,0.04)" } },
        formatter: (params: { dataIndex: number }[]) => {
          const task = taskOrder[params[0].dataIndex];
          return ttTitle(task) + years.map((y, i) => {
            const v = data.tasks.find((r) => r.task === task && r.survey_year === y)?.share_w;
            return v == null ? ttRow(ramp[i], String(y), "not asked", "rect") : ttRow(ramp[i], String(y), pct(v, 0), "rect");
          }).join("") + ttEnd;
        } }),
      xAxis: { type: "value", ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => pct(v, 0) } },
      yAxis: { type: "category", data: taskOrder, inverse: true, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
      series: years.map((y, i) => ({
        id: String(y), name: String(y), type: "bar", barWidth: 7, barGap: "35%",
        data: taskOrder.map((task) => data.tasks.find((r) => r.task === task && r.survey_year === y)?.share_w ?? null),
        itemStyle: { color: ramp[i], borderRadius: [0, 3, 3, 0] },
      })),
    } as EChartsOption;

    const tools = [...new Set(data.tools.filter((r) => r.survey_year === 2025).sort((a, b) => b.share_used_w - a.share_used_w).slice(0, 5).map((r) => r.tech))];
    const toolsChart = lineOption(tools.map((tech, i) => ({
      name: tech, color: t.series[i],
      points: data.tools.filter((r) => r.tech === tech).map((r) => ({ x: r.survey_year, y: r.share_used_w })),
    })), t, { yFormat: (v) => pct(v, 0), yMin: 0, yMax: 1, yInterval: 0.25, endLabels: true });

    return { paradox, trustChart, sentimentChart, tasksChart, toolsChart, trust, years };
  }, [data, t]);

  const dumbbell = useMemo(() => {
    if (!data) return null;
    let rows = data.segments.filter((s) => s.survey_year === 2025 && s.dimension === dimension && s.segment !== "Unknown");
    const order = dimension === "experience" ? EXP_ORDER : dimension === "age" ? AGE_ORDER : dimension === "org_size" ? ORG_ORDER : null;
    rows = order ? rows.sort((a, b) => order.indexOf(a.segment) - order.indexOf(b.segment)) : rows.sort((a, b) => b.using_w - a.using_w);
    return dumbbellOption(rows.map((r) => ({ label: r.segment, a: r.using_w, b: r.trust_w })), t, ["Use AI tools", "Trust the output"]);
  }, [data, t, dimension]);

  const drivers = useMemo(() => {
    if (!data) return null;
    const name = model === "adoption" ? "Uses AI tools" : "Trusts AI accuracy (users)";
    const rows = data.drivers.filter((d) => d.model === name && d.level !== "Unknown");
    const varLabel: Record<string, string> = { exp_band: "Experience", age_band: "Age", dev_role: "Role", region: "Region", org_size: "Company size" };
    const ordered = ["exp_band", "age_band", "dev_role", "org_size", "region"].flatMap((v) =>
      rows.filter((r) => r.variable === v).sort((a, b) => b.odds_ratio - a.odds_ratio));
    return {
      option: forestOption(ordered.map((r) => ({
        label: `${varLabel[r.variable]}: ${r.level}`, est: r.odds_ratio, lo: r.or_lo, hi: r.or_hi, strong: r.q_value < 0.05,
        group: `vs ${r.reference}; ${significance(r.q_value)}; n = ${r.n_level.toLocaleString()}`,
      })), t, { fmt: (v) => `${fixed(v, 2)}×`, reference: 1, log: true, estLabel: "Odds ratio" }),
      n: ordered.length, base: rows[0]?.baseline_rate, nModel: rows[0]?.n_model,
    };
  }, [data, t, model]);

  if (isError) return <><PageHeader title="AI adoption and trust" /><ErrorState error={error} /></>;
  const y25 = data?.years.find((y) => y.survey_year === 2025);
  const daily = data?.likert.filter((l) => l.question === "ai_frequency" && l.survey_year === 2025);
  const dailyShare = daily?.length ? (daily.find((d) => d.answer === "Daily")?.share_w ?? 0) : null;
  const agents = data?.segments.find((s) => s.survey_year === 2025 && s.dimension === "all");

  return (
    <>
      <PageHeader
        title="AI adoption and trust"
        lede="Three survey waves (2023–2025) on generative AI in software development. Adoption rose quickly while confidence in the output fell, and experienced developers distrust it most."
      />
      {!data || !charts ? <Loading height={600} /> : (
        <>
          <div className="stats">
            <div className="stat"><div className="stat__label">Use AI tools, 2025</div><div className="stat__value">{pct(y25?.using_w, 0)}</div><div className="stat__note">from {pct(data.years[0]?.using_w, 0)} in 2023</div></div>
            <div className="stat"><div className="stat__label">Use them daily</div><div className="stat__value">{pct(dailyShare, 0)}</div><div className="stat__note">of AI users, 2025</div></div>
            <div className="stat"><div className="stat__label">Distrust the output</div><div className="stat__value">{pct(y25?.distrust_w, 0)}</div><div className="stat__note">from {pct(data.years[0]?.distrust_w, 0)} in 2023</div></div>
            <div className="stat"><div className="stat__label">Use AI agents at work</div><div className="stat__value">{pct(agents?.agents_w, 0)}</div><div className="stat__note">daily, weekly or monthly, 2025</div></div>
            <div className="stat"><div className="stat__label">See AI as a job threat</div><div className="stat__value">{pct(y25?.threat_w, 0)}</div><div className="stat__note">answered yes, 2025</div></div>
          </div>
          <div className="grid" style={{ marginTop: 18 }}>
            <Panel className="span-7" hero title="The adoption–trust gap"
                   caption="Composition-weighted shares of respondents. Usage keeps climbing; favourability and trust in accuracy move the other way.">
              <EChart option={charts.paradox} height={360} label="AI adoption versus trust" />
            </Panel>
            <Panel className="span-5" title="How much developers trust AI output"
                   caption="Share of respondents by trust in the accuracy of AI tools.">
              <Legend items={TRUST.map((a, i) => ({ label: a, color: divergingColors(t)[i] }))} shape="swatch" />
              <EChart option={charts.trustChart} height={170} label="Trust distribution by year" />
              <h3 className="panel__title" style={{ fontSize: 14, marginTop: 14 }}>How developers feel about AI tools</h3>
              <Legend items={SENTIMENT.map((a, i) => ({ label: a, color: divergingColors(t)[i] }))} shape="swatch" />
              <EChart option={charts.sentimentChart} height={170} label="Sentiment distribution by year" />
            </Panel>

            <Panel className="span-6" title="Who adopts, who trusts, 2025"
                   caption="Share using AI tools against share trusting their accuracy, by segment. The horizontal gap is the trust deficit.">
              <div className="controls" style={{ marginBottom: 6 }}>
                <Segmented label="Segment by" options={DIMENSIONS} value={dimension} onChange={setDimension} />
              </div>
              <Legend items={[{ label: "Use AI tools", color: t.series[0] }, { label: "Trust the output", color: t.series[1] }]} shape="dot" />
              {dumbbell && <EChart option={dumbbell} height={dimension === "role" || dimension === "region" ? 470 : 300} label="Adoption versus trust by segment" />}
            </Panel>
            <Panel className="span-6" title="What predicts it"
                   caption={drivers ? `Odds ratios from a survey-weighted logistic regression (${drivers.nModel?.toLocaleString()} respondents, 2025), each factor holding the others constant. Right of 1 means more likely; grey rows are not significant after FDR correction.` : undefined}
                   tools={<Segmented label="Outcome" options={[{ value: "trust", label: "Trusts output" }, { value: "adoption", label: "Uses AI" }]} value={model} onChange={setModel} />}>
              {drivers && <EChart option={drivers.option} height={Math.max(360, drivers.n * 21 + 60)} label="Odds ratios" />}
            </Panel>

            <Panel className="span-6" title="Where AI is used in the workflow"
                   caption="Share of respondents currently using AI for each task (2025 counts mostly- or partly-AI use).">
              <Legend items={charts.years.map((y, i) => ({ label: String(y), color: [t.seq[2], t.seq[4], t.seq[6]][i] }))} shape="swatch" />
              <EChart option={charts.tasksChart} height={440} label="AI use by task" />
            </Panel>
            <Panel className="span-6" title="The assistant and model landscape"
                   caption="Share of AI-question respondents using each tool. 2023–2024 asked about tools, 2025 about model families, so Claude's jump partly reflects the new question.">
              <EChart option={charts.toolsChart} height={440} label="AI tools and models over time" />
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
