import type { EChartsOption } from "echarts";
import type { QuadrantPoint } from "../lib/api";
import { fixed, pct } from "../lib/format";
import type { Tokens } from "../lib/theme";
import { axisStyle, base, symmetricBound, tooltip, ttEnd, ttRow, ttSub, ttTitle } from "./base";

const Y_MIN = 0.01;
const Y_MAX = 1;

/**
 * Market-position quadrant for one category-year.
 * x = momentum (within-category z-score), y = adoption (log scale).
 * All technologies of the category keep a fixed slot in the data array so that
 * changing the year animates every dot to its new position.
 */
export function quadrantOption(all: QuadrantPoint[], year: number, t: Tokens, opts: {
  selected?: string | null;
  labelAll?: boolean;
  compact?: boolean;
} = {}): EChartsOption {
  const techs = [...new Set(all.map((p) => p.tech))].sort();
  const byKey = new Map(all.map((p) => [`${p.survey_year}|${p.tech}`, p]));
  const current = all.filter((p) => p.survey_year === year);
  const threshold = current[0]?.adoption_threshold ?? 0.05;
  const xb = symmetricBound(all.map((p) => p.momentum));
  const selected = opts.selected ?? null;
  const ax = axisStyle(t);

  const data = techs.map((tech) => {
    const p = byKey.get(`${year}|${tech}`);
    const isSel = tech === selected;
    if (!p) return { name: tech, value: ["-", "-"] };
    return {
      name: tech,
      value: [p.momentum, Math.max(Y_MIN, p.adoption)],
      symbolSize: isSel ? 15 : opts.compact ? 9 : 10,
      itemStyle: {
        color: selected ? (isSel ? t.series[0] : t.deemph) : t.series[0],
        borderColor: t.surface,
        borderWidth: 2,
      },
      label: {
        show: true,
        color: isSel ? t.ink : t.ink2,
        fontWeight: isSel ? 700 : 500,
      },
      z: isSel ? 10 : 2,
    };
  });

  // the selected technology's trajectory up to the current year
  const trail = selected
    ? all.filter((p) => p.tech === selected && p.survey_year <= year).sort((a, b) => a.survey_year - b.survey_year)
    : [];

  const quadrantLabel = (text: string, position: string) => ({
    show: true, position, color: t.ink3, fontSize: opts.compact ? 11.5 : 12.5, fontWeight: 650 as const,
    fontFamily: t.font, padding: [6, 8], formatter: text,
  });

  return {
    ...base(t),
    grid: { left: 54, right: 26, top: 18, bottom: 46 },
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (params: { name: string; seriesId?: string }) => {
        if (params.seriesId !== "techs") return "";
        const p = byKey.get(`${year}|${params.name}`);
        if (!p) return "";
        return ttTitle(`${p.tech}, ${year}`) +
          ttRow(null, "Position", p.quadrant) +
          ttRow(null, "Adoption", `${pct(p.adoption)} (${pct(p.adoption_lo)}–${pct(p.adoption_hi)})`) +
          ttRow(null, "Momentum", `${p.momentum >= 0 ? "+" : ""}${fixed(p.momentum)} σ`) +
          ttRow(null, "Retention", pct(p.retention, 0)) +
          ttRow(null, "Attraction", pct(p.attraction, 0)) +
          ttSub(`${p.base_n.toLocaleString()} respondents answered`) + ttEnd;
      },
    }),
    xAxis: {
      type: "value", min: -xb, max: xb, name: "Momentum  (retention, attraction, growth vs category)",
      nameLocation: "middle", nameGap: 28, ...ax,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => (v === 0 ? "avg" : `${v > 0 ? "+" : ""}${v}σ`) },
    },
    yAxis: {
      type: "log", logBase: 10, min: Y_MIN, max: Y_MAX, name: "Adoption", nameLocation: "middle", nameGap: 40, ...ax,
      axisLabel: { ...ax.axisLabel, formatter: (v: number) => `${Math.round(v * 100)}%` },
      minorTick: { show: false },
      minorSplitLine: { show: true, lineStyle: { color: t.grid, width: 1, opacity: 0.55 } },
    },
    series: [
      {
        id: "quadrants",
        type: "scatter",
        data: [],
        silent: true,
        markArea: {
          silent: true,
          itemStyle: { color: "transparent" },
          data: [
            [{ coord: [0, threshold], itemStyle: { color: t.dark ? "rgba(86,182,203,0.07)" : "rgba(14,102,121,0.05)" },
               label: quadrantLabel("Leaders", "insideTopRight") }, { coord: [xb, Y_MAX] }],
            [{ coord: [-xb, threshold], label: quadrantLabel("Challengers", "insideTopLeft") }, { coord: [0, Y_MAX] }],
            [{ coord: [0, Y_MIN], label: quadrantLabel("Visionaries", "insideBottomRight") }, { coord: [xb, threshold] }],
            [{ coord: [-xb, Y_MIN], label: quadrantLabel("Niche players", "insideBottomLeft") }, { coord: [0, threshold] }],
          ] as never,
        },
        markLine: {
          silent: true, symbol: "none", animation: false,
          lineStyle: { color: t.axis, width: 1, type: "solid" },
          label: { show: false },
          data: [{ xAxis: 0 }, { yAxis: threshold }],
        },
      },
      {
        id: "trail",
        type: "line",
        data: trail.map((p, i) => ({
          value: [p.momentum, Math.max(Y_MIN, p.adoption)], name: String(p.survey_year),
          label: { show: i === 0 && trail.length > 1 },   // label where the path starts; the dot names the end
        })),
        showSymbol: true,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { color: t.series[0], width: 2, opacity: 0.55 },
        itemStyle: { color: t.surface, borderColor: t.series[0], borderWidth: 2 },
        label: { show: true, formatter: "{b}", fontSize: 10, color: t.ink3, position: "top" },
        silent: true,
        z: 5,
        animationDurationUpdate: 300,
      },
      {
        id: "techs",
        type: "scatter",
        data,
        label: {
          show: true, formatter: "{b}", position: "right", distance: 6, fontSize: opts.compact ? 11 : 11.5,
          fontFamily: t.font,
        },
        labelLayout: { hideOverlap: !opts.labelAll },
        emphasis: { scale: 1.25, label: { color: t.ink, fontWeight: 700 } },
        z: 3,
      },
    ],
  } as EChartsOption;
}
