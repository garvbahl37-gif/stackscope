"""Gold layer — build the DuckDB warehouse by running the versioned SQL models in order.

    sql/core/*.sql   conformed dimensions, facts and bridges (star schema)
    sql/marts/*.sql  aggregated, analysis-ready marts consumed by the API and reports

The staging schema is a set of views over the silver Parquet files; it is dropped at the end so
the resulting .duckdb file is self-contained and portable.
"""

from __future__ import annotations

import time
from pathlib import Path
from string import Template

import duckdb

from .. import settings

SQL_DIR = Path(__file__).resolve().parent / "sql"
SILVER_TABLES = ["respondents", "tech_usage", "answered", "tech_year_group", "roles", "ai_tasks",
                 "label_coverage", "countries", "tech_catalog"]


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings.WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.WAREHOUSE_PATH), read_only=read_only)
    con.execute("SET enable_progress_bar = false")
    return con


def _params() -> dict[str, str]:
    return {"base_year": str(settings.BASE_PRICE_YEAR)}


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path) -> float:
    sql = Template(path.read_text()).safe_substitute(_params())
    t0 = time.time()
    con.execute(sql)
    return time.time() - t0


def run_sql_dir(con: duckdb.DuckDBPyConnection, name: str) -> None:
    for path in sorted((SQL_DIR / name).glob("*.sql")):
        elapsed = run_sql_file(con, path)
        print(f"  [gold] {name}/{path.name:<28} {elapsed:5.1f}s")


def _create_staging(con: duckdb.DuckDBPyConnection) -> None:
    for schema in ("staging", "core", "mart", "dq", "ml"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for table in SILVER_TABLES:
        path = settings.SILVER_DIR / f"{table}.parquet"
        con.execute(f"CREATE OR REPLACE VIEW staging.{table} AS SELECT * FROM read_parquet('{path}')")
    ext = settings.EXTERNAL_DIR
    con.execute(f"CREATE OR REPLACE VIEW staging.wb_indicators AS SELECT * FROM read_csv('{ext / 'wb_indicators.csv'}', header=true)")
    con.execute(f"CREATE OR REPLACE VIEW staging.cpi AS SELECT * FROM read_csv('{ext / 'cpi_us.csv'}', header=true)")


def build_core() -> None:
    con = connect()
    try:
        _create_staging(con)
        run_sql_dir(con, "core")
        con.execute("DROP SCHEMA staging CASCADE")
    finally:
        con.close()


def build_marts() -> None:
    con = connect()
    try:
        run_sql_dir(con, "marts")
    finally:
        con.close()


def compact() -> dict:
    """Rewrite the warehouse into a fresh file in DuckDB's newest storage format.

    Stages rewrite tables in place, which leaves free blocks behind; a fresh copy with the newest compression
    is ~10% smaller, which keeps the file under the 100 MB per-file limit of Vercel CLI uploads. The copy
    replaces the original only after every table's row count and order-independent content hash, and the
    number of views and macros, match.
    """
    src, tmp = settings.WAREHOUSE_PATH, settings.WAREHOUSE_PATH.with_suffix(".compact.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{src}' AS src (READ_ONLY)")
        con.execute(f"ATTACH '{tmp}' AS dst (STORAGE_VERSION 'latest')")
        con.execute("COPY FROM DATABASE src TO dst")
        tables = con.execute("""SELECT schema_name, table_name FROM duckdb_tables()
                                WHERE database_name = 'src' ORDER BY ALL""").fetchall()
        for schema, table in tables:
            probe = "SELECT count(*), bit_xor(hash(t)) FROM {db}." + f"{schema}.{table} AS t"
            if con.execute(probe.format(db="src")).fetchone() != con.execute(probe.format(db="dst")).fetchone():
                raise RuntimeError(f"compaction changed {schema}.{table}")
        objects = """SELECT (SELECT count(*) FROM duckdb_views() WHERE database_name = '{db}' AND NOT internal),
                            (SELECT count(*) FROM duckdb_functions() WHERE database_name = '{db}' AND NOT internal
                                                                         AND function_type LIKE '%macro')"""
        if con.execute(objects.format(db="src")).fetchone() != con.execute(objects.format(db="dst")).fetchone():
            raise RuntimeError("compaction lost views or macros")
    finally:
        con.close()
    before, after = src.stat().st_size, tmp.stat().st_size
    tmp.replace(src)
    return {"tables": len(tables), "mb_before": round(before / 1e6, 1), "mb_after": round(after / 1e6, 1)}
