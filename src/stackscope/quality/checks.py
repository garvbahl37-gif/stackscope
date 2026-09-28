"""Automated data-quality checks, organised by DAMA dimension, persisted to dq.check_results.

Every pipeline run re-executes the suite; a failing "blocker" check stops the build (see cli.py).
Checks cover source reconciliation, integrity, completeness, validity, consistency, mapping coverage
and statistical-weighting health, plus a completeness matrix (field x year) for the dashboard.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import pandas as pd

from .. import settings
from ..harmonize.schema import SCHEMAS
from . import reconcile


@dataclass
class Check:
    check_id: str
    dimension: str          # Accuracy | Completeness | Consistency | Validity | Uniqueness | Integrity | Timeliness
    description: str
    metric: float
    threshold: str
    status: str             # pass | warn | fail
    blocker: bool
    detail: str


def _status(ok: bool, warn: bool = False) -> str:
    return "pass" if ok else ("warn" if warn else "fail")


def run_checks(con, reconciliation: pd.DataFrame | None = None) -> list[Check]:
    checks: list[Check] = []
    q = lambda sql: con.execute(sql).fetchone()  # noqa: E731

    # --- Accuracy: source reconciliation against published respondent counts ------------------
    counts = dict(con.execute("SELECT survey_year, respondents FROM core.dim_year").fetchall())
    for year, cfg in settings.sources()["survey"].items():
        expected = cfg["expected_rows"]
        actual = counts.get(int(year), 0)
        checks.append(Check(f"reconcile_{year}", "Accuracy", f"{year} respondent count matches the publisher's released file",
                            actual, f"= {expected:,}", _status(actual == expected), True,
                            f"loaded {actual:,} of {expected:,} released responses"))

    # --- Accuracy: reproduce Stack Overflow's own published results (unweighted, publisher's definitions) ----
    rec = reconciliation if reconciliation is not None else reconcile.compute(con)
    shares = rec[rec.unit == "pct"]
    same = shares[shares.same_base]
    with_count = rec[rec.status == "count matches"]
    problems = int((rec.status == "differs").sum())
    checks.append(Check("published_reconciliation", "Accuracy", "Figures reproduce Stack Overflow's published results",
                        float((same.status == "match").mean()) if len(same) else 1.0,
                        f"like-for-like within {reconcile.TOLERANCE_PP} pp", _status(problems == 0), False,
                        f"{len(same)} like-for-like figures within {same['diff'].abs().max():.2f} pp; {len(with_count)} shares on a "
                        f"larger published base confirmed by user counts; {problems} unexplained"))

    manifest_path = settings.RAW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    hashed = sum(1 for v in manifest.values() if v.get("sha256"))
    checks.append(Check("provenance_hashes", "Accuracy", "Every raw file has a recorded SHA-256 fingerprint",
                        hashed, f"= {len(settings.survey_years())}", _status(hashed == len(settings.survey_years())),
                        False, "raw files fingerprinted in data/raw/manifest.json"))

    # --- Uniqueness & integrity ---------------------------------------------------------------
    dup = q("SELECT count(*) - count(DISTINCT resp_key) FROM core.fact_respondent")[0]
    checks.append(Check("unique_respondent", "Uniqueness", "resp_key is unique in fact_respondent", dup, "= 0",
                        _status(dup == 0), True, f"{dup} duplicate keys"))
    orphans = q("SELECT count(*) FROM core.bridge_tech_usage b ANTI JOIN core.fact_respondent r USING (resp_key)")[0]
    checks.append(Check("fk_tech_usage", "Integrity", "Every technology-usage row references a respondent", orphans,
                        "= 0", _status(orphans == 0), True, f"{orphans} orphan rows"))
    orphan_tech = q("SELECT count(*) FROM core.bridge_tech_usage b ANTI JOIN core.dim_technology t USING (tech_id)")[0]
    checks.append(Check("fk_technology", "Integrity", "Every usage row references a known technology", orphan_tech,
                        "= 0", _status(orphan_tech == 0), True, f"{orphan_tech} unknown technology ids"))
    dup_usage = q("SELECT count(*) FROM (SELECT resp_key, tech_id FROM core.bridge_tech_usage GROUP BY ALL HAVING count(*) > 1)")[0]
    checks.append(Check("unique_usage", "Uniqueness", "One row per respondent x technology", dup_usage, "= 0",
                        _status(dup_usage == 0), True, f"{dup_usage} duplicated pairs"))

    # --- Completeness ---------------------------------------------------------------------------
    country = q("SELECT avg(CASE WHEN iso3 IS NOT NULL THEN 1.0 ELSE 0 END) FROM core.fact_respondent")[0]
    checks.append(Check("country_resolved", "Completeness", "Respondents resolved to an ISO-3166 country",
                        country, ">= 95%", _status(country >= 0.95), False,
                        "unresolved = no answer, 'Nomadic' or 'Other country'"))
    mapped = q("""SELECT sum(mentions) FILTER (WHERE status = 'mapped') / sum(mentions) FILTER (WHERE status <> 'excluded')
                  FROM dq.label_coverage""")[0]
    unmapped = q("SELECT count(DISTINCT raw_label) FROM dq.label_coverage WHERE status = 'unmapped'")[0]
    checks.append(Check("taxonomy_coverage", "Completeness", "Share of in-scope technology mentions mapped to the taxonomy",
                        mapped, ">= 99.5%", _status(mapped >= 0.995), True, f"{unmapped} unmapped raw labels"))

    # --- Validity ---------------------------------------------------------------------------------
    bad_share = q("""SELECT count(*) FROM mart.tech_year
                     WHERE share_used_w NOT BETWEEN 0 AND 1 OR retention_w NOT BETWEEN 0 AND 1
                        OR share_used_w_lo > share_used_w OR share_used_w_hi < share_used_w""")[0]
    checks.append(Check("share_bounds", "Validity", "All shares and intervals are valid probabilities (lo <= p <= hi)",
                        bad_share, "= 0", _status(bad_share == 0), True, f"{bad_share} invalid technology-year rows"))
    pay_valid = q("""SELECT avg(CASE WHEN comp_status = 'valid' THEN 1.0 ELSE 0 END)
                     FROM core.fact_respondent WHERE comp_usd_raw IS NOT NULL""")[0]
    checks.append(Check("pay_validity_rate", "Validity", "Reported salaries passing bounds + market-outlier screen",
                        pay_valid, ">= 90%", _status(pay_valid >= 0.9, pay_valid >= 0.85), False,
                        "screen: $1k-$1M and |modified z| <= 3.5 within country-year"))
    # explicit IS NOT NULL: DuckDB 1.5.6 returns 0.0 for a bare min() over this NULL-heavy column
    pay_range = q("SELECT min(comp_usd), max(comp_usd) FROM core.fact_respondent WHERE comp_usd IS NOT NULL")
    in_window = pay_range[0] is not None and pay_range[0] >= 1000 and pay_range[1] <= 1_000_000
    checks.append(Check("pay_bounds", "Validity", "Cleaned salaries inside the documented $1k-$1M window",
                        float(pay_range[1] or 0), "<= 1,000,000", _status(in_window), True,
                        f"min ${pay_range[0]:,.0f}, max ${pay_range[1]:,.0f}"))
    implausible = con.execute("""SELECT iso3, list(year ORDER BY year) AS years FROM core.fact_macro
                                 WHERE price_level_status = 'implausible' AND year >= 2017 GROUP BY iso3 ORDER BY iso3""").fetchall()
    used_bad = q("""SELECT count(*) FROM core.fact_respondent AS r
                    JOIN core.fact_macro AS m ON m.iso3 = r.iso3 AND m.year = r.survey_year
                    WHERE r.comp_ppp IS NOT NULL AND m.price_level NOT BETWEEN 0.10 AND 1.80""")[0]
    checks.append(Check("ppp_price_levels", "Validity",
                        "PPP conversions only use plausible price levels (0.10-1.80 x US)", used_bad, "= 0",
                        _status(used_bad == 0), True,
                        "withheld (official-rate distortion / unit mismatch): "
                        + "; ".join(f"{iso} {min(ys)}-{max(ys)}" for iso, ys in implausible)))
    extreme, n_ppp = q("""SELECT count(*) FILTER (WHERE comp_ppp > 2500000), count(*)
                          FROM core.fact_respondent WHERE comp_ppp IS NOT NULL""")
    checks.append(Check("extreme_ppp_pay", "Validity", "Self-reported pay above $2.5M in PPP terms is rare",
                        extreme / n_ppp, "<= 0.01%", _status(extreme / n_ppp <= 0.0001, True), False,
                        f"{extreme} salaries (medians and robust models are insensitive to them)"))
    dupes = q("""WITH sig AS (
                     SELECT resp_key, string_agg(tech_id::VARCHAR || CASE WHEN used THEN 'u' ELSE '' END
                                                 || CASE WHEN wanted THEN 'w' ELSE '' END, ',' ORDER BY tech_id) AS s
                     FROM core.bridge_tech_usage GROUP BY resp_key)
                 SELECT count(*) FROM (
                     SELECT row_number() OVER (PARTITION BY r.survey_year, r.iso3, r.comp_usd_raw, r.years_code, r.dev_role,
                                               r.ed_level, r.age_band, r.org_size, sig.s ORDER BY r.resp_key) AS rn
                     FROM core.fact_respondent AS r JOIN sig USING (resp_key) WHERE r.comp_usd_raw IS NOT NULL)
                 WHERE rn > 1""")[0]
    checks.append(Check("duplicate_submissions", "Uniqueness",
                        "Probable duplicate submissions (identical profile, pay and full tech signature)",
                        dupes, "<= 0.1% of salaried responses", _status(dupes <= 300), False,
                        f"{dupes} probable duplicates; demographic-only matching over-flags ~1,600 coincidental matches"))
    domain_2023 = q("""SELECT count(*) FROM core.fact_respondent
                       WHERE survey_year = 2023 AND ai_trust IS NOT NULL
                         AND ai_trust NOT IN ('Highly trust','Somewhat trust','Neither trust nor distrust','Somewhat distrust','Highly distrust')""")[0]
    trusted_2023 = q("SELECT count(ai_trust) FROM core.fact_respondent WHERE survey_year = 2023")[0]
    checks.append(Check("publisher_defect_2023_ai", "Validity",
                        "2023 AI-trust answers sit in the Likert domain (publisher swapped AIAcc/AIBen)",
                        domain_2023, "= 0", _status(domain_2023 == 0 and trusted_2023 > 30000), True,
                        f"{trusted_2023:,} trust answers recovered from the swapped column"))

    # --- Consistency ------------------------------------------------------------------------------
    incons = q("""SELECT avg(CASE WHEN years_pro > years_code + 1 THEN 1.0 ELSE 0 END)
                  FROM core.fact_respondent WHERE years_pro IS NOT NULL AND years_code IS NOT NULL""")[0]
    checks.append(Check("tenure_consistency", "Consistency", "Professional coding years do not exceed total coding years",
                        incons, "<= 2%", _status(incons <= 0.02, incons <= 0.05), False,
                        f"{incons:.2%} of answers are internally inconsistent (kept, flagged)"))
    teen_veterans = q("""SELECT avg(CASE WHEN age_band = 'Under 18' AND years_code > 15 THEN 1.0 ELSE 0 END)
                         FROM core.fact_respondent WHERE age_band IS NOT NULL AND years_code IS NOT NULL""")[0]
    checks.append(Check("age_experience_plausibility", "Consistency", "No implausible age/experience combinations",
                        teen_veterans, "<= 0.1%", _status(teen_veterans <= 0.001, teen_veterans <= 0.005), False,
                        "under-18s reporting 15+ years of coding"))

    # --- Statistical health -------------------------------------------------------------------------
    diag = con.execute("SELECT * FROM dq.weight_diagnostics").df()
    checks.append(Check("raking_converged", "Accuracy", "Raking converged for every survey year",
                        int(diag.converged.sum()), f"= {len(diag)}", _status(bool(diag.converged.all())), True,
                        f"max margin error {diag.max_margin_error.max():.1e}"))
    deff = float(diag.design_effect.max())
    checks.append(Check("design_effect", "Accuracy", "Weighting variance inflation (Kish design effect) stays moderate",
                        deff, "<= 1.5", _status(deff <= 1.5, deff <= 2.0), False,
                        f"design effect range {diag.design_effect.min():.2f}-{deff:.2f}"))

    # --- Timeliness -----------------------------------------------------------------------------------
    latest = max(counts)
    checks.append(Check("latest_wave", "Timeliness", "Latest published survey wave is loaded", latest,
                        f">= {settings.survey_years()[-1]}", _status(latest >= settings.survey_years()[-1]), False,
                        f"waves {min(counts)}-{latest}"))
    return checks


FIELDS = {
    "country": "iso3", "respondent type": "respondent_type", "employment": "employment", "education": "ed_level",
    "org size": "org_size", "remote work": "remote_work", "age": "age_band", "years coding": "years_code",
    "years coding (pro)": "years_pro", "work experience": "work_exp", "developer role": "dev_role",
    "salary (valid)": "comp_usd", "industry": "industry", "AI usage": "ai_use", "AI trust": "ai_trust",
}


def completeness_matrix(con) -> pd.DataFrame:
    exprs = ", ".join(f"avg(CASE WHEN {col} IS NOT NULL THEN 1.0 ELSE 0 END) AS \"{name}\"" for name, col in FIELDS.items())
    wide = con.execute(f"SELECT survey_year, {exprs} FROM core.fact_respondent GROUP BY 1 ORDER BY 1").df()
    long = wide.melt(id_vars="survey_year", var_name="field", value_name="completeness")
    long["asked"] = long.completeness > 0
    return long


def schema_notes() -> pd.DataFrame:
    return pd.DataFrame([{"survey_year": y, "note": n} for y, s in SCHEMAS.items() for n in s.notes])


def run(con) -> dict:
    reconciliation = reconcile.compute(con)
    checks = run_checks(con, reconciliation)
    frames = {"check_results": pd.DataFrame([asdict(c) for c in checks]), "published_reconciliation": reconciliation,
              "completeness": completeness_matrix(con), "schema_notes": schema_notes()}
    for name, frame in frames.items():
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE dq.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    status = frames["check_results"].status.value_counts().to_dict()
    blockers = [c.check_id for c in checks if c.blocker and c.status == "fail"]
    return {"checks": len(checks), **status, "blocking_failures": blockers}
