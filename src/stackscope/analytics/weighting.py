"""Composition-adjusted survey weights via raking (iterative proportional fitting).

Why: raw year-over-year shares mix two effects — genuine technology shifts and changes in *who
answered* (the share of respondents from South Asia, learners, or 20-year veterans moves a lot
between waves). Each year is raked to the same reference composition (the average of all nine
waves) on three margins — analysis region, respondent type and coding-experience band — so trends
compare like with like.

Method: classic IPF on known categories (a missing answer is never forced toward a target), then a
trim-and-re-rake loop that caps weights at [0.2, 5] x mean to limit variance inflation. The Kish
design effect and effective sample size are reported per year.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DIMENSIONS = ("region", "respondent_type", "exp_band")
TRIM = (0.2, 5.0)


@dataclass
class RakeResult:
    weights: np.ndarray
    iterations: int
    max_margin_error: float
    converged: bool


def _margin_error(weights, codes, tgt) -> float:
    worst = 0.0
    for dim, code in codes.items():
        known = code >= 0
        shares = np.bincount(code[known], weights=weights[known], minlength=len(tgt[dim])) / weights[known].sum()
        worst = max(worst, float(np.abs(shares - tgt[dim]).max()))
    return worst


def _ipf(weights, codes, tgt, max_iter, tol) -> tuple[np.ndarray, int]:
    iteration = 0
    while iteration < max_iter:
        iteration += 1
        for dim, code in codes.items():
            known = code >= 0
            sums = np.bincount(code[known], weights=weights[known], minlength=len(tgt[dim]))
            factor = np.divide(tgt[dim] * weights[known].sum(), sums, out=np.ones_like(sums), where=sums > 0)
            weights[known] *= factor[code[known]]
        if _margin_error(weights, codes, tgt) < tol:
            break
    return weights, iteration


def rake(frame: pd.DataFrame, targets: dict[str, pd.Series], max_iter: int = 500, tol: float = 1e-7,
         trim: tuple[float, float] | None = TRIM, trim_rounds: int = 25) -> RakeResult:
    """Rake unit weights so each column's weighted distribution (known values) matches its target.

    `targets[dim]` is a Series of shares indexed by category. Categories absent from this frame are
    dropped and the rest renormalised; values not in the target (e.g. missing) keep factor 1 on that
    dimension.
    """
    codes, tgt = {}, {}
    for dim, target in targets.items():
        present = target[target.index.isin(frame[dim].dropna().unique())]
        tgt[dim] = (present / present.sum()).to_numpy()
        codes[dim] = pd.Categorical(frame[dim], categories=present.index).codes

    weights, iterations = _ipf(np.ones(len(frame)), codes, tgt, max_iter, tol)
    if trim:
        for _ in range(trim_rounds):
            weights = np.clip(weights / weights.mean(), *trim)
            weights, extra = _ipf(weights, codes, tgt, max_iter, tol)
            iterations += extra
            if weights.min() / weights.mean() >= trim[0] * 0.999 and weights.max() / weights.mean() <= trim[1] * 1.001:
                break
    weights = weights / weights.mean()
    error = _margin_error(weights, codes, tgt)
    return RakeResult(weights, iterations, error, error < 5e-3)


def kish_deff(weights: np.ndarray) -> float:
    """Kish design effect: n * sum(w^2) / sum(w)^2 (1 = no variance inflation)."""
    return float(len(weights) * np.square(weights).sum() / np.square(weights.sum()))


def build_weights(respondents: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (weights[resp_key, survey_year, weight], per-year diagnostics, reference targets)."""
    frame = respondents[["resp_key", "survey_year", *DIMENSIONS]].copy()

    # Reference composition over known values: every wave counts equally, whatever its size.
    targets = {}
    for dim in DIMENSIONS:
        by_year = frame.dropna(subset=[dim]).groupby("survey_year")[dim].value_counts(normalize=True)
        targets[dim] = by_year.unstack(fill_value=0).mean(axis=0).sort_values(ascending=False)

    weight_parts, diagnostics = [], []
    for year, part in frame.groupby("survey_year"):
        result = rake(part.reset_index(drop=True), targets)
        weight_parts.append(pd.DataFrame({"resp_key": part.resp_key.to_numpy(), "survey_year": year,
                                          "weight": result.weights}))
        deff = kish_deff(result.weights)
        diagnostics.append({
            "survey_year": int(year), "respondents": len(part), "design_effect": round(deff, 4),
            "effective_n": round(len(part) / deff), "min_weight": round(float(result.weights.min()), 4),
            "max_weight": round(float(result.weights.max()), 4), "iterations": result.iterations,
            "max_margin_error": result.max_margin_error, "converged": result.converged,
        })
    target_rows = pd.DataFrame([{"dimension": d, "category": c, "target_share": float(s)}
                                for d, series in targets.items() for c, s in series.items()])
    return pd.concat(weight_parts, ignore_index=True), pd.DataFrame(diagnostics), target_rows


def write_weights(con) -> pd.DataFrame:
    """Compute weights from core.fact_respondent and persist core.respondent_weight + diagnostics."""
    respondents = con.execute(
        "SELECT resp_key, survey_year, region, respondent_type, exp_band FROM core.fact_respondent").df()
    weights, diagnostics, targets = build_weights(respondents)
    con.register("_w", weights)
    con.execute("CREATE OR REPLACE TABLE core.respondent_weight AS "
                "SELECT resp_key, CAST(survey_year AS SMALLINT) AS survey_year, weight FROM _w ORDER BY resp_key")
    con.register("_d", diagnostics)
    con.execute("CREATE OR REPLACE TABLE dq.weight_diagnostics AS SELECT * FROM _d")
    con.register("_t", targets)
    con.execute("CREATE OR REPLACE TABLE dq.weight_targets AS SELECT * FROM _t")
    for name in ("_w", "_d", "_t"):
        con.unregister(name)
    return diagnostics
