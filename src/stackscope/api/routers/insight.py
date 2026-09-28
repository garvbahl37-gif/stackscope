"""Personas, ecosystem network, GenAI pulse and data quality."""

from __future__ import annotations

from fastapi import APIRouter

from ..db import cached

router = APIRouter(tags=["insight"])


@router.get("/segments")
def segments() -> dict:
    return {
        "profiles": cached("SELECT * FROM mart.segment_profile ORDER BY share_w DESC"),
        "technologies": cached("""SELECT * FROM mart.segment_tech WHERE lift >= 1.2 OR prevalence >= 0.3
                                  ORDER BY segment_id, lift DESC"""),
        "regions": cached("SELECT * FROM mart.segment_region WHERE region IS NOT NULL ORDER BY segment_id, share_w DESC"),
        "model": cached("SELECT * FROM mart.segment_model ORDER BY k"),
    }


@router.get("/segments/points")
def segment_points() -> dict:
    return {"points": cached("SELECT round(x, 3) AS x, round(y, 3) AS y, segment_id FROM mart.segment_points")}


@router.get("/network")
def network(year: int = 2025) -> dict:
    return {
        "year": year,
        "nodes": cached("SELECT * FROM mart.network_nodes WHERE survey_year = ? ORDER BY prevalence DESC", (year,)),
        "edges": cached("SELECT a, b, co_users, support, lift, npmi FROM mart.network_edges WHERE survey_year = ?", (year,)),
        "years": [r["survey_year"] for r in cached("SELECT DISTINCT survey_year FROM mart.network_nodes ORDER BY 1")],
    }


@router.get("/network/rules")
def rules(tech: str, year: int = 2025) -> dict:
    return {"tech": tech, "rules": cached("""SELECT consequent, co_users, support, confidence, lift FROM mart.assoc_rules
                                            WHERE antecedent = ? AND survey_year = ? ORDER BY lift DESC LIMIT 25""",
                                          (tech, year))}


@router.get("/ai")
def ai_pulse() -> dict:
    return {
        "years": cached("SELECT * FROM mart.ai_year ORDER BY survey_year"),
        "likert": cached("SELECT * FROM mart.ai_likert ORDER BY question, survey_year"),
        "tasks": cached("SELECT * FROM mart.ai_task_year ORDER BY survey_year, share_w DESC"),
        "segments": cached("SELECT * FROM mart.ai_segment ORDER BY survey_year, dimension, using_w DESC"),
        "drivers": cached("SELECT * FROM mart.ai_drivers ORDER BY model, variable, odds_ratio DESC"),
        "tools": cached("""SELECT tech, survey_year, share_used_w, retention_w FROM mart.tech_year
                           WHERE category = 'ai' AND share_used_w >= 0.02 ORDER BY survey_year, share_used_w DESC"""),
    }


@router.get("/quality")
def quality() -> dict:
    layers = cached("""
        SELECT 'bronze' AS layer, 'Raw survey files (9 CSVs)' AS object, sum(respondents) AS rows FROM core.dim_year
        UNION ALL SELECT 'silver', 'Harmonised respondents', count(*) FROM core.fact_respondent
        UNION ALL SELECT 'silver', 'Technology usage facts', count(*) FROM core.bridge_tech_usage
        UNION ALL SELECT 'silver', 'Question-answered facts', count(*) FROM core.bridge_answered
        UNION ALL SELECT 'gold', 'Technology-year KPI cube', count(*) FROM mart.tech_year
        UNION ALL SELECT 'gold', 'Pay benchmark cells', count(*) FROM mart.pay_benchmark
        UNION ALL SELECT 'gold', 'Churn-flow pairs', count(*) FROM mart.tech_switching
    """)
    coverage = cached("""SELECT survey_year, status, count(*) AS labels, sum(mentions) AS mentions
                         FROM dq.label_coverage GROUP BY ALL ORDER BY survey_year, status""")
    top_aliases = cached("""SELECT tech, count(DISTINCT raw_label) AS raw_labels, list(DISTINCT raw_label) AS labels,
                                   sum(mentions) AS mentions
                            FROM dq.label_coverage WHERE status = 'mapped' GROUP BY tech
                            HAVING count(DISTINCT raw_label) > 1 ORDER BY raw_labels DESC, mentions DESC LIMIT 14""")
    tables = cached("""SELECT schema_name, table_name, estimated_size AS rows, column_count FROM duckdb_tables()
                       ORDER BY schema_name, table_name""")
    return {
        "checks": cached("SELECT * FROM dq.check_results"),
        "completeness": cached("SELECT * FROM dq.completeness ORDER BY field, survey_year"),
        "weights": cached("SELECT * FROM dq.weight_diagnostics ORDER BY survey_year"),
        "targets": cached("SELECT * FROM dq.weight_targets"),
        "schema_notes": cached("SELECT * FROM dq.schema_notes ORDER BY survey_year"),
        "layers": layers, "coverage": coverage, "aliases": top_aliases, "tables": tables,
    }
