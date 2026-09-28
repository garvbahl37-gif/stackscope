import type { EChartsOption } from "echarts";
import type { NetworkNode } from "../lib/api";
import { fixed, pct } from "../lib/format";
import type { Tokens } from "../lib/theme";
import { axisStyle, base, inkOn, tooltip, ttEnd, ttRow, ttSub, ttTitle } from "./base";

// ------------------------------------------------------------------------------------------
// Heatmap (sequential one-hue scale; "not asked" cells stay empty and are labelled as such)
// ------------------------------------------------------------------------------------------
export function heatmapOption(xs: string[], ys: string[], cells: { x: string; y: string; v: number | null; label?: string }[], t: Tokens, opts: {
  fmt: (v: number) => string;
  min?: number;
  max?: number;
  cellLabels?: boolean;
  valueName?: string;
}): EChartsOption {
  const ax = axisStyle(t);
  const values = cells.map((c) => c.v).filter((v): v is number => v != null);
  const min = opts.min ?? Math.min(...values);
  const max = opts.max ?? Math.max(...values);
  const lookup = new Map(cells.map((c) => [`${c.x}|${c.y}`, c]));
  return {
    ...base(t),
    grid: { left: 8, right: 12, top: 8, bottom: 56, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (p: { value: [number, number, number | null] }) => {
        const [xi, yi] = p.value;
        const c = lookup.get(`${xs[xi]}|${ys[yi]}`);
        return ttTitle(`${ys[yi]}, ${xs[xi]}`) +
          ttRow(null, opts.valueName ?? "Value", c?.v == null ? "not asked" : opts.fmt(c.v)) + (c?.label ? ttSub(c.label) : "") + ttEnd;
      },
    }),
    xAxis: { type: "category", data: xs, ...ax, splitLine: { show: false }, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, interval: 0, rotate: xs.length > 12 ? 40 : 0 } },
    yAxis: { type: "category", data: ys, inverse: true, ...ax, splitLine: { show: false }, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
    visualMap: {
      min, max, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 12, itemHeight: 160,
      text: [opts.fmt(max), opts.fmt(min)], textGap: 8,
      inRange: { color: t.seq }, textStyle: { color: t.ink3, fontSize: 11 },
    },
    series: [{
      id: "heat", type: "heatmap",
      data: cells.map((c) => {
        const value = [xs.indexOf(c.x), ys.indexOf(c.y), c.v ?? "-"];
        if (c.v == null) return value;
        // label ink chosen against the ramp step this value lands on
        const step = t.seq[Math.max(0, Math.min(t.seq.length - 1, Math.round(((c.v - min) / (max - min || 1)) * (t.seq.length - 1))))];
        return { value, label: { color: inkOn(step) } };
      }),
      itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 3 },
      label: {
        show: !!opts.cellLabels, fontSize: 10.5,
        formatter: (p: { value: [number, number, number] }) => (typeof p.value[2] === "number" ? opts.fmt(p.value[2]) : ""),
      },
      emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 1 } },
    }],
  } as EChartsOption;
}

// ------------------------------------------------------------------------------------------
// Labelled scatter with quadrant guides (retention vs attraction)
// ------------------------------------------------------------------------------------------
export function labelledScatterOption(points: { name: string; x: number; y: number; size: number; note?: string }[], t: Tokens, opts: {
  xName: string; yName: string; xFmt: (v: number) => string; yFmt: (v: number) => string;
  guides?: { x: number; y: number };
  corners?: [string, string, string, string]; // top-left, top-right, bottom-left, bottom-right
  selected?: string | null;
}): EChartsOption {
  const ax = axisStyle(t);
  const maxSize = Math.max(...points.map((p) => p.size), 1e-9);
  const cornerLabel = (text: string, position: string) => ({ show: true, position, color: t.ink3, fontSize: 12, fontWeight: 650 as const, formatter: text, padding: [4, 6] });
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const [xmin, xmax] = [Math.min(...xs), Math.max(...xs)];
  const [ymin, ymax] = [Math.min(...ys), Math.max(...ys)];
  const px = (xmax - xmin) * 0.08 || 0.05;
  const py = (ymax - ymin) * 0.1 || 0.05;
  const bounds = { x0: Math.max(0, xmin - px), x1: Math.min(1, xmax + px), y0: Math.max(0, ymin - py), y1: Math.min(1, ymax + py) };
  return {
    ...base(t),
    grid: { left: 56, right: 24, top: 16, bottom: 46 },
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (p: { dataIndex: number; seriesId: string }) => {
        if (p.seriesId !== "pts") return "";
        const d = points[p.dataIndex];
        return ttTitle(d.name) + ttRow(null, opts.xName, opts.xFmt(d.x)) + ttRow(null, opts.yName, opts.yFmt(d.y)) + (d.note ? ttSub(d.note) : "") + ttEnd;
      },
    }),
    xAxis: { type: "value", name: opts.xName, nameLocation: "middle", nameGap: 28, min: bounds.x0, max: bounds.x1, ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => opts.xFmt(v) } },
    yAxis: { type: "value", name: opts.yName, nameLocation: "middle", nameGap: 42, min: bounds.y0, max: bounds.y1, ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => opts.yFmt(v) } },
    series: [
      {
        id: "guides", type: "scatter", data: [], silent: true,
        markArea: opts.guides && opts.corners ? {
          silent: true, itemStyle: { color: "transparent" },
          data: [
            [{ coord: [bounds.x0, opts.guides.y], label: cornerLabel(opts.corners[0], "insideTopLeft") }, { coord: [opts.guides.x, bounds.y1] }],
            [{ coord: [opts.guides.x, opts.guides.y], label: cornerLabel(opts.corners[1], "insideTopRight"),
               itemStyle: { color: t.dark ? "rgba(86,182,203,0.07)" : "rgba(14,102,121,0.05)" } }, { coord: [bounds.x1, bounds.y1] }],
            [{ coord: [bounds.x0, bounds.y0], label: cornerLabel(opts.corners[2], "insideBottomLeft") }, { coord: [opts.guides.x, opts.guides.y] }],
            [{ coord: [opts.guides.x, bounds.y0], label: cornerLabel(opts.corners[3], "insideBottomRight") }, { coord: [bounds.x1, opts.guides.y] }],
          ] as never,
        } : undefined,
        markLine: opts.guides ? { silent: true, symbol: "none", lineStyle: { color: t.axis, width: 1, type: "solid" }, label: { show: false },
                                  data: [{ xAxis: opts.guides.x }, { yAxis: opts.guides.y }] } : undefined,
      },
      {
        id: "pts", type: "scatter",
        data: points.map((p) => ({
          value: [p.x, p.y], name: p.name,
          symbolSize: 7 + 17 * Math.sqrt(p.size / maxSize),
          itemStyle: { color: opts.selected && opts.selected !== p.name ? t.deemph : t.series[0], borderColor: t.surface, borderWidth: 2, opacity: 0.92 },
        })),
        label: { show: true, formatter: "{b}", position: "right", fontSize: 11.5, color: t.ink2 },
        labelLayout: { hideOverlap: true },
        emphasis: { focus: "self", label: { color: t.ink, fontWeight: 700 } },
      },
    ],
  } as EChartsOption;
}

// ------------------------------------------------------------------------------------------
// Emphasis scatter (UMAP personas): one group in the accent, the rest recede
// ------------------------------------------------------------------------------------------
export function emphasisScatterOption(points: { x: number; y: number; g: number }[], active: number | null, t: Tokens, names: Record<number, string>): EChartsOption {
  const rest = points.filter((p) => active === null || p.g !== active);
  const focus = active === null ? [] : points.filter((p) => p.g === active);
  return {
    ...base(t),
    grid: { left: 4, right: 4, top: 4, bottom: 4 },
    tooltip: { show: false },
    xAxis: { type: "value", show: false, scale: true },
    yAxis: { type: "value", show: false, scale: true },
    series: [
      { id: "rest", type: "scatter", data: rest.map((p) => [p.x, p.y]), symbolSize: 3.5, large: true,
        itemStyle: { color: active === null ? t.series[0] : t.deemph, opacity: active === null ? 0.35 : 0.5 }, silent: true },
      { id: "focus", type: "scatter", data: focus.map((p) => [p.x, p.y]), symbolSize: 4.5, large: true,
        itemStyle: { color: t.series[0], opacity: 0.85 }, silent: true, name: active === null ? "" : names[active] },
    ],
  } as EChartsOption;
}

// ------------------------------------------------------------------------------------------
// Sankey: churn flows from a technology (left) to the one its leavers want (right)
// ------------------------------------------------------------------------------------------
export function churnSankeyOption(flows: { from_tech: string; to_tech: string; n: number; share_of_churners: number }[], order: string[], t: Tokens): EChartsOption {
  const colorOf = new Map(order.map((tech, i) => [tech, t.series[i % 8]]));
  const left = [...new Set(flows.map((f) => f.from_tech))];
  const right = [...new Set(flows.map((f) => f.to_tech))];
  const nodes = [
    ...left.map((n) => ({ name: `from:${n}`, itemStyle: { color: colorOf.get(n) ?? t.series[0], borderColor: t.surface, borderWidth: 1 } })),
    ...right.map((n) => ({ name: `to:${n}`, itemStyle: { color: t.ink3, borderColor: t.surface, borderWidth: 1 } })),
  ];
  return {
    ...base(t),
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (p: { dataType: string; data: { source?: string; target?: string; value?: number; share?: number }; name: string; value: number }) => {
        if (p.dataType === "edge") {
          const s = p.data.source!.slice(5);
          const d = p.data.target!.slice(3);
          return ttTitle(`${s} to ${d}`) + ttRow(colorOf.get(s) ?? null, "Developers", (p.data.value ?? 0).toLocaleString()) +
            ttRow(null, `Share of ${s} leavers`, pct(p.data.share ?? 0, 0)) + ttEnd;
        }
        const [side, name] = [p.name.split(":")[0], p.name.split(":").slice(1).join(":")];
        return ttTitle(name) + ttRow(null, side === "from" ? "Leavers shown" : "Arrivals shown", Math.round(p.value).toLocaleString()) + ttEnd;
      },
    }),
    series: [{
      id: "sankey", type: "sankey", left: 8, right: 120, top: 8, bottom: 8, nodeWidth: 12, nodeGap: 10, draggable: false,
      layoutIterations: 64, emphasis: { focus: "adjacency" },
      data: nodes,
      links: flows.map((f) => ({ source: `from:${f.from_tech}`, target: `to:${f.to_tech}`, value: f.n, share: f.share_of_churners,
                                 lineStyle: { color: colorOf.get(f.from_tech) ?? t.series[0], opacity: t.dark ? 0.42 : 0.3 } })),
      label: { color: t.ink, fontSize: 12, fontFamily: t.font, formatter: (p: { name: string }) => p.name.split(":").slice(1).join(":") },
      lineStyle: { curveness: 0.5 },
    }],
  } as EChartsOption;
}

// ------------------------------------------------------------------------------------------
// Network: precomputed layout (spring layout in Python), communities as categories
// ------------------------------------------------------------------------------------------
export function networkOption(nodes: NetworkNode[], edges: { a: string; b: string; npmi: number; lift: number }[], t: Tokens, opts: {
  selected?: string | null; communityColor: (c: number) => string;
}): EChartsOption {
  const maxPrev = Math.max(...nodes.map((n) => n.prevalence));
  const labelFloor = [...nodes].sort((a, b) => b.prevalence - a.prevalence)[Math.min(34, nodes.length - 1)]?.prevalence ?? 0;
  const neighbours = new Set<string>();
  if (opts.selected) edges.forEach((e) => {
    if (e.a === opts.selected) neighbours.add(e.b);
    if (e.b === opts.selected) neighbours.add(e.a);
  });
  const lit = (name: string) => !opts.selected || name === opts.selected || neighbours.has(name);
  return {
    ...base(t),
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (p: { dataType: string; data: NetworkNode & { source?: string; target?: string; lift?: number; npmi?: number } }) => {
        if (p.dataType === "edge") {
          return ttTitle(`${p.data.source} and ${p.data.target}`) + ttRow(null, "Lift", `${fixed(p.data.lift ?? 0, 1)}×`) +
            ttRow(null, "Normalised PMI", fixed(p.data.npmi ?? 0, 2)) + ttEnd;
        }
        const n = p.data;
        return ttTitle(n.tech) + ttRow(opts.communityColor(n.community), n.community_label, "", "dot") +
          ttRow(null, "Used by", pct(n.prevalence)) + ttRow(null, "Strong ties", String(n.degree)) +
          ttRow(null, "Bridge score", fixed(n.betweenness, 3)) + ttEnd;
      },
    }),
    series: [{
      id: "net", type: "graph", layout: "none", roam: true, scaleLimit: { min: 0.6, max: 4 },
      left: 12, right: 12, top: 12, bottom: 12,
      data: nodes.map((n) => ({
        ...n, name: n.tech, x: n.x, y: n.y,
        symbolSize: 7 + 30 * Math.sqrt(n.prevalence / maxPrev),
        itemStyle: { color: opts.communityColor(n.community), borderColor: t.surface, borderWidth: 1.5, opacity: lit(n.tech) ? 1 : 0.3 },
        label: {
          show: n.prevalence >= labelFloor || n.tech === opts.selected || neighbours.has(n.tech),
          color: lit(n.tech) ? t.ink : t.ink3, fontWeight: n.tech === opts.selected ? 700 : 500,
        },
      })),
      links: edges.map((e) => ({
        source: e.a, target: e.b, lift: e.lift, npmi: e.npmi,
        lineStyle: {
          color: t.dark ? "#5b6b70" : "#9aa7a8", width: 0.6 + 2.2 * e.npmi,
          opacity: !opts.selected ? 0.35 : e.a === opts.selected || e.b === opts.selected ? 0.9 : 0.1,
        },
      })),
      label: { position: "right", fontSize: 11, fontFamily: t.font },
      labelLayout: { hideOverlap: true },
      emphasis: { focus: "adjacency", lineStyle: { opacity: 0.9 } },
      lineStyle: { curveness: 0.08 },
    }],
  } as EChartsOption;
}

// ------------------------------------------------------------------------------------------
// Waterfall (multiplicative SHAP contributions shown on a dollar axis)
// ------------------------------------------------------------------------------------------
export function waterfallOption(start: { label: string; value: number }, steps: { label: string; value: number }[], t: Tokens, fmt: (v: number) => string): EChartsOption {
  const ax = axisStyle(t);
  const labels = [start.label, ...steps.map((s) => s.label), "Estimate"];
  let running = start.value;
  const invisible: number[] = [start.value * 0];
  const bars: { value: number; itemStyle: { color: string; borderRadius: number } }[] = [{ value: start.value, itemStyle: { color: t.deemph, borderRadius: 3 } }];
  const deltas: number[] = [0];
  steps.forEach((s) => {
    const next = s.value;
    const lo = Math.min(running, next);
    invisible.push(lo);
    bars.push({ value: Math.abs(next - running), itemStyle: { color: next >= running ? t.div.pos2 : t.div.neg2, borderRadius: 3 } });
    deltas.push(next - running);
    running = next;
  });
  invisible.push(0);
  bars.push({ value: running, itemStyle: { color: t.series[0], borderRadius: 3 } });
  deltas.push(0);
  return {
    ...base(t),
    grid: { left: 8, right: 56, top: 8, bottom: 24, containLabel: true },
    tooltip: tooltip(t, {
      trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: t.dark ? "rgba(255,255,255,0.04)" : "rgba(15,42,51,0.04)" } },
      formatter: (params: { dataIndex: number }[]) => {
        const i = params[0].dataIndex;
        if (i === 0) return ttTitle(labels[0]) + ttRow(t.deemph, "Typical pay", fmt(start.value), "rect") + ttEnd;
        if (i === labels.length - 1) return ttTitle("Estimate") + ttRow(t.series[0], "Median estimate", fmt(running), "rect") + ttEnd;
        const d = deltas[i];
        return ttTitle(labels[i]) + ttRow(d >= 0 ? t.div.pos2 : t.div.neg2, d >= 0 ? "Adds" : "Subtracts", fmt(Math.abs(d)), "rect") +
          ttRow(null, "Running estimate", fmt(steps[i - 1].value)) + ttEnd;
      },
    }),
    xAxis: { type: "value", ...ax, axisLine: { show: false }, axisLabel: { ...ax.axisLabel, formatter: (v: number) => fmt(v) } },
    yAxis: { type: "category", data: labels, inverse: true, ...ax, splitLine: { show: false }, axisLabel: { ...ax.axisLabel, color: t.ink2, fontSize: 12 } },
    series: [
      { id: "base", type: "bar", stack: "w", data: invisible, itemStyle: { color: "transparent" }, barWidth: 14, silent: true },
      {
        id: "delta", type: "bar", stack: "w", data: bars, barWidth: 14,
        label: {
          show: true, position: "right", fontSize: 11, color: t.ink2,
          formatter: (p: { dataIndex: number }) => {
            const i = p.dataIndex;
            if (i === 0 || i === labels.length - 1) return fmt(i === 0 ? start.value : running);
            const d = deltas[i];
            return `${d >= 0 ? "+" : "−"}${fmt(Math.abs(d))}`;
          },
        },
      },
    ],
  } as EChartsOption;
}

export { inkOn };
