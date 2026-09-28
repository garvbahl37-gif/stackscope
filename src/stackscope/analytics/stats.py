"""Small, dependency-light statistical helpers shared by the analytics modules (all unit-tested)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

Z95 = 1.959963984540054


def wilson_interval(successes, n, z: float = Z95) -> tuple[np.ndarray, np.ndarray]:
    """Wilson score interval; vectorised. Works with fractional (weighted / effective) counts."""
    successes, n = np.asarray(successes, dtype=float), np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = successes / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return np.clip(centre - half, 0, 1), np.clip(centre + half, 0, 1)


def two_proportion_z(p1, n1, p2, n2) -> tuple[np.ndarray, np.ndarray]:
    """Unpooled two-proportion z-test (effective sample sizes allowed). Returns (z, two-sided p)."""
    p1, n1, p2, n2 = (np.asarray(x, dtype=float) for x in (p1, n1, p2, n2))
    with np.errstate(divide="ignore", invalid="ignore"):
        se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
        z = (p2 - p1) / se
    return z, 2 * stats.norm.sf(np.abs(z))


def benjamini_hochberg(pvalues) -> np.ndarray:
    """Benjamini-Hochberg FDR-adjusted q-values (NaNs preserved)."""
    p = np.asarray(pvalues, dtype=float)
    q = np.full_like(p, np.nan)
    mask = ~np.isnan(p)
    m = mask.sum()
    if m == 0:
        return q
    order = np.argsort(p[mask])
    ranked = p[mask][order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(ranked, 0, 1)
    q[mask] = out
    return q


def logit(p, eps: float = 1e-4):
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


def inv_logit(x):
    return 1 / (1 + np.exp(-np.asarray(x, dtype=float)))


def weighted_logit_trend(years, shares, n_eff) -> dict:
    """Inverse-variance WLS of logit(share) on year.

    The delta-method variance of logit(p) is 1 / (n p (1 - p)), so weights are n p (1 - p).
    Returns slope (log-odds per year), its SE, p-value and the implied annual growth in odds.
    """
    years, shares, n_eff = (np.asarray(x, dtype=float) for x in (years, shares, n_eff))
    keep = ~(np.isnan(shares) | np.isnan(n_eff)) & (shares > 0) & (shares < 1)
    years, shares, n_eff = years[keep], shares[keep], n_eff[keep]
    if len(years) < 3:
        return {"slope": np.nan, "se": np.nan, "p_value": np.nan, "n_points": int(len(years))}
    y = logit(shares)
    w = n_eff * shares * (1 - shares)
    X = np.column_stack([np.ones_like(years), years - years.mean()])
    W = np.diag(w)
    xtwx_inv = np.linalg.inv(X.T @ W @ X)
    beta = xtwx_inv @ X.T @ W @ y
    resid = y - X @ beta
    dof = len(years) - 2
    # scale by residual dispersion (quasi-likelihood): survey waves differ by more than sampling noise
    dispersion = max(1.0, float((w * resid**2).sum() / dof)) if dof > 0 else 1.0
    se = float(np.sqrt(xtwx_inv[1, 1] * dispersion))
    slope = float(beta[1])
    t = slope / se if se > 0 else np.nan
    p = float(2 * stats.t.sf(abs(t), dof)) if dof > 0 and se > 0 else np.nan
    return {"slope": slope, "se": se, "p_value": p, "n_points": int(len(years))}


def zscore(series: pd.Series) -> pd.Series:
    sd = series.std(ddof=0)
    if not sd or np.isnan(sd):
        return series * 0.0
    return (series - series.mean()) / sd
