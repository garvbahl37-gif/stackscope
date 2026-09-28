import { Play } from "lucide-react";
import { useState } from "react";
import { ApiError, useRunSql, useSqlExamples, useSqlSchema } from "../lib/api";
import { downloadCsv, int } from "../lib/format";
import { Loading, PageHeader, Panel } from "../components/ui";

const STARTER = `-- The ten technologies with the highest retention in 2025 (min. 1,000 users asked)
SELECT tech, category,
       round(100 * retention_w, 1)   AS retention_pct,
       round(100 * share_used_w, 1)  AS adoption_pct
FROM mart.tech_year
WHERE survey_year = 2025 AND users_asked_want >= 1000
ORDER BY retention_w DESC
LIMIT 10;`;

function cell(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (Array.isArray(v)) return `[${v.map(cell).join(", ")}]`;
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function SqlLab() {
  const schema = useSqlSchema();
  const examples = useSqlExamples();
  const run = useRunSql();
  const [sql, setSql] = useState(STARTER);
  const [open, setOpen] = useState<string | null>("mart.tech_year");

  const execute = () => run.mutate(sql);
  const result = run.data;
  const err = run.error instanceof ApiError ? run.error.message : run.error ? String(run.error) : null;

  return (
    <>
      <PageHeader
        title="SQL lab"
        lede="Query the warehouse directly. The connection is read-only with file and network access disabled; queries time out after 10 seconds and return up to 500 rows."
      />
      <div className="sql-layout">
        <aside className="panel sql-schema" aria-label="Warehouse schema">
          <h2 className="panel__title">Tables</h2>
          {!schema.data ? <Loading height={300} /> : (
            <ul>
              {schema.data.tables.map((tbl) => (
                <li key={tbl.name}>
                  <button type="button" onClick={() => setOpen(open === tbl.name ? null : tbl.name)} aria-expanded={open === tbl.name}>
                    <span>{tbl.name}</span><span className="muted small num">{int(tbl.rows)}</span>
                  </button>
                  {open === tbl.name && (
                    <ul className="sql-cols">
                      {tbl.columns.map((c) => <li key={c.name}><span>{c.name}</span><span className="muted">{c.type.toLowerCase()}</span></li>)}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </aside>
        <div className="sql-main">
          <Panel title="Examples" caption="Each one shows a different SQL technique; click to load it into the editor.">
            <div className="chips">
              {(examples.data?.examples ?? []).map((ex) => (
                <button key={ex.title} type="button" className="chip" onClick={() => setSql(ex.sql)} title={ex.skill}>
                  {ex.title}<span className="muted small">{ex.skill}</span>
                </button>
              ))}
            </div>
          </Panel>
          <Panel title="Query">
            <textarea className="sql-editor" value={sql} onChange={(e) => setSql(e.target.value)} spellCheck={false}
                      aria-label="SQL query"
                      onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); execute(); } }} />
            <div className="controls" style={{ marginTop: 10, marginBottom: 0 }}>
              <button type="button" className="btn" onClick={execute} disabled={run.isPending}><Play aria-hidden /> {run.isPending ? "Running" : "Run query"}</button>
              <span className="small muted">Ctrl or Cmd + Enter</span>
              {result && (
                <span className="small muted">{int(result.row_count)} rows{result.truncated ? " (first 500 shown)" : ""} in {result.elapsed_ms} ms</span>
              )}
              {result && result.rows.length > 0 && (
                <button type="button" className="btn btn--quiet" onClick={() => downloadCsv("query_result.csv", result.columns.map((c) => c.name), result.rows)}>Download CSV</button>
              )}
            </div>
          </Panel>
          <Panel title="Result">
            {err ? <p className="sql-error" role="alert">{err}</p> : !result ? <p className="small muted">Run a query to see results here.</p> : (
              <div className="table-wrap" style={{ maxHeight: 520 }}>
                <table className="data">
                  <thead><tr>{result.columns.map((c) => <th key={c.name} title={c.type}>{c.name}</th>)}</tr></thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === "number" ? "n" : undefined}>{cell(v)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
