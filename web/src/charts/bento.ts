/** Overview bento charts: the heat-ramp stream, the spotlight line chart and the pay heat map. */
import type { EChartsOption } from "echarts";
import { escapeHtml } from "../lib/format";
import type { Tokens } from "../lib/theme";
import { base, tooltip } from "./base";

/** Horizontal heat gradient, lime on the left to red on the right. */
export function heatGradient(t: Tokens, alpha = 1) {
  const a = (hex: string) => (alpha === 1 ? hex : `${hex}${Math.round(alpha * 255).toString(16).padStart(2, "0")}`);
  return {
    type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
    colorStops: [
      { offset: 0, color: a(t.heat[0]) }, { offset: 0.4, color: a(t.heat[1]) },
      { offset: 0.72, color: a(t.heat[2]) }, { offset: 1, color: a(t.heat[3]) },
    ],
  };
}

export type StreamPoint = { year: number; core: number; halo: number };

/**
 * A band centred on zero whose thickness is the core share, inside a translucent halo for the wider share.
 * Years sit at their centres on a value axis padded by half a year, so the band bleeds to both edges.
 */
export function streamOption(points: StreamPoint[], marks: number[], t: Tokens): EChartsOption {
  const first = points[0], last = points[points.length - 1];
  const padded = [{ ...first, year: first.year - 0.5 }, ...points, { ...last, year: last.year + 0.5 }];
  const bound = (Math.max(...points.map((p) => p.halo)) / 2) * 1.12;
  // stackStrategy "all": the positive band must stack on the negative half-width base, not restart at zero
  const band = (id: string, stack: string, key: "core" | "halo", alpha: number) => [
    { id: `${id}-base`, type: "line" as const, stack, stackStrategy: "all", smooth: 0.35, symbol: "none", silent: true,
      lineStyle: { opacity: 0 }, data: padded.map((p) => [p.year, -p[key] / 2]) },
    { id, type: "line" as const, stack, stackStrategy: "all", smooth: 0.35, symbol: "none", silent: true,
      lineStyle: { opacity: 0 }, areaStyle: { color: heatGradient(t, alpha), opacity: 1 },
      data: padded.map((p) => [p.year, p[key]]) },
  ];
  return {
    ...base(t),
    animationDuration: 900,
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "value", min: first.year - 0.5, max: last.year + 0.5, show: false },
    yAxis: { type: "value", min: -bound, max: bound, show: false },
    series: [
      ...band("halo", "h", "halo", 0.28),
      ...band("core", "c", "core", 1),
      {
        id: "marks", type: "line", data: [], silent: true,
        markLine: {
          silent: true, symbol: "none", label: { show: false }, animation: false,
          lineStyle: { color: t.ink, width: 1, type: [3, 3], opacity: 0.7 },
          data: marks.map((y) => ({ xAxis: y })),
        },
      },
    ],
  } as EChartsOption;
}

export type SpotlightSeries = { name: string; points: { x: number; y: number | null }[] };

/**
 * One highlighted series on the heat gradient, the rest in gray, each ending in a pill label.
 * The tooltip leads with the highlighted value and its change on the year before.
 */
export function spotlightOption(series: SpotlightSeries[], highlight: string, t: Tokens, fmt: (v: number) => string,
                                delta: (d: number) => string): EChartsOption {
  const years = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const valueAt = (s: SpotlightSeries, x: number) => s.points.find((p) => p.x === x)?.y ?? null;
  const max = Math.max(...series.flatMap((s) => s.points.map((p) => p.y ?? 0)));
  const step = max > 0.5 ? 0.2 : 0.1;
  const ordered = [...series.filter((s) => s.name !== highlight), ...series.filter((s) => s.name === highlight)];
  const pill = (bg: string | object, glow: boolean) => ({
    show: true, formatter: "{a}", distance: 12, color: "#ffffff", fontFamily: t.font, fontSize: 12, fontWeight: 600,
    backgroundColor: bg, borderRadius: 999, padding: [5, 12], lineHeight: 15,
    ...(glow ? { shadowBlur: 18, shadowColor: "rgba(255,98,36,0.45)", shadowOffsetY: 6 } : {}),
  });
  return {
    ...base(t),
    grid: { left: 40, right: 112, top: 12, bottom: 26 },
    tooltip: tooltip(t, {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: t.ink, width: 1, type: [4, 4] }, z: 1 },
      formatter: (params: { dataIndex: number }[]) => {
        const i = params[0]?.dataIndex ?? 0;
        const x = years[i];
        const hi = series.find((s) => s.name === highlight)!;
        const v = valueAt(hi, x);
        const prev = i > 0 ? valueAt(hi, years[i - 1]) : null;
        const change = v != null && prev != null ? v - prev : null;
        const others = series.filter((s) => s.name !== highlight)
          .map((s) => `<div class="tt__row"><span></span><span class="tt__label">${escapeHtml(s.name)}</span><span class="tt__value">${(() => { const o = valueAt(s, x); return o == null ? "–" : escapeHtml(fmt(o)); })()}</span></div>`)
          .join("");
        return `<div class="tt"><div class="tt__big">${v == null ? "–" : escapeHtml(fmt(v))}${change == null ? "" : ` <span class="tt__delta${change < 0 ? " tt__delta--down" : ""}">${escapeHtml(delta(change))}</span>`}</div>` +
          `<div class="tt__sub" style="margin:0 0 6px">${escapeHtml(highlight)}, ${x}</div>${others}</div>`;
      },
    }),
    xAxis: {
      type: "category", data: years.map(String), boundaryGap: false,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: t.axisInk, fontSize: 11, fontFamily: t.font, margin: 12 },
    },
    yAxis: {
      type: "value", min: 0, max: Math.ceil(max / step) * step, interval: step,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: t.axisInk, fontSize: 11, fontFamily: t.font, formatter: (v: number) => fmt(v) },
      splitLine: { lineStyle: { color: t.grid } },
    },
    labelLayout: { moveOverlap: "shiftY" },
    series: ordered.map((s) => {
      const on = s.name === highlight;
      return {
        id: s.name, name: s.name, type: "line", smooth: 0.4, symbol: "circle", symbolSize: on ? 12 : 8, showSymbol: false,
        data: years.map((x) => valueAt(s, x)),
        lineStyle: { width: on ? 2.6 : 1.8, color: on ? heatGradient(t) : t.deemph },
        itemStyle: { color: t.surface, borderColor: on ? t.heat[2] : t.pillGrey, borderWidth: on ? 3 : 2 },
        emphasis: { disabled: true },
        endLabel: on
          ? pill({ type: "linear", x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: "#f97316" }, { offset: 1, color: "#e8401c" }] }, true)
          : pill(t.pillGrey, false),
        z: on ? 4 : 2,
      };
    }),
  } as EChartsOption;
}

export type PayCountry = { id: string; country: string; value: number };

/** World map on the heat ramp, low to high; hovering is reported to the card, which pins a callout. */
export function payHeatMapOption(rows: PayCountry[], t: Tokens, zoom: number): EChartsOption {
  const values = rows.map((r) => r.value).sort((a, b) => a - b);
  const q = (p: number) => values[Math.min(values.length - 1, Math.max(0, Math.round(p * (values.length - 1))))];
  return {
    ...base(t),
    visualMap: { show: false, type: "continuous", min: q(0.04), max: q(0.96), inRange: { color: t.heat } },
    series: [{
      id: "map", type: "map", map: "world", nameProperty: "iso_n", roam: "move", zoom,
      left: 58, right: 96, top: 6, bottom: 6,
      animationDurationUpdate: 400,
      itemStyle: { areaColor: t.mapNone, borderColor: t.surface, borderWidth: 0.7 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: t.inverse, borderColor: t.surface } },
      select: { disabled: true },
      data: rows.map((r) => ({ name: r.id, value: r.value })),
    }],
  } as EChartsOption;
}
