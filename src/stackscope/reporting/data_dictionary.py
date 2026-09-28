"""Self-documenting warehouse: writes docs/data_dictionary.md from the live DuckDB catalog."""

from __future__ import annotations

from pathlib import Path

from .. import settings

DESCRIPTIONS = {
    "core.fact_respondent": "One row per survey response (664k). Harmonised demographics, work, pay (USD, constant-2025 USD, PPP) and GenAI attitudes.",
    "core.respondent_weight": "Raking weight per respondent: each wave matched to the average region x respondent-type x experience mix.",
    "core.bridge_tech_usage": "Respondent x technology facts: used this year / wants next year (canonical technology ids).",
    "core.bridge_answered": "Which technology question groups each respondent answered; the denominator of every share.",
    "core.tech_year_group": "Which question group(s) listed each technology in each year (technologies move between questions).",
    "core.bridge_role": "Respondent x developer role (multi-select years keep every role).",
    "core.bridge_ai_task": "Respondent x development task currently done with AI (2023+).",
    "core.dim_country": "ISO-3166 countries with analysis region, World Bank income group and capital coordinates.",
    "core.dim_technology": "309 canonical technologies with category, first/last year observed and series-break notes.",
    "core.dim_year": "Survey waves with respondent counts.",
    "core.dim_cpi": "US CPI-U annual averages and the factor to constant 2025 dollars.",
    "core.fact_macro": "Country-year PPP factor, exchange rate, price level (validated), GDP per capita and population.",
    "core.v_tech_usage": "Convenience view: usage facts with technology names.",
    "mart.tech_year": "Technology KPI cube: raw and weighted adoption with Wilson intervals, desire, retention, attraction, rank.",
    "mart.tech_yoy": "Wave-on-wave adoption changes with two-proportion tests and Benjamini-Hochberg q-values.",
    "mart.tech_trend": "Multi-year trajectory per technology: weighted logistic trend, annual odds growth with CI, verdict.",
    "mart.tech_quadrant": "Market-position quadrant per category and year (adoption vs momentum z-score).",
    "mart.tech_radar": "Technology radar blips (Adopt / Trial / Assess / Hold) for the latest waves.",
    "mart.tech_forecast": "Adoption history plus 2026-2027 projections with backtest-calibrated 80% intervals.",
    "mart.forecast_backtest": "Rolling-origin backtest of five forecasting models by horizon.",
    "mart.forecast_indicator": "Leading-indicator model coefficients (desire gap, retention, attraction, momentum).",
    "mart.tech_mindshare": "Each technology's share of usage mentions within its category and year.",
    "mart.market_concentration": "HHI, CR3/CR5, leader and structure per category-year.",
    "mart.tech_switching": "Churn flows: users leaving technology A who want technology B, with shares of leavers.",
    "mart.tech_net_migration": "Net migration between technology pairs (A->B minus B->A).",
    "mart.selection_intensity": "Mean options ticked per respondent per question and year (questionnaire-effect diagnostic).",
    "mart.pay_benchmark": "Pay percentiles by year across cuts (country, region, role, experience, company size, ...), n >= 30.",
    "mart.country_year": "Country profiles: respondents, pay, remote share, AI use, top language, reach per million people.",
    "mart.real_pay_trend": "Median real pay with a fixed country mix vs the raw median.",
    "mart.skill_premium": "Regression-adjusted pay premium per technology and market scope, with CIs and FDR q-values.",
    "mart.skill_premium_model": "Fit statistics of each skill-premium regression.",
    "mart.workforce_mix": "Weighted distribution of work arrangement, roles, experience, company size, education, age by year.",
    "mart.remote_by_region": "Remote / hybrid / in-person shares of professionals by region and year.",
    "mart.ai_year": "GenAI adoption, sentiment, trust and threat perception by year (weighted).",
    "mart.ai_likert": "Answer distributions for the GenAI Likert questions by year.",
    "mart.ai_segment": "GenAI adoption and trust by role, experience, region, company size and age.",
    "mart.ai_task_year": "Share using AI for each development task by year.",
    "mart.ai_drivers": "Odds ratios from survey-weighted logistic regressions of AI adoption and trust.",
    "mart.segment_profile": "Developer personas from stack clustering: size, pay, AI use, remote share, signature technologies.",
    "mart.segment_tech": "Technology prevalence and lift within each persona.",
    "mart.segment_points": "2-D UMAP coordinates of a stratified respondent sample (persona map).",
    "mart.segment_region": "Regional mix of each persona.",
    "mart.segment_model": "Silhouette and inertia for each candidate number of clusters.",
    "mart.network_nodes": "Technology co-usage graph nodes with community, degree, betweenness and layout coordinates.",
    "mart.network_edges": "Graph edges: co-usage counts, lift and normalised PMI.",
    "mart.assoc_rules": "Association rules A -> B with support, confidence and lift.",
    "mart.key_findings": "Evidence-backed headlines generated from the marts on every run.",
    "dq.check_results": "Automated data-quality checks by DAMA dimension with status and evidence.",
    "dq.completeness": "Share of respondents with a usable answer per field and wave.",
    "dq.label_coverage": "Every raw technology label per wave and question with its mapping outcome.",
    "dq.weight_diagnostics": "Raking convergence, design effect and effective sample size per wave.",
    "dq.weight_targets": "Reference composition used for raking.",
    "dq.schema_notes": "Per-wave schema changes handled during harmonisation.",
    "ml.salary_model_metrics": "Salary model evaluation on the held-out test split vs a country-year median baseline.",
    "ml.salary_feature_importance": "Mean absolute TreeSHAP contribution per feature.",
    "ml.salary_group_importance": "TreeSHAP importance aggregated into feature groups.",
}


def build(con, path: Path | None = None) -> Path:
    rows = con.execute("""
        SELECT c.schema_name, c.table_name, c.column_name, c.data_type, t.estimated_size
        FROM duckdb_columns() c LEFT JOIN duckdb_tables() t USING (schema_name, table_name)
        WHERE c.schema_name IN ('core', 'mart', 'dq', 'ml')
        ORDER BY c.schema_name, c.table_name, c.column_index""").fetchall()
    tables: dict[str, dict] = {}
    for schema, table, column, dtype, size in rows:
        key = f"{schema}.{table}"
        tables.setdefault(key, {"rows": size, "columns": []})["columns"].append((column, dtype))

    lines = ["# Data dictionary", "",
             "Generated from the live DuckDB catalog by `stackscope run --only reports`. Schemas: `core` (star schema),",
             "`mart` (analysis-ready aggregates), `dq` (data quality), `ml` (model evaluation).", ""]
    current = None
    for key, info in tables.items():
        schema = key.split(".")[0]
        if schema != current:
            lines += [f"## `{schema}`", ""]
            current = schema
        rows_txt = f"{info['rows']:,} rows" if info["rows"] is not None else "view"
        lines += [f"### `{key}`", "", f"{DESCRIPTIONS.get(key, '')} {rows_txt.capitalize()}.".strip(), "",
                  "| Column | Type |", "|---|---|"]
        lines += [f"| `{c}` | {t.lower()} |" for c, t in info["columns"]]
        lines.append("")
    path = path or settings.ROOT / "docs" / "data_dictionary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path
