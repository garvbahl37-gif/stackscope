-- =============================================================================================
-- Talent & compensation marts.
-- Benchmark population: full-time professional developers with a validated salary.
-- =============================================================================================

-- Pay benchmarks across many cuts in one pass (GROUPING SETS), suppressed below n = 30.
CREATE OR REPLACE TABLE mart.pay_benchmark AS
SELECT
    survey_year,
    CASE
        WHEN GROUPING(region) = 0 AND GROUPING(dev_role) = 0 THEN 'region_role'
        WHEN GROUPING(region) = 0 AND GROUPING(exp_band) = 0 THEN 'region_experience'
        WHEN GROUPING(iso3) = 0      THEN 'country'
        WHEN GROUPING(region) = 0    THEN 'region'
        WHEN GROUPING(dev_role) = 0  THEN 'role'
        WHEN GROUPING(exp_band) = 0  THEN 'experience'
        WHEN GROUPING(org_size) = 0  THEN 'org_size'
        WHEN GROUPING(remote_work) = 0 THEN 'remote'
        WHEN GROUPING(ed_level) = 0  THEN 'education'
        ELSE 'all'
    END AS cut,
    coalesce(iso3, region, dev_role, exp_band, org_size, remote_work, ed_level, 'All') AS segment,
    CASE WHEN GROUPING(region) = 0 AND (GROUPING(dev_role) = 0 OR GROUPING(exp_band) = 0)
         THEN coalesce(dev_role, exp_band) END AS sub_segment,
    count(*)                                  AS n,
    quantile_cont(comp_usd, 0.25)             AS p25_usd,
    median(comp_usd)                          AS median_usd,
    quantile_cont(comp_usd, 0.75)             AS p75_usd,
    median(comp_usd_real)                     AS median_real,
    median(comp_ppp)                          AS median_ppp,
    quantile_cont(comp_ppp, 0.25)             AS p25_ppp,
    quantile_cont(comp_ppp, 0.75)             AS p75_ppp
FROM core.fact_respondent
WHERE in_pay_benchmark
GROUP BY GROUPING SETS (
    (survey_year),
    (survey_year, iso3),
    (survey_year, region),
    (survey_year, dev_role),
    (survey_year, exp_band),
    (survey_year, org_size),
    (survey_year, remote_work),
    (survey_year, ed_level),
    (survey_year, region, dev_role),
    (survey_year, region, exp_band)
)
HAVING count(*) >= 30;

-- Country profile per year: reach, workforce mix, pay and GenAI adoption.
CREATE OR REPLACE TABLE mart.country_year AS
WITH lang AS (
    SELECT r.survey_year, r.iso3, t.tech, count(*) AS n,
           row_number() OVER (PARTITION BY r.survey_year, r.iso3 ORDER BY count(*) DESC) AS rn
    FROM core.bridge_tech_usage AS u
    JOIN core.fact_respondent AS r USING (resp_key)
    JOIN core.dim_technology AS t USING (tech_id)
    WHERE u.used AND t.category = 'language' AND t.tech NOT IN ('HTML/CSS', 'SQL', 'Bash/Shell')
    GROUP BY r.survey_year, r.iso3, t.tech
)
SELECT
    r.survey_year,
    r.iso3,
    c.country,
    c.iso_numeric,
    c.region,
    c.income_group,
    c.lon,
    c.lat,
    count(*)                                                        AS respondents,
    avg(CASE WHEN r.is_professional THEN 1.0 ELSE 0 END)             AS professional_share,
    avg(CASE WHEN r.remote_work = 'Remote' THEN 1.0 WHEN r.remote_work IS NOT NULL THEN 0 END) AS remote_share,
    avg(CASE WHEN r.ai_use = 'Using' THEN 1.0 WHEN r.ai_use IS NOT NULL THEN 0 END)            AS ai_use_share,
    median(r.years_code)                                             AS median_years_code,
    count(*) FILTER (WHERE r.in_pay_benchmark)                       AS pay_n,
    median(r.comp_usd) FILTER (WHERE r.in_pay_benchmark)             AS median_pay_usd,
    median(r.comp_ppp) FILTER (WHERE r.in_pay_benchmark)             AS median_pay_ppp,
    any_value(m.gdp_pc_ppp)                                          AS gdp_pc_ppp,
    any_value(m.population)                                          AS population,
    1e6 * count(*) / any_value(m.population)                         AS respondents_per_million,
    any_value(l.tech)                                                AS top_language
FROM core.fact_respondent AS r
JOIN core.dim_country AS c USING (iso3)
LEFT JOIN core.fact_macro AS m ON m.iso3 = r.iso3 AND m.year = r.survey_year
LEFT JOIN lang AS l ON l.survey_year = r.survey_year AND l.iso3 = r.iso3 AND l.rn = 1
GROUP BY ALL;

-- Real-pay trend with a fixed country mix: median real pay per country, averaged with the
-- country's average share of the benchmark population (removes the US-share composition effect).
CREATE OR REPLACE TABLE mart.real_pay_trend AS
WITH country_med AS (
    SELECT survey_year, iso3, count(*) AS n, median(comp_usd_real) AS med_real, median(comp_ppp) AS med_ppp
    FROM core.fact_respondent
    WHERE in_pay_benchmark AND iso3 IS NOT NULL
    GROUP BY ALL
    HAVING count(*) >= 50
),
stable AS (      -- countries with a benchmark in every year
    SELECT iso3 FROM country_med GROUP BY iso3
    HAVING count(DISTINCT survey_year) = (SELECT count(DISTINCT survey_year) FROM country_med)
),
mix AS (
    SELECT iso3, avg(n) AS avg_n FROM country_med SEMI JOIN stable USING (iso3) GROUP BY iso3
),
raw_median AS (
    SELECT survey_year, median(comp_usd_real) AS raw_median_real
    FROM core.fact_respondent WHERE in_pay_benchmark GROUP BY survey_year
)
SELECT
    cm.survey_year,
    count(*)                                        AS countries,
    sum(cm.med_real * mix.avg_n) / sum(mix.avg_n)   AS fixed_mix_median_real,
    sum(cm.med_ppp * mix.avg_n) / sum(mix.avg_n)    AS fixed_mix_median_ppp,
    any_value(rm.raw_median_real)                   AS raw_median_real
FROM country_med AS cm
JOIN mix USING (iso3)
JOIN raw_median AS rm USING (survey_year)
GROUP BY cm.survey_year
ORDER BY cm.survey_year;
