import { useMemo, useState } from "react";
import { churnSankeyOption, labelledScatterOption } from "../charts/misc";
import { EChart } from "../components/EChart";
import { type Column, DataTable, DownloadButton, ErrorState, Loading, PageHeader, Panel, Segmented } from "../components/ui";
import { type Retention as RetentionData, useRetention } from "../lib/api";
import { int, pct } from "../lib/format";
import { useTokens } from "../lib/theme";

const CATS = [
  { value: "language", label: "Languages" }, { value: "database", label: "Databases" },
  { value: "cloud", label: "Cloud" }, { value: "webframe", label: "Web frameworks" },
  { value: "devops", label: "DevOps" }, { value: "ide", label: "IDEs" }, { value: "ai", label: "AI tools" },
];

type Leader = RetentionData["leaderboard"][number];
type Net = RetentionData["net"][number];

const LEADER_COLUMNS: Column<Leader>[] = [
  { key: "tech", label: "Technology" },
  { key: "adoption", label: "Adoption", numeric: true, render: (r) => pct(r.adoption), value: (r) => r.adoption },
  { key: "retention", label: "Retention", numeric: true, render: (r) => pct(r.retention, 0), value: (r) => r.retention },
  { key: "churn", label: "Churn intent", numeric: true, render: (r) => pct(r.churn, 0), value: (r) => r.churn },
  { key: "attraction", label: "Attraction", numeric: true, render: (r) => pct(r.attraction, 0), value: (r) => r.attraction },
  { key: "users_asked_want", label: "Users asked", numeric: true, render: (r) => int(r.users_asked_want) },
];

const NET_COLUMNS: Column<Net>[] = [
  { key: "from_tech", label: "From" },
  { key: "to_tech", label: "To" },
  { key: "flow_forward", label: "Moving across", numeric: true, render: (r) => int(r.flow_forward) },
  { key: "flow_backward", label: "Moving back", numeric: true, render: (r) => int(r.flow_backward) },
  { key: "net_flow", label: "Net", numeric: true, render: (r) => `+${int(r.net_flow)}` },
  { key: "net_ratio", label: "One-sidedness", numeric: true, render: (r) => pct(r.net_ratio, 0), value: (r) => r.net_ratio },
];

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
}

export default function Retention() {
  const t = useTokens();
  const [category, setCategory] = useState("language");
  const { data, isError, error, isPlaceholderData } = useRetention(category);

  const scatter = useMemo(() => {
    if (!data || data.leaderboard.length < 3) return null;
    const pts = data.leaderboard.filter((r) => r.adoption >= 0.01);
    return labelledScatterOption(
      pts.map((r) => ({ name: r.tech, x: r.retention, y: r.attraction, size: r.adoption, note: `Adoption ${pct(r.adoption)}` })), t,
      {
        xName: "Retention: users who want to keep it", yName: "Attraction: non-users who want it",
        xFmt: (v) => pct(v, 0), yFmt: (v) => pct(v, 0),
        guides: { x: median(pts.map((p) => p.retention)), y: median(pts.map((p) => p.attraction)) },
        corners: ["Leaky buckets", "Magnets", "At risk", "Loyal bases"],
      },
    );
  }, [data, t]);

  const sankey = useMemo(() => {
    if (!data || !data.flows.length) return null;
    const order = [...new Set(data.flows.map((f) => f.from_tech))];
    return churnSankeyOption(data.flows, order, t);
  }, [data, t]);

  return (
    <>
      <PageHeader
        title="Retention and churn"
        lede="Client-retention analytics applied to technologies. Retention is the share of a technology's users who want to keep using it next year; the rest are churn intent. Following each group of leavers shows where the market is moving."
      />
      <div className="controls">
        <Segmented label="Category" options={CATS} value={category} onChange={setCategory} />
      </div>
      {isError ? <ErrorState error={error} /> : !data ? <Loading height={520} /> : (
        <div className="grid">
          <Panel className="span-7" stale={isPlaceholderData} title={`Keep versus pull, ${data.year}`}
                 caption="Bubble size is adoption. Guides are the category medians; the top-right holds technologies that keep their users and win new ones."
                 table={{ columns: LEADER_COLUMNS, rows: data.leaderboard, filename: `retention_${category}.csv` }}>
            {scatter ? <EChart option={scatter} height={470} label="Retention versus attraction" /> : <p className="state">Not enough technologies with 300+ users for this view.</p>}
          </Panel>
          <Panel className="span-5" title="Retention leaderboard" caption="Technologies with at least 300 users asked about next year."
                 tools={<DownloadButton columns={LEADER_COLUMNS} rows={data.leaderboard} filename={`retention_${category}.csv`} />}>
            <DataTable columns={LEADER_COLUMNS.filter((c) => !["users_asked_want", "attraction"].includes(c.key))} rows={data.leaderboard} rowKey={(r) => r.tech} maxHeight={470} />
          </Panel>
          <Panel className="span-12" stale={isPlaceholderData} title="Where the leavers want to go"
                 caption="Churn flows for the technologies losing the most users: each band is developers who use the left technology, don't want it next year, and want the right one (which they don't use yet). Top five destinations per source."
                 table={{ columns: [
                   { key: "from_tech", label: "From" }, { key: "to_tech", label: "To" },
                   { key: "n", label: "Developers", numeric: true, render: (r: RetentionData["flows"][number]) => int(r.n) },
                   { key: "share_of_churners", label: "Share of leavers", numeric: true, render: (r: RetentionData["flows"][number]) => pct(r.share_of_churners, 0), value: (r: RetentionData["flows"][number]) => r.share_of_churners },
                 ], rows: data.flows, filename: `churn_flows_${category}.csv` }}>
            {sankey ? <EChart option={sankey} height={560} label="Churn flow sankey" /> : <p className="state">No churn flows above the reliability threshold for this category.</p>}
          </Panel>
          <Panel className="span-12" title="Net migration between pairs"
                 caption="Developers moving from A to B minus those moving from B to A. One-sidedness near 100% means the flow barely runs the other way."
                 tools={<DownloadButton columns={NET_COLUMNS} rows={data.net} filename={`net_migration_${category}.csv`} />}>
            <DataTable columns={NET_COLUMNS} rows={data.net} rowKey={(r) => `${r.from_tech}>${r.to_tech}`} maxHeight={420} />
          </Panel>
        </div>
      )}
    </>
  );
}
