import type { EChartsOption } from "echarts";
import type { FeatureCollection } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import { echarts } from "../lib/echarts";
import type { Tokens } from "../lib/theme";
import { base, tooltip, ttEnd, ttRow, ttSub, ttTitle } from "./base";

let registered: Promise<void> | null = null;

/** Lazily load the 110m world atlas and register it with ECharts, keyed by ISO-3166 numeric id. */
export function ensureWorldMap(): Promise<void> {
  if (!registered) {
    registered = import("world-atlas/countries-110m.json").then((mod) => {
      const topo = (mod.default ?? mod) as unknown as Topology<{ countries: GeometryCollection }>;
      const geo = feature(topo, topo.objects.countries) as unknown as FeatureCollection;
      geo.features = geo.features
        .filter((f) => f.properties?.name !== "Antarctica")
        .map((f) => ({ ...f, properties: { ...(f.properties ?? {}), iso_n: String(Number(f.id)) } }));
      echarts.registerMap("world", geo as never);
    });
  }
  return registered;
}

export type MapRow = { iso_numeric: number; country: string; value: number | null; n: number; extra?: string };

export function choroplethOption(rows: MapRow[], t: Tokens, fmt: (v: number) => string, valueName: string): EChartsOption {
  const values = rows.map((r) => r.value).filter((v): v is number => v != null);
  const byId = new Map(rows.map((r) => [String(r.iso_numeric), r]));
  const sorted = [...values].sort((a, b) => a - b);
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.max(0, Math.round(p * (sorted.length - 1))))];
  return {
    ...base(t),
    tooltip: tooltip(t, {
      trigger: "item",
      formatter: (p: { name: string }) => {
        const r = byId.get(p.name);
        if (!r) return "";
        return ttTitle(r.country) + ttRow(null, valueName, r.value == null ? "fewer than 30 salaries" : fmt(r.value)) +
          ttSub(`${r.n.toLocaleString()} salaries${r.extra ? `, ${r.extra}` : ""}`) + ttEnd;
      },
    }),
    visualMap: {
      type: "continuous", min: q(0.02), max: q(0.98), left: 12, bottom: 12, itemWidth: 10, itemHeight: 120,
      inRange: { color: t.seq }, text: [fmt(q(0.98)), fmt(q(0.02))], textStyle: { color: t.ink3, fontSize: 11 }, calculable: false,
    },
    series: [{
      id: "map", type: "map", map: "world", nameProperty: "iso_n", roam: true, scaleLimit: { min: 1, max: 6 },
      zoom: 1.12, center: [12, 18],
      itemStyle: { areaColor: t.dark ? "#222c30" : "#e6ebea", borderColor: t.surface, borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: t.brand, borderColor: t.surface } },
      select: { disabled: true },
      data: rows.filter((r) => r.value != null).map((r) => ({ name: String(r.iso_numeric), value: r.value })),
    }],
  } as EChartsOption;
}
