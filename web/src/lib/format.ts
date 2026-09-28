/** Number formatting — one place, so every page speaks the same numeric language. */

const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

export const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function int(v: number | null | undefined): string {
  return isNum(v) ? nf0.format(v) : "–";
}

export function compactNum(v: number | null | undefined): string {
  return isNum(v) ? compact.format(v) : "–";
}

/** 0.4213 -> "42.1%" (digits = decimals). */
export function pct(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}

/** Signed percentage for premiums / growth: 0.068 -> "+6.8%". */
export function signedPct(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return "–";
  const s = (v * 100).toFixed(digits);
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s.replace("-", "")}%`;
}

/** Percentage points: 3.42 -> "+3.4 pp". */
export function pp(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return "–";
  const s = Math.abs(v).toFixed(digits);
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s} pp`;
}

/** Money, compact when large: 81210 -> "$81.2k", 1540 -> "$1,540". */
export function money(v: number | null | undefined, opts: { compact?: boolean } = {}): string {
  if (!isNum(v)) return "–";
  const useCompact = opts.compact ?? Math.abs(v) >= 10_000;
  if (useCompact) {
    if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
    return `$${(v / 1000).toFixed(v >= 100_000 ? 0 : 1)}k`;
  }
  return `$${nf0.format(v)}`;
}

export function fixed(v: number | null | undefined, digits = 2): string {
  return isNum(v) ? v.toFixed(digits) : "–";
}

export function oneDp(v: number | null | undefined): string {
  return isNum(v) ? nf1.format(v) : "–";
}

/** q-value with significance wording used across the app. */
export function significance(q: number | null | undefined): string {
  if (!isNum(q)) return "n/a";
  if (q < 0.001) return "q < 0.001";
  return `q = ${q.toFixed(3)}`;
}

export function escapeHtml(s: unknown): string {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function downloadCsv(filename: string, columns: string[], rows: unknown[][]): void {
  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const csv = [columns.map(cell).join(","), ...rows.map((r) => r.map(cell).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
