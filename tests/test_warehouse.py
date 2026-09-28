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


def test_pay_benchmark_uses_all_only_for_the_total(con):
    # a missing answer in a breakdown is 'Unknown'; 'All' may only label the grand total
    bad = con.execute("SELECT count(*) FROM mart.pay_benchmark WHERE segment = 'All' AND cut <> 'all'").fetchone()[0]
    assert bad == 0


def test_churn_flows_use_weighted_retention(con):
    gap = con.execute("""SELECT max(abs(s.from_churn_rate - (1 - y.retention_w)))
                         FROM mart.tech_switching AS s
                         JOIN core.dim_technology AS d ON d.tech = s.from_tech
                         JOIN mart.tech_year AS y ON y.tech_id = d.tech_id AND y.survey_year = s.survey_year""").fetchone()[0]
    assert gap < 1e-12


def test_like_for_like_hhi_is_anchored_to_the_latest_wave(con):
    rows = con.execute("""SELECT category, arg_max(hhi, survey_year), arg_max(hhi_like_for_like, survey_year)
                          FROM mart.market_concentration GROUP BY category""").fetchall()
    assert rows and all(abs(snapshot - chained) <= 1 for _, snapshot, chained in rows)
