-- =============================================================================================
-- Bridge tables (many-to-many facts) keyed on integer surrogate keys
-- =============================================================================================

CREATE OR REPLACE TABLE core.bridge_tech_usage AS
SELECT u.resp_key, u.survey_year, t.tech_id, u.used, u.wanted
FROM staging.tech_usage AS u
JOIN core.dim_technology AS t USING (tech)
ORDER BY u.survey_year, t.tech_id;

-- Which technology question groups each respondent answered: the denominator of every share.
CREATE OR REPLACE TABLE core.bridge_answered AS
SELECT resp_key, survey_year, field_group, side
FROM staging.answered
ORDER BY survey_year, field_group;

-- Which question group(s) listed each technology in each year (technologies move between questions).
CREATE OR REPLACE TABLE core.tech_year_group AS
SELECT y.survey_year, t.tech_id, y.field_group
FROM staging.tech_year_group AS y
JOIN core.dim_technology AS t USING (tech);

CREATE OR REPLACE TABLE core.bridge_role AS
SELECT resp_key, survey_year, role FROM staging.roles;

CREATE OR REPLACE TABLE core.bridge_ai_task AS
SELECT resp_key, survey_year, task FROM staging.ai_tasks;

CREATE OR REPLACE VIEW core.v_tech_usage AS
SELECT b.resp_key, b.survey_year, t.tech, t.category, b.used, b.wanted
FROM core.bridge_tech_usage AS b
JOIN core.dim_technology AS t USING (tech_id);

CREATE OR REPLACE TABLE dq.label_coverage AS
SELECT * FROM staging.label_coverage;
