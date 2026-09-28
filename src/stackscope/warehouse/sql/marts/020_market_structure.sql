-- =============================================================================================
-- Market structure: mindshare concentration per category and year.
--
-- Mindshare = a technology's share of all (weighted) usage mentions in its category. From it we
-- derive the classic market-analysis statistics: Herfindahl-Hirschman Index (HHI, 0-10,000),
-- CR3 / CR5 concentration ratios, the leader and its lead over #2, and the "effective number of
-- competitors" (10,000 / HHI). Note: this is developer mindshare, not vendor revenue.
-- =============================================================================================

CREATE OR REPLACE TABLE mart.tech_mindshare AS
SELECT
    survey_year, category, category_label, tech_id, tech,
    share_used_w,
    share_used_w / sum(share_used_w) OVER (PARTITION BY survey_year, category) AS mindshare,
    row_number() OVER (PARTITION BY survey_year, category ORDER BY share_used_w DESC) AS position
FROM mart.tech_year;

CREATE OR REPLACE TABLE mart.market_concentration AS
WITH ranked AS (SELECT * FROM mart.tech_mindshare)
SELECT
    survey_year,
    category,
    any_value(category_label)                                      AS category_label,
    count(*)                                                       AS technologies,
    round(10000 * sum(mindshare * mindshare))                      AS hhi,
    round(1 / sum(mindshare * mindshare), 2)                        AS effective_competitors,
    sum(mindshare) FILTER (WHERE position <= 3)                    AS cr3,
    sum(mindshare) FILTER (WHERE position <= 5)                    AS cr5,
    arg_max(tech, mindshare)                                       AS leader,
    max(mindshare)                                                 AS leader_share,
    max(mindshare) - max(mindshare) FILTER (WHERE position = 2)    AS lead_over_second,
    CASE
        WHEN 10000 * sum(mindshare * mindshare) >= 2500 THEN 'Highly concentrated'
        WHEN 10000 * sum(mindshare * mindshare) >= 1500 THEN 'Moderately concentrated'
        ELSE 'Competitive'
    END                                                            AS structure
FROM ranked
GROUP BY survey_year, category
ORDER BY category, survey_year;
