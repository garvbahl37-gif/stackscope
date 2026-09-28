-- =============================================================================================
-- fact_respondent: one row per survey response (664k), conformed to the dimensions, with a
-- three-way normalised compensation measure:
--     comp_usd       nominal USD, cleaned
--     comp_usd_real  constant ${base_year} USD (US CPI-U)
--     comp_ppp       international dollars (World Bank PPP price level)
--
-- Cleaning is robust and market-relative: a salary is kept when it lies within $1k-$1M and its
-- log value sits within 3.5 modified z-scores (Iglewicz-Hoaglin, MAD-based) of the full-time
-- median for the same country and year (region-year when the country has < 30 salaries).
-- This removes monthly-entered-as-annual answers and typos without trimming real top earners.
-- =============================================================================================

CREATE OR REPLACE TABLE core.fact_respondent AS
WITH base AS (
    SELECT r.*, c.iso3, c.region, c.income_group
    FROM staging.respondents AS r
    LEFT JOIN staging.countries AS c USING (country_raw)
),
pay_scope AS (
    SELECT survey_year, iso3, region, ln(comp_usd_raw) AS log_pay
    FROM base
    WHERE comp_usd_raw BETWEEN 1000 AND 1000000
      AND employment = 'Full-time'
),
country_ref AS (
    SELECT survey_year, iso3, count(*) AS n, median(log_pay) AS med, mad(log_pay) AS mad
    FROM pay_scope WHERE iso3 IS NOT NULL GROUP BY ALL
),
region_ref AS (
    SELECT survey_year, region, count(*) AS n, median(log_pay) AS med, mad(log_pay) AS mad
    FROM pay_scope WHERE region IS NOT NULL GROUP BY ALL
),
scored AS (
    SELECT
        b.*,
        CASE WHEN cr.n >= 30 THEN cr.med ELSE rr.med END AS ref_median,
        CASE WHEN cr.n >= 30 THEN cr.mad ELSE rr.mad END AS ref_mad
    FROM base AS b
    LEFT JOIN country_ref AS cr ON cr.survey_year = b.survey_year AND cr.iso3 = b.iso3
    LEFT JOIN region_ref  AS rr ON rr.survey_year = b.survey_year AND rr.region = b.region
),
cleaned AS (
    SELECT
        s.* EXCLUDE (ref_median, ref_mad, country_raw),
        0.6745 * (ln(s.comp_usd_raw) - s.ref_median) / nullif(s.ref_mad, 0) AS comp_mod_z,
        CASE
            WHEN s.comp_usd_raw IS NULL                             THEN 'missing'
            WHEN s.comp_usd_raw NOT BETWEEN 1000 AND 1000000        THEN 'out_of_bounds'
            WHEN s.ref_mad IS NULL                                  THEN 'no_reference'
            WHEN abs(0.6745 * (ln(s.comp_usd_raw) - s.ref_median) / nullif(s.ref_mad, 0)) > 3.5
                                                                    THEN 'market_outlier'
            ELSE 'valid'
        END AS comp_status
    FROM scored AS s
)
SELECT
    c.*,
    CASE WHEN c.comp_status = 'valid' THEN c.comp_usd_raw END                         AS comp_usd,
    CASE WHEN c.comp_status = 'valid' THEN c.comp_usd_raw * cpi.to_base_year END      AS comp_usd_real,
    CASE WHEN c.comp_status = 'valid' THEN c.comp_usd_raw / m.price_level END         AS comp_ppp,
    c.respondent_type = 'Professional developer'                                      AS is_professional,
    c.comp_status = 'valid' AND c.employment = 'Full-time'
        AND c.respondent_type = 'Professional developer'                              AS in_pay_benchmark,
    c.survey_year = 2017                                                              AS comp_topcoded
FROM cleaned AS c
LEFT JOIN core.dim_cpi   AS cpi ON cpi.year = c.survey_year
LEFT JOIN core.fact_macro AS m  ON m.iso3 = c.iso3 AND m.year = c.survey_year;
