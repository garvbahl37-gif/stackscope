"""Warehouse invariants (integration: need the built warehouse)."""

import pytest

from stackscope import settings

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not settings.WAREHOUSE_PATH.exists(), reason="warehouse not built (run `make pipeline`)")]


@pytest.fixture(scope="module")
def con():
    # share the API's read-only connection: DuckDB allows one configuration per database per process
    from stackscope.api.db import connection
    cur = connection().cursor()
    yield cur
    cur.close()


def test_row_counts_reconcile_with_publisher(con):
    counts = dict(con.execute("SELECT survey_year, respondents FROM core.dim_year").fetchall())
    for year, cfg in settings.sources()["survey"].items():
        assert counts[int(year)] == cfg["expected_rows"], year


def test_tech_year_intervals_are_valid(con):
    bad = con.execute("""SELECT count(*) FROM mart.tech_year
                         WHERE NOT (share_used_w_lo <= share_used_w AND share_used_w <= share_used_w_hi)
                            OR share_used_w NOT BETWEEN 0 AND 1""").fetchone()[0]
    assert bad == 0


def test_weights_average_one_per_wave(con):
    means = con.execute("SELECT survey_year, avg(weight) FROM core.respondent_weight GROUP BY 1").fetchall()
    assert all(abs(m - 1) < 1e-9 for _, m in means)


def test_quality_gate_passes(con):
    failing = con.execute("SELECT check_id FROM dq.check_results WHERE blocker AND status = 'fail'").fetchall()
    assert failing == []


def test_every_finding_rendered(con):
    assert con.execute("SELECT count(*) FROM mart.key_findings").fetchone()[0] >= 10


def test_pay_is_cleaned(con):
    lo, hi = con.execute("SELECT min(comp_usd), max(comp_usd) FROM core.fact_respondent WHERE comp_usd IS NOT NULL").fetchone()
    assert lo >= 1000 and hi <= 1_000_000
