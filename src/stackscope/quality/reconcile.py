"""Reconcile the pipeline with Stack Overflow's own published results.

config/published_benchmarks.yml holds figures from survey.stackoverflow.co. Each is recomputed from the warehouse,
unweighted and with the publisher's definition, so agreement shows the harmonisation reproduces the source. When the
publisher's base counts respondents the public data file does not show as answering (answers withheld from the
release), the share is compared but flagged, and the published count of users is checked instead.
"""

from __future__ import annotations

import pandas as pd
import yaml

from .. import settings

TOLERANCE_PP = 0.5       # shares on the same base must agree within half a percentage point
BASE_TOLERANCE = 0.01    # our base within 1% of the published responses counts as the same definition


def benchmarks() -> list[dict]:
    with open(settings.CONFIG_DIR / "published_benchmarks.yml") as fh:
        return yaml.safe_load(fh)


def _tech_share(con, b: dict) -> tuple[float, int, int]:
    """(percent of the base using the technology, users, base) for one published usage figure."""
    tech_id = con.execute("SELECT tech_id FROM core.dim_technology WHERE tech = ?", [b["item"]]).fetchone()[0]
    groups = ("field_group IN ('language', 'framework', 'database', 'platform')" if b.get("base") == "any_technology"
              else "field_group IN (SELECT field_group FROM core.tech_year_group WHERE survey_year = $year AND tech_id = $tech)")
    users, base = con.execute(f"""
        WITH base AS (SELECT DISTINCT resp_key FROM core.bridge_answered WHERE survey_year = $year AND side = 'used' AND {groups}),
             users AS (SELECT DISTINCT resp_key FROM core.bridge_tech_usage WHERE survey_year = $year AND tech_id = $tech AND used)
        SELECT count(users.resp_key), count(*) FROM base LEFT JOIN users USING (resp_key)""",
        {"year": b["year"], "tech": tech_id}).fetchone()
    return 100 * users / base, users, base


def _admired(con, b: dict) -> tuple[float, int, int]:
    """Stack Overflow's "admired": users of the technology who also want it next year, over all its users."""
    wanted, users = con.execute("""
        SELECT count(*) FILTER (WHERE wanted), count(*)
        FROM (SELECT resp_key, bool_or(u.used) AS used, bool_or(u.wanted) AS wanted
              FROM core.bridge_tech_usage AS u JOIN core.dim_technology AS t USING (tech_id)
              WHERE u.survey_year = ? AND t.tech = ? GROUP BY resp_key)
        WHERE used""", [b["year"], b["item"]]).fetchone()
    return 100 * wanted / users, wanted, users


def _answer_share(con, column: str, answer: str, year: int, all_respondents: bool = False) -> tuple[float, int, int]:
    base = "TRUE" if all_respondents else f"{column} IS NOT NULL"
    hits, n = con.execute(f"""SELECT count(*) FILTER (WHERE {column} = ?), count(*) FILTER (WHERE {base})
                              FROM core.fact_respondent WHERE survey_year = ?""", [answer, year]).fetchone()
    return 100 * hits / n, hits, n


def compute(con) -> pd.DataFrame:
    rows = []
    for b in benchmarks():
        metric, year, published = b["metric"], b["year"], b["published"]
        count_ours = base_ours = None
        if metric == "responses":
            ours = con.execute("SELECT count(*) FROM core.fact_respondent WHERE survey_year = ?", [year]).fetchone()[0]
        elif metric == "share_used":
            ours, count_ours, base_ours = _tech_share(con, b)
        elif metric == "admired":
            ours, count_ours, base_ours = _admired(con, b)
        elif metric == "ai_use":
            ours, count_ours, base_ours = _answer_share(con, "ai_use", b["item"], year, b.get("base") == "all_respondents")
        elif metric == "ai_trust":
            ours, count_ours, base_ours = _answer_share(con, "ai_trust", b["item"], year)
        elif metric == "ai_sentiment":
            ours, count_ours, base_ours = _answer_share(con, "ai_sentiment", b["item"], year)
        elif metric == "remote_work":
            ours, count_ours, base_ours = _answer_share(con, "remote_work", b["item"], year)
        else:
            raise ValueError(f"unknown benchmark metric {metric}")

        is_count = b.get("unit") == "count"
        base_published = b.get("responses")
        # "admired" is defined over each technology's own users, so the question's response total says nothing
        # about its base; the definition itself is replicated
        same_base = not is_count and (metric == "admired" or base_published is None or (
            base_ours is not None and abs(base_ours - base_published) <= BASE_TOLERANCE * base_published))
        count_published = b.get("count")
        implied = None
        if count_published is None and base_published is not None and not is_count and not same_base:
            # published share x published responses gives the count, to within the rounding of the published share
            # (plus one respondent: the 2025 file holds 114 responses the report left out)
            decimals = len(str(published).split(".")[1]) if "." in str(published) else 0
            implied = (published / 100 * base_published, 0.5 * 10 ** -decimals / 100 * base_published)
        if is_count:
            status = "match" if ours == published else "different scope"
        elif same_base:
            status = "match" if abs(ours - published) <= TOLERANCE_PP else "differs"
        elif count_published is not None:
            status = "count matches" if count_ours == count_published else "differs"
        elif implied is not None:
            status = "count matches" if abs(count_ours - implied[0]) <= implied[1] + 1.5 else "differs"   # rounding, +-1 respondent
        else:
            status = "different base"
        rows.append({
            "survey_year": year, "metric": metric, "item": b["item"], "group": b.get("group"),
            "published": float(published), "ours": float(ours), "diff": float(ours - published),
            "unit": "count" if is_count else "pct", "base_published": base_published, "base_ours": base_ours,
            "count_published": count_published, "count_ours": count_ours, "same_base": bool(same_base),
            "status": status, "note": b.get("note"), "url": b["url"],
        })
    return pd.DataFrame(rows)


def run(con) -> dict:
    frame = compute(con)
    con.register("_r", frame)
    con.execute("CREATE OR REPLACE TABLE dq.published_reconciliation AS SELECT * FROM _r")
    con.unregister("_r")
    shares = frame[frame.unit == "pct"]
    same = shares[shares.same_base]
    counts = frame[frame.count_published.notna()]
    return {
        "benchmarks": len(frame),
        "same_base": len(same), "same_base_matched": int((same.status == "match").sum()),
        "max_abs_diff_same_base": float(same["diff"].abs().max()) if len(same) else 0.0,
        "counts": len(counts), "counts_matched": int((counts.count_ours == counts.count_published).sum()),
        "different_base": int((~shares.same_base).sum()),
    }
