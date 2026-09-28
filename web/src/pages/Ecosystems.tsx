import { useMemo, useState } from "react";
import { networkOption } from "../charts/misc";
import { EChart } from "../components/EChart";
import { type Column, DataTable, DownloadButton, ErrorState, Loading, PageHeader, Panel, Segmented } from "../components/ui";
import { type NetworkNode, type Rules, useNetwork, useRules } from "../lib/api";
import { fixed, int, pct } from "../lib/format";
import { useTokens } from "../lib/theme";

type Rule = Rules["rules"][number];
const RULE_COLUMNS: Column<Rule>[] = [
  { key: "consequent", label: "Also uses" },
  { key: "confidence", label: "Confidence", numeric: true, render: (r) => pct(r.confidence, 0), value: (r) => r.confidence },
  { key: "lift", label: "Lift", numeric: true, render: (r) => `${fixed(r.lift, 1)}×`, value: (r) => r.lift },
  { key: "co_users", label: "Developers", numeric: true, render: (r) => int(r.co_users) },
];

export default function Ecosystems() {
  const t = useTokens();
  const [year, setYear] = useState(2025);
  const [selected, setSelected] = useState<string | null>("Rust");
  const net = useNetwork(year);
  const rules = useRules(selected, year);

  // communities are ranked by size; the eight largest take the categorical slots, any extra fold to gray
  const communityColor = useMemo(() => {
    return (c: number) => (c < 8 ? t.series[c] : t.deemph);
  }, [t]);
  const option = useMemo(() => (net.data ? networkOption(net.data.nodes, net.data.edges, t, { selected, communityColor }) : null),
    [net.data, t, selected, communityColor]);
  const events = useMemo(() => ({ click: (p: { dataType?: string; name?: string }) => p.dataType === "node" && p.name && setSelected(p.name) }), []);

  const communities = useMemo(() => {
    if (!net.data) return [];
    const byId = new Map<number, NetworkNode[]>();
    net.data.nodes.forEach((n) => byId.set(n.community, [...(byId.get(n.community) ?? []), n]));
    return [...byId.entries()].sort((a, b) => a[0] - b[0]).map(([id, nodes]) => ({
      id, label: nodes[0].community_label, members: nodes.sort((a, b) => b.prevalence - a.prevalence),
    }));
  }, [net.data]);
  const bridges = useMemo(() => [...(net.data?.nodes ?? [])].sort((a, b) => b.betweenness - a.betweenness).slice(0, 8), [net.data]);
  const node = net.data?.nodes.find((n) => n.tech === selected) ?? null;

  return (
    <>
      <PageHeader
        title="Technology ecosystems"
        lede="Which technologies travel together. Links join pairs used together far more often than chance would predict (lift and normalised PMI); modularity clustering then finds the ecosystems, and bridge scores show what connects them."
      />
      <div className="controls">
        <Segmented label="Survey wave" options={(net.data?.years ?? [2024, 2025]).map((y) => ({ value: y, label: String(y) }))}
                   value={year} onChange={(y) => setYear(y)} />
        <span className="small muted">2024 includes libraries and build tools; 2025 adds AI models and agents.</span>
      </div>
      {net.isError ? <ErrorState error={net.error} /> : (
        <div className="grid">
          <Panel className="span-8" hero stale={net.isPlaceholderData} title={`The ${year} technology graph`}
                 caption="Node size is adoption; colour is the ecosystem. Drag to pan, scroll to zoom, click a technology to isolate its neighbours."
                 table={net.data ? { columns: [
                   { key: "tech", label: "Technology" }, { key: "community_label", label: "Ecosystem" },
                   { key: "prevalence", label: "Adoption", numeric: true, render: (r: NetworkNode) => pct(r.prevalence), value: (r: NetworkNode) => r.prevalence },
                   { key: "degree", label: "Strong ties", numeric: true },
                   { key: "betweenness", label: "Bridge score", numeric: true, render: (r: NetworkNode) => fixed(r.betweenness, 3), value: (r: NetworkNode) => r.betweenness },
                 ], rows: net.data.nodes, filename: `network_nodes_${year}.csv` } : undefined}>
            {option ? <EChart option={option} height={640} renderer="canvas" events={events} label="Technology co-usage network" /> : <Loading height={640} />}
          </Panel>
          <div className="span-4" style={{ display: "grid", gap: 18, alignContent: "start" }}>
            <Panel title={selected ? `Developers who use ${selected}` : "Pick a technology"}
                   caption={node ? `${node.community_label} ecosystem; used by ${pct(node.prevalence)} of respondents; ${node.degree} strong ties.` : "Click a node in the graph."}
                   tools={rules.data ? <DownloadButton columns={RULE_COLUMNS} rows={rules.data.rules} filename={`rules_${selected}_${year}.csv`} /> : undefined}>
              {rules.data ? (
                rules.data.rules.length ? <DataTable columns={RULE_COLUMNS.filter((c) => c.key !== "co_users")} rows={rules.data.rules.slice(0, 12)} rowKey={(r) => r.consequent} maxHeight={380}
                                                     onRowClick={(r) => setSelected(r.consequent)} />
                  : <p className="small muted">No association rules pass the support, confidence and lift thresholds.</p>
              ) : selected ? <Loading height={200} /> : null}
              <p className="panel__foot">Confidence: share of {selected ?? "its"} users who also use it. Lift: how many times more likely than for a random developer.</p>
            </Panel>
            <Panel title="Bridge technologies" caption="Highest betweenness: the connectors between ecosystems.">
              <ol className="rank-list">
                {bridges.map((b) => (
                  <li key={b.tech}>
                    <button type="button" onClick={() => setSelected(b.tech)}>
                      <span className="legend__dot" style={{ background: communityColor(b.community) }} />{b.tech}
                    </button>
                    <span className="num muted">{fixed(b.betweenness, 3)}</span>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
          <Panel className="span-12" title="The ecosystems" caption="Communities found by Louvain modularity on the co-usage graph, named by their best-matching signature.">
            <div className="community-grid">
              {communities.map((c) => (
                <div key={c.id} className="community">
                  <h3><span className="legend__dot" style={{ background: communityColor(c.id) }} />{c.label}</h3>
                  <p className="small muted">{c.members.slice(0, 12).map((m) => m.tech).join(", ")}{c.members.length > 12 ? ` and ${c.members.length - 12} more` : ""}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
