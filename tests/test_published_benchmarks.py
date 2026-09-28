"""Reconciliation with Stack Overflow's published results (config/published_benchmarks.yml)."""

import pytest

from stackscope import settings
from stackscope.quality import reconcile

METRICS = {"responses", "share_used", "admired", "ai_use", "ai_trust", "ai_sentiment", "remote_work"}


def test_benchmarks_are_well_formed():
    rows = reconcile.benchmarks()
    assert len(rows) >= 100
    for r in rows:
        assert r["metric"] in METRICS, r
        assert 2017 <= r["year"] <= 2025, r
        assert r["url"].startswith("https://survey.stackoverflow.co/"), r
        if r.get("unit") != "count":
            assert 0 <= r["published"] <= 100, r
        if r["metric"] == "share_used":
            assert r["group"] in {"language", "database", "platform"}, r


@pytest.mark.integration
@pytest.mark.skipif(not settings.WAREHOUSE_PATH.exists(), reason="warehouse not built (run `make pipeline`)")
def test_every_published_figure_is_reproduced_or_explained():
    from stackscope.api.db import connection

    cur = connection().cursor()
    try:
        frame = reconcile.compute(cur)
    finally:
        cur.close()
    assert not (frame.status == "differs").any(), frame[frame.status == "differs"]
    same = frame[(frame.unit == "pct") & frame.same_base]
    assert len(same) >= 90 and same["diff"].abs().max() <= reconcile.TOLERANCE_PP
    counted = frame[frame.count_published.notna()]
    assert (counted.count_ours == counted.count_published).all()
