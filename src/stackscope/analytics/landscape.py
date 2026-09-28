"""Market positioning — a data-driven, Magic-Quadrant-style view and a technology radar.

Quadrant axes (computed per category and year, only for technologies with >= 1,000 answerers and
>= 1% adoption):
  * Adoption  (y, "ability to execute" proxy): weighted share of respondents using the technology.
  * Momentum  (x, "completeness of vision" proxy): mean of within-category z-scores of
      - retention  (% of users who want to keep using it),
      - attraction (% of non-users who want to adopt it),
      - wave-on-wave change in adoption (log-odds).
Quadrants split at momentum 0 (category average) and the category's median adoption:
  Leaders (high/high), Challengers (high adoption, low momentum),
  Visionaries (low adoption, high momentum), Niche players (low/low).

Radar rings (latest wave per technology, 2024+): Adopt / Trial / Assess / Hold from adoption
percentile, momentum and the multi-year trend test (see `radar_ring`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import logit, zscore

MIN_BASE = 1000
MIN_ADOPTION = 0.01

RADAR_SECTORS = {
    "language": "Languages",
    "webframe": "Frameworks", "library": "Frameworks",
    "database": "Data & AI", "ai": "Data & AI",
    "cloud": "Platforms & Tools", "devops": "Platforms & Tools", "buildtool": "Platforms & Tools", "ide": "Platforms & Tools",
}
# Blips shown per sector and ring; within a ring the most decision-relevant technologies win
# (Adopt/Hold: highest adoption; Trial/Assess: strongest momentum).
RING_QUOTA = {"Adopt": 8, "Trial": 6, "Assess": 5, "Hold": 6}


def quadrant(tech_year: pd.DataFrame) -> pd.DataFrame:
    df = tech_year[(tech_year.base_n >= MIN_BASE) & (tech_year.share_used_w >= MIN_ADOPTION)].copy()
    df["yoy_logodds"] = logit(df.share_used_w) - logit(df.prev_share_used_w)
    parts = []
    for _, g in df.groupby(["survey_year", "category"]):
        if len(g) < 4:
            continue
        g = g.copy()
        comps = pd.DataFrame({
            "retention": zscore(g.retention_w) if g.retention_w.notna().sum() >= 3 else np.nan,
            "attraction": zscore(g.attraction_w) if g.attraction_w.notna().sum() >= 3 else np.nan,
            "change": zscore(g.yoy_logodds) if g.yoy_logodds.notna().sum() >= 3 else np.nan,
        }, index=g.index)
        g["momentum"] = comps.mean(axis=1, skipna=True).fillna(0.0)
        g["momentum_components"] = comps.notna().sum(axis=1)
        g["adoption_threshold"] = g.share_used_w.median()
        high_adopt = g.share_used_w >= g.adoption_threshold
        high_mom = g.momentum >= 0
        g["quadrant"] = np.select(
            [high_adopt & high_mom, high_adopt & ~high_mom, ~high_adopt & high_mom],
            ["Leaders", "Challengers", "Visionaries"], default="Niche players")
        g["adoption_pct_rank"] = g.share_used_w.rank(pct=True)
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    return out[["survey_year", "category", "category_label", "tech_id", "tech", "base_n", "share_used_w",
                "share_used_w_lo", "share_used_w_hi", "retention_w", "attraction_w", "net_desire_w", "yoy_logodds",
                "momentum", "momentum_components", "adoption_threshold", "adoption_pct_rank", "quadrant"]]


def radar_ring(adoption_pct: float, momentum: float, trend: str) -> str:
    """Hold: losing pull or in statistically significant decline. Adopt: mainstream and healthy.
    Assess: small but with strong pull. Trial: mid-adoption with positive momentum."""
    if momentum < -0.5 or (trend == "Declining" and momentum < 0.25):
        return "Hold"
    if adoption_pct >= 0.6 and momentum >= -0.25:
        return "Adopt"
    if adoption_pct < 0.4 and momentum >= 0.3:
        return "Assess"
    if momentum >= 0 or trend == "Rising":
        return "Trial"
    return "Hold"


def radar(quad: pd.DataFrame, trends: pd.DataFrame) -> pd.DataFrame:
    latest = quad[quad.survey_year >= 2024].sort_values("survey_year").groupby("tech_id").tail(1)
    latest = latest.merge(trends[["tech_id", "trend", "odds_growth", "q_value"]], on="tech_id", how="left")
    latest["trend"] = latest.trend.fillna("Insufficient history")
    latest["ring"] = [radar_ring(a, m, t) for a, m, t in zip(latest.adoption_pct_rank, latest.momentum, latest.trend, strict=True)]
    latest["sector"] = latest.category.map(RADAR_SECTORS)
    # Adopt: mainstream *and* healthy first; Hold: most-used first; Trial/Assess: strongest pull first
    by_ring = latest.groupby(["sector", "ring"])
    combined = by_ring.share_used_w.rank(pct=True) + by_ring.momentum.rank(pct=True)
    latest["relevance"] = np.select([latest.ring == "Adopt", latest.ring == "Hold"],
                                    [combined, latest.share_used_w], default=latest.momentum)
    picked = pd.concat(
        g.sort_values("relevance", ascending=False).head(RING_QUOTA[ring])
        for (_, ring), g in latest.groupby(["sector", "ring"]))
    ring_order = {"Adopt": 0, "Trial": 1, "Assess": 2, "Hold": 3}
    picked = picked.assign(ring_order=picked.ring.map(ring_order)).sort_values(["sector", "ring_order", "momentum"],
                                                                               ascending=[True, True, False])
    picked["blip"] = np.arange(1, len(picked) + 1)
    return picked[["blip", "sector", "category", "tech_id", "tech", "survey_year", "ring", "share_used_w", "momentum",
                   "retention_w", "attraction_w", "trend", "odds_growth", "adoption_pct_rank"]]


def run(con) -> dict[str, int]:
    tech_year = con.execute("SELECT * FROM mart.tech_year").df()
    trends = con.execute("SELECT * FROM mart.tech_trend").df()
    quad = quadrant(tech_year)
    rad = radar(quad, trends)
    for name, frame in (("tech_quadrant", quad), ("tech_radar", rad)):
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    return {"tech_quadrant": len(quad), "tech_radar": len(rad)}
