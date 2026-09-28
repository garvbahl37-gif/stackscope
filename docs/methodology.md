# Methodology

This document records every analytical decision behind StackScope, why it was made, and where it lives in the code.

## 1. Research questions

1. Which technologies are gaining or losing developer mindshare once changes in *who answered* are removed?
2. How is each technology market positioned, and how concentrated is it?
3. Which technologies keep their users, and where do the leavers go?
4. What is a skill worth on a pay cheque, holding everything else constant?
5. What developer segments exist, judged by the stacks people actually use?
6. How fast is generative AI being adopted, and who trusts it?

## 2. Sources and provenance

| Source | Coverage | Rows | Licence |
|---|---|---|---|
| Stack Overflow Developer Survey (via Kaggle) | 2017–2025, 9 files, 924 raw columns | 664,042 responses | ODbL |
| World Bank World Development Indicators API | PPP conversion factor, official exchange rate, GDP per capita (PPP), population, 2015–2025 | 9,950 country-years | CC BY 4.0 |
| World Bank country metadata | region, income group, capital coordinates | 217 economies | CC BY 4.0 |
| FRED CPIAUCSL (US CPI-U, monthly) | 2010–2026 | annualised | public domain |

Raw files are fingerprinted (SHA-256) in `data/raw/manifest.json`, and the quality gate reconciles each wave's row count
with the total Stack Overflow published (all nine match exactly).

## 3. Pipeline

`bronze -> silver -> gold -> marts -> analytics -> quality gate -> reports`, orchestrated by `stackscope run`
(`src/stackscope/cli.py`). One command rebuilds everything in about 90 seconds; every stage is idempotent and seeded, and
two consecutive runs produce bit-identical outputs.

- **Silver** (`harmonize/`): year-specific schemas mapped to one model; Parquet outputs.
- **Gold** (`warehouse/sql/core`): DuckDB star schema. The fact table is `fact_respondent`; bridges hold the many-to-many
  technology, role and AI-task facts; dimensions cover countries, technologies, years and CPI.
- **Marts** (`warehouse/sql/marts`): versioned SQL (window functions, GROUPING SETS, PIVOT/UNPIVOT, macros).
- **Analytics** (`analytics/`): Python statistics and machine learning writing back into the warehouse.
- **Compact** (`warehouse/build.py`): the finished warehouse is copied into a fresh file in DuckDB's newest storage
  format. The copy drops free blocks, is about 10% smaller (93.6 MB), and replaces the original only after every table's
  row count and content hash match.

## 4. Harmonisation

**Schemas.** `harmonize/schema.py` maps each harmonised field to its column in each year (for example
`HaveWorkedLanguage` 2017, `LanguageWorkedWith` 2018–2020, `LanguageHaveWorkedWith` 2021+). Questions not asked in a year
stay explicitly null. Per-year handling includes:

- **2018** has no main-branch question, so respondent type is derived from employment, student status and roles, and flagged.
- **2023**: the `AIAcc` and `AIBen` columns are swapped in the published file. This was detected by validating value
  domains, so trust is read from `AIBen`. A blocking quality check asserts that 2023 trust answers lie in the Likert domain.
- **2025** dropped years of professional coding, so work experience is the professional-tenure proxy. It also no longer
  separates full-time from part-time employment, and it moved DevOps and build tools into the platform question.

**Values.** Experience ranges (`"3-5 years"`, `"1 to 2 years"`, `"Less than a year"`) become midpoints. Five remote-work
scales collapse to Remote, Hybrid and In-person. Multi-select employment keeps the dominant status. Roles use a documented
precedence to pick a primary role in the multi-select years (2017–2022); the switch to single-select in 2023 is a flagged
series break.

**Technology taxonomy** (`config/tech_taxonomy.yml`). 448 raw labels map to 309 canonical technologies across nine
categories:
- Aliases merge renamed options (`Bash/Shell/PowerShell` becomes `Bash/Shell`, `React.js` becomes `React`).
- Field restrictions separate identical labels that mean different things in different questions: `Firebase` is a database
  in one question and a cloud platform in another.
- Deliberate exclusions (operating systems, devices, "Other") are tracked separately, so any unmapped label signals a gap to
  fix. Mapping coverage is 100% of in-scope mentions.

**Denominators.** A technology's share is computed among respondents who answered the question group that listed it *in
that year*. This matters because options move between questions: Node.js was a framework, then "misc tech", then a
language, then a web framework. The 2023 AI tools, split across two questions, are pooled into one denominator.

**Countries.** 254 spellings are resolved to ISO-3166 codes with `country_converter`, with manual fixes for archaic names
such as "Azerbaidjan" and "Moldavia". UN M49 sub-regions roll up into 10 analysis regions, finer than World Bank regions for
Europe and Asia. World Bank income groups are joined on.

## 5. Compensation

- **Source columns.** 2017 `Salary` (USD, top-coded near $200k by the publisher); 2018 `ConvertedSalary`; 2019–2020
  `ConvertedComp` (capped at $2M); 2021+ `ConvertedCompYearly`.
- **Screen.** A salary must lie within $1k–$1M, and its log value within 3.5 modified z-scores (MAD-based, Iglewicz–Hoaglin)
  of the full-time median for the same country and year. Region-year is used when the country has fewer than 30 salaries.
  93.6% of reported salaries pass. The screen removes monthly-entered-as-annual answers and typos without trimming genuine
  top earners.
- **Real pay.** Deflated with US CPI-U annual averages to constant 2025 dollars. The 2025 average uses 11 months because the
  October 2025 release was never published.
- **PPP.** Price level = PPP factor / official exchange rate, with two validations:
  - Croatia's PPP series is re-denominated to euros (euro adoption, 2023) while its historical exchange rate is in kuna, so
    kuna are converted to euros at the fixed 7.53450 rate.
  - Price levels outside 0.10–1.80 are withheld. These arise where official or pegged rates diverge from market rates (Iran,
    Lebanon, Sudan) and in dollarised economies (Zimbabwe, Liberia).
- **Benchmark population:** full-time professional developers with a valid salary (253k across nine waves).
- **Fixed-mix trend:** medians for 35 countries surveyed every year, weighted by each country's average sample share. This
  separates real pay growth (+27% since 2017) from composition change (the raw median shows +15%).

## 6. Composition weighting (`analytics/weighting.py`)

Each wave is raked (iterative proportional fitting) to the average composition across the nine waves on three margins:
analysis region, respondent type and coding-experience band.
- Known values only: a missing answer is never forced toward a target.
- Weights are trimmed to 0.2–5× the mean inside a trim-and-rerake loop.
- All waves converge (margin error ≈ 1e-8).
- The Kish design effect ranges from 1.02 to 1.22, so effective sample sizes stay between 43k and 87k per wave.

## 7. Metric definitions

| Metric | Definition |
|---|---|
| Adoption | weighted share of question-answerers who used the technology in the past year |
| Desire | weighted share who want to work with it next year |
| Retention | among current users who were asked about next year, the share who want to keep it (1 − churn intent) |
| Attraction | among non-users asked about next year, the share who want to start |
| Net desire | desire − adoption |
| Mindshare | a technology's share of all usage mentions in its category |
| HHI | Σ mindshare² × 10,000 (<1,500 competitive, 1,500–2,500 moderately concentrated, >2,500 highly concentrated) |

## 8. Statistical inference

- **Intervals.** Wilson 95% intervals, using the Kish effective sample size for weighted shares (a SQL macro, `wilson_lo`
  and `wilson_hi`).
- **Wave-on-wave change.** Unpooled two-proportion z-test on weighted shares; Benjamini–Hochberg FDR across all 953 tests.
  With samples this large, 77% of changes are significant, so the dashboard leads with effect sizes (percentage points and
  odds growth).
- **Multi-year trend.** Inverse-variance weighted least squares of logit(share) on year (weights n·p·(1−p)), with
  quasi-likelihood standard errors: dispersion is estimated from the residuals because survey waves vary by more than
  sampling noise. The slope is reported as annual growth in the odds of use, with a 95% CI and FDR control. A technology is
  labelled Rising or Declining only when q < 0.05 and it has at least four waves.

## 9. Market positioning (`analytics/landscape.py`)

- **Quadrant.** Momentum is the mean of within-category z-scores of retention, attraction and the wave-on-wave change in
  log-odds of adoption. Quadrants split at momentum 0 and the category's median adoption. Only technologies with ≥ 1,000
  answerers and ≥ 1% adoption are placed.
- **Radar.** Rings are assigned by rule:
  - *Hold*: momentum < −0.5, or a significant multi-year decline with momentum < 0.25.
  - *Adopt*: adoption percentile ≥ 0.6 and momentum ≥ −0.25.
  - *Assess*: adoption percentile < 0.4 and momentum ≥ 0.3.
  - *Trial*: everything else with positive momentum or a rising trend.
  Ring quotas per sector keep the radar legible.

## 10. Forecasting (`analytics/forecast.py`)

Five candidate models, all fitted on the logit scale: naive, drift, damped trend, an ensemble, and a leading-indicator panel
regression. The leading-indicator model regresses next-wave change on the desire gap, retention, attraction and recent
momentum with a robust Huber fit.

Rolling-origin backtests (origins 2020–2024, horizons 1–2) select the model with the lowest MAE. **None beat the naive
forecast** (MAE 1.9 pp one year ahead), which is reported as a finding. The 80% intervals are the 10th–90th percentiles of
the selected model's own backtest errors.

## 11. Skill premiums (`analytics/compensation.py`)

The model is OLS on ln(real pay):
- **Fixed effects:** country (top 40, plus "Other" by region), experience bands, role, company size, education, work
  arrangement, industry and survey year.
- **Controls:** which technology questions the respondent answered.
- **Technology indicators:** every technology with at least 2% prevalence that was asked in all three waves (2023–2025).

Standard errors are HC1 robust and q-values are Benjamini–Hochberg. The model is fitted separately for Global
(n = 71,318, R² 0.68), United States, India and Western Europe. The raw median gap is shown next to each adjusted premium:
controls shrink the typical gap 4.4×. These are associations, not causal effects.

## 12. Salary estimator (`analytics/salary_model.py`)

- **Models.** LightGBM quantile regression for P10, P50 and P90 of ln(real pay), with native categorical handling, 60
  technology flags and early stopping.
- **Split.** Stratified by year: 65% train, 10% validation, 10% calibration, 15% test.
- **Calibration.** Conformalized quantile regression widens P10–P90 by the finite-sample quantile of the conformity scores
  on the calibration split. Test coverage is 80.1% against the 80% target (73.8% before calibration).
- **Accuracy.** R² on log pay is 0.714, against 0.562 for a country-year median baseline. Median absolute percentage error
  is 20.7%, against 30.0% for the baseline.
- **Explanations.** Exact TreeSHAP contributions from `pred_contrib`, aggregated into feature groups.
- **Determinism.** LightGBM runs in deterministic mode on a sorted training frame, so metrics are reproducible exactly.
- **Serving** (`analytics/salary_runtime.py`). The API scores the saved models through LightGBM's C API (via ctypes)
  instead of the Python package, so it needs no NumPy, SciPy or pandas. Features are encoded as in training. Tests
  confirm the predictions and TreeSHAP contributions are identical to `lightgbm.Booster.predict`.

## 13. Developer personas (`analytics/segments.py`)

- **Input:** the binary 2025 respondent × technology matrix (31,664 respondents, 168 technologies).
- **Pipeline:** TF-IDF, then 24-component truncated SVD, then L2 normalisation, then k-means (spherical, i.e. cosine).
- **Choosing k:** k = 8 maximises the cosine silhouette (0.197) among 6–10 clusters.
- **Naming:** clusters are named by an optimal Hungarian assignment between each cluster's over-indexed technologies (lift)
  and archetype signatures, so names survive data refreshes.
- **Persona map:** a 2-D UMAP of a stratified sample.

## 14. Ecosystem network (`analytics/network.py`)

- **Nodes:** technologies used by at least 2% of respondents.
- **Edges:** pairs with normalised PMI ≥ 0.08, lift ≥ 1.4 and at least 100 co-users; each node keeps its six strongest ties.
- **Communities:** Louvain modularity, named by signature matching.
- **Bridges:** betweenness centrality on 1/NPMI distances identifies connector technologies.
- **Association rules (A → B):** reported with support, confidence and lift.

## 15. GenAI drivers (`analytics/ai_drivers.py`)

Binomial GLMs of "uses AI tools" and "trusts AI accuracy" (among users) for 2025. Predictors are experience, age, role,
region and company size; raking weights enter as variance weights; standard errors are HC1. Results are reported as odds
ratios against named reference levels.

## 16. Data quality (`quality/checks.py`)

28 automated checks across the DAMA dimensions, run on every build. Failing blocking checks stop the pipeline.
- **Accuracy:** source reconciliation, provenance hashes, raking convergence, design effect.
- **Uniqueness:** unique keys, duplicate submissions.
- **Integrity:** foreign keys.
- **Completeness:** country resolution, taxonomy coverage.
- **Validity:** share bounds, pay bounds, PPP price levels, the 2023 swapped-column defect.
- **Consistency:** tenure versus experience, age versus experience.
- **Timeliness:** latest wave loaded.

Engineering safeguards found along the way: a DuckDB 1.5.6 quirk (a bare `min()` over a NULL-heavy column returned 0.0) is
guarded with explicit `IS NOT NULL` filters, and every analytics query that feeds a random split is explicitly ordered.

## 17. Limitations

- Survey respondents self-select. Weighting fixes drift *between* waves, not selection into the survey.
- Option lists and routing change between waves, and known breaks are flagged in the UI. For example, respondents ticked 14%
  more languages in 2025 than in 2024, and in 2025 the AI questions moved from tools to model families.
- Mindshare measures developer usage, not revenue, installed base or vendor market share.
- Pay premiums are conditional associations; an omitted-variable story (for example sector or seniority within role) can
  never be fully ruled out.
