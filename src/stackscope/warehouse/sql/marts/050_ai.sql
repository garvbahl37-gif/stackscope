-- =============================================================================================
-- Generative-AI adoption pulse, 2023-2025 (composition-weighted).
-- Net scores are the weighted mean of the Likert score (-2 .. +2): > 0 means net positive.
-- =============================================================================================

CREATE OR REPLACE TABLE mart.ai_year AS
SELECT
    r.survey_year,
    count(*) FILTER (WHERE r.ai_use IS NOT NULL)                                          AS n,
    sum(w.weight) FILTER (WHERE r.ai_use = 'Using')        / sum(w.weight) FILTER (WHERE r.ai_use IS NOT NULL) AS using_w,
    sum(w.weight) FILTER (WHERE r.ai_use = 'Planning')     / sum(w.weight) FILTER (WHERE r.ai_use IS NOT NULL) AS planning_w,
    sum(w.weight) FILTER (WHERE r.ai_use = 'Not planning') / sum(w.weight) FILTER (WHERE r.ai_use IS NOT NULL) AS not_planning_w,
    sum(w.weight * r.ai_sentiment_score) / sum(w.weight) FILTER (WHERE r.ai_sentiment_score IS NOT NULL) AS sentiment_net,
    sum(w.weight) FILTER (WHERE r.ai_sentiment_score > 0) / sum(w.weight) FILTER (WHERE r.ai_sentiment IS NOT NULL) AS favorable_w,
    sum(w.weight * r.ai_trust_score) / sum(w.weight) FILTER (WHERE r.ai_trust_score IS NOT NULL)          AS trust_net,
    sum(w.weight) FILTER (WHERE r.ai_trust_score > 0)  / sum(w.weight) FILTER (WHERE r.ai_trust IS NOT NULL) AS trust_w,
    sum(w.weight) FILTER (WHERE r.ai_trust_score < 0)  / sum(w.weight) FILTER (WHERE r.ai_trust IS NOT NULL) AS distrust_w,
    sum(w.weight * r.ai_complex_score) / sum(w.weight) FILTER (WHERE r.ai_complex_score IS NOT NULL)      AS complex_net,
    sum(w.weight) FILTER (WHERE r.ai_threat = 'Yes') / sum(w.weight) FILTER (WHERE r.ai_threat IS NOT NULL) AS threat_w
FROM core.fact_respondent AS r
JOIN core.respondent_weight AS w USING (resp_key)
WHERE r.survey_year >= 2023
GROUP BY r.survey_year
ORDER BY r.survey_year;

-- Likert distributions (for diverging bar charts).
CREATE OR REPLACE TABLE mart.ai_likert AS
WITH src AS (
    SELECT r.survey_year, w.weight, r.ai_sentiment, r.ai_trust, r.ai_complex, r.ai_frequency, r.ai_agents
    FROM core.fact_respondent AS r JOIN core.respondent_weight AS w USING (resp_key)
    WHERE r.survey_year >= 2023
),
long AS (UNPIVOT src ON ai_sentiment, ai_trust, ai_complex, ai_frequency, ai_agents INTO NAME question VALUE answer)
SELECT survey_year, question, answer, count(*) AS n,
       sum(weight) / sum(sum(weight)) OVER (PARTITION BY survey_year, question) AS share_w
FROM long
WHERE answer IS NOT NULL
GROUP BY survey_year, question, answer;

-- Adoption, trust and threat perception by segment (latest waves), one pass with GROUPING SETS.
CREATE OR REPLACE TABLE mart.ai_segment AS
SELECT
    r.survey_year,
    CASE WHEN GROUPING(r.dev_role) = 0 THEN 'role'
         WHEN GROUPING(r.exp_band) = 0 THEN 'experience'
         WHEN GROUPING(r.region) = 0   THEN 'region'
         WHEN GROUPING(r.org_size) = 0 THEN 'org_size'
         WHEN GROUPING(r.age_band) = 0 THEN 'age'
         ELSE 'all' END                                                              AS dimension,
    coalesce(r.dev_role, r.exp_band, r.region, r.org_size, r.age_band, 'All')        AS segment,
    count(*) FILTER (WHERE r.ai_use IS NOT NULL)                                     AS n,
    sum(w.weight) FILTER (WHERE r.ai_use = 'Using') / sum(w.weight) FILTER (WHERE r.ai_use IS NOT NULL) AS using_w,
    sum(w.weight) FILTER (WHERE r.ai_frequency = 'Daily') / sum(w.weight) FILTER (WHERE r.ai_use IS NOT NULL) AS daily_w,
    sum(w.weight) FILTER (WHERE r.ai_trust_score > 0) / sum(w.weight) FILTER (WHERE r.ai_trust IS NOT NULL) AS trust_w,
    sum(w.weight * r.ai_trust_score) / sum(w.weight) FILTER (WHERE r.ai_trust_score IS NOT NULL) AS trust_net,
    sum(w.weight * r.ai_sentiment_score) / sum(w.weight) FILTER (WHERE r.ai_sentiment_score IS NOT NULL) AS sentiment_net,
    sum(w.weight) FILTER (WHERE r.ai_threat = 'Yes') / sum(w.weight) FILTER (WHERE r.ai_threat IS NOT NULL) AS threat_w,
    sum(w.weight) FILTER (WHERE r.ai_agents IN ('Daily', 'Weekly', 'Monthly or less'))
        / sum(w.weight) FILTER (WHERE r.ai_agents IS NOT NULL)                       AS agents_w
FROM core.fact_respondent AS r
JOIN core.respondent_weight AS w USING (resp_key)
WHERE r.survey_year >= 2023
GROUP BY GROUPING SETS ((r.survey_year), (r.survey_year, r.dev_role), (r.survey_year, r.exp_band),
                        (r.survey_year, r.region), (r.survey_year, r.org_size), (r.survey_year, r.age_band))
HAVING count(*) FILTER (WHERE r.ai_use IS NOT NULL) >= 100;

-- Where in the development workflow AI is used (share of respondents who answered the task grid).
CREATE OR REPLACE TABLE mart.ai_task_year AS
WITH answered AS (
    SELECT r.survey_year, sum(w.weight) AS sw, count(*) AS n
    FROM core.fact_respondent AS r JOIN core.respondent_weight AS w USING (resp_key)
    WHERE r.ai_task_answered GROUP BY r.survey_year
)
SELECT t.survey_year, t.task, count(*) AS n, sum(w.weight) / any_value(a.sw) AS share_w, any_value(a.n) AS base_n
FROM core.bridge_ai_task AS t
JOIN core.respondent_weight AS w ON w.resp_key = t.resp_key
JOIN answered AS a ON a.survey_year = t.survey_year
GROUP BY t.survey_year, t.task
ORDER BY t.survey_year, share_w DESC;
