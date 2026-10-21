import type { EChartsOption } from "echarts";
import type { FeatureCollection } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import { echarts } from "../lib/echarts";
import type { Tokens } from "../lib/theme";
import { base, tooltip, ttEnd, ttRow, ttSub, ttTitle } from "./base";

let registered: Promise<void> | null = null;

type Ring = number[][];
/** A ring that crosses the antimeridian (Russia's Chukotka, Fiji) would be drawn as a stripe across the whole map;
 *  fold its far side onto the 180° meridian instead. */
function foldRing(ring: Ring): Ring {
  const crosses = ring.some((p, i) => i > 0 && Math.abs(p[0] - ring[i - 1][0]) > 180);
  return crosses ? ring.map(([x, y]) => [x < 0 ? 180 : x, y]) : ring;
}
function foldGeometry(g: { type: string; coordinates: unknown }) {
  if (g.type === "Polygon") return { ...g, coordinates: (g.coordinates as Ring[]).map(foldRing) };
  if (g.type === "MultiPolygon") return { ...g, coordinates: (g.coordinates as Ring[][]).map((poly) => poly.map(foldRing)) };
  return g;
}

/** Lazily load the 110m world atlas and register it with ECharts, keyed by ISO-3166 numeric id. */
export function ensureWorldMap(): Promise<void> {
  if (!registered) {
    registered = import("world-atlas/countries-110m.json").then((mod) => {
      const topo = (mod.default ?? mod) as unknown as Topology<{ countries: GeometryCollection }>;
      const geo = feature(topo, topo.objects.countries) as unknown as FeatureCollection;
      geo.features = geo.features
        .filter((f) => f.properties?.name !== "Antarctica")
        .map((f) => ({
          ...f,
          geometry: f.geometry ? foldGeometry(f.geometry as never) : f.geometry,
          properties: { ...(f.properties ?? {}), iso_n: String(Number(f.id)) },
        })) as FeatureCollection["features"];
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
      type: "continuous", min: q(0.02), max: q(0.98), left: 12, bottom: 12, itemWidth: 8, itemHeight: 120,
      inRange: { color: t.heat }, text: [fmt(q(0.98)), fmt(q(0.02))], textStyle: { color: t.ink2, fontSize: 11, fontWeight: 600 }, calculable: false,
    },
    series: [{
      id: "map", type: "map", map: "world", nameProperty: "iso_n", roam: true, scaleLimit: { min: 1, max: 6 },
      zoom: 1.12, center: [12, 18],
      itemStyle: { areaColor: t.mapNone, borderColor: t.surface, borderWidth: 0.7 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: t.inverse, borderColor: t.surface } },
      select: { disabled: true },
      data: rows.filter((r) => r.value != null).map((r) => ({ name: String(r.iso_numeric), value: r.value })),
    }],
  } as EChartsOption;
}
