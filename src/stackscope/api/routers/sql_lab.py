"""SQL Lab — run read-only SQL against the warehouse from the browser.

Defence in depth: single statement, read-only statement types only, a dedicated read-only connection
with external file/network access disabled and configuration locked (so it cannot be re-enabled via
SET), memory/thread caps, a 10-second timeout and a 500-row result cap.
"""

from __future__ import annotations

import threading
import time

import duckdb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ... import settings
from ..db import clean

router = APIRouter(prefix="/sql", tags=["sql-lab"])

ALLOWED_FIRST_WORDS = {"select", "with", "pivot", "unpivot", "describe", "summarize", "show", "from", "values",
                       "explain", "table"}
MAX_ROWS = 500
TIMEOUT_S = 10.0

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


def _connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        with _lock:
            if _con is None:
                con = duckdb.connect(str(settings.WAREHOUSE_PATH), read_only=True,
                                     config={"enable_external_access": False})
                con.execute("SET memory_limit = '1GB'")
                con.execute("SET threads = 2")
                con.execute("SET enable_progress_bar = false")
                con.execute("SET lock_configuration = true")
                _con = con
    return _con


class SqlRequest(BaseModel):
    query: str = Field(..., max_length=20_000)


def code_only(sql: str) -> str:
    """Blank out comments and string/identifier literals so validation sees only SQL keywords."""
    out, i, n = [], 0, len(sql)
    while i < n:
        two = sql[i:i + 2]
        if two == "--":
            end = sql.find("\n", i)
            i = n if end == -1 else end
        elif two == "/*":
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        elif sql[i] in ("'", '"'):
            quote, j = sql[i], i + 1
            while j < n and not (sql[j] == quote and sql[j + 1:j + 2] != quote):
                j += 2 if sql[j] == quote else 1
            out.append(" ")
            i = j + 1
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)


def validate(sql: str) -> str:
    code = code_only(sql).strip().rstrip(";").strip()
    if not code:
        raise HTTPException(400, "Empty query")
    if ";" in code:
        raise HTTPException(400, "Run one statement at a time")
    first = code.lstrip("(").split(None, 1)[0].lower()
    if first not in ALLOWED_FIRST_WORDS:
        raise HTTPException(400, f"Only read-only queries are allowed (got '{first.upper()}')")
    return sql.strip().rstrip(";")


@router.post("/run")
def run(request: SqlRequest) -> dict:
    statement = validate(request.query)
    cur = _connection().cursor()
    timer = threading.Timer(TIMEOUT_S, cur.interrupt)
    started = time.perf_counter()
    timer.start()
    try:
        result = cur.execute(statement)
        columns = [{"name": d[0], "type": str(d[1])} for d in result.description] if result.description else []
        rows = result.fetchmany(MAX_ROWS + 1)
    except duckdb.InterruptException as exc:
        raise HTTPException(408, f"Query exceeded {TIMEOUT_S:.0f}s and was cancelled") from exc
    except duckdb.Error as exc:
        raise HTTPException(400, str(exc).split("\n")[0][:500]) from exc
    finally:
        timer.cancel()
        cur.close()
    elapsed = (time.perf_counter() - started) * 1000
    truncated = len(rows) > MAX_ROWS
    return {"columns": columns, "rows": [clean(list(r)) for r in rows[:MAX_ROWS]], "row_count": min(len(rows), MAX_ROWS),
            "truncated": truncated, "elapsed_ms": round(elapsed, 1)}


@router.get("/schema")
def schema() -> dict:
    cur = _connection().cursor()
    try:
        rows = cur.execute("""
            SELECT c.schema_name, c.table_name, c.column_name, c.data_type, t.estimated_size
            FROM duckdb_columns() AS c
            LEFT JOIN duckdb_tables() AS t USING (schema_name, table_name)
            WHERE c.schema_name IN ('core', 'mart', 'dq', 'ml')
            ORDER BY c.schema_name, c.table_name, c.column_index""").fetchall()
    finally:
        cur.close()
    tables: dict[str, dict] = {}
    for schema_name, table, column, dtype, size in rows:
        key = f"{schema_name}.{table}"
        tables.setdefault(key, {"name": key, "schema": schema_name, "rows": size, "columns": []})["columns"].append(
            {"name": column, "type": dtype})
    return {"tables": list(tables.values())}


EXAMPLES = [
    {"title": "Top 5 languages per year", "skill": "Window ranking + QUALIFY", "sql": """SELECT survey_year, tech, round(100 * share_used_w, 1) AS pct_using
FROM mart.tech_year
WHERE category = 'language'
QUALIFY dense_rank() OVER (PARTITION BY survey_year ORDER BY share_used_w DESC) <= 5
ORDER BY survey_year, pct_using DESC;"""},
    {"title": "Year-over-year change with confidence intervals", "skill": "LAG + custom Wilson-interval macros", "sql": """SELECT tech, survey_year,
       round(100 * share_used, 1)                          AS pct,
       round(100 * wilson_lo(share_used, base_n), 1)       AS ci_low,
       round(100 * wilson_hi(share_used, base_n), 1)       AS ci_high,
       round(100 * (share_used - lag(share_used) OVER (PARTITION BY tech ORDER BY survey_year)), 1) AS yoy_pp
FROM mart.tech_year
WHERE tech IN ('Rust', 'Go', 'TypeScript')
ORDER BY tech, survey_year;"""},
    {"title": "Salary percentiles by country (2025)", "skill": "Star-schema join + percentiles + HAVING", "sql": """SELECT c.country,
       count(*)                                  AS n,
       round(quantile_cont(r.comp_usd, 0.25))    AS p25_usd,
       round(median(r.comp_usd))                 AS median_usd,
       round(quantile_cont(r.comp_usd, 0.75))    AS p75_usd,
       round(median(r.comp_ppp))                 AS median_ppp
FROM core.fact_respondent AS r
JOIN core.dim_country AS c USING (iso3)
WHERE r.in_pay_benchmark AND r.survey_year = 2025
GROUP BY c.country
HAVING count(*) >= 200
ORDER BY median_usd DESC;"""},
    {"title": "Remote-work mix by year", "skill": "PIVOT", "sql": """PIVOT (
    SELECT survey_year, remote_work, count(*) AS n
    FROM core.fact_respondent
    WHERE is_professional AND remote_work IS NOT NULL
    GROUP BY ALL
) ON remote_work USING sum(n)
ORDER BY survey_year;"""},
    {"title": "What else do Rust developers use?", "skill": "CTE + SEMI JOIN on a bridge table", "sql": """WITH rust_devs AS (
    SELECT resp_key FROM core.v_tech_usage
    WHERE tech = 'Rust' AND used AND survey_year = 2025
)
SELECT u.tech, u.category,
       count(*) AS developers,
       round(100.0 * count(*) / (SELECT count(*) FROM rust_devs), 1) AS pct_of_rust_devs
FROM core.v_tech_usage AS u
SEMI JOIN rust_devs USING (resp_key)
WHERE u.used AND u.survey_year = 2025 AND u.tech <> 'Rust'
GROUP BY ALL
ORDER BY developers DESC
LIMIT 15;"""},
    {"title": "Real pay by region and experience", "skill": "GROUP BY ROLLUP (subtotals)", "sql": """SELECT coalesce(region, 'All regions')      AS region,
       coalesce(exp_band, 'All experience')  AS experience,
       count(*)                              AS n,
       round(median(comp_usd_real))          AS median_real_usd
FROM core.fact_respondent
WHERE in_pay_benchmark AND survey_year = 2025
  AND region IN ('North America', 'Western Europe', 'South Asia')
GROUP BY ROLLUP (region, exp_band)
ORDER BY region NULLS LAST, experience;"""},
    {"title": "Where do PHP developers want to go?", "skill": "Churn-flow analysis", "sql": """SELECT to_tech,
       n                                AS developers,
       round(100 * share_of_churners, 1) AS pct_of_leavers,
       round(100 * from_churn_rate, 1)   AS php_churn_rate
FROM mart.tech_switching
WHERE from_tech = 'PHP' AND survey_year = 2025
ORDER BY n DESC
LIMIT 10;"""},
    {"title": "GenAI adoption and trust by experience", "skill": "Weighted conditional aggregation (FILTER)", "sql": """SELECT r.exp_band,
       count(*) FILTER (WHERE r.ai_use IS NOT NULL) AS n,
       round(100 * sum(w.weight) FILTER (WHERE r.ai_use = 'Using')
                 / sum(w.weight) FILTER (WHERE r.ai_use IS NOT NULL), 1) AS pct_using_ai,
       round(sum(w.weight * r.ai_trust_score) / sum(w.weight) FILTER (WHERE r.ai_trust_score IS NOT NULL), 2) AS net_trust
FROM core.fact_respondent AS r
JOIN core.respondent_weight AS w USING (resp_key)
WHERE r.survey_year = 2025 AND r.exp_band IS NOT NULL
GROUP BY r.exp_band
ORDER BY min(r.years_code);"""},
    {"title": "Market concentration (HHI) of cloud platforms", "skill": "Market-share analytics", "sql": """SELECT survey_year, hhi, effective_competitors, round(100 * cr3, 1) AS cr3_pct,
       leader, round(100 * leader_share, 1) AS leader_share_pct, structure
FROM mart.market_concentration
WHERE category = 'cloud'
ORDER BY survey_year;"""},
    {"title": "Data-quality scorecard", "skill": "Automated DQ checks", "sql": """SELECT dimension, check_id, status, threshold, detail
FROM dq.check_results
ORDER BY dimension, check_id;"""},
]


@router.get("/examples")
def examples() -> dict:
    return {"examples": EXAMPLES}
