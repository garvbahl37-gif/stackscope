"""Adoption trends: which movements are real?

Two layers of evidence, both on composition-weighted shares with Kish effective sample sizes:
  1. Wave-on-wave change  — two-proportion z-test, Benjamini-Hochberg FDR across ~1,000 tests.
  2. Multi-year trajectory — inverse-variance WLS of logit(share) on year (quasi-likelihood SEs),
     reported as the annual growth in the odds of using the technology, with a 95% CI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import benjamini_hochberg, two_proportion_z, weighted_logit_trend

MIN_BASE = 1000  # suppress technology-years with fewer answerers


def yoy_tests(tech_year: pd.DataFrame) -> pd.DataFrame:
    df = tech_year[tech_year.prev_share_used_w.notna() & (tech_year.base_n >= MIN_BASE)].copy()
    z, p = two_proportion_z(df.prev_share_used_w, df.prev_base_n_eff, df.share_used_w, df.base_n_eff)
    df["delta_pp"] = 100 * (df.share_used_w - df.prev_share_used_w)
    df["z"] = z
    df["p_value"] = p
    df["q_value"] = benjamini_hochberg(p)
    df["significant"] = df.q_value < 0.05
    return df[["tech_id", "tech", "category", "survey_year", "prev_share_used_w", "share_used_w", "delta_pp",
               "z", "p_value", "q_value", "significant"]]


def trajectories(tech_year: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (tech_id, tech, category), g in tech_year[tech_year.base_n >= MIN_BASE].groupby(["tech_id", "tech", "category"]):
        g = g.sort_values("survey_year")
        full = weighted_logit_trend(g.survey_year, g.share_used_w, g.base_n_eff)
        recent = weighted_logit_trend(g.survey_year.tail(4), g.share_used_w.tail(4), g.base_n_eff.tail(4))
        first, last = g.iloc[0], g.iloc[-1]
        rows.append({
            "tech_id": tech_id, "tech": tech, "category": category,
            "first_year": int(first.survey_year), "last_year": int(last.survey_year), "n_points": full["n_points"],
            "share_first": first.share_used_w, "share_last": last.share_used_w,
            "change_pp": 100 * (last.share_used_w - first.share_used_w),
            "slope": full["slope"], "slope_se": full["se"], "p_value": full["p_value"],
            "recent_slope": recent["slope"], "recent_p_value": recent["p_value"],
        })
    out = pd.DataFrame(rows)
    out["q_value"] = benjamini_hochberg(out.p_value)
    out["odds_growth"] = np.expm1(out.slope)
    out["odds_growth_lo"] = np.expm1(out.slope - 1.96 * out.slope_se)
    out["odds_growth_hi"] = np.expm1(out.slope + 1.96 * out.slope_se)
    out["recent_odds_growth"] = np.expm1(out.recent_slope)
    out["trend"] = np.select(
        [out.n_points < 4, (out.q_value < 0.05) & (out.slope > 0), (out.q_value < 0.05) & (out.slope < 0)],
        ["Insufficient history", "Rising", "Declining"], default="Stable")
    return out


def run(con) -> dict[str, int]:
    tech_year = con.execute("SELECT * FROM mart.tech_year").df()
    yoy = yoy_tests(tech_year)
    traj = trajectories(tech_year)
    for name, frame in (("tech_yoy", yoy), ("tech_trend", traj)):
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    return {"tech_yoy": len(yoy), "tech_trend": len(traj),
            "significant_yoy": int(yoy.significant.sum()), "rising": int((traj.trend == "Rising").sum()),
            "declining": int((traj.trend == "Declining").sum())}
