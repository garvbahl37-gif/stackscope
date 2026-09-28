-- =============================================================================================
-- Selection intensity: how many options respondents tick per question, by year.
-- A jump (e.g. languages 5.4 -> 6.1 per respondent in 2025) signals a questionnaire effect that
-- lifts every technology's share at once; shares of mentions (mindshare) are robust to it.
-- =============================================================================================

CREATE OR REPLACE TABLE mart.selection_intensity AS
WITH per_person AS (
    SELECT u.survey_year, u.resp_key, t.category, count(*) FILTER (WHERE u.used) AS picks
    FROM core.bridge_tech_usage AS u
    JOIN core.dim_technology AS t USING (tech_id)
    GROUP BY u.survey_year, u.resp_key, t.category
)
SELECT
    survey_year,
    category,
    avg(picks) FILTER (WHERE picks > 0)            AS mean_picks,
    median(picks) FILTER (WHERE picks > 0)         AS median_picks,
    count(*) FILTER (WHERE picks > 0)              AS respondents
FROM per_person
GROUP BY survey_year, category
ORDER BY category, survey_year;
