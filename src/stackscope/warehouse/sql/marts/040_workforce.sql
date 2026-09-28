-- =============================================================================================
-- Workforce trends (composition-weighted): work arrangements, roles, experience, education.
-- =============================================================================================

-- Generic weighted distribution of a categorical attribute per year (and region for remote work).
CREATE OR REPLACE TABLE mart.workforce_mix AS
WITH src AS (
    SELECT r.survey_year, r.region, w.weight, r.is_professional,
           r.remote_work, r.dev_role, r.exp_band, r.org_size, r.ed_level, r.age_band, r.respondent_type
    FROM core.fact_respondent AS r
    JOIN core.respondent_weight AS w USING (resp_key)
),
long AS (
    UNPIVOT src
    ON remote_work, dev_role, exp_band, org_size, ed_level, age_band, respondent_type
    INTO NAME attribute VALUE category
)
SELECT
    survey_year,
    attribute,
    category,
    count(*)                                                                    AS n,
    sum(weight) / sum(sum(weight)) OVER (PARTITION BY survey_year, attribute)    AS share_w
FROM long
WHERE category IS NOT NULL
  AND (attribute NOT IN ('remote_work', 'dev_role', 'org_size') OR is_professional)
GROUP BY survey_year, attribute, category
ORDER BY attribute, category, survey_year;

-- Remote work by region, professionals only (the post-2020 shift and the return-to-office drift).
CREATE OR REPLACE TABLE mart.remote_by_region AS
SELECT
    r.survey_year,
    coalesce(r.region, 'Unknown')                                              AS region,
    count(*)                                                                   AS n,
    sum(w.weight) FILTER (WHERE r.remote_work = 'Remote')    / sum(w.weight)   AS remote_w,
    sum(w.weight) FILTER (WHERE r.remote_work = 'Hybrid')    / sum(w.weight)   AS hybrid_w,
    sum(w.weight) FILTER (WHERE r.remote_work = 'In-person') / sum(w.weight)   AS in_person_w
FROM core.fact_respondent AS r
JOIN core.respondent_weight AS w USING (resp_key)
WHERE r.remote_work IS NOT NULL AND r.is_professional
GROUP BY ALL
HAVING count(*) >= 100;
