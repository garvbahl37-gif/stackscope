import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

from stackscope.analytics.salary_model import conformal_margin
from stackscope.analytics.stats import (
    benjamini_hochberg,
    inv_logit,
    logit,
    two_proportion_z,
    weighted_logit_trend,
    wilson_interval,
)
from stackscope.analytics.weighting import kish_deff, rake
from stackscope.harmonize.taxonomy import alias_frame, catalog, excluded_labels


# ---------------------------------------------------------------------------- taxonomy
def lookup(group: str, label: str):
    a = alias_frame()
    hit = a[(a.field_group == group) & (a.raw_label == label)]
    return None if hit.empty else hit.tech.iloc[0]


def test_taxonomy_is_unambiguous_and_names_unique():
    a = alias_frame()
    assert not a.duplicated(["field_group", "raw_label"]).any()
    assert catalog().tech.is_unique


@pytest.mark.parametrize("group, label, tech", [
    ("language", "Bash/Shell/PowerShell", "Bash/Shell"),
    ("language", "Bash/Shell (all shells)", "Bash/Shell"),
    ("language", "Node.js", "Node.js"),                  # 2021 listed Node.js as a language
    ("webframe", "React.js", "React"),
    ("webframe", "Angular/Angular.js", "Angular"),
    ("database", "SQL Server", "Microsoft SQL Server"),
    ("database", "Firebase", "Firebase Realtime DB"),    # same label, different question ...
    ("platform", "Firebase", "Firebase"),                # ... different technology
    ("platform", "Linode, now Akamai", "Linode (Akamai)"),
    ("ai_models", "Anthropic: Claude Sonnet", "Claude"),
    ("misctech", "Teraform", "Terraform"),               # publisher typo in 2020
])
def test_aliases_resolve(group, label, tech):
    assert lookup(group, label) == tech


def test_field_restrictions_hold():
    assert lookup("platform", "Supabase") is None and "Supabase" in excluded_labels()
    assert lookup("database", "Supabase") == "Supabase"


# ---------------------------------------------------------------------------- statistics
def test_wilson_matches_statsmodels():
    x, n = np.array([0, 3, 50, 99, 100]), np.array([100, 100, 100, 100, 100])
    lo, hi = wilson_interval(x, n)
    ref_lo, ref_hi = proportion_confint(x, n, method="wilson")
    np.testing.assert_allclose(lo, ref_lo, atol=1e-9)
    np.testing.assert_allclose(hi, ref_hi, atol=1e-9)


def test_benjamini_hochberg_matches_statsmodels():
    rng = np.random.default_rng(0)
    p = rng.uniform(size=200) ** 3
    ours = benjamini_hochberg(p)
    ref = multipletests(p, method="fdr_bh")[1]
    np.testing.assert_allclose(ours, ref, atol=1e-12)
    assert np.isnan(benjamini_hochberg([0.01, np.nan])[1])


def test_two_proportion_z_symmetry():
    z, p = two_proportion_z(0.2, 1000, 0.2, 1000)
    assert z == 0 and p == pytest.approx(1.0)
    z1, _ = two_proportion_z(0.2, 1000, 0.3, 1000)
    z2, _ = two_proportion_z(0.3, 1000, 0.2, 1000)
    assert z1 == pytest.approx(-z2)


def test_weighted_logit_trend_recovers_slope():
    years = np.arange(2017, 2026)
    shares = inv_logit(-2 + 0.3 * (years - 2017))
    out = weighted_logit_trend(years, shares, np.full(len(years), 50_000))
    assert out["slope"] == pytest.approx(0.3, abs=1e-6)
    assert out["p_value"] < 1e-6


def test_logit_round_trip():
    p = np.array([0.01, 0.5, 0.99])
    np.testing.assert_allclose(inv_logit(logit(p)), p)


# ---------------------------------------------------------------------------- weighting
def test_rake_hits_targets_and_respects_trim():
    rng = np.random.default_rng(1)
    frame = pd.DataFrame({"a": rng.choice(["x", "y"], 5000, p=[0.8, 0.2]),
                          "b": rng.choice(["u", "v", "w"], 5000, p=[0.5, 0.3, 0.2])})
    targets = {"a": pd.Series({"x": 0.5, "y": 0.5}), "b": pd.Series({"u": 0.2, "v": 0.3, "w": 0.5})}
    res = rake(frame, targets)
    assert res.converged
    w = res.weights
    share_a = pd.Series(w).groupby(frame.a.values).sum() / w.sum()
    assert share_a["y"] == pytest.approx(0.5, abs=1e-4)
    # trim-and-rerake keeps margins exact and weights inside the [0.2, 5] cap to within 0.1%
    assert w.max() / w.mean() <= 5.0 * 1.001 and w.min() / w.mean() >= 0.2 * 0.999


def test_rake_leaves_missing_values_unforced():
    frame = pd.DataFrame({"a": ["x"] * 50 + ["y"] * 30 + [None] * 20})
    res = rake(frame, {"a": pd.Series({"x": 0.5, "y": 0.5})}, trim=None)
    w = pd.Series(res.weights)
    known = frame.a.notna()
    assert (w[known & (frame.a == "x")].sum() / w[known].sum()) == pytest.approx(0.5, abs=1e-6)


def test_kish_design_effect():
    assert kish_deff(np.ones(100)) == pytest.approx(1.0)
    assert kish_deff(np.array([1, 1, 1, 5])) > 1.0


# ---------------------------------------------------------------------------- conformal prediction
def test_conformal_margin_delivers_coverage():
    rng = np.random.default_rng(7)
    n = 20_000
    y = rng.normal(size=n)
    # deliberately too narrow quantile band (covers ~50% instead of 80%)
    lower, upper = np.full(n, -0.67), np.full(n, 0.67)
    cal, test = slice(0, n // 2), slice(n // 2, n)
    m = conformal_margin(lower[cal], upper[cal], y[cal], alpha=0.2)
    coverage = np.mean((y[test] >= lower[test] - m) & (y[test] <= upper[test] + m))
    assert m > 0
    assert coverage == pytest.approx(0.8, abs=0.015)
