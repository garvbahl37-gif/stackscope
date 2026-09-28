import { useMemo, useState } from "react";
import { simpleBarOption } from "../charts/bars";
import { emphasisScatterOption, heatmapOption } from "../charts/misc";
import { EChart } from "../components/EChart";
import { type Column, DataTable, ErrorState, Loading, PageHeader, Panel } from "../components/ui";
import { type Segments, useSegmentPoints, useSegments } from "../lib/api";
import { fixed, money, pct } from "../lib/format";
import { useTokens } from "../lib/theme";

type Profile = Segments["profiles"][number];

const MODEL_COLUMNS: Column<Segments["model"][number]>[] = [
  { key: "k", label: "Clusters (k)", numeric: true },
  { key: "silhouette", label: "Silhouette (cosine)", numeric: true, render: (r) => fixed(r.silhouette, 3), value: (r) => r.silhouette },
  { key: "inertia", label: "Inertia", numeric: true, render: (r) => fixed(r.inertia, 0) },
  { key: "chosen", label: "Chosen", render: (r) => (r.chosen ? "Yes" : "") },
];

export default function Personas() {
  const t = useTokens();
  const seg = useSegments();
  const pts = useSegmentPoints();
  const [active, setActive] = useState<number | null>(null);

  const names = useMemo(() => Object.fromEntries((seg.data?.profiles ?? []).map((p) => [p.segment_id, p.name])), [seg.data]);
  const scatter = useMemo(() => (pts.data ? emphasisScatterOption(pts.data.points.map((p) => ({ x: p.x, y: p.y, g: p.segment_id })), active, t, names) : null),
    [pts.data, active, t, names]);

  const heat = useMemo(() => {
    if (!seg.data) return null;
    const profiles = [...seg.data.profiles].sort((a, b) => b.share_w - a.share_w);
    // columns: each persona's three most over-indexed technologies (prevalence >= 25%)
    const picks: string[] = [];
    profiles.forEach((p) => {
      seg.data!.technologies.filter((r) => r.segment_id === p.segment_id && r.prevalence >= 0.25)
        .sort((a, b) => b.lift - a.lift).slice(0, 3).forEach((r) => !picks.includes(r.tech) && picks.push(r.tech));
    });
    const lookup = new Map(seg.data.technologies.map((r) => [`${r.segment_id}|${r.tech}`, r]));
    const cells = profiles.flatMap((p) => picks.map((tech) => {
      const r = lookup.get(`${p.segment_id}|${tech}`);
      return { x: tech, y: p.name, v: r ? r.prevalence : 0, label: r ? `${fixed(r.lift, 1)}× the average developer` : "under 5% use it" };
    }));
    return heatmapOption(picks, profiles.map((p) => p.name), cells, t, { fmt: (v) => pct(v, 0), min: 0, max: 1, valueName: "Use it", cellLabels: false });
  }, [seg.data, t]);

  const payBars = useMemo(() => {
    if (!seg.data) return null;
    const rows = seg.data.profiles.filter((p) => p.median_pay_real != null).sort((a, b) => (b.median_pay_real ?? 0) - (a.median_pay_real ?? 0));
    return simpleBarOption(rows.map((p) => ({ label: p.name, value: p.median_pay_real!, highlight: active === null || active === p.segment_id })), t, (v) => money(v));
  }, [seg.data, t, active]);

  if (seg.isError) return <><PageHeader title="Developer personas" /><ErrorState error={seg.error} /></>;
  const profiles = [...(seg.data?.profiles ?? [])].sort((a, b) => b.share_w - a.share_w);
  const chosen = seg.data?.model.find((m) => m.chosen);

  return (
    <>
      <PageHeader
        title="Developer personas"
        lede="Eight segments discovered from what 31,664 developers actually used in 2025, not from job titles. Each persona is a recognisable stack with its own pay, work style and appetite for AI."
      />
      {!seg.data ? <Loading height={600} /> : (
        <>
          <div className="persona-grid">
            {profiles.map((p: Profile) => (
              <button key={p.segment_id} type="button" className="persona" aria-pressed={active === p.segment_id}
                      onClick={() => setActive(active === p.segment_id ? null : p.segment_id)}>
                <span className="persona__share">{pct(p.share_w, 0)}</span>
                <span className="persona__name">{p.name}</span>
                <span className="persona__sig">{p.signature.split(", ").slice(0, 5).join(", ")}</span>
                <span className="persona__facts">
                  <span><strong>{p.median_pay_real ? money(p.median_pay_real) : "–"}</strong> median pay</span>
                  <span><strong>{pct(p.ai_daily, 0)}</strong> use AI daily</span>
                  <span><strong>{pct(p.remote_share, 0)}</strong> fully remote</span>
                </span>
                <span className="persona__role">Most common role: {p.top_role} ({pct(p.top_role_share, 0)})</span>
              </button>
            ))}
          </div>

          <div className="grid" style={{ marginTop: 18 }}>
            <Panel className="span-6" title={active === null ? "The persona map" : `Where ${names[active]} sit`}
                   caption="A UMAP projection of each respondent's stack: nearby points use similar technologies. Select a persona card to highlight it.">
              {scatter ? <EChart option={scatter} height={420} renderer="canvas" label="Persona map" /> : <Loading height={420} />}
            </Panel>
            <Panel className="span-6" title="Median pay by persona" caption="Full-time professionals in each persona, constant 2025 US dollars.">
              {payBars ? <EChart option={payBars} height={420} label="Median pay by persona" /> : <Loading height={420} />}
            </Panel>
            <Panel className="span-12" title="Signature technologies"
                   caption="Share of each persona using each technology; columns are the three most over-indexed technologies per persona."
                   table={{ columns: [
                     { key: "segment_id", label: "Persona", render: (r: Segments["technologies"][number]) => names[r.segment_id] },
                     { key: "tech", label: "Technology" },
                     { key: "prevalence", label: "Use it", numeric: true, render: (r: Segments["technologies"][number]) => pct(r.prevalence, 0), value: (r: Segments["technologies"][number]) => r.prevalence },
                     { key: "lift", label: "Lift", numeric: true, render: (r: Segments["technologies"][number]) => `${fixed(r.lift, 1)}×`, value: (r: Segments["technologies"][number]) => r.lift },
                   ], rows: seg.data.technologies, filename: "persona_technologies.csv" }}>
              {heat ? <EChart option={heat} height={430} label="Persona technology heatmap" /> : <Loading height={430} />}
            </Panel>
            <Panel className="span-12" title="How the personas were found"
                   caption={chosen ? `TF-IDF weighting of a respondent-by-technology matrix, 24-dimension truncated SVD, then spherical k-means. k = ${chosen.k} maximised the cosine silhouette (${fixed(chosen.silhouette, 3)}) among 6–10 clusters; names come from an optimal matching of each cluster's over-indexed technologies to archetype signatures.` : undefined}>
              <DataTable columns={MODEL_COLUMNS} rows={seg.data.model} rowKey={(r) => String(r.k)} />
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
