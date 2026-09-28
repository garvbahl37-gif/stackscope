"""SQL-lab validation (unit) and API contract tests (integration: need the built warehouse)."""

import pytest
from fastapi import HTTPException

from stackscope import settings
from stackscope.api.routers.sql_lab import validate


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select * from mart.tech_year;",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "-- a comment; with a semicolon\nSELECT 1",
    "/* block; comment */ SELECT 1",
    "SELECT 'text; with semicolon' AS s",
    "PIVOT (SELECT 1 AS a, 'x' AS b) ON b USING sum(a)",
    "DESCRIBE core.fact_respondent",
])
def test_sql_lab_accepts_read_only(sql):
    assert validate(sql)


@pytest.mark.parametrize("sql, reason", [
    ("DROP TABLE core.fact_respondent", "read-only"),
    ("DELETE FROM mart.tech_year", "read-only"),
    ("SELECT 1; DROP TABLE x", "one statement"),
    ("COPY core.dim_year TO 'x.csv'", "read-only"),
    ("ATTACH 'other.db'", "read-only"),
    ("SET enable_external_access = true", "read-only"),
    ("-- nothing but a comment", "Empty"),
])
def test_sql_lab_blocks_everything_else(sql, reason):
    with pytest.raises(HTTPException) as err:
        validate(sql)
    assert reason.lower() in err.value.detail.lower()


needs_warehouse = pytest.mark.skipif(not settings.WAREHOUSE_PATH.exists(), reason="warehouse not built (run `make pipeline`)")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from stackscope.api.main import app
    return TestClient(app)


@pytest.mark.integration
@needs_warehouse
def test_health_reports_all_respondents(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["respondents"] == 664_042


@pytest.mark.integration
@needs_warehouse
def test_trends_contract(client):
    body = client.get("/api/tech/trends", params={"techs": "Python,Rust", "metric": "adoption"}).json()
    assert {s["tech"] for s in body["series"]} == {"Python", "Rust"}
    point = body["series"][0]["points"][-1]
    assert point["lo"] <= point["value"] <= point["hi"]


@pytest.mark.integration
@needs_warehouse
def test_sql_lab_cannot_read_files(client):
    res = client.post("/api/sql/run", json={"query": "SELECT * FROM read_csv('/etc/passwd')"})
    assert res.status_code == 400


@pytest.mark.integration
@needs_warehouse
def test_estimate_is_ordered_and_explained(client):
    res = client.post("/api/talent/estimate", json={"country": "IND", "dev_role": "Back-end developer", "years_code": 5,
                                                    "technologies": ["Python", "AWS"]})
    body = res.json()
    assert res.status_code == 200
    assert body["p10"] < body["p50"] < body["p90"]
    assert {c["group"] for c in body["contributions"]} >= {"Location", "Experience"}
