# Data dictionary

Generated from the live DuckDB catalog by `stackscope run --only reports`. Schemas: `core` (star schema),
`mart` (analysis-ready aggregates), `dq` (data quality), `ml` (model evaluation).

## `core`

### `core.bridge_ai_task`

Respondent x development task currently done with AI (2023+). 343,327 rows.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `task` | varchar |

### `core.bridge_answered`

Which technology question groups each respondent answered; the denominator of every share. 5,818,870 rows.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `field_group` | varchar |
| `side` | varchar |

### `core.bridge_role`

Respondent x developer role (multi-select years keep every role). 1,260,500 rows.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `role` | varchar |

### `core.bridge_tech_usage`

Respondent x technology facts: used this year / wants next year (canonical technology ids). 12,483,481 rows.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `tech_id` | smallint |
| `used` | boolean |
| `wanted` | boolean |

### `core.dim_country`

ISO-3166 countries with analysis region, World Bank income group and capital coordinates. 226 rows.

| Column | Type |
|---|---|
| `iso3` | varchar |
| `country` | varchar |
| `iso_numeric` | integer |
| `region` | varchar |
| `un_region` | varchar |
| `income_group` | varchar |
| `capital` | varchar |
| `lon` | double |
| `lat` | double |

### `core.dim_cpi`

US CPI-U annual averages and the factor to constant 2025 dollars. 17 rows.

| Column | Type |
|---|---|
| `year` | integer |
| `cpi` | double |
| `to_base_year` | double |

### `core.dim_technology`

309 canonical technologies with category, first/last year observed and series-break notes. 309 rows.

| Column | Type |
|---|---|
| `tech_id` | smallint |
| `tech` | varchar |
| `category` | varchar |
| `category_label` | varchar |
| `note` | varchar |
| `first_year` | smallint |
| `last_year` | smallint |
| `n_years` | bigint |

### `core.dim_year`

Survey waves with respondent counts. 9 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `respondents` | bigint |
| `professionals` | bigint |
| `country_labels` | bigint |
| `respondent_type_derived` | boolean |

### `core.fact_macro`

Country-year PPP factor, exchange rate, price level (validated), GDP per capita and population. 2,486 rows.

| Column | Type |
|---|---|
| `iso3` | varchar |
| `year` | integer |
| `ppp_factor` | double |
| `fx_rate` | double |
| `gdp_pc_ppp` | double |
| `population` | double |
| `ppp_imputed` | boolean |
| `price_level_raw` | double |
| `price_level` | double |
| `price_level_status` | varchar |

### `core.fact_respondent`

One row per survey response (664k). Harmonised demographics, work, pay (USD, constant-2025 USD, PPP) and GenAI attitudes. 664,042 rows.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `employment` | varchar |
| `ed_level` | varchar |
| `org_size` | varchar |
| `remote_work` | varchar |
| `age_band` | varchar |
| `industry` | varchar |
| `years_code` | double |
| `years_pro` | double |
| `work_exp` | double |
| `exp_band` | varchar |
| `pro_tenure` | double |
| `pro_tenure_source` | varchar |
| `dev_role` | varchar |
| `n_roles` | smallint |
| `respondent_type` | varchar |
| `respondent_type_derived` | boolean |
| `comp_usd_raw` | double |
| `ai_use` | varchar |
| `ai_frequency` | varchar |
| `ai_sentiment` | varchar |
| `ai_sentiment_score` | double |
| `ai_trust` | varchar |
| `ai_trust_score` | double |
| `ai_complex` | varchar |
| `ai_complex_score` | double |
| `ai_threat` | varchar |
| `ai_agents` | varchar |
| `ai_task_answered` | boolean |
| `iso3` | varchar |
| `region` | varchar |
| `income_group` | varchar |
| `comp_mod_z` | double |
| `comp_status` | varchar |
| `comp_usd` | double |
| `comp_usd_real` | double |
| `comp_ppp` | double |
| `is_professional` | boolean |
| `in_pay_benchmark` | boolean |
| `comp_topcoded` | boolean |

### `core.respondent_weight`

Raking weight per respondent: each wave matched to the average region x respondent-type x experience mix. 664,042 rows.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `weight` | double |

### `core.tech_year_group`

Which question group(s) listed each technology in each year (technologies move between questions). 1,306 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `tech_id` | smallint |
| `field_group` | varchar |

### `core.v_tech_usage`

Convenience view: usage facts with technology names. View.

| Column | Type |
|---|---|
| `resp_key` | bigint |
| `survey_year` | smallint |
| `tech` | varchar |
| `category` | varchar |
| `used` | boolean |
| `wanted` | boolean |

## `dq`

### `dq.check_results`

Automated data-quality checks by DAMA dimension with status and evidence. 28 rows.

| Column | Type |
|---|---|
| `check_id` | varchar |
| `dimension` | varchar |
| `description` | varchar |
| `metric` | double |
| `threshold` | varchar |
| `status` | varchar |
| `blocker` | boolean |
| `detail` | varchar |

### `dq.completeness`

Share of respondents with a usable answer per field and wave. 135 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `field` | varchar |
| `completeness` | double |
| `asked` | boolean |

### `dq.label_coverage`

Every raw technology label per wave and question with its mapping outcome. 2,842 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `field_group` | varchar |
| `side` | varchar |
| `raw_label` | varchar |
| `mentions` | bigint |
| `tech` | varchar |
| `status` | varchar |

### `dq.schema_notes`

Per-wave schema changes handled during harmonisation. 8 rows.

| Column | Type |
|---|---|
| `survey_year` | bigint |
| `note` | varchar |

### `dq.weight_diagnostics`

Raking convergence, design effect and effective sample size per wave. 9 rows.

| Column | Type |
|---|---|
| `survey_year` | bigint |
| `respondents` | bigint |
| `design_effect` | double |
| `effective_n` | bigint |
| `min_weight` | double |
| `max_weight` | double |
| `iterations` | bigint |
| `max_margin_error` | double |
| `converged` | boolean |

### `dq.weight_targets`

Reference composition used for raking. 21 rows.

| Column | Type |
|---|---|
| `dimension` | varchar |
| `category` | varchar |
| `target_share` | double |

## `mart`

### `mart.ai_drivers`

Odds ratios from survey-weighted logistic regressions of AI adoption and trust. 78 rows.

| Column | Type |
|---|---|
| `model` | varchar |
| `variable` | varchar |
| `level` | varchar |
| `odds_ratio` | double |
| `or_lo` | double |
| `or_hi` | double |
| `p_value` | double |
| `n_level` | bigint |
| `reference` | varchar |
| `q_value` | double |
| `n_model` | bigint |
| `baseline_rate` | double |

### `mart.ai_likert`

Answer distributions for the GenAI Likert questions by year. 53 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `question` | varchar |
| `answer` | varchar |
| `n` | bigint |
| `share_w` | double |

### `mart.ai_segment`

GenAI adoption and trust by role, experience, region, company size and age. 167 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `dimension` | varchar |
| `segment` | varchar |
| `n` | bigint |
| `using_w` | double |
| `daily_w` | double |
| `trust_w` | double |
| `trust_net` | double |
| `sentiment_net` | double |
| `threat_w` | double |
| `agents_w` | double |

### `mart.ai_task_year`

Share using AI for each development task by year. 32 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `task` | varchar |
| `n` | bigint |
| `share_w` | double |
| `base_n` | bigint |

### `mart.ai_year`

GenAI adoption, sentiment, trust and threat perception by year (weighted). 3 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `n` | bigint |
| `using_w` | double |
| `planning_w` | double |
| `not_planning_w` | double |
| `sentiment_net` | double |
| `favorable_w` | double |
| `trust_net` | double |
| `trust_w` | double |
| `distrust_w` | double |
| `complex_net` | double |
| `threat_w` | double |

### `mart.assoc_rules`

Association rules A -> B with support, confidence and lift. 5,047 rows.

| Column | Type |
|---|---|
| `antecedent` | varchar |
| `consequent` | varchar |
| `co_users` | double |
| `support` | double |
| `confidence` | double |
| `lift` | double |
| `survey_year` | bigint |

### `mart.country_year`

Country profiles: respondents, pay, remote share, AI use, top language, reach per million people. 1,629 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `iso3` | varchar |
| `country` | varchar |
| `iso_numeric` | integer |
| `region` | varchar |
| `income_group` | varchar |
| `lon` | double |
| `lat` | double |
| `respondents` | bigint |
| `professional_share` | double |
| `remote_share` | double |
| `ai_use_share` | double |
| `median_years_code` | double |
| `pay_n` | bigint |
| `median_pay_usd` | double |
| `median_pay_ppp` | double |
| `gdp_pc_ppp` | double |
| `population` | double |
| `respondents_per_million` | double |
| `top_language` | varchar |

### `mart.forecast_backtest`

Rolling-origin backtest of five forecasting models by horizon. 10 rows.

| Column | Type |
|---|---|
| `model` | varchar |
| `horizon` | bigint |
| `n` | bigint |
| `mae_pp` | double |
| `rmse_pp` | double |
| `skill_vs_naive` | double |
| `selected` | boolean |

### `mart.forecast_indicator`

Leading-indicator model coefficients (desire gap, retention, attraction, momentum). 4 rows.

| Column | Type |
|---|---|
| `feature` | varchar |
| `coefficient` | double |

### `mart.key_findings`

Evidence-backed headlines generated from the marts on every run. 11 rows.

| Column | Type |
|---|---|
| `rank` | bigint |
| `finding_id` | varchar |
| `theme` | varchar |
| `route` | varchar |
| `value` | double |
| `value_label` | varchar |
| `headline` | varchar |
| `detail` | varchar |

### `mart.market_concentration`

HHI, CR3/CR5, leader and structure per category-year. 67 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `category` | varchar |
| `category_label` | varchar |
| `technologies` | bigint |
| `hhi` | double |
| `effective_competitors` | double |
| `cr3` | double |
| `cr5` | double |
| `leader` | varchar |
| `leader_share` | double |
| `lead_over_second` | double |
| `structure` | varchar |

### `mart.network_edges`

Graph edges: co-usage counts, lift and normalised PMI. 1,310 rows.

| Column | Type |
|---|---|
| `survey_year` | bigint |
| `a` | varchar |
| `b` | varchar |
| `co_users` | double |
| `support` | double |
| `lift` | double |
| `npmi` | double |

### `mart.network_nodes`

Technology co-usage graph nodes with community, degree, betweenness and layout coordinates. 321 rows.

| Column | Type |
|---|---|
| `survey_year` | bigint |
| `tech` | varchar |
| `category` | varchar |
| `prevalence` | double |
| `community` | bigint |
| `degree` | bigint |
| `betweenness` | double |
| `x` | double |
| `y` | double |
| `community_label` | varchar |

### `mart.pay_benchmark`

Pay percentiles by year across cuts (country, region, role, experience, company size, ...), n >= 30. 2,149 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `cut` | varchar |
| `segment` | varchar |
| `sub_segment` | varchar |
| `n` | bigint |
| `p25_usd` | double |
| `median_usd` | double |
| `p75_usd` | double |
| `median_real` | double |
| `median_ppp` | double |
| `p25_ppp` | double |
| `p75_ppp` | double |

### `mart.real_pay_trend`

Median real pay with a fixed country mix vs the raw median. 9 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `countries` | bigint |
| `fixed_mix_median_real` | double |
| `fixed_mix_median_ppp` | double |
| `raw_median_real` | double |

### `mart.remote_by_region`

Remote / hybrid / in-person shares of professionals by region and year. 62 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `region` | varchar |
| `n` | bigint |
| `remote_w` | double |
| `hybrid_w` | double |
| `in_person_w` | double |

### `mart.segment_model`

Silhouette and inertia for each candidate number of clusters. 5 rows.

| Column | Type |
|---|---|
| `k` | bigint |
| `silhouette` | double |
| `inertia` | double |
| `chosen` | boolean |

### `mart.segment_points`

2-D UMAP coordinates of a stratified respondent sample (persona map). 5,600 rows.

| Column | Type |
|---|---|
| `x` | float |
| `y` | float |
| `segment_id` | integer |

### `mart.segment_profile`

Developer personas from stack clustering: size, pay, AI use, remote share, signature technologies. 8 rows.

| Column | Type |
|---|---|
| `segment_id` | bigint |
| `name` | varchar |
| `respondents` | bigint |
| `share_w` | double |
| `median_pay_real` | double |
| `pay_n` | bigint |
| `ai_daily` | double |
| `remote_share` | double |
| `median_years_code` | double |
| `top_role` | varchar |
| `top_role_share` | double |
| `signature` | varchar |
| `most_used` | varchar |

### `mart.segment_region`

Regional mix of each persona. 80 rows.

| Column | Type |
|---|---|
| `segment_id` | integer |
| `region` | varchar |
| `share_w` | double |

### `mart.segment_tech`

Technology prevalence and lift within each persona. 709 rows.

| Column | Type |
|---|---|
| `segment_id` | bigint |
| `tech` | varchar |
| `category` | varchar |
| `prevalence` | double |
| `lift` | double |

### `mart.selection_intensity`

Mean options ticked per respondent per question and year (questionnaire-effect diagnostic). 67 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `category` | varchar |
| `mean_picks` | double |
| `median_picks` | double |
| `respondents` | bigint |

### `mart.skill_premium`

Regression-adjusted pay premium per technology and market scope, with CIs and FDR q-values. 326 rows.

| Column | Type |
|---|---|
| `scope` | varchar |
| `tech` | varchar |
| `category` | varchar |
| `n_users` | bigint |
| `prevalence` | double |
| `coef` | double |
| `se` | double |
| `p_value` | double |
| `premium` | double |
| `premium_lo` | double |
| `premium_hi` | double |
| `raw_premium` | double |
| `q_value` | double |
| `significant` | boolean |

### `mart.skill_premium_model`

Fit statistics of each skill-premium regression. 4 rows.

| Column | Type |
|---|---|
| `scope` | varchar |
| `n` | bigint |
| `r2` | double |
| `adj_r2` | double |
| `features` | bigint |
| `technologies` | bigint |
| `years` | varchar |
| `median_pay_real` | double |

### `mart.tech_forecast`

Adoption history plus 2026-2027 projections with backtest-calibrated 80% intervals. 793 rows.

| Column | Type |
|---|---|
| `tech_id` | bigint |
| `tech` | varchar |
| `category` | varchar |
| `survey_year` | bigint |
| `share` | double |
| `lo80` | double |
| `hi80` | double |
| `kind` | varchar |
| `model` | varchar |

### `mart.tech_mindshare`

Each technology's share of usage mentions within its category and year. 1,304 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `category` | varchar |
| `category_label` | varchar |
| `tech_id` | smallint |
| `tech` | varchar |
| `share_used_w` | double |
| `mindshare` | double |
| `position` | bigint |

### `mart.tech_net_migration`

Net migration between technology pairs (A->B minus B->A). 12,921 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `category` | varchar |
| `from_tech` | varchar |
| `to_tech` | varchar |
| `flow_forward` | bigint |
| `flow_backward` | bigint |
| `net_flow` | bigint |
| `net_ratio` | double |

### `mart.tech_quadrant`

Market-position quadrant per category and year (adoption vs momentum z-score). 1,202 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `category` | varchar |
| `category_label` | varchar |
| `tech_id` | smallint |
| `tech` | varchar |
| `base_n` | bigint |
| `share_used_w` | double |
| `share_used_w_lo` | double |
| `share_used_w_hi` | double |
| `retention_w` | double |
| `attraction_w` | double |
| `net_desire_w` | double |
| `yoy_logodds` | double |
| `momentum` | double |
| `momentum_components` | bigint |
| `adoption_threshold` | double |
| `adoption_pct_rank` | double |
| `quadrant` | varchar |

### `mart.tech_radar`

Technology radar blips (Adopt / Trial / Assess / Hold) for the latest waves. 95 rows.

| Column | Type |
|---|---|
| `blip` | bigint |
| `sector` | varchar |
| `category` | varchar |
| `tech_id` | smallint |
| `tech` | varchar |
| `survey_year` | smallint |
| `ring` | varchar |
| `share_used_w` | double |
| `momentum` | double |
| `retention_w` | double |
| `attraction_w` | double |
| `trend` | varchar |
| `odds_growth` | double |
| `adoption_pct_rank` | double |

### `mart.tech_switching`

Churn flows: users leaving technology A who want technology B, with shares of leavers. 19,586 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `category` | varchar |
| `from_tech` | varchar |
| `to_tech` | varchar |
| `n` | bigint |
| `sw` | double |
| `share_of_churners` | double |
| `from_churners` | bigint |
| `from_churn_rate` | double |
| `destination_rank` | bigint |

### `mart.tech_trend`

Multi-year trajectory per technology: weighted logistic trend, annual odds growth with CI, verdict. 309 rows.

| Column | Type |
|---|---|
| `tech_id` | bigint |
| `tech` | varchar |
| `category` | varchar |
| `first_year` | bigint |
| `last_year` | bigint |
| `n_points` | bigint |
| `share_first` | double |
| `share_last` | double |
| `change_pp` | double |
| `slope` | double |
| `slope_se` | double |
| `p_value` | double |
| `recent_slope` | double |
| `recent_p_value` | double |
| `q_value` | double |
| `odds_growth` | double |
| `odds_growth_lo` | double |
| `odds_growth_hi` | double |
| `recent_odds_growth` | double |
| `trend` | varchar |

### `mart.tech_year`

Technology KPI cube: raw and weighted adoption with Wilson intervals, desire, retention, attraction, rank. 1,304 rows.

| Column | Type |
|---|---|
| `tech_id` | smallint |
| `tech` | varchar |
| `category` | varchar |
| `category_label` | varchar |
| `survey_year` | smallint |
| `base_n` | bigint |
| `base_n_eff` | double |
| `n_used` | bigint |
| `share_used` | double |
| `share_used_w` | double |
| `base_want_n` | bigint |
| `n_wanted` | bigint |
| `share_wanted` | double |
| `share_wanted_w` | double |
| `users_asked_want` | bigint |
| `n_retained` | bigint |
| `retention` | double |
| `retention_w` | double |
| `attraction` | double |
| `attraction_w` | double |
| `share_used_lo` | double |
| `share_used_hi` | double |
| `share_used_w_lo` | double |
| `share_used_w_hi` | double |
| `net_desire_w` | double |
| `prev_share_used_w` | double |
| `prev_base_n_eff` | double |
| `rank_in_category` | bigint |
| `mention_share` | double |

### `mart.tech_yoy`

Wave-on-wave adoption changes with two-proportion tests and Benjamini-Hochberg q-values. 953 rows.

| Column | Type |
|---|---|
| `tech_id` | smallint |
| `tech` | varchar |
| `category` | varchar |
| `survey_year` | smallint |
| `prev_share_used_w` | double |
| `share_used_w` | double |
| `delta_pp` | double |
| `z` | double |
| `p_value` | double |
| `q_value` | double |
| `significant` | boolean |

### `mart.workforce_mix`

Weighted distribution of work arrangement, roles, experience, company size, education, age by year. 469 rows.

| Column | Type |
|---|---|
| `survey_year` | smallint |
| `attribute` | varchar |
| `category` | varchar |
| `n` | bigint |
| `share_w` | double |

## `ml`

### `ml.salary_feature_importance`

Mean absolute TreeSHAP contribution per feature. 74 rows.

| Column | Type |
|---|---|
| `feature` | varchar |
| `mean_abs_shap` | double |
| `group` | varchar |
| `label` | varchar |

### `ml.salary_group_importance`

TreeSHAP importance aggregated into feature groups. 9 rows.

| Column | Type |
|---|---|
| `group` | varchar |
| `mean_abs_shap` | double |
| `share` | double |

### `ml.salary_model_metrics`

Salary model evaluation on the held-out test split vs a country-year median baseline. 15 rows.

| Column | Type |
|---|---|
| `metric` | varchar |
| `value` | double |
