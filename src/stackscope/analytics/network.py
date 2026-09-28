"""Technology ecosystem network and association rules (market-basket analysis on tech stacks).

For each wave (2024: richest taxonomy; 2025: latest), technologies used by >= 2% of respondents are
nodes. Pairwise co-usage is scored with lift and normalised PMI; each node keeps its strongest
edges (NPMI >= 0.08, lift >= 1.4, top 6 per node) so the graph shows real ecosystems rather than a
hairball. Louvain modularity finds communities; betweenness centrality identifies "bridge"
technologies that connect ecosystems. Association rules A -> B carry support, confidence and lift.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linear_sum_assignment

from .. import settings

YEARS = (2024, 2025)
MIN_PREVALENCE = 0.02
EDGES_PER_NODE = 6
MIN_NPMI = 0.08
MIN_LIFT = 1.4

# Communities are named by best one-to-one match (Hungarian) against these ecosystem signatures.
ECOSYSTEMS = {
    "JavaScript & Web": {"JavaScript", "TypeScript", "Node.js", "React", "npm", "Next.js", "Vite", "Angular", "Express",
                         "Yarn", "Webpack", "pnpm", "Vercel", "MongoDB"},
    "Python & Data/ML": {"Python", "Pip", "NumPy", "Pandas", "Jupyter", "PyTorch", "TensorFlow", "Scikit-learn", "FastAPI",
                         "Django", "Flask", "PyCharm", "Hugging Face Transformers", "Poetry"},
    "Microsoft & .NET": {"C#", ".NET", "Visual Studio", "Microsoft SQL Server", "Microsoft Azure", "ASP.NET", "NuGet",
                         "PowerShell", "Blazor", "MSBuild", "Chocolatey"},
    "Cloud-Native & DevOps": {"Docker", "Kubernetes", "Terraform", "AWS", "PostgreSQL", "Redis", "Go", "Prometheus",
                              "Ansible", "Apache Kafka", "RabbitMQ", "Podman", "Elasticsearch"},
    "JVM & Android": {"Java", "Kotlin", "Spring", "Maven", "Gradle", "IntelliJ IDEA", "Android Studio", "Groovy"},
    "PHP & LAMP": {"PHP", "MySQL", "Laravel", "WordPress", "jQuery", "MariaDB", "Composer", "Symfony", "PhpStorm"},
    "Systems & Unix": {"C", "C++", "Rust", "Make", "Bash/Shell", "Vim", "Neovim", "Assembly", "Lua", "Cargo", "APT", "Nano"},
    "Mobile (iOS & Flutter)": {"Swift", "Xcode", "Dart", "Flutter", "Firebase", "Cloud Firestore", "Firebase Realtime DB", "Homebrew"},
    "GenAI Assistants": {"ChatGPT / OpenAI", "Claude", "Google Gemini", "GitHub Copilot", "DeepSeek", "Cursor", "Meta Llama",
                         "Perplexity", "Codeium", "Claude Code"},
    "Data Platforms & Science": {"BigQuery", "Snowflake", "Databricks", "R", "MATLAB", "DuckDB", "Scala", "Julia", "InfluxDB"},
}


def name_communities(nodes: pd.DataFrame) -> dict[int, str]:
    comms = sorted(nodes.community.unique())
    names = list(ECOSYSTEMS)
    score = np.zeros((len(comms), len(names)))
    for i, c in enumerate(comms):
        members = nodes[nodes.community == c].set_index("tech").prevalence
        for j, name in enumerate(names):
            score[i, j] = members[members.index.isin(ECOSYSTEMS[name])].sum()
    rows, cols = linear_sum_assignment(-score)
    labels = {comms[r]: names[c] for r, c in zip(rows, cols, strict=True) if score[r, c] > 0}
    fallback = nodes.sort_values("prevalence", ascending=False).groupby("community").tech.first()
    return {c: labels.get(c, f"{fallback[c]} ecosystem") for c in comms}


def _matrix(con, year: int):
    usage = con.execute(f"""
        SELECT u.resp_key, t.tech, t.category FROM core.bridge_tech_usage AS u
        JOIN core.dim_technology AS t USING (tech_id)
        WHERE u.used AND u.survey_year = {year}
    """).df()
    n_people = usage.resp_key.nunique()
    prevalence = usage.groupby("tech").resp_key.nunique() / n_people
    techs = sorted(prevalence[prevalence >= MIN_PREVALENCE].index)
    usage = usage[usage.tech.isin(techs)]
    people = np.array(sorted(usage.resp_key.unique()))
    row = np.searchsorted(people, usage.resp_key.to_numpy())
    col = np.searchsorted(np.array(techs), usage.tech.to_numpy())
    X = sparse.csr_matrix((np.ones(len(row)), (row, col)), shape=(len(people), len(techs)))
    X.data[:] = 1.0
    category = usage.drop_duplicates("tech").set_index("tech").category.reindex(techs)
    return X, techs, category, n_people


def _pairs(X: sparse.csr_matrix, techs: list[str], n: int) -> pd.DataFrame:
    co = (X.T @ X).toarray()
    counts = np.diag(co).astype(float)
    p = counts / n
    i, j = np.triu_indices(len(techs), k=1)
    pij = co[i, j] / n
    with np.errstate(divide="ignore", invalid="ignore"):
        lift = pij / (p[i] * p[j])
        pmi = np.log(pij / (p[i] * p[j]))
        npmi = pmi / -np.log(pij)
    frame = pd.DataFrame({"a": np.array(techs)[i], "b": np.array(techs)[j], "co_users": co[i, j],
                          "support": pij, "lift": lift, "npmi": npmi,
                          "conf_a_b": co[i, j] / counts[i], "conf_b_a": co[i, j] / counts[j]})
    return frame[frame.co_users > 0]


def _prune(pairs: pd.DataFrame) -> pd.DataFrame:
    strong = pairs[(pairs.npmi >= MIN_NPMI) & (pairs.lift >= MIN_LIFT) & (pairs.co_users >= 100)]
    both = pd.concat([strong.rename(columns={"a": "node", "b": "other"}), strong.rename(columns={"b": "node", "a": "other"})])
    top = both.sort_values("npmi", ascending=False).groupby("node").head(EDGES_PER_NODE)
    keep = set(map(frozenset, zip(top.node, top.other, strict=True)))
    mask = [frozenset((a, b)) in keep for a, b in zip(strong.a, strong.b, strict=True)]
    return strong[mask]


def build(con, year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    X, techs, category, n = _matrix(con, year)
    pairs = _pairs(X, techs, n)
    edges = _prune(pairs)

    G = nx.Graph()
    prevalence = np.asarray(X.sum(axis=0)).ravel() / n
    for tech, prev in zip(techs, prevalence, strict=True):
        G.add_node(tech, prevalence=float(prev), category=category[tech])
    for e in edges.itertuples():
        G.add_edge(e.a, e.b, weight=float(e.npmi), distance=float(1 / e.npmi))
    G.remove_nodes_from([node for node in list(G.nodes) if G.degree(node) == 0])

    communities = nx.community.louvain_communities(G, weight="weight", resolution=1.0, seed=settings.RANDOM_SEED)
    community_of = {node: idx for idx, members in enumerate(sorted(communities, key=len, reverse=True)) for node in members}
    betweenness = nx.betweenness_centrality(G, weight="distance", normalized=True)
    layout = nx.spring_layout(G, weight="weight", seed=settings.RANDOM_SEED, k=1.6 / np.sqrt(G.number_of_nodes()), iterations=300)

    nodes = pd.DataFrame([{
        "survey_year": year, "tech": node, "category": G.nodes[node]["category"], "prevalence": G.nodes[node]["prevalence"],
        "community": community_of[node], "degree": G.degree(node), "betweenness": betweenness[node],
        "x": float(layout[node][0]), "y": float(layout[node][1]),
    } for node in G.nodes])
    nodes["community_label"] = nodes.community.map(name_communities(nodes))
    edge_frame = edges.assign(survey_year=year)[["survey_year", "a", "b", "co_users", "support", "lift", "npmi"]]

    rules = pd.concat([
        pairs.rename(columns={"a": "antecedent", "b": "consequent", "conf_a_b": "confidence"})[
            ["antecedent", "consequent", "co_users", "support", "confidence", "lift"]],
        pairs.rename(columns={"b": "antecedent", "a": "consequent", "conf_b_a": "confidence"})[
            ["antecedent", "consequent", "co_users", "support", "confidence", "lift"]],
    ])
    rules = rules[(rules.support >= 0.01) & (rules.confidence >= 0.3) & (rules.lift >= 1.3)].assign(survey_year=year)
    rules = rules.sort_values(["antecedent", "lift"], ascending=[True, False])
    return nodes, edge_frame, rules


def run(con) -> dict:
    out = {"network_nodes": [], "network_edges": [], "assoc_rules": []}
    for year in YEARS:
        nodes, edges, rules = build(con, year)
        out["network_nodes"].append(nodes)
        out["network_edges"].append(edges)
        out["assoc_rules"].append(rules)
    summary = {}
    for name, frames in out.items():
        frame = pd.concat(frames, ignore_index=True)
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _f")
        con.unregister("_f")
        summary[name] = len(frame)
    return summary
