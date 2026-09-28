-- =============================================================================================
-- Core dimensions: country, technology, survey year
-- =============================================================================================

CREATE OR REPLACE TABLE core.dim_country AS
SELECT DISTINCT
    iso3,
    country,
    CAST(iso_numeric AS INTEGER)    AS iso_numeric,
    region,
    un_region,
    income_group,
    capital,
    lon,
    lat
FROM staging.countries
WHERE iso3 IS NOT NULL;

-- A technology exists in the warehouse only if at least one respondent selected it.
CREATE OR REPLACE TABLE core.dim_technology AS
WITH seen AS (
    SELECT tech,
           min(survey_year)            AS first_year,
           max(survey_year)            AS last_year,
           count(DISTINCT survey_year) AS n_years
    FROM staging.tech_year_group
    GROUP BY tech
)
SELECT
    CAST(row_number() OVER (ORDER BY c.category, c.tech) AS SMALLINT) AS tech_id,
    c.tech,
    c.category,
    c.category_label,
    c.note,
    s.first_year,
    s.last_year,
    s.n_years
FROM staging.tech_catalog AS c
JOIN seen AS s USING (tech);

CREATE OR REPLACE TABLE core.dim_year AS
SELECT
    survey_year,
    count(*)                                                     AS respondents,
    count(*) FILTER (WHERE respondent_type = 'Professional developer') AS professionals,
    count(DISTINCT country_raw)                                  AS country_labels,
    bool_or(respondent_type_derived)                             AS respondent_type_derived
FROM staging.respondents
GROUP BY survey_year;
