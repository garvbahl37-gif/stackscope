-- =============================================================================================
-- Retention & churn-flow analysis (the technology equivalent of client-retention analytics).
--
-- A "churner" of X uses X today, was asked what they want next year, and did not pick X.
-- A churn flow X -> Y counts churners of X who want Y (same category) and do not use Y yet.
-- Weighted counts are used for shares; raw counts gate statistical reliability (n >= 20).
-- =============================================================================================

CREATE OR REPLACE TABLE mart.tech_switching AS
WITH u AS (
    SELECT b.resp_key, b.survey_year, b.tech_id, t.category, b.used, b.wanted, w.weight
    FROM core.bridge_tech_usage AS b
    JOIN core.dim_technology AS t USING (tech_id)
    JOIN core.respondent_weight AS w USING (resp_key)
    WHERE t.category IN ('language', 'database', 'cloud', 'webframe', 'library', 'devops', 'ide', 'ai')
),
flows AS (
    SELECT
        a.survey_year,
        a.category,
        a.tech_id                     AS from_id,
        b.tech_id                     AS to_id,
        count(*)                      AS n,
        sum(a.weight)                 AS sw
    FROM u AS a
    JOIN u AS b
      ON b.resp_key = a.resp_key AND b.category = a.category AND b.tech_id <> a.tech_id
    WHERE a.used AND NOT a.wanted          -- a: leaving
      AND b.wanted AND NOT b.used          -- b: arriving
    GROUP BY ALL
),
churners AS (   -- churners per technology-year, from the KPI cube
    SELECT survey_year, tech_id, users_asked_want - n_retained AS churners, retention
    FROM mart.tech_year
    WHERE users_asked_want > n_retained
)
SELECT
    f.survey_year,
    f.category,
    tf.tech                                             AS from_tech,
    tt.tech                                             AS to_tech,
    f.n,
    f.sw,
    f.n / c.churners                                    AS share_of_churners,
    c.churners                                          AS from_churners,
    1 - c.retention                                     AS from_churn_rate,
    rank() OVER (PARTITION BY f.survey_year, f.from_id ORDER BY f.n DESC) AS destination_rank
FROM flows AS f
JOIN core.dim_technology AS tf ON tf.tech_id = f.from_id
JOIN core.dim_technology AS tt ON tt.tech_id = f.to_id
JOIN churners AS c ON c.survey_year = f.survey_year AND c.tech_id = f.from_id
WHERE f.n >= 20;

-- Net migration between technology pairs: flow(A->B) - flow(B->A), as a share of both user bases.
CREATE OR REPLACE TABLE mart.tech_net_migration AS
SELECT
    a.survey_year, a.category,
    a.from_tech, a.to_tech,
    a.n                                      AS flow_forward,
    coalesce(b.n, 0)                         AS flow_backward,
    a.n - coalesce(b.n, 0)                   AS net_flow,
    (a.n - coalesce(b.n, 0)) / (a.n + coalesce(b.n, 0)) AS net_ratio
FROM mart.tech_switching AS a
LEFT JOIN mart.tech_switching AS b
  ON b.survey_year = a.survey_year AND b.from_tech = a.to_tech AND b.to_tech = a.from_tech
WHERE a.n > coalesce(b.n, 0);
