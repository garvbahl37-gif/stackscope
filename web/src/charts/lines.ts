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
  dashed?: boolean;        // a secondary or reference series, drawn dashed throughout
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
  height?: number;   // rendered chart height; lets end labels be laid out exactly (pass it whenever endLabels is on)
};

const LABEL_FONT = 11.5;
const LABEL_HEIGHT = 15;      // px per end label, including breathing room
const CHAR_WIDTH = 6.6;       // average advance width at LABEL_FONT, used to size the right margin

/** A "nice" axis step (1, 2, 2.5 or 5 x 10^k) that splits `range` into about five intervals, as ECharts does. */
function niceStep(range: number): number {
  const raw = range / 5;
  const p = 10 ** Math.floor(Math.log10(raw));
  const f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}

/**
 * Separate labels that would overlap. Targets are positions in pixels (down = larger); overlapping labels are merged
 * into groups centred on their targets' mean and spaced `gap` apart, then clamped to [lo, hi].
 */
function dodge(targets: number[], gap: number, lo: number, hi: number): number[] {
  const order = targets.map((_, i) => i).sort((a, b) => targets[a] - targets[b]);
  let groups = order.map((i) => ({ members: [i], start: targets[i] }));
  let merged = true;
  while (merged) {
    merged = false;
    for (let k = 0; k + 1 < groups.length; k++) {
      const a = groups[k], b = groups[k + 1];
      if (a.start + a.members.length * gap > b.start) {
        const members = [...a.members, ...b.members];
        const centre = members.reduce((acc, i) => acc + targets[i], 0) / members.length;
        groups = [...groups.slice(0, k), { members, start: centre - ((members.length - 1) * gap) / 2 }, ...groups.slice(k + 2)];
        merged = true;
        break;
      }
    }
  }
  const out = new Array<number>(targets.length);
  groups.forEach((g) => {
    const start = Math.min(Math.max(g.start, lo), hi - (g.members.length - 1) * gap);
    g.members.forEach((i, j) => { out[i] = start + j * gap; });
  });
  return out;
}

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
  const grid = {
    left: opts.compact ? 38 : 56,
    right: opts.endLabels ? Math.min(190, Math.max(96, Math.ceil(Math.max(...series.map((s) => s.name.length)) * CHAR_WIDTH + 18))) : 20,
    top: opts.compact ? 10 : 16,
    bottom: opts.compact ? 22 : opts.xLabel ? 44 : 30,
  };

  // End labels: pin the y-axis to a nice extent so value -> pixel is exact, then push colliding labels apart.
  const lastOf = (arr: (number | null | undefined)[]) => [...arr].reverse().find((v) => v != null) ?? null;
  const labelTargets = series.map((s) => lastOf(xs.map((x) => s.points.find((p) => p.x === x)?.y)));
  let yExtent: [number, number] | null = null;
  const labelOffset = new Map<number, number>();
  if (opts.endLabels && opts.height) {
    const values = series.flatMap((s) => s.points.flatMap((p) => [p.y, opts.bands ? p.lo : null, opts.bands ? p.hi : null]))
      .filter((v): v is number => v != null && Number.isFinite(v));
    const dataMin = Math.min(...values), dataMax = Math.max(...values);
    const step = opts.yInterval ?? niceStep((dataMax - (typeof opts.yMin === "number" ? opts.yMin : dataMin)) || 1);
    const lo = typeof opts.yMin === "number" ? opts.yMin : Math.floor(dataMin / step) * step;
    const hi = opts.yMax ?? Math.ceil(dataMax / step) * step;
    yExtent = [lo, hi];
    const plot = opts.height - grid.top - grid.bottom;
    const toPx = (v: number) => grid.top + ((hi - v) / (hi - lo || 1)) * plot;
    const labelled = series.map((_, i) => i).filter((i) => labelTargets[i] != null);
    const wanted = labelled.map((i) => toPx(labelTargets[i] as number));
    const placed = dodge(wanted, LABEL_HEIGHT, LABEL_HEIGHT / 2, opts.height - LABEL_HEIGHT / 2);
    labelled.forEach((i, k) => labelOffset.set(i, placed[k] - wanted[k]));
  }

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
        ? { value: v, label: { show: true, position: "right" as const, distance: 6, formatter: s.name, color: t.ink2, fontSize: LABEL_FONT,
                               fontFamily: t.font, offset: [0, labelOffset.get(i) ?? 0] } }
        : v));
    };
    out.push({
      id: `line-${s.name}`, name: s.name, type: "line", data: labelled(actual, !!opts.endLabels && split === undefined), symbol: "circle", symbolSize: opts.compact ? 5 : 7,
      showSymbol: !opts.compact, lineStyle: { color: s.color, width: s.width ?? 2, cap: "round", join: "round", type: s.dashed ? [5, 4] : "solid" },
      itemStyle: { color: s.color, borderColor: t.surface, borderWidth: 2 },
      emphasis: { focus: "series" },
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
          z: 3, tooltip: { show: false },
      });
    }
  });

  return {
    ...base(t),
    grid,
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
      type: "value", min: yExtent ? yExtent[0] : opts.yMin, max: yExtent ? yExtent[1] : opts.yMax, interval: opts.yInterval, ...ax,
      splitNumber: opts.compact ? 3 : 5,
      axisLine: { show: false }, name: opts.yLabel, nameLocation: "middle", nameGap: 44,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => opts.yFormat(v) },
    },
    series: out,
  } as EChartsOption;
}
