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

-- Answer options change between waves: the cloud question listed 6 platforms in 2018 and 11 in 2025,
-- and adding options lowers the HHI by itself. hhi_like_for_like is a chain-linked index that compares
-- each pair of consecutive waves only on the technologies listed in both, then chains the steps back
-- from the latest wave. It equals the latest HHI, and earlier values differ from it only by like-for-like
-- change. hhi is each wave's own snapshot over the options listed that year.
CREATE OR REPLACE TABLE mart.market_concentration AS
WITH snapshot AS (
    SELECT
        survey_year,
        category,
        any_value(category_label)                                      AS category_label,
        count(*)                                                       AS technologies,
        10000 * sum(mindshare * mindshare)                             AS hhi_exact,
        round(1 / sum(mindshare * mindshare), 2)                       AS effective_competitors,
        sum(mindshare) FILTER (WHERE position <= 3)                    AS cr3,
        sum(mindshare) FILTER (WHERE position <= 5)                    AS cr5,
        arg_max(tech, mindshare)                                       AS leader,
        max(mindshare)                                                 AS leader_share,
        max(mindshare) - max(mindshare) FILTER (WHERE position = 2)    AS lead_over_second
    FROM mart.tech_mindshare
    GROUP BY survey_year, category
),
waves AS (      -- consecutive waves of each category
    SELECT category, survey_year AS y1, lead(survey_year) OVER (PARTITION BY category ORDER BY survey_year) AS y2
    FROM snapshot
),
common AS (     -- technologies listed in both waves of a pair
    SELECT w.category, w.y1, w.y2, a.tech_id
    FROM waves AS w
    JOIN mart.tech_year AS a ON a.category = w.category AND a.survey_year = w.y1
    JOIN mart.tech_year AS b ON b.category = w.category AND b.survey_year = w.y2 AND b.tech_id = a.tech_id
),
common_hhi AS ( -- HHI of each wave of the pair, over the common technologies only
    SELECT c.category, c.y1, c.y2, t.survey_year,
           10000 * sum(t.share_used_w * t.share_used_w) / (sum(t.share_used_w) * sum(t.share_used_w)) AS hhi
    FROM common AS c
    JOIN mart.tech_year AS t ON t.category = c.category AND t.tech_id = c.tech_id AND t.survey_year IN (c.y1, c.y2)
    GROUP BY c.category, c.y1, c.y2, t.survey_year
),
steps AS (      -- like-for-like log change from y1 to y2
    SELECT category, y1,
           ln(max(hhi) FILTER (WHERE survey_year = y2) / max(hhi) FILTER (WHERE survey_year = y1)) AS log_step
    FROM common_hhi
    GROUP BY category, y1, y2
),
chain AS (      -- cumulative like-for-like change from each wave to the latest
    SELECT s.category, s.survey_year, coalesce(sum(st.log_step), 0) AS log_to_latest
    FROM snapshot AS s
    LEFT JOIN steps AS st ON st.category = s.category AND st.y1 >= s.survey_year
    GROUP BY s.category, s.survey_year
),
latest AS (
    SELECT category, arg_max(hhi_exact, survey_year) AS hhi_latest FROM snapshot GROUP BY category
)
SELECT
    s.survey_year,
    s.category,
    s.category_label,
    s.technologies,
    round(s.hhi_exact)                                             AS hhi,
    round(l.hhi_latest * exp(-c.log_to_latest))                    AS hhi_like_for_like,
    s.effective_competitors,
    s.cr3,
    s.cr5,
    s.leader,
    s.leader_share,
    s.lead_over_second,
    CASE
        WHEN s.hhi_exact >= 2500 THEN 'Highly concentrated'
        WHEN s.hhi_exact >= 1500 THEN 'Moderately concentrated'
        ELSE 'Competitive'
    END                                                            AS structure
FROM snapshot AS s
JOIN chain AS c USING (category, survey_year)
JOIN latest AS l USING (category)
ORDER BY s.category, s.survey_year;
