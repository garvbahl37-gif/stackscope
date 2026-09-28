"""Drivers of GenAI adoption and trust (2025): survey-weighted logistic regressions.

Outcome 1: uses AI tools in the development process (all respondents who answered).
Outcome 2: trusts the accuracy of AI output (users only; "somewhat" or "highly" trust).
Predictors: coding experience, primary role, analysis region, organisation size, age band.
Binomial GLM with raking weights as variance weights and HC1 robust errors. Odds ratios are
relative to the reference level shown in the output; q-values are BH-adjusted within each model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .stats import benjamini_hochberg

YEAR = 2025
REFERENCE = {"exp_band": "6-10", "dev_role": "Full-stack developer", "region": "North America",
             "org_size": "100-499", "age_band": "25-34"}
TOP_ROLES = 12


def _design(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    roles = df.dev_role.value_counts().head(TOP_ROLES).index
    df["dev_role"] = df.dev_role.where(df.dev_role.isin(roles), "Other roles")
    parts = []
    for var, ref in REFERENCE.items():
        col = df[var].fillna("Unknown")
        dummies = pd.get_dummies(col, prefix=var, prefix_sep="=", dtype=float)
        parts.append(dummies.drop(columns=[f"{var}={ref}"], errors="ignore"))
    return sm.add_constant(pd.concat(parts, axis=1), has_constant="add")


def _fit(df: pd.DataFrame, outcome: pd.Series, name: str) -> pd.DataFrame:
    X = _design(df)
    model = sm.GLM(outcome.astype(float), X, family=sm.families.Binomial(), var_weights=df.weight).fit(cov_type="HC1")
    params, bse, pvalues = model.params.drop("const"), model.bse.drop("const"), model.pvalues.drop("const")
    out = pd.DataFrame({
        "model": name,
        "variable": [c.split("=", 1)[0] for c in params.index],
        "level": [c.split("=", 1)[1] for c in params.index],
        "odds_ratio": np.exp(params.to_numpy()),
        "or_lo": np.exp((params - 1.96 * bse).to_numpy()),
        "or_hi": np.exp((params + 1.96 * bse).to_numpy()),
        "p_value": pvalues.to_numpy(),
        "n_level": [int(X[c].sum()) for c in params.index],
    })
    out["reference"] = out.variable.map(REFERENCE)
    out["q_value"] = benjamini_hochberg(out.p_value)
    out["n_model"] = int(model.nobs)
    out["baseline_rate"] = float(np.average(outcome, weights=df.weight))
    return out[out.n_level >= 100]


def run(con) -> dict:
    df = con.execute(f"""
        SELECT r.ai_use, r.ai_trust_score, r.exp_band, r.dev_role, r.region, r.org_size, r.age_band, w.weight
        FROM core.fact_respondent AS r JOIN core.respondent_weight AS w USING (resp_key)
        WHERE r.survey_year = {YEAR} AND r.ai_use IS NOT NULL
    """).df()
    adoption = _fit(df, df.ai_use == "Using", "Uses AI tools")
    users = df[(df.ai_use == "Using") & df.ai_trust_score.notna()].reset_index(drop=True)
    trust = _fit(users, users.ai_trust_score > 0, "Trusts AI accuracy (users)")
    result = pd.concat([adoption, trust], ignore_index=True)
    con.register("_f", result)
    con.execute("CREATE OR REPLACE TABLE mart.ai_drivers AS SELECT * FROM _f")
    con.unregister("_f")
    return {"terms": len(result), "adoption_n": int(adoption.n_model.iloc[0]), "trust_n": int(trust.n_model.iloc[0])}
