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
