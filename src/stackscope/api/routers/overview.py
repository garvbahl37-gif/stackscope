"""Metadata, executive overview and key findings."""

from __future__ import annotations

import json

from fastapi import APIRouter

from ... import settings
from ..db import cached

router = APIRouter(tags=["overview"])


@router.get("/meta")
def meta() -> dict:
    years = [r["survey_year"] for r in cached("SELECT survey_year FROM core.dim_year ORDER BY 1")]
    categories = cached("""SELECT category AS id, any_value(category_label) AS label, count(*) AS technologies
                           FROM core.dim_technology GROUP BY 1 ORDER BY technologies DESC""")
    technologies = cached("""SELECT tech, category, first_year, last_year, n_years, note FROM core.dim_technology
                             ORDER BY category, tech""")
    countries = cached("""SELECT c.iso3, c.country, c.region, count(*) AS respondents
                          FROM core.fact_respondent r JOIN core.dim_country c USING (iso3)
                          GROUP BY ALL ORDER BY respondents DESC""")
    regions = [r["region"] for r in cached("SELECT DISTINCT region FROM core.dim_country WHERE region IS NOT NULL ORDER BY 1")]
    manifest = settings.RAW_DIR / "manifest.json"
    sources = json.loads(manifest.read_text()) if manifest.exists() else {}
    return {"years": years, "categories": categories, "technologies": technologies, "countries": countries,
            "regions": regions, "sources": sources}


@router.get("/overview")
def overview() -> dict:
    kpis = cached("""
        SELECT
            (SELECT count(*) FROM core.fact_respondent)                                   AS respondents,
            (SELECT count(*) FROM core.dim_year)                                          AS waves,
            (SELECT count(DISTINCT iso3) FROM core.fact_respondent WHERE iso3 IS NOT NULL) AS countries,
            (SELECT count(*) FROM core.dim_technology)                                    AS technologies,
            (SELECT count(*) FROM core.bridge_tech_usage)                                 AS tech_observations,
            (SELECT count(*) FROM core.fact_respondent WHERE in_pay_benchmark)            AS pay_records,
            (SELECT sum(mentions) FROM dq.label_coverage)                                 AS raw_mentions,
            (SELECT count(DISTINCT raw_label) FROM dq.label_coverage)                     AS raw_labels,
            (SELECT count(*) FILTER (WHERE status = 'pass') FROM dq.check_results)        AS checks_passed,
            (SELECT count(*) FROM dq.check_results)                                       AS checks_total
    """)[0]
    findings = cached("SELECT * FROM mart.key_findings ORDER BY rank")
    by_year = cached("""SELECT y.survey_year, y.respondents, y.professionals, d.effective_n, d.design_effect
                        FROM core.dim_year y JOIN dq.weight_diagnostics d USING (survey_year) ORDER BY 1""")
    ai = cached("SELECT survey_year, using_w, trust_w, distrust_w FROM mart.ai_year ORDER BY 1")
    remote = cached("""SELECT survey_year, share_w FROM mart.workforce_mix
                       WHERE attribute = 'remote_work' AND category = 'Remote' ORDER BY 1""")
    pay = cached("SELECT survey_year, fixed_mix_median_real FROM mart.real_pay_trend ORDER BY 1")
    leaders = cached("""SELECT category, category_label, tech, share_used_w, momentum FROM mart.tech_quadrant
                        WHERE survey_year = (SELECT max(survey_year) FROM mart.tech_quadrant) AND quadrant = 'Leaders'
                        QUALIFY row_number() OVER (PARTITION BY category ORDER BY momentum DESC) <= 3
                        ORDER BY category, momentum DESC""")
    movers = cached("""SELECT tech, category, odds_growth, share_first, share_last, first_year, trend
                       FROM mart.tech_trend WHERE trend IN ('Rising', 'Declining') AND n_points >= 5
                       ORDER BY odds_growth DESC""")
    return {"kpis": kpis, "findings": findings, "by_year": by_year, "ai": ai, "remote": remote, "real_pay": pay,
            "leaders": leaders, "movers": movers}
