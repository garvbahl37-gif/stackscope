import type { EChartsOption } from "echarts";
import type { Tokens } from "../lib/theme";
import { axisStyle, base, inkOn, tooltip, ttEnd, ttRow, ttSub, ttTitle } from "./base";

const BAR = 12; // thin marks (<= 24px), air between bands

/** Horizontal P25-P75 range with a median dot, sorted by the caller. */
export function rangeDotOption(rows: { label: string; lo: number; mid: number; hi: number; n: number }[], t: Tokens, fmt: (v: number) => string, opts: { reference?: { value: number; label: string } } = {}): EChartsOption {
  const ax = axisStyle(t);
  const labels = rows.map((r) => r.label);
  return {
    ...base(t),
    grid: { left: 8, right: 40, top: opts.reference ? 34 : 22, bottom: 28, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: t.dark ? "rgba(255,255,255,0.04)" : "rgba(15,42,51,0.04)" } },
      formatter: (params: { dataIndex: number }[]) => {
        const r = rows[params[0].dataIndex];
        return ttTitle(r.label) + ttRow(t.series[0], "Median", fmt(r.mid), "dot") + ttRow(null, "Middle 50%", `${fmt(r.lo)} – ${fmt(r.hi)}`) +
          ttSub(`${r.n.toLocaleString()} salaries`) + ttEnd;
      },
    }),
    xAxis: { type: "value", ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => fmt(v) } },
    yAxis: { type: "category", data: labels, inverse: true, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
    series: [
      { id: "base", type: "bar", stack: "r", data: rows.map((r) => r.lo), itemStyle: { color: "transparent" }, barWidth: BAR, silent: true },
      {
        id: "iqr", type: "bar", stack: "r", data: rows.map((r) => r.hi - r.lo), barWidth: BAR,
        itemStyle: { color: t.dark ? "rgba(57,135,229,0.35)" : "rgba(42,120,214,0.22)", borderRadius: 6 },
        markLine: opts.reference ? {
          silent: true, symbol: "none", lineStyle: { color: t.ink3, width: 1, type: "solid" },
          // the y-axis is inverted, so "start" is the top of the line: clear of the x-axis labels
          label: { formatter: `${opts.reference.label} ${fmt(opts.reference.value)}`, color: t.ink2, fontSize: 11, position: "start",
                   rotate: 0, distance: 6, backgroundColor: t.surface, padding: [1, 4], borderRadius: 3 },
          data: [{ xAxis: opts.reference.value }],
        } : undefined,
      },
      {
        id: "median", type: "scatter", data: rows.map((r) => r.mid), symbolSize: 10,
        itemStyle: { color: t.series[0], borderColor: t.surface, borderWidth: 2 },
        // surface-coloured label background keeps values legible where the reference line crosses them
        label: { show: true, position: "right", distance: 10, formatter: (p: { value: number }) => fmt(p.value), color: t.ink2, fontSize: 11,
                 backgroundColor: t.surface, padding: [1, 3], borderRadius: 3 },
        z: 3,
      },
    ],
  } as EChartsOption;
}

/** Diverging horizontal bars around zero (above/below a baseline). */
export function divergingBarOption(rows: { label: string; value: number; note?: string }[], t: Tokens, fmt: (v: number) => string): EChartsOption {
  const ax = axisStyle(t);
  return {
    ...base(t),
    grid: { left: 8, right: 56, top: 8, bottom: 24, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (p: { dataIndex: number }) => {
        const r = rows[p.dataIndex];
        return ttTitle(r.label) + ttRow(r.value >= 0 ? t.div.pos2 : t.div.neg2, "Change", fmt(r.value), "rect") + (r.note ? ttSub(r.note) : "") + ttEnd;
      },
    }),
    xAxis: { type: "value", ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => fmt(v) } },
    yAxis: { type: "category", data: rows.map((r) => r.label), inverse: true, ...ax, splitLine: { show: false },
             axisLine: { lineStyle: { color: t.axis } }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
    series: [{
      id: "delta", type: "bar", barWidth: BAR,
      data: rows.map((r) => ({
        value: r.value,
        itemStyle: { color: r.value >= 0 ? t.div.pos2 : t.div.neg2, borderRadius: r.value >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
        label: { position: r.value >= 0 ? "right" : "left" },
      })),
      label: { show: true, formatter: (p: { value: number }) => fmt(p.value), color: t.ink2, fontSize: 11 },
    }],
  } as EChartsOption;
}

/** Forest plot: point estimate with 95% whiskers; optional hollow marker for a comparison value. */
export function forestOption(rows: { label: string; est: number; lo: number; hi: number; compare?: number; strong?: boolean; group?: string }[], t: Tokens, opts: {
  fmt: (v: number) => string;
  reference: number;
  log?: boolean;
  compareLabel?: string;
  estLabel?: string;
}): EChartsOption {
  const ax = axisStyle(t);
  const labels = rows.map((r) => r.label);
  const values = rows.flatMap((r) => [r.lo, r.hi, r.compare ?? r.est]).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.06 || 0.05;
  // round the linear axis out to whole steps so it never ends on an odd tick such as "+76%"
  const raw = (max - min + 2 * pad) / 6;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((v) => v >= raw) ?? 10 * mag;
  const lo = Math.floor(Math.min(min - pad, opts.reference) / step) * step;
  const hi = Math.ceil(Math.max(max + pad, opts.reference) / step) * step;
  return {
    ...base(t),
    grid: { left: 8, right: 30, top: 8, bottom: 30, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: t.dark ? "rgba(255,255,255,0.04)" : "rgba(15,42,51,0.04)" } },
      formatter: (params: { dataIndex: number }[]) => {
        const r = rows[params[0].dataIndex];
        return ttTitle(r.label) + ttRow(t.series[0], opts.estLabel ?? "Estimate", opts.fmt(r.est), "dot") +
          ttRow(null, "95% interval", `${opts.fmt(r.lo)} to ${opts.fmt(r.hi)}`) +
          (r.compare !== undefined ? ttRow(t.ink3, opts.compareLabel ?? "Comparison", opts.fmt(r.compare), "dot") : "") +
          (r.group ? ttSub(r.group) : "") + ttEnd;
      },
    }),
    xAxis: {
      type: opts.log ? "log" : "value", ...ax, axisLine: { show: false }, logBase: 2,
      min: opts.log ? 2 ** Math.floor(Math.log2(Math.min(min, opts.reference))) : lo,
      max: opts.log ? 2 ** Math.ceil(Math.log2(Math.max(max, opts.reference))) : hi,
      interval: opts.log ? undefined : step,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => opts.fmt(v) },
    },
    yAxis: { type: "category", data: labels, inverse: true, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
    series: [
      {
        id: "ci", type: "custom",
        renderItem: (_: unknown, api: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
          const idx = api.value(0);
          const r = rows[idx];
          const a = api.coord([r.lo, idx]);
          const b = api.coord([r.hi, idx]);
          return { type: "line", shape: { x1: a[0], y1: a[1], x2: b[0], y2: b[1] },
                   style: { stroke: r.strong === false ? t.deemph : t.series[0], lineWidth: 2, lineCap: "round" } };
        },
        data: rows.map((_, i) => [i]),
        encode: { y: 0 },
        silent: true,
        markLine: {
          silent: true, symbol: "none", lineStyle: { color: t.ink3, width: 1, type: "solid" }, label: { show: false },
          data: [{ xAxis: opts.reference }],
        },
      },
      ...(rows.some((r) => r.compare !== undefined) ? [{
        id: "compare", type: "scatter", data: rows.map((r) => r.compare ?? null), symbolSize: 8,
        itemStyle: { color: t.surface, borderColor: t.ink3, borderWidth: 1.5 }, z: 2,
      }] : []),
      {
        id: "est", type: "scatter", data: rows.map((r) => ({ value: r.est, itemStyle: { color: r.strong === false ? t.deemph : t.series[0] } })),
        symbolSize: 10, itemStyle: { borderColor: t.surface, borderWidth: 2 }, z: 3,
      },
    ],
  } as EChartsOption;
}

/** 100% stacked bars (ordinal or diverging segments), 2px surface gap between segments. */
export function stackedShareOption(categories: string[], segments: { name: string; color: string; values: (number | null)[] }[], t: Tokens, opts: {
  horizontal?: boolean;
  fmt: (v: number) => string;
  labelMin?: number;
}): EChartsOption {
  const ax = axisStyle(t);
  const catAxis = { type: "category" as const, data: categories, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 }, inverse: opts.horizontal };
  const valAxis = { type: "value" as const, max: 1, ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => opts.fmt(v) } };
  return {
    ...base(t),
    grid: { left: 8, right: 16, top: 8, bottom: 24, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: t.dark ? "rgba(255,255,255,0.04)" : "rgba(15,42,51,0.04)" } },
      formatter: (params: { dataIndex: number }[]) => {
        const i = params[0].dataIndex;
        return ttTitle(categories[i]) + segments.map((s) => (s.values[i] == null ? "" : ttRow(s.color, s.name, opts.fmt(s.values[i] as number), "rect"))).join("") + ttEnd;
      },
    }),
    xAxis: opts.horizontal ? valAxis : catAxis,
    yAxis: opts.horizontal ? catAxis : valAxis,
    series: segments.map((s) => ({
      id: s.name, name: s.name, type: "bar", stack: "share", barWidth: opts.horizontal ? 18 : 24,
      data: s.values,
      itemStyle: { color: s.color, borderColor: t.surface, borderWidth: 1 },
      label: {
        show: true, fontSize: 10.5, fontWeight: 600,
        formatter: (p: { value: number }) => (p.value >= (opts.labelMin ?? 0.08) ? opts.fmt(p.value) : ""),
        color: inkOn(s.color),
      },
      emphasis: { focus: "series" },
    })),
  } as EChartsOption;
}

/** Single-series bars (one entity type -> one hue), value at the tip. */
export function simpleBarOption(rows: { label: string; value: number; highlight?: boolean }[], t: Tokens, fmt: (v: number) => string, opts: { horizontal?: boolean } = {}): EChartsOption {
  const ax = axisStyle(t);
  const horizontal = opts.horizontal ?? true;
  const cat = { type: "category" as const, data: rows.map((r) => r.label), inverse: horizontal, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } };
  const val = { type: "value" as const, ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => fmt(v) } };
  return {
    ...base(t),
    grid: { left: 8, right: 48, top: 8, bottom: 24, containLabel: true },
    tooltip: tooltip(t, { trigger: "item", formatter: (p: { dataIndex: number }) => ttTitle(rows[p.dataIndex].label) + ttRow(t.series[0], "Value", fmt(rows[p.dataIndex].value), "rect") + ttEnd }),
    xAxis: horizontal ? val : cat,
    yAxis: horizontal ? cat : val,
    series: [{
      id: "bars", type: "bar", barWidth: BAR,
      data: rows.map((r) => ({ value: r.value, itemStyle: { color: r.highlight === false ? t.deemph : t.series[0], borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } })),
      label: { show: true, position: horizontal ? "right" : "top", formatter: (p: { value: number }) => fmt(p.value), color: t.ink2, fontSize: 11 },
    }],
  } as EChartsOption;
}
