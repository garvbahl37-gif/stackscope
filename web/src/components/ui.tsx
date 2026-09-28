import { AlertTriangle, CheckCircle2, Download, Pause, Play, Table2, XCircle } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { downloadCsv } from "../lib/format";

// ------------------------------------------------------------------------------------------
// Page header
// ------------------------------------------------------------------------------------------
export function PageHeader({ title, lede, actions }: { title: string; lede?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div>
        <h1 className="page-title">{title}</h1>
        {lede && <p className="page-lede">{lede}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

// ------------------------------------------------------------------------------------------
// Data table (the accessible twin of every chart)
// ------------------------------------------------------------------------------------------
export type Column<T> = {
  key: string;
  label: string;
  numeric?: boolean;
  wrap?: boolean;   // allow long text to wrap instead of forcing horizontal scroll
  render?: (row: T) => ReactNode;
  value?: (row: T) => unknown; // raw value for CSV (defaults to row[key])
};

export function DataTable<T extends object>({ columns, rows, maxHeight, selectedKey, rowKey, onRowClick }: {
  columns: Column<T>[];
  rows: T[];
  maxHeight?: number;
  rowKey?: (row: T) => string;
  selectedKey?: string | null;
  onRowClick?: (row: T) => void;
}) {
  return (
    <div className="table-wrap" style={maxHeight ? { maxHeight } : undefined}>
      <table className="data">
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.numeric ? "n" : undefined} scope="col">{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const key = rowKey ? rowKey(row) : String(i);
            return (
              <tr key={key} data-selected={selectedKey === key || undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  style={onRowClick ? { cursor: "pointer" } : undefined}>
                {columns.map((c) => (
                  <td key={c.key} className={[c.numeric ? "n" : "", c.wrap ? "wrap" : ""].join(" ").trim() || undefined}>
                    {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "–")}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------------------------------
// Panel: title, caption, chart <-> table toggle, CSV export
// ------------------------------------------------------------------------------------------
type TableSpec<T> = { columns: Column<T>[]; rows: T[]; filename: string };

export function Panel<T extends object>({ title, caption, children, table, tools, foot, className = "", hero, stale }: {
  title?: ReactNode;
  caption?: ReactNode;
  children: ReactNode;
  table?: TableSpec<T>;
  tools?: ReactNode;
  foot?: ReactNode;
  className?: string;
  hero?: boolean;
  stale?: boolean;
}) {
  const [showTable, setShowTable] = useState(false);
  const exportCsv = () => {
    if (!table) return;
    const cols = table.columns;
    downloadCsv(table.filename, cols.map((c) => c.label),
      table.rows.map((r) => cols.map((c) => (c.value ? c.value(r) : (r as Record<string, unknown>)[c.key]))));
  };
  return (
    <section className={`panel ${hero ? "panel--hero" : ""} ${className}`} data-stale={stale || undefined}>
      {(title || table || tools) && (
        <div className="panel__head">
          <div>
            {title && <h2 className="panel__title">{title}</h2>}
            {caption && <p className="panel__caption">{caption}</p>}
          </div>
          <div className="panel__tools">
            {tools}
            {table && (
              <>
                <button type="button" className="icon-btn" aria-pressed={showTable} onClick={() => setShowTable((s) => !s)}
                        title={showTable ? "Show chart" : "Show data table"}>
                  <Table2 aria-hidden /> <span>{showTable ? "Chart" : "Table"}</span>
                </button>
                <button type="button" className="icon-btn" onClick={exportCsv} title="Download CSV" aria-label="Download CSV">
                  <Download aria-hidden />
                </button>
              </>
            )}
          </div>
        </div>
      )}
      {showTable && table ? <DataTable columns={table.columns} rows={table.rows} maxHeight={460} /> : children}
      {foot && <p className="panel__foot">{foot}</p>}
    </section>
  );
}

export function DownloadButton<T extends object>({ columns, rows, filename }: TableSpec<T>) {
  return (
    <button type="button" className="icon-btn" title="Download CSV" aria-label="Download CSV"
            onClick={() => downloadCsv(filename, columns.map((c) => c.label),
              rows.map((r) => columns.map((c) => (c.value ? c.value(r) : (r as Record<string, unknown>)[c.key]))))}>
      <Download aria-hidden />
    </button>
  );
}

// ------------------------------------------------------------------------------------------
// Controls
// ------------------------------------------------------------------------------------------
export function Segmented<V extends string | number>({ options, value, onChange, label }: {
  options: { value: V; label: string }[];
  value: V;
  onChange: (v: V) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Select<V extends string | number>({ options, value, onChange, label, id }: {
  options: { value: V; label: string }[];
  value: V;
  onChange: (v: V) => void;
  label: string;
  id?: string;
}) {
  return (
    <label className="control" htmlFor={id}>
      <span>{label}</span>
      <select id={id} className="select" value={String(value)}
              onChange={(e) => {
                const hit = options.find((o) => String(o.value) === e.target.value);
                if (hit) onChange(hit.value);
              }}>
        {options.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}
      </select>
    </label>
  );
}

/** Year scrubber with an optional play-through (the one orchestrated motion in the product). */
export function YearScrubber({ years, value, onChange, autoplay = false }: {
  years: number[];
  value: number;
  onChange: (y: number) => void;
  autoplay?: boolean;
}) {
  const [playing, setPlaying] = useState(autoplay);
  const valueRef = useRef(value);
  valueRef.current = value;
  useEffect(() => {
    if (!playing || years.length < 2) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setPlaying(false);
      onChange(years[years.length - 1]);
      return;
    }
    const id = window.setInterval(() => {
      const idx = years.indexOf(valueRef.current);
      if (idx >= years.length - 1) {
        setPlaying(false);
        return;
      }
      onChange(years[idx + 1]);
    }, 1100);
    return () => window.clearInterval(id);
  }, [playing, years, onChange]);

  const idx = Math.max(0, years.indexOf(value));
  return (
    <div className="year-scrubber">
      <button type="button" className="icon-btn" onClick={() => {
        if (!playing && idx >= years.length - 1) onChange(years[0]);
        setPlaying((p) => !p);
      }} aria-label={playing ? "Pause" : "Play through the years"}>
        {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
      </button>
      <input type="range" min={0} max={years.length - 1} step={1} value={idx}
             aria-label="Survey year" aria-valuetext={String(value)}
             onChange={(e) => { setPlaying(false); onChange(years[Number(e.target.value)]); }} />
      <span className="year-scrubber__value">{value}</span>
    </div>
  );
}

// ------------------------------------------------------------------------------------------
// States & badges
// ------------------------------------------------------------------------------------------
export function Loading({ height = 260 }: { height?: number }) {
  return <div className="skeleton" style={{ height }} aria-label="Loading" role="status" />;
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="state state--error" role="alert">
      <div>
        <strong>Couldn't load this view.</strong>
        <p className="small">{message}. Check that the API is running (<code>make api</code>) and the warehouse is built.</p>
      </div>
    </div>
  );
}

export function StatusBadge({ status }: { status: "pass" | "warn" | "fail" }) {
  const Icon = status === "pass" ? CheckCircle2 : status === "warn" ? AlertTriangle : XCircle;
  const label = status === "pass" ? "Pass" : status === "warn" ? "Warning" : "Fail";
  return <span className={`status status--${status}`}><Icon aria-hidden />{label}</span>;
}

export function Legend({ items, shape = "line" }: { items: { label: string; color: string }[]; shape?: "line" | "swatch" | "dot" }) {
  const cls = shape === "line" ? "legend__line" : shape === "dot" ? "legend__dot" : "legend__swatch";
  return (
    <div className="legend">
      {items.map((i) => (
        <span className="legend__item" key={i.label}><span className={cls} style={{ background: i.color }} />{i.label}</span>
      ))}
    </div>
  );
}
