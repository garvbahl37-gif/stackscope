-- =============================================================================================
-- mart.tech_year — the technology KPI cube: one row per technology per survey year.
--
--   share_used      % of respondents who answered the question that listed the technology and used it
--   share_wanted    % who want to work with it next year
--   retention       % of current users who want to keep using it   ("admired"; 1 - churn)
--   attraction      % of non-users who want to start using it      (acquisition pull)
--   net_desire      share_wanted - share_used                       (mindshare flowing in or out)
--
-- Every metric exists raw and composition-weighted (_w). Weighted intervals use the Kish effective
-- sample size. Denominators are respondents who answered the question group(s) that listed the
-- technology that year — never all respondents — because technologies move between questions.
-- =============================================================================================

CREATE OR REPLACE TABLE mart.tech_year AS
WITH
group_base AS (      -- answerers per question group, year and side (used / want)
    SELECT a.survey_year, a.field_group, a.side,
           count(*) AS n, sum(w.weight) AS sw, sum(w.weight * w.weight) AS sw2
    FROM core.bridge_answered AS a
    JOIN core.respondent_weight AS w USING (resp_key)
    GROUP BY ALL
),
multi AS (           -- technology-years listed in more than one question group (e.g. Spring in 2023)
    SELECT survey_year, tech_id FROM core.tech_year_group GROUP BY ALL HAVING count(*) > 1
),
multi_base AS (      -- exact union of answerers for those
    SELECT x.survey_year, x.tech_id, x.side,
           count(*) AS n, sum(w.weight) AS sw, sum(w.weight * w.weight) AS sw2
    FROM (
        SELECT DISTINCT g.survey_year, g.tech_id, a.side, a.resp_key
        FROM core.tech_year_group AS g
        SEMI JOIN multi AS m ON m.survey_year = g.survey_year AND m.tech_id = g.tech_id
        JOIN core.bridge_answered AS a ON a.survey_year = g.survey_year AND a.field_group = g.field_group
    ) AS x
    JOIN core.respondent_weight AS w USING (resp_key)
    GROUP BY ALL
),
base AS (
    SELECT g.survey_year, g.tech_id, gb.side, gb.n, gb.sw, gb.sw2
    FROM core.tech_year_group AS g
    ANTI JOIN multi AS m ON m.survey_year = g.survey_year AND m.tech_id = g.tech_id
    JOIN group_base AS gb ON gb.survey_year = g.survey_year AND gb.field_group = g.field_group
    UNION ALL
    SELECT survey_year, tech_id, side, n, sw, sw2 FROM multi_base
),
numerators AS (
    SELECT u.survey_year, u.tech_id,
           count(*)          FILTER (WHERE u.used)              AS n_used,
           sum(w.weight)     FILTER (WHERE u.used)              AS sw_used,
           count(*)          FILTER (WHERE u.wanted)            AS n_wanted,
           sum(w.weight)     FILTER (WHERE u.wanted)            AS sw_wanted,
           count(*)          FILTER (WHERE u.used AND u.wanted) AS n_retained,
           sum(w.weight)     FILTER (WHERE u.used AND u.wanted) AS sw_retained
    FROM core.bridge_tech_usage AS u
    JOIN core.respondent_weight AS w USING (resp_key)
    GROUP BY ALL
),
users_answered_want AS (   -- retention denominator: users who were also asked what they want next
    SELECT x.survey_year, x.tech_id, count(*) AS n, sum(w.weight) AS sw
    FROM (
        SELECT DISTINCT u.survey_year, u.tech_id, u.resp_key
        FROM core.bridge_tech_usage AS u
        JOIN core.tech_year_group AS g ON g.survey_year = u.survey_year AND g.tech_id = u.tech_id
        JOIN core.bridge_answered AS a
          ON a.resp_key = u.resp_key AND a.field_group = g.field_group AND a.side = 'want'
        WHERE u.used
    ) AS x
    JOIN core.respondent_weight AS w USING (resp_key)
    GROUP BY ALL
),
metrics AS (
    SELECT
        t.tech_id, t.tech, t.category, t.category_label, nu.survey_year,
        bu.n                                           AS base_n,
        round(kish_n(bu.sw, bu.sw2))                   AS base_n_eff,
        nu.n_used,
        nu.n_used / bu.n                               AS share_used,
        nu.sw_used / bu.sw                             AS share_used_w,
        bw.n                                           AS base_want_n,
        nu.n_wanted,
        safe_div(nu.n_wanted, bw.n)                    AS share_wanted,
        safe_div(nu.sw_wanted, bw.sw)                  AS share_wanted_w,
        uw.n                                           AS users_asked_want,
        uw.sw                                          AS users_asked_want_w,
        nu.n_retained,
        safe_div(nu.n_retained, uw.n)                  AS retention,
        safe_div(nu.sw_retained, uw.sw)                AS retention_w,
        safe_div(nu.n_wanted - nu.n_retained, bw.n - uw.n)       AS attraction,
        safe_div(nu.sw_wanted - nu.sw_retained, bw.sw - uw.sw)   AS attraction_w,
        kish_n(bu.sw, bu.sw2)                          AS neff
    FROM numerators AS nu
    JOIN core.dim_technology AS t USING (tech_id)
    JOIN base AS bu ON bu.survey_year = nu.survey_year AND bu.tech_id = nu.tech_id AND bu.side = 'used'
    LEFT JOIN base AS bw ON bw.survey_year = nu.survey_year AND bw.tech_id = nu.tech_id AND bw.side = 'want'
    LEFT JOIN users_answered_want AS uw ON uw.survey_year = nu.survey_year AND uw.tech_id = nu.tech_id
)
SELECT
    m.* EXCLUDE (neff),
    wilson_lo(m.share_used, m.base_n)       AS share_used_lo,
    wilson_hi(m.share_used, m.base_n)       AS share_used_hi,
    wilson_lo(m.share_used_w, m.neff)       AS share_used_w_lo,
    wilson_hi(m.share_used_w, m.neff)       AS share_used_w_hi,
    m.share_wanted_w - m.share_used_w       AS net_desire_w,
    -- previous-wave value only when the previous wave is exactly one year earlier
    CASE WHEN lag(m.survey_year) OVER w = m.survey_year - 1
         THEN lag(m.share_used_w) OVER w END AS prev_share_used_w,
    CASE WHEN lag(m.survey_year) OVER w = m.survey_year - 1
         THEN lag(m.base_n_eff)   OVER w END AS prev_base_n_eff,
    rank() OVER (PARTITION BY m.survey_year, m.category ORDER BY m.share_used_w DESC) AS rank_in_category,
    m.n_used / sum(m.n_used) OVER (PARTITION BY m.survey_year, m.category)           AS mention_share
FROM metrics AS m
WINDOW w AS (PARTITION BY m.tech_id ORDER BY m.survey_year)
ORDER BY m.category, m.tech, m.survey_year;
