import type { EChartsOption } from "echarts";
import type { Tokens } from "../lib/theme";
import { axisStyle, base, tooltip, ttEnd, ttRow, ttSub, ttTitle } from "./base";

export type LinePoint = { x: number; y: number | null; lo?: number | null; hi?: number | null };
export type LineSeries = {
  name: string;
  color: string;
  points: LinePoint[];
  forecastFrom?: number;   // x at which the series becomes a projection (drawn dashed)
  width?: number;
};

type Opts = {
  yFormat: (v: number) => string;
  valueFormat?: (v: number) => string;
  yMin?: number | "dataMin";
  yMax?: number;
  yInterval?: number;
  bands?: boolean;
  endLabels?: boolean;
  compact?: boolean;
  xLabel?: string;
  yLabel?: string;
  note?: (x: number) => string | null;
  markX?: { x: number; label: string }[];
};

function withAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/**
 * Multi-series line chart on a shared category x-axis of years, with optional 95% bands
 * (stacked-area trick: an invisible lower line plus a translucent upper-lower difference),
 * a dashed projection segment, direct end labels and a one-tooltip-every-series crosshair.
 */
export function lineOption(series: LineSeries[], t: Tokens, opts: Opts): EChartsOption {
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const cat = xs.map(String);
  const ax = axisStyle(t);
  const fmt = opts.valueFormat ?? opts.yFormat;
  const out: Record<string, unknown>[] = [];

  series.forEach((s, i) => {
    const byX = new Map(s.points.map((p) => [p.x, p]));
    const val = (x: number) => byX.get(x)?.y ?? null;
    if (opts.bands) {
      const lo = xs.map((x) => byX.get(x)?.lo ?? null);
      const diff = xs.map((x) => {
        const p = byX.get(x);
        return p && p.lo != null && p.hi != null ? p.hi - p.lo : null;
      });
      out.push({ id: `band-lo-${s.name}`, name: `${s.name} lower`, type: "line", data: lo, stack: `band-${i}`, symbol: "none",
                 lineStyle: { opacity: 0 }, silent: true, tooltip: { show: false }, z: 1, connectNulls: false });
      out.push({ id: `band-${s.name}`, name: `${s.name} band`, type: "line", data: diff, stack: `band-${i}`, symbol: "none",
                 lineStyle: { opacity: 0 }, areaStyle: { color: withAlpha(s.color, t.dark ? 0.2 : 0.13) }, silent: true,
                 tooltip: { show: false }, z: 1 });
    }
    const split = s.forecastFrom;
    const actual = xs.map((x) => (split === undefined || x <= split ? val(x) : null));
    // Direct label on the series' last point (static; ECharts' animated endLabel misplaces text on some frames)
    const labelled = (arr: (number | null)[], show: boolean) => {
      const last = arr.reduce<number>((acc, v, idx) => (v == null ? acc : idx), -1);
      return arr.map((v, idx) => (idx === last && show && v != null
        ? { value: v, label: { show: true, position: "right" as const, distance: 6, formatter: s.name, color: t.ink2, fontSize: 11.5, fontFamily: t.font } }
        : v));
    };
    out.push({
      id: `line-${s.name}`, name: s.name, type: "line", data: labelled(actual, !!opts.endLabels && split === undefined), symbol: "circle", symbolSize: opts.compact ? 5 : 7,
      showSymbol: !opts.compact, lineStyle: { color: s.color, width: s.width ?? 2, cap: "round", join: "round" },
      itemStyle: { color: s.color, borderColor: t.surface, borderWidth: 2 },
      emphasis: { focus: "series" },
      labelLayout: { moveOverlap: "shiftY" },
      z: 3,
      markLine: opts.markX && i === 0 ? {
        silent: true, symbol: "none", lineStyle: { color: t.axis, width: 1, type: "solid" },
        label: { color: t.ink3, fontSize: 10.5, formatter: (p: { name: string }) => p.name, position: "insideEndTop" },
        data: opts.markX.map((m) => ({ xAxis: String(m.x), name: m.label })),
      } : undefined,
    });
    if (split !== undefined) {
      const proj = xs.map((x) => (x >= split ? val(x) : null));
      out.push({
        id: `proj-${s.name}`, name: `${s.name} (projection)`, type: "line", data: labelled(proj, !!opts.endLabels), symbol: "circle", symbolSize: 6,
        lineStyle: { color: s.color, width: 2, type: [5, 4] }, itemStyle: { color: t.surface, borderColor: s.color, borderWidth: 2 },
        labelLayout: { moveOverlap: "shiftY" },
        z: 3, tooltip: { show: false },
      });
    }
  });

  return {
    ...base(t),
    grid: {
      left: opts.compact ? 38 : 56, right: opts.endLabels ? 96 : 20, top: opts.compact ? 10 : 16,
      bottom: opts.compact ? 22 : opts.xLabel ? 44 : 30,
    },
    tooltip: tooltip(t, {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: t.axis, width: 1 } },
      formatter: (params: { axisValue: string; seriesName: string; seriesId: string; value: number | null }[]) => {
        const x = Number(params[0]?.axisValue);
        let html = ttTitle(String(x));
        series.forEach((s) => {
          const p = s.points.find((pt) => pt.x === x);
          if (!p || p.y == null) return;
          const ci = p.lo != null && p.hi != null && opts.bands ? ` (${fmt(p.lo)}–${fmt(p.hi)})` : "";
          const projected = s.forecastFrom !== undefined && x > s.forecastFrom ? " projected" : "";
          html += ttRow(s.color, s.name + projected, fmt(p.y) + ci);
        });
        const note = opts.note?.(x);
        return html + (note ? ttSub(note) : "") + ttEnd;
      },
    }),
    xAxis: {
      type: "category", data: cat, boundaryGap: false, ...ax, splitLine: { show: false },
      name: opts.xLabel, nameLocation: "middle", nameGap: 28,
    },
    yAxis: {
      type: "value", min: opts.yMin, max: opts.yMax, interval: opts.yInterval, ...ax, splitNumber: opts.compact ? 3 : 5,
      axisLine: { show: false }, name: opts.yLabel, nameLocation: "middle", nameGap: 44,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => opts.yFormat(v) },
    },
    series: out,
  } as EChartsOption;
}
