"""Skill-premium estimation: what is a technology worth on a pay cheque, other things equal?

Model (per scope: Global, United States, India, Western Europe), 2023-2025 full-time professional
developers with a validated salary who answered the language question:

    ln(pay, constant 2025 USD) = country FE + experience bands + role FE + org-size FE + education FE
                                 + work-arrangement FE + industry FE + survey-year FE
                                 + question-answered controls + sum_k beta_k * uses_tech_k + e

exp(beta_k) - 1 is the conditional pay premium associated with technology k. Standard errors are
heteroskedasticity-robust (HC1); p-values are Benjamini-Hochberg adjusted across technologies.
The raw (unadjusted) median premium is reported alongside to show how much the controls matter.
These are associations, not causal effects: a skill can proxy for unobserved seniority or sector.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .stats import benjamini_hochberg

YEARS = (2023, 2024, 2025)
CATEGORIES = ("language", "database", "cloud", "webframe", "devops")
MIN_PREVALENCE = 0.02
TOP_COUNTRIES = 40
SCOPES = {
    "Global": None,
    "United States": ("iso3", "USA"),
    "India": ("iso3", "IND"),
    "Western Europe": ("region", "Western Europe"),
}
EXPERIENCE_BINS = [0, 2, 4, 6, 8, 11, 16, 21, 26, 31, np.inf]
EXPERIENCE_LABELS = ["0-1", "2-3", "4-5", "6-7", "8-10", "11-15", "16-20", "21-25", "26-30", "31+"]


def load_sample(con) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    years = ", ".join(map(str, YEARS))
    cats = ", ".join(f"'{c}'" for c in CATEGORIES)
    people = con.execute(f"""
        SELECT r.resp_key, r.survey_year, r.iso3, r.region, r.dev_role, r.org_size, r.ed_level, r.remote_work,
               r.industry, r.years_code, ln(r.comp_usd_real) AS log_pay, r.comp_usd_real
        FROM core.fact_respondent AS r
        WHERE r.in_pay_benchmark AND r.survey_year IN ({years}) AND r.years_code IS NOT NULL
          AND r.resp_key IN (SELECT resp_key FROM core.bridge_answered WHERE field_group = 'language' AND side = 'used')
        ORDER BY r.resp_key
    """).df()
    # technologies asked in every modelled year (otherwise "not selected" would mean "not asked")
    eligible = con.execute(f"""
        SELECT t.tech FROM core.tech_year_group AS g JOIN core.dim_technology AS t USING (tech_id)
        WHERE g.survey_year IN ({years}) AND t.category IN ({cats})
        GROUP BY t.tech HAVING count(DISTINCT g.survey_year) = {len(YEARS)}
    """).df().tech.tolist()
    usage = con.execute(f"""
        SELECT u.resp_key, t.tech, t.category FROM core.bridge_tech_usage AS u
        JOIN core.dim_technology AS t USING (tech_id)
        WHERE u.used AND u.survey_year IN ({years}) AND t.category IN ({cats})
    """).df()
    usage = usage[usage.tech.isin(eligible)]
    answered = con.execute(f"""
        SELECT resp_key, field_group FROM core.bridge_answered
        WHERE side = 'used' AND survey_year IN ({years}) AND field_group IN ('database', 'platform', 'webframe', 'toolstech')
    """).df()
    people = people.merge(
        answered.assign(v=1).pivot_table(index="resp_key", columns="field_group", values="v", fill_value=0)
        .add_prefix("answered_").reset_index(), on="resp_key", how="left").fillna(
        {c: 0 for c in ["answered_database", "answered_platform", "answered_webframe", "answered_toolstech"]})
    return people, usage, eligible


def _design(people: pd.DataFrame, usage: pd.DataFrame, scope_countries: bool) -> tuple[pd.DataFrame, list[str]]:
    df = people.copy()
    if scope_countries:
        top = df.iso3.value_counts().head(TOP_COUNTRIES).index
        df["country_fe"] = np.where(df.iso3.isin(top), df.iso3, "Other " + df.region.fillna("Unknown"))
    df["exp_fe"] = pd.cut(df.years_code, EXPERIENCE_BINS, right=False, labels=EXPERIENCE_LABELS).astype(str)
    for col in ("dev_role", "org_size", "ed_level", "remote_work", "industry"):
        df[col] = df[col].fillna("Unknown")
    fe_cols = ["exp_fe", "dev_role", "org_size", "ed_level", "remote_work", "industry", "survey_year"]
    if scope_countries:
        fe_cols.insert(0, "country_fe")
    X = pd.get_dummies(df[fe_cols].astype(str), drop_first=True, dtype=float)
    answered_cols = [c for c in df.columns if c.startswith("answered_") and df[c].nunique() > 1]
    X[answered_cols] = df[answered_cols].astype(float)

    prevalence = usage.groupby("tech").resp_key.nunique() / len(df)
    techs = sorted(prevalence[prevalence >= MIN_PREVALENCE].index)
    flags = (usage[usage.tech.isin(techs)].assign(v=1.0)
             .pivot_table(index="resp_key", columns="tech", values="v", aggfunc="max", fill_value=0.0))
    flags = flags.reindex(df.resp_key).fillna(0.0).set_index(df.index)
    X = pd.concat([X, flags.add_prefix("tech::")], axis=1)
    X = sm.add_constant(X, has_constant="add")
    return X, techs


def estimate(people: pd.DataFrame, usage: pd.DataFrame, scope: str) -> tuple[pd.DataFrame, dict]:
    rule = SCOPES[scope]
    if rule:
        people = people[people[rule[0]] == rule[1]]
    usage = usage[usage.resp_key.isin(people.resp_key)]
    X, techs = _design(people, usage, scope_countries=rule is None or rule[0] == "region")
    y = people.log_pay.to_numpy()
    fit = sm.OLS(y, X).fit(cov_type="HC1")

    rows = []
    pay = people.set_index("resp_key").comp_usd_real
    for tech in techs:
        col = f"tech::{tech}"
        if col not in fit.params:
            continue
        users = usage.loc[usage.tech == tech, "resp_key"].unique()
        user_mask = pay.index.isin(users)
        coef, se = fit.params[col], fit.bse[col]
        rows.append({
            "scope": scope, "tech": tech, "category": usage.loc[usage.tech == tech, "category"].iloc[0],
            "n_users": int(user_mask.sum()), "prevalence": float(user_mask.mean()),
            "coef": coef, "se": se, "p_value": fit.pvalues[col],
            "premium": np.expm1(coef), "premium_lo": np.expm1(coef - 1.96 * se), "premium_hi": np.expm1(coef + 1.96 * se),
            "raw_premium": pay[user_mask].median() / pay[~user_mask].median() - 1,
        })
    out = pd.DataFrame(rows)
    out["q_value"] = benjamini_hochberg(out.p_value)
    out["significant"] = out.q_value < 0.05
    meta = {"scope": scope, "n": int(fit.nobs), "r2": float(fit.rsquared), "adj_r2": float(fit.rsquared_adj),
            "features": int(X.shape[1]), "technologies": len(techs), "years": "-".join(map(str, (YEARS[0], YEARS[-1]))),
            "median_pay_real": float(people.comp_usd_real.median())}
    return out, meta


def run(con) -> dict:
    people, usage, _ = load_sample(con)
    premiums, metas = [], []
    for scope in SCOPES:
        est, meta = estimate(people, usage, scope)
        premiums.append(est)
        metas.append(meta)
    for name, frame in (("skill_premium", pd.concat(premiums, ignore_index=True)), ("skill_premium_model", pd.DataFrame(metas))):
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    return {m["scope"]: {"n": m["n"], "r2": round(m["r2"], 3), "techs": m["technologies"]} for m in metas}
