"""Read-only warehouse access for the API.

One process-wide DuckDB connection (read-only, external file/network access disabled); each request
uses its own cursor, which DuckDB makes safe across threads. Values are sanitised for JSON (NaN/inf
-> null). The warehouse is immutable between pipeline runs, so query results are memoised.
"""

from __future__ import annotations

import math
import threading
from datetime import date, datetime
from functools import lru_cache
from typing import Any

import duckdb

from .. import settings

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


def connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        with _lock:
            if _con is None:
                if not settings.WAREHOUSE_PATH.exists():
                    raise RuntimeError(f"Warehouse not found at {settings.WAREHOUSE_PATH}. Run `stackscope run` first.")
                _con = duckdb.connect(str(settings.WAREHOUSE_PATH), read_only=True,
                                      config={"enable_external_access": False})
                _con.execute("SET enable_progress_bar = false")
    return _con


def clean(value: Any) -> Any:
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def query(sql: str, params: list | tuple | None = None) -> list[dict[str, Any]]:
    cur = connection().cursor()
    try:
        result = cur.execute(sql, list(params or []))
        columns = [d[0] for d in result.description]
        return [{c: clean(v) for c, v in zip(columns, row, strict=True)} for row in result.fetchall()]
    finally:
        cur.close()


def scalar(sql: str, params: list | tuple | None = None) -> Any:
    rows = query(sql, params)
    return next(iter(rows[0].values())) if rows else None


@lru_cache(maxsize=512)
def cached(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Memoised query for immutable warehouse data (params must be a hashable tuple)."""
    return query(sql, params)
