import { useMemo, useState } from "react";
import { simpleBarOption } from "../charts/bars";
import { heatmapOption, RECON_BAND, reconciliationOption, reconLabel } from "../charts/misc";
import { EChart } from "../components/EChart";
import { type Column, DataTable, DownloadButton, ErrorState, Legend, Loading, PageHeader, Panel, Segmented, StatusBadge } from "../components/ui";
import { type Check, type Quality as QualityData, type ReconRow, useQuality } from "../lib/api";
import { compactNum, fixed, int, pct } from "../lib/format";
import { useTokens } from "../lib/theme";

const CHECK_COLUMNS: Column<Check>[] = [
  { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "dimension", label: "Dimension" },
  { key: "description", label: "Check", wrap: true },
  { key: "threshold", label: "Threshold" },
  { key: "detail", label: "Evidence", wrap: true },
  { key: "blocker", label: "Gate", render: (r) => (r.blocker ? "Blocks build" : "Reported") },
];

type Alias = QualityData["aliases"][number];
const ALIAS_COLUMNS: Column<Alias>[] = [
  { key: "tech", label: "Canonical technology" },
  { key: "labels", label: "Raw survey labels merged into it", wrap: true, render: (r) => r.labels.join("  |  "), value: (r) => r.labels.join(" | ") },
  { key: "mentions", label: "Mentions", numeric: true, render: (r) => compactNum(r.mentions) },
];

type Weight = QualityData["weights"][number];
const WEIGHT_COLUMNS: Column<Weight>[] = [
  { key: "survey_year", label: "Wave" },
  { key: "respondents", label: "Respondents", numeric: true, render: (r) => int(r.respondents) },
  { key: "effective_n", label: "Effective n", numeric: true, render: (r) => int(r.effective_n) },
  { key: "design_effect", label: "Design effect", numeric: true, render: (r) => fixed(r.design_effect, 3) },
  { key: "max_weight", label: "Max weight", numeric: true, render: (r) => fixed(r.max_weight, 2) },
  { key: "iterations", label: "IPF iterations", numeric: true },
];

const STAGES = [
  { stage: "Sources", items: ["Kaggle: 9 annual survey files", "World Bank API: PPP, FX, GDP, population", "FRED: US CPI-U"] },
  { stage: "Bronze", items: ["Raw CSVs, 1.2 GB", "SHA-256 manifest", "Row counts reconciled to the released files"] },
  { stage: "Silver", items: ["Year-specific schemas harmonised", "309-technology taxonomy, 448 raw labels", "Country, role, pay and AI fields normalised"] },
  { stage: "Gold", items: ["DuckDB star schema", "Facts, bridges, conformed dimensions", "Raking weights per respondent"] },
  { stage: "Marts & models", items: ["SQL marts with Wilson intervals", "Python analytics: trends, premiums, ML, clustering", "Quality gate: 29 automated checks"] },
  { stage: "Serving", items: ["FastAPI (read-only, cached)", "React dashboard", "Sandboxed SQL lab"] },
];

const TOLERANCE_PP = 0.5;   // matches quality/reconcile.py

const RECON_COLUMNS: Column<ReconRow>[] = [
  { key: "item", label: "Published figure", render: (r) => (r.unit === "count" ? `Responses, ${r.survey_year}` : reconLabel(r)) },
  { key: "published", label: "Published", numeric: true, render: (r) => (r.unit === "count" ? int(r.published) : `${fixed(r.published, 2)}%`) },
  { key: "ours", label: "Recomputed", numeric: true, render: (r) => (r.unit === "count" ? int(r.ours) : `${fixed(r.ours, 2)}%`) },
  { key: "diff", label: "Difference", numeric: true, render: (r) => (r.unit === "count" ? int(r.diff) : `${r.diff >= 0 ? "+" : ""}${fixed(r.diff, 2)} pp`) },
  { key: "status", label: "Result" },
  { key: "note", label: "Note", wrap: true, render: (r) => r.note ?? (r.same_base || r.unit === "count" ? "" : "published base is larger than the public file shows") },
];

export default function Quality() {
  const t = useTokens();
  const { data, isError, error } = useQuality();
  const [filter, setFilter] = useState<"all" | "pass" | "warn" | "fail">("all");

  const heat = useMemo(() => {
    if (!data) return null;
    const years = [...new Set(data.completeness.map((c) => String(c.survey_year)))].sort();
    const label = (f: string) => f.charAt(0).toUpperCase() + f.slice(1);
    const fields = [...new Set(data.completeness.map((c) => label(c.field)))];
    return heatmapOption(years, fields, data.completeness.map((c) => ({
      x: String(c.survey_year), y: label(c.field), v: c.asked ? c.completeness : null, label: c.asked ? undefined : "question not asked this year",
    })), t, { fmt: (v) => pct(v, 0), min: 0, max: 1, cellLabels: true, valueName: "Answered" });
  }, [data, t]);
  const recon = useMemo(() => {
    if (!data?.reconciliation?.length) return null;
    const shares = data.reconciliation.filter((r) => r.unit === "pct");
    const same = shares.filter((r) => r.same_base);
    return {
      option: reconciliationOption(data.reconciliation, TOLERANCE_PP, t),
      same: same.length, maxDiff: Math.max(...same.map((r) => Math.abs(r.diff))),
      counted: shares.filter((r) => !r.same_base && r.status === "count matches").length,
      unexplained: data.reconciliation.filter((r) => r.status === "differs").length,
    };
  }, [data, t]);
  const deff = useMemo(() => data ? simpleBarOption(data.weights.map((w) => ({ label: String(w.survey_year), value: w.design_effect })), t, (v) => fixed(v, 2), { horizontal: false }) : null, [data, t]);

  if (isError) return <><PageHeader title="Data quality and method" /><ErrorState error={error} /></>;
  const checks = (data?.checks ?? []).filter((c) => filter === "all" || c.status === filter);
  const passed = data?.checks.filter((c) => c.status === "pass").length ?? 0;
  const mapped = data?.coverage.filter((c) => c.status === "mapped").reduce((s, c) => s + c.mentions, 0) ?? 0;
  const inScope = data?.coverage.filter((c) => c.status !== "excluded").reduce((s, c) => s + c.mentions, 0) ?? 1;
  const layerRows = new Map((data?.layers ?? []).map((l) => [l.object, l.rows]));

  return (
    <>
      <PageHeader
        title="Data quality and method"
        lede="Every number on this site is reproducible from one command. This page shows how nine inconsistent survey files became one warehouse, and the checks that must pass before anything is published."
      />
      {!data ? <Loading height={600} /> : (
        <>
          <div className="stats">
            <div className="stat"><div className="stat__label">Automated checks passing</div><div className="stat__value">{passed}/{data.checks.length}</div><div className="stat__note">blocking checks stop the build</div></div>
            <div className="stat"><div className="stat__label">Technology mentions mapped</div><div className="stat__value">{pct(mapped / inScope, 2)}</div><div className="stat__note">{compactNum(mapped)} of in-scope mentions</div></div>
            <div className="stat"><div className="stat__label">Respondents reconciled</div><div className="stat__value">{compactNum(layerRows.get("Harmonised respondents"))}</div><div className="stat__note">exactly the publisher's totals</div></div>
            <div className="stat"><div className="stat__label">Raking converged</div><div className="stat__value">{data.weights.filter((w) => w.converged).length}/{data.weights.length}</div><div className="stat__note">waves; max margin error {data.weights.reduce((m, w) => Math.max(m, w.max_margin_error), 0).toExponential(0)}</div></div>
            <div className="stat"><div className="stat__label">Largest design effect</div><div className="stat__value">{fixed(Math.max(...data.weights.map((w) => w.design_effect)), 2)}</div><div className="stat__note">variance cost of weighting</div></div>
          </div>

          <h2 className="section-title">Lineage</h2>
          <div className="lineage" role="list">
            {STAGES.map((s) => (
              <div key={s.stage} className="lineage__stage" role="listitem">
                <h3>{s.stage}</h3>
                <ul>{s.items.map((i) => <li key={i}>{i}</li>)}</ul>
                {s.stage === "Silver" && <p className="lineage__rows">{compactNum(layerRows.get("Technology usage facts"))} usage rows</p>}
                {s.stage === "Gold" && <p className="lineage__rows">{compactNum(layerRows.get("Harmonised respondents"))} respondents</p>}
                {s.stage === "Marts & models" && <p className="lineage__rows">{int(layerRows.get("Technology-year KPI cube"))} tech-year KPIs</p>}
              </div>
            ))}
          </div>

          <div className="grid" style={{ marginTop: 18 }}>
            <Panel className="span-12" title="Quality checks"
                   caption="Organised by DAMA data-quality dimension. The build fails if any blocking check fails."
                   tools={<><Segmented label="Filter" options={[{ value: "all", label: "All" }, { value: "pass", label: "Pass" }, { value: "warn", label: "Warning" }, { value: "fail", label: "Fail" }]} value={filter} onChange={setFilter} />
                     <DownloadButton columns={CHECK_COLUMNS} rows={data.checks} filename="quality_checks.csv" /></>}>
              <DataTable columns={CHECK_COLUMNS} rows={checks} rowKey={(r) => r.check_id} maxHeight={520} />
            </Panel>

            {recon && (
              <Panel className="span-12" title="Reconciliation with Stack Overflow's published results"
                     caption={`${recon.same} published figures, recomputed unweighted with Stack Overflow's own definitions, agree within ${fixed(recon.maxDiff, 2)} percentage points. For ${recon.counted} database and cloud shares the published figure divides by more respondents than the public data file shows as answering, so the share differs, but the number of users matches the published count.${recon.unexplained ? ` ${recon.unexplained} figure(s) are unexplained.` : ""} The rest of the dashboard is weighted and differs from these by design.`}
                     table={{ columns: RECON_COLUMNS, rows: data.reconciliation, filename: "published_reconciliation.csv" }}
                     foot="Published figures collected from survey.stackoverflow.co on 29 September 2026; every source link is in config/published_benchmarks.yml and in the table download.">
                <Legend items={[{ label: "Same definition as published", color: t.series[0] }, { label: "Larger published base, user count matches", color: t.series[1] }]} shape="dot" />
                <Legend items={[{ label: `Shaded: within ±${TOLERANCE_PP} percentage points`, color: RECON_BAND(t) }]} shape="swatch" />
                <EChart option={recon.option} height={400} label="Difference between recomputed and published figures" />
              </Panel>
            )}

            <Panel className="span-7" title="What each wave asked"
                   caption="Share of respondents with a usable answer, by field and wave. Blank cells were not asked that year; the harmonised schema keeps them explicit rather than silently empty."
                   table={{ columns: [
                     { key: "field", label: "Field" }, { key: "survey_year", label: "Wave" },
                     { key: "completeness", label: "Answered", numeric: true, render: (r: QualityData["completeness"][number]) => (r.asked ? pct(r.completeness, 1) : "not asked"), value: (r: QualityData["completeness"][number]) => r.completeness },
                   ], rows: data.completeness, filename: "completeness.csv" }}>
              {heat ? <EChart option={heat} height={520} label="Completeness heatmap" /> : <Loading height={520} />}
            </Panel>
            <Panel className="span-5" title="Composition weighting"
                   caption="Each wave is raked to the average respondent mix (region, respondent type, experience). Design effect is the variance cost: 1.0 means none."
                   table={{ columns: WEIGHT_COLUMNS, rows: data.weights, filename: "weight_diagnostics.csv" }}>
              {deff ? <EChart option={deff} height={220} label="Design effect by wave" /> : null}
              <DataTable columns={WEIGHT_COLUMNS.filter((c) => ["survey_year", "respondents", "effective_n", "design_effect"].includes(c.key))} rows={data.weights} rowKey={(r) => String(r.survey_year)} maxHeight={260} />
            </Panel>

            <Panel className="span-12" title="Harmonising the taxonomy"
                   caption="Stack Overflow renamed, merged and moved answer options almost every year. These canonical technologies each absorb several raw labels; the full mapping lives in config/tech_taxonomy.yml."
                   tools={<DownloadButton columns={ALIAS_COLUMNS} rows={data.aliases} filename="taxonomy_aliases.csv" />}>
              <DataTable columns={ALIAS_COLUMNS} rows={data.aliases} rowKey={(r) => r.tech} maxHeight={420} />
            </Panel>

            <Panel className="span-6" title="Known issues handled" caption="Per-wave schema notes applied during harmonisation.">
              <ul className="notes">
                {data.schema_notes.map((n) => <li key={`${n.survey_year}${n.note}`}><strong>{n.survey_year}:</strong> {n.note}</li>)}
                <li><strong>World Bank:</strong> Croatia's PPP series moved to euros while its historical exchange rate stayed in kuna; converted at the fixed 7.53450 rate.</li>
                <li><strong>World Bank:</strong> official-rate distortions (Iran, Lebanon, Sudan, Zimbabwe, Liberia) produce implausible price levels; PPP pay is withheld for those country-years.</li>
                <li><strong>FRED:</strong> the October 2025 CPI release was never published (US government shutdown); the 2025 annual average uses 11 months.</li>
                <li><strong>2025:</strong> respondents ticked 14% more languages than in 2024, a questionnaire effect flagged wherever 2024–2025 changes are shown.</li>
              </ul>
            </Panel>
            <Panel className="span-6" title="Warehouse inventory" caption="Every table in the DuckDB warehouse, queryable from the SQL lab."
                   tools={<DownloadButton columns={[{ key: "schema_name", label: "Schema" }, { key: "table_name", label: "Table" }, { key: "rows", label: "Rows" }, { key: "column_count", label: "Columns" }]} rows={data.tables} filename="warehouse_tables.csv" />}>
              <DataTable columns={[
                { key: "schema_name", label: "Schema" }, { key: "table_name", label: "Table" },
                { key: "rows", label: "Rows", numeric: true, render: (r: QualityData["tables"][number]) => int(r.rows) },
                { key: "column_count", label: "Columns", numeric: true },
              ]} rows={data.tables} rowKey={(r) => `${r.schema_name}.${r.table_name}`} maxHeight={420} />
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
