-- =============================================================================================
-- Macro context per country-year (World Bank) with forward-fill for publication lag,
-- and the US CPI deflator used to express pay in constant ${base_year} dollars.
-- =============================================================================================

CREATE OR REPLACE TABLE core.fact_macro AS
WITH wide AS (
    PIVOT staging.wb_indicators
    ON indicator IN ('ppp_factor', 'fx_rate', 'gdp_pc_ppp', 'population')
    USING first(value)
    GROUP BY iso3, year
),
grid AS (
    SELECT c.iso3, CAST(y.year AS INTEGER) AS year
    FROM (SELECT DISTINCT iso3 FROM core.dim_country) AS c
    CROSS JOIN range(2015, ${base_year} + 1) AS y(year)
),
filled AS (
    SELECT
        g.iso3,
        g.year,
        -- the World Bank publishes with a lag: carry the latest observation forward
        last_value(w.ppp_factor IGNORE NULLS) OVER win AS ppp_factor,
        last_value(w.fx_rate    IGNORE NULLS) OVER win AS fx_rate,
        last_value(w.gdp_pc_ppp IGNORE NULLS) OVER win AS gdp_pc_ppp,
        last_value(w.population IGNORE NULLS) OVER win AS population,
        w.ppp_factor IS NULL AS ppp_imputed
    FROM grid AS g
    LEFT JOIN wide AS w ON w.iso3 = g.iso3 AND w.year = g.year
    WINDOW win AS (PARTITION BY g.iso3 ORDER BY g.year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
-- Price level relative to the US (< 1 means a dollar buys more locally), with two integration fixes:
--  * Croatia's PPP series was re-denominated into euros at euro adoption (2023) while its historical
--    official exchange rate is still in kuna -> convert kuna to euro at the fixed 7.53450 rate.
--  * Pegged/official rates far from market rates (Iran, Lebanon, Sudan) and dollarised economies
--    (Zimbabwe, Liberia) produce meaningless ratios -> values outside the plausible 0.10-1.80 band
--    (ICP extremes) are withheld rather than silently distorting PPP pay.
, adjusted AS (
    SELECT
        *,
        ppp_factor / nullif(CASE WHEN iso3 = 'HRV' AND fx_rate > 3 THEN fx_rate / 7.53450 ELSE fx_rate END, 0)
            AS price_level_raw
    FROM filled
)
SELECT
    * EXCLUDE (price_level_raw),
    price_level_raw,
    CASE WHEN price_level_raw BETWEEN 0.10 AND 1.80 THEN price_level_raw END AS price_level,
    CASE
        WHEN price_level_raw IS NULL                     THEN 'missing'
        WHEN price_level_raw BETWEEN 0.10 AND 1.80        THEN 'ok'
        ELSE 'implausible'
    END AS price_level_status
FROM adjusted;

CREATE OR REPLACE TABLE core.dim_cpi AS
SELECT
    CAST(year AS INTEGER) AS year,
    cpi,
    (SELECT cpi FROM staging.cpi WHERE year = ${base_year}) / cpi AS to_base_year
FROM staging.cpi;
