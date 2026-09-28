import { ArrowDown, ArrowUp } from "lucide-react";
import { useMemo, useState } from "react";
import { inkOn } from "../charts/base";
import { type Column, DownloadButton, ErrorState, Loading, PageHeader, Panel } from "../components/ui";
import { type Blip, useRadar } from "../lib/api";
import { fixed, pct, signedPct } from "../lib/format";
import { useTokens } from "../lib/theme";

const SIZE = 720;
const C = SIZE / 2;
const R = 332;
const BLIP_R = 11;
const RINGS = ["Adopt", "Trial", "Assess", "Hold"] as const;
const RING_BANDS: Record<string, [number, number]> = { Adopt: [0.1, 0.39], Trial: [0.39, 0.61], Assess: [0.61, 0.8], Hold: [0.8, 0.985] };
// sector -> angular range in degrees (0 = east, counter-clockwise)
const SECTORS: Record<string, [number, number]> = {
  Frameworks: [0, 90], Languages: [90, 180], "Platforms & Tools": [180, 270], "Data & AI": [270, 360],
};
const RING_TEXT: Record<string, string> = {
  Adopt: "Mainstream and healthy: high adoption, momentum at or above the category average.",
  Trial: "Rising or holding momentum at mid-level adoption; proven in production for many teams.",
  Assess: "Small but pulling hard: low adoption, strong retention and attraction.",
  Hold: "Losing pull or in statistically significant decline; plan migrations deliberately.",
};

type Placed = Blip & { x: number; y: number; color: string };

function polar(r: number, deg: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [C + r * Math.cos(a), C - r * Math.sin(a)];
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

/** Deterministic, collision-free blip placement inside each sector x ring cell. */
function layout(blips: Blip[], colors: Record<string, string>): Placed[] {
  const placed: Placed[] = [];
  const cells = new Map<string, Blip[]>();
  blips.forEach((b) => cells.set(`${b.sector}|${b.ring}`, [...(cells.get(`${b.sector}|${b.ring}`) ?? []), b]));
  cells.forEach((items, key) => {
    const [sector, ring] = key.split("|");
    const [a0, a1] = SECTORS[sector];
    const [f0, f1] = RING_BANDS[ring];
    const candidates: [number, number][] = [];
    for (let ri = 0; ri < 6; ri++) {
      const r = R * (f0 + ((f1 - f0) * (ri + 0.5)) / 6);
      const pad = ((BLIP_R + 13) / r) * (180 / Math.PI);   // keep sector boundaries clear for ring labels
      for (let ai = 0; ai < 14; ai++) {
        const deg = a0 + pad + ((a1 - a0 - 2 * pad) * (ai + 0.5)) / 14;
        candidates.push(polar(r, deg));
      }
    }
    items.forEach((b) => {
      const order = [...candidates].sort((p, q) => hash(b.tech + p.join()) - hash(b.tech + q.join()));
      let best = order[0];
      let bestGap = -Infinity;
      for (const c of order) {
        const gap = Math.min(Infinity, ...placed.map((p) => Math.hypot(p.x - c[0], p.y - c[1])));
        if (gap > 2 * BLIP_R + 5) { best = c; bestGap = gap; break; }
        if (gap > bestGap) { best = c; bestGap = gap; }
      }
      placed.push({ ...b, x: best[0], y: best[1], color: colors[b.sector] });
    });
  });
  return placed;
}

function TrendMark({ trend }: { trend: string }) {
  if (trend === "Rising") return <ArrowUp size={13} aria-label="rising" style={{ color: "var(--good-ink)" }} />;
  if (trend === "Declining") return <ArrowDown size={13} aria-label="declining" style={{ color: "var(--critical)" }} />;
  return null;
}

const COLUMNS: Column<Blip>[] = [
  { key: "blip", label: "#", numeric: true },
  { key: "tech", label: "Technology" },
  { key: "sector", label: "Sector" },
  { key: "ring", label: "Ring" },
  { key: "share_used_w", label: "Adoption", numeric: true, render: (b) => pct(b.share_used_w), value: (b) => b.share_used_w },
  { key: "momentum", label: "Momentum (σ)", numeric: true, render: (b) => fixed(b.momentum), value: (b) => b.momentum },
  { key: "trend", label: "Multi-year trend" },
];

export default function RadarPage() {
  const t = useTokens();
  const { data, isError, error } = useRadar();
  const [hover, setHover] = useState<string | null>(null);
  const colors = useMemo(() => ({ Languages: t.series[0], Frameworks: t.series[1], "Data & AI": t.series[2], "Platforms & Tools": t.series[3] }) as Record<string, string>, [t]);
  const placed = useMemo(() => (data ? layout(data.blips, colors) : []), [data, colors]);
  const active = placed.find((b) => b.tech === hover) ?? null;

  return (
    <>
      <PageHeader
        title="Technology radar"
        lede="Where to invest, experiment, watch and retire. Every placement is computed from the 2024–2025 survey waves (adoption percentile, momentum and a multi-year significance test), not from opinion."
      />
      {isError ? <ErrorState error={error} /> : !data ? <Loading height={640} /> : (
        <div className="grid">
          {/* own grid, so the sticky radar stops where the lists end */}
          <div className="grid span-12 radar-layout">
            <Panel className="span-8 radar-panel" hero title="The 2025 radar" caption="Rings run from Adopt at the centre to Hold at the edge. Hover a blip or a list entry to compare."
                   tools={<DownloadButton columns={COLUMNS} rows={data.blips} filename="tech_radar.csv" />}>
              <div className="radar-wrap">
                <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="radar" role="img" aria-label="Technology radar with four sectors and four rings">
                  {[...RINGS].reverse().map((ring) => (
                    <circle key={ring} cx={C} cy={C} r={R * RING_BANDS[ring][1]} fill={ring === "Adopt" ? "var(--brand-soft)" : "none"}
                            fillOpacity={ring === "Adopt" ? 0.55 : 0} stroke="var(--line-strong)" strokeWidth={1} />
                  ))}
                  <line x1={C - R} y1={C} x2={C + R} y2={C} stroke="var(--line-strong)" strokeWidth={1} />
                  <line x1={C} y1={C - R} x2={C} y2={C + R} stroke="var(--line-strong)" strokeWidth={1} />
                  {RINGS.map((ring) => {
                    const [f0, f1] = RING_BANDS[ring];
                    return (
                      <text key={ring} x={C} y={C - R * ((f0 + f1) / 2) + 4} textAnchor="middle" className="radar__ring">{ring}</text>
                    );
                  })}
                  {Object.entries(SECTORS).map(([sector, [a0, a1]]) => {
                    const [x, y] = polar(R * 1.0, (a0 + a1) / 2);
                    const anchor = x < C ? "start" : "end";
                    return (
                      <text key={sector} x={x < C ? 14 : SIZE - 14} y={y < C ? 30 : SIZE - 18} textAnchor={anchor} className="radar__sector">
                        <tspan fill={colors[sector]}>●</tspan> {sector}
                      </text>
                    );
                  })}
                  {placed.map((b) => {
                    const isActive = b.tech === hover;
                    return (
                      <g key={b.tech} transform={`translate(${b.x} ${b.y})`} className="radar__blip" tabIndex={0}
                         onMouseEnter={() => setHover(b.tech)} onMouseLeave={() => setHover(null)}
                         onFocus={() => setHover(b.tech)} onBlur={() => setHover(null)}
                         aria-label={`${b.blip}. ${b.tech}, ${b.ring}`}>
                        <circle r={BLIP_R + 12} fill="transparent" />
                        <circle r={isActive ? BLIP_R + 3 : BLIP_R} fill={b.color} stroke="var(--surface)" strokeWidth={2}
                                opacity={hover && !isActive ? 0.35 : 1} />
                        <text textAnchor="middle" dy="0.35em" fill={inkOn(b.color)} className="radar__num">{b.blip}</text>
                      </g>
                    );
                  })}
                </svg>
                {active && (
                  <div className="radar__card" style={{ left: `${(active.x / SIZE) * 100}%`, top: `${(active.y / SIZE) * 100}%` }}>
                    <strong>{active.tech}</strong>
                    <span className="muted small">{active.ring} ring, {active.sector}</span>
                    <dl className="kv small" style={{ marginTop: 6 }}>
                      <dt>Adoption {active.survey_year}</dt><dd>{pct(active.share_used_w)}</dd>
                      <dt>Momentum</dt><dd>{fixed(active.momentum)} σ</dd>
                      <dt>Retention</dt><dd>{pct(active.retention_w, 0)}</dd>
                      <dt>Attraction</dt><dd>{pct(active.attraction_w, 0)}</dd>
                      <dt>Trend</dt><dd>{active.trend}{active.odds_growth != null ? ` (${signedPct(active.odds_growth, 0)}/yr)` : ""}</dd>
                    </dl>
                  </div>
                )}
              </div>
            </Panel>
            <div className="span-4 radar-lists">
              {Object.keys(SECTORS).sort().map((sector) => (
                <section key={sector} className="panel" style={{ padding: "14px 16px" }}>
                  <h2 className="panel__title"><span style={{ color: colors[sector] }}>●</span> {sector}</h2>
                  {RINGS.map((ring) => {
                    const items = placed.filter((b) => b.sector === sector && b.ring === ring).sort((a, b) => a.blip - b.blip);
                    if (!items.length) return null;
                    return (
                      <div key={ring} className="radar-list__ring">
                        <span className="tag">{ring}</span>
                        <ul>
                          {items.map((b) => (
                            <li key={b.tech} onMouseEnter={() => setHover(b.tech)} onMouseLeave={() => setHover(null)}
                                data-active={hover === b.tech || undefined}>
                              <span className="num muted">{b.blip}</span> {b.tech} <TrendMark trend={b.trend} />
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </section>
              ))}
            </div>
          </div>
          <Panel className="span-12" title="How the rings are assigned">
            <div className="ring-defs">
              {RINGS.map((ring) => <div key={ring}><span className="tag">{ring}</span><p className="small">{RING_TEXT[ring]}</p></div>)}
            </div>
            <p className="panel__foot">Momentum is the within-category z-score average of retention, attraction and wave-on-wave change. The multi-year trend is an inverse-variance weighted logistic trend with Benjamini-Hochberg control (arrows mark significant rises and declines). Up to 8 Adopt, 6 Trial, 5 Assess and 6 Hold blips are shown per sector.</p>
          </Panel>
        </div>
      )}
    </>
  );
}
