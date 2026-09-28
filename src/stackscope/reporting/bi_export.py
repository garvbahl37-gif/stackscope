"""Power BI / Tableau pack: the star schema and key marts as Parquet, plus DAX measures and the model map."""

from __future__ import annotations

from pathlib import Path

from .. import settings

TABLES = {
    "fact_respondent": """SELECT resp_key, survey_year, iso3, region, income_group, respondent_type, employment, dev_role, exp_band,
                                 years_code, org_size, remote_work, ed_level, age_band, industry, ai_use, ai_frequency,
                                 ai_sentiment, ai_trust, ai_threat, comp_usd, comp_usd_real, comp_ppp, in_pay_benchmark
                          FROM core.fact_respondent""",
    "respondent_weight": "SELECT resp_key, weight FROM core.respondent_weight",
    "dim_country": "SELECT * FROM core.dim_country",
    "dim_technology": "SELECT * FROM core.dim_technology",
    "dim_year": "SELECT * FROM core.dim_year",
    "bridge_tech_usage": "SELECT * FROM core.bridge_tech_usage",
    "tech_year": "SELECT * FROM mart.tech_year",
    "tech_quadrant": "SELECT * FROM mart.tech_quadrant",
    "skill_premium": "SELECT * FROM mart.skill_premium",
    "pay_benchmark": "SELECT * FROM mart.pay_benchmark",
    "ai_year": "SELECT * FROM mart.ai_year",
}

MEASURES = """\
// StackScope DAX measures (Power BI). Load the Parquet files in this folder, then create the
// relationships listed in model.md. All measures respect slicers on year, country and technology.

Respondents = COUNTROWS ( fact_respondent )

Weighted respondents = SUM ( respondent_weight[weight] )

Median pay (USD) =
    CALCULATE ( MEDIAN ( fact_respondent[comp_usd] ), fact_respondent[in_pay_benchmark] = TRUE () )

Median pay (PPP) =
    CALCULATE ( MEDIAN ( fact_respondent[comp_ppp] ), fact_respondent[in_pay_benchmark] = TRUE () )

Median real pay (2025 USD) =
    CALCULATE ( MEDIAN ( fact_respondent[comp_usd_real] ), fact_respondent[in_pay_benchmark] = TRUE () )

Pay vs all countries =
    DIVIDE ( [Median pay (USD)], CALCULATE ( [Median pay (USD)], REMOVEFILTERS ( dim_country ) ) ) - 1

AI adoption % (weighted) =
    DIVIDE (
        CALCULATE ( [Weighted respondents], fact_respondent[ai_use] = "Using" ),
        CALCULATE ( [Weighted respondents], NOT ISBLANK ( fact_respondent[ai_use] ) )
    )

Technology users =
    CALCULATE ( DISTINCTCOUNT ( bridge_tech_usage[resp_key] ), bridge_tech_usage[used] = TRUE () )

// Adoption from the pre-computed KPI cube (correct denominators per question and year)
Adoption % = AVERAGE ( tech_year[share_used_w] )

Retention % = AVERAGE ( tech_year[retention_w] )

Adoption change vs previous wave (pp) =
    VAR thisYear = SELECTEDVALUE ( tech_year[survey_year] )
    VAR prev = CALCULATE ( [Adoption %], tech_year[survey_year] = thisYear - 1 )
    RETURN IF ( NOT ISBLANK ( prev ), ( [Adoption %] - prev ) * 100 )

Adoption rank in category =
    RANKX ( ALLSELECTED ( tech_year[tech] ), [Adoption %], , DESC, DENSE )
"""

MODEL = """\
# StackScope BI model

Star schema exported from the DuckDB warehouse.

| From (many) | To (one) | Key |
|---|---|---|
| fact_respondent | dim_country | iso3 |
| fact_respondent | dim_year | survey_year |
| respondent_weight | fact_respondent | resp_key (one-to-one) |
| bridge_tech_usage | fact_respondent | resp_key |
| bridge_tech_usage | dim_technology | tech_id |
| tech_year | dim_technology | tech_id |

`tech_year`, `tech_quadrant`, `skill_premium`, `pay_benchmark` and `ai_year` are pre-aggregated marts: use them for visuals
that need survey-correct denominators (adoption shares), and the fact/bridge tables for free slicing.
"""


def build(con, folder: Path | None = None) -> Path:
    folder = folder or settings.REPORTS_DIR / "bi"
    folder.mkdir(parents=True, exist_ok=True)
    for name, sql in TABLES.items():
        con.execute(f"COPY ({sql}) TO '{folder / (name + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    (folder / "measures.dax").write_text(MEASURES)
    (folder / "model.md").write_text(MODEL)
    return folder
