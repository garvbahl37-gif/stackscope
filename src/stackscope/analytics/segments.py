"""Developer personas — unsupervised segmentation of 2025 respondents by the stack they actually use.

Pipeline: binary respondent x technology matrix -> TF-IDF (down-weights ubiquitous tools such as
JavaScript or VS Code) -> TruncatedSVD (24 latent "stack" dimensions) -> L2 normalisation ->
spherical k-means. k is chosen by cosine silhouette within an interpretable range (6-10).

Clusters are named by matching their over-indexed technologies (lift) to archetype signatures with
an optimal one-to-one assignment (Hungarian algorithm), so names stay stable when the data is
refreshed. A 2-D UMAP projection of a stratified sample powers the dashboard scatter.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

from .. import settings

YEAR = 2025
MIN_TECHS = 3
MIN_PREVALENCE = 0.01
K_RANGE = range(6, 11)
N_COMPONENTS = 24

ARCHETYPES = {
    "Modern Web Builders": {"TypeScript", "React", "Next.js", "Node.js", "Vite", "pnpm", "Vercel", "Svelte", "Astro",
                            "Bun", "Supabase", "Netlify", "Vue.js", "Nuxt.js", "npm"},
    "Classic Web & PHP": {"PHP", "Laravel", "WordPress", "jQuery", "MySQL", "MariaDB", "Composer", "Symfony", "Drupal"},
    "Microsoft & .NET Enterprise": {"C#", "ASP.NET", "Microsoft SQL Server", "Visual Studio", "Microsoft Azure", "NuGet",
                                    "Blazor", "MSBuild", "PowerShell", "Rider", "Cosmos DB"},
    "JVM Backend Engineers": {"Java", "Spring", "Kotlin", "Maven", "Gradle", "IntelliJ IDEA", "Oracle", "Groovy", "Scala"},
    "Data & ML Practitioners": {"Python", "Jupyter", "PyCharm", "Pip", "Poetry", "BigQuery", "Snowflake", "Databricks",
                                "DuckDB", "R", "Julia", "FastAPI", "Flask", "Django"},
    "Cloud-Native & DevOps": {"Go", "Docker", "Kubernetes", "Terraform", "AWS", "Prometheus", "Datadog", "Ansible",
                              "Podman", "Google Cloud", "Splunk", "New Relic", "Bash/Shell"},
    "Systems & Embedded": {"C", "C++", "Assembly", "Rust", "Make", "Cargo", "Zig", "Lua", "MicroPython", "Ninja", "Neovim",
                           "Vim", "RustRover", "Ada", "Fortran"},
    "Mobile App Developers": {"Kotlin", "Swift", "Dart", "Xcode", "Android Studio", "Firebase", "Cloud Firestore",
                              "Firebase Realtime DB"},
    "AI-Native Builders": {"Cursor", "Claude Code", "Claude", "Windsurf", "Lovable", "Bolt", "Aider", "Cline / Roo",
                           "DeepSeek", "Zed"},
    "Game & Creative Coders": {"GDScript", "Lua", "C#", "Godot", "Unity"},
}


def load(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    usage = con.execute(f"""
        SELECT u.resp_key, t.tech, t.category FROM core.bridge_tech_usage AS u
        JOIN core.dim_technology AS t USING (tech_id)
        WHERE u.used AND u.survey_year = {YEAR}
    """).df()
    people = con.execute(f"""
        SELECT r.resp_key, r.dev_role, r.region, r.years_code, r.remote_work, r.ai_frequency, r.ai_use,
               r.in_pay_benchmark, r.comp_usd_real, w.weight
        FROM core.fact_respondent AS r JOIN core.respondent_weight AS w USING (resp_key)
        WHERE r.survey_year = {YEAR}
    """).df()
    return usage, people


def build_matrix(usage: pd.DataFrame) -> tuple[sparse.csr_matrix, np.ndarray, list[str]]:
    per_person = usage.groupby("resp_key").tech.nunique()
    keep_people = per_person[per_person >= MIN_TECHS].index
    usage = usage[usage.resp_key.isin(keep_people)]
    prevalence = usage.groupby("tech").resp_key.nunique() / len(keep_people)
    techs = sorted(prevalence[prevalence >= MIN_PREVALENCE].index)
    usage = usage[usage.tech.isin(techs)]
    people = np.array(sorted(usage.resp_key.unique()))
    row = np.searchsorted(people, usage.resp_key.to_numpy())
    col = np.searchsorted(np.array(techs), usage.tech.to_numpy())
    matrix = sparse.csr_matrix((np.ones(len(row)), (row, col)), shape=(len(people), len(techs)))
    matrix.data[:] = 1.0
    return matrix, people, techs


def embed(matrix: sparse.csr_matrix) -> np.ndarray:
    tfidf = TfidfTransformer(sublinear_tf=False).fit_transform(matrix)
    latent = TruncatedSVD(n_components=N_COMPONENTS, random_state=settings.RANDOM_SEED).fit_transform(tfidf)
    return normalize(latent)


def choose_k(latent: np.ndarray) -> tuple[int, pd.DataFrame, dict[int, KMeans]]:
    rng = np.random.default_rng(settings.RANDOM_SEED)
    sample = rng.choice(len(latent), size=min(8000, len(latent)), replace=False)
    rows, models = [], {}
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=10, random_state=settings.RANDOM_SEED).fit(latent)
        models[k] = km
        sil = silhouette_score(latent[sample], km.labels_[sample], metric="cosine")
        rows.append({"k": k, "silhouette": float(sil), "inertia": float(km.inertia_)})
    table = pd.DataFrame(rows)
    best = int(table.loc[table.silhouette.idxmax(), "k"])
    table["chosen"] = table.k == best
    return best, table, models


def name_clusters(lift: pd.DataFrame, prevalence: pd.DataFrame) -> dict[int, str]:
    clusters = list(lift.index)
    names = list(ARCHETYPES)
    score = np.zeros((len(clusters), len(names)))
    for i, c in enumerate(clusters):
        for j, name in enumerate(names):
            members = [t for t in ARCHETYPES[name] if t in lift.columns]
            if members:
                score[i, j] = sum(max(0.0, np.log(lift.loc[c, t])) * prevalence.loc[c, t] for t in members)
    rows, cols = linear_sum_assignment(-score)
    out = {}
    for r, c in zip(rows, cols, strict=True):
        cluster = clusters[r]
        if score[r, c] > 0.05:
            out[cluster] = names[c]
        else:
            top = lift.loc[cluster][prevalence.loc[cluster] >= 0.2].sort_values(ascending=False).head(2).index
            out[cluster] = "Generalists: " + " & ".join(top)
    for cluster in clusters:
        out.setdefault(cluster, "Generalists")
    return out


def run(con) -> dict:
    usage, people = load(con)
    matrix, keys, techs = build_matrix(usage)
    latent = embed(matrix)
    k, k_table, models = choose_k(latent)
    labels = models[k].labels_

    dense = pd.DataFrame(matrix.toarray(), columns=techs, index=keys)
    overall = dense.mean()
    prevalence = dense.groupby(labels).mean()
    lift = prevalence / overall
    names = name_clusters(lift, prevalence)

    ppl = people.set_index("resp_key").loc[keys].assign(segment_id=labels)
    total_w = ppl.weight.sum()
    profiles, tech_rows = [], []
    category = usage.drop_duplicates("tech").set_index("tech").category
    for seg, g in ppl.groupby("segment_id"):
        sig = (lift.loc[seg][prevalence.loc[seg] >= 0.2].sort_values(ascending=False).head(8))
        top_prev = prevalence.loc[seg].sort_values(ascending=False).head(8)
        role = g.dev_role.value_counts(normalize=True)
        pay = g.loc[g.in_pay_benchmark, "comp_usd_real"]
        profiles.append({
            "segment_id": int(seg), "name": names[seg], "respondents": len(g), "share_w": float(g.weight.sum() / total_w),
            "median_pay_real": float(pay.median()) if len(pay) >= 30 else None, "pay_n": int(len(pay)),
            "ai_daily": float((g.ai_frequency == "Daily").sum() / max(1, g.ai_use.notna().sum())),
            "remote_share": float((g.remote_work == "Remote").sum() / max(1, g.remote_work.notna().sum())),
            "median_years_code": float(g.years_code.median()),
            "top_role": role.index[0] if len(role) else None, "top_role_share": float(role.iloc[0]) if len(role) else None,
            "signature": ", ".join(sig.index), "most_used": ", ".join(top_prev.index),
        })
        for tech in techs:
            if prevalence.loc[seg, tech] >= 0.05:
                tech_rows.append({"segment_id": int(seg), "tech": tech, "category": category.get(tech),
                                  "prevalence": float(prevalence.loc[seg, tech]), "lift": float(lift.loc[seg, tech])})

    region_mix = (ppl.groupby(["segment_id", "region"]).weight.sum() / ppl.groupby("segment_id").weight.sum()).reset_index(name="share_w")

    # 2-D map of a stratified sample
    import umap  # noqa: PLC0415  (heavy import, only needed here)

    rng = np.random.default_rng(settings.RANDOM_SEED)
    idx = np.concatenate([rng.choice(np.where(labels == s)[0], size=min(700, int((labels == s).sum())), replace=False)
                          for s in np.unique(labels)])
    coords = umap.UMAP(n_neighbors=30, min_dist=0.25, metric="cosine", random_state=settings.RANDOM_SEED).fit_transform(latent[idx])
    points = pd.DataFrame({"x": coords[:, 0], "y": coords[:, 1], "segment_id": labels[idx]})

    outputs = {"segment_profile": pd.DataFrame(profiles), "segment_tech": pd.DataFrame(tech_rows),
               "segment_points": points, "segment_region": region_mix, "segment_model": k_table}
    for name, frame in outputs.items():
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    return {"k": k, "respondents": int(len(keys)), "technologies": len(techs),
            "silhouette": round(float(k_table.silhouette.max()), 3), "names": sorted(set(names.values()))}
