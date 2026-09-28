"""Adoption forecasts to 2027 with rolling-origin backtests and empirically calibrated intervals.

Annual survey series are short (<= 9 points), so every candidate is simple and fitted on the logit
scale (forecasts stay inside 0-100%):
  naive              last observed value
  drift              last value + average step over the last k waves
  damped_trend       OLS level/slope on the last 5 waves, slope damped (phi = 0.8) into the future
  ensemble           mean of naive and damped_trend
  leading_indicator  pooled panel model: next-wave change in logit(adoption) regressed (Huber) on
                     this wave's desire gap (want vs use), retention, attraction and last change.
                     It asks: does what developers *want* today predict what they *use* next year?

Each candidate is backtested from origins 2020-2024 (horizons 1-2) using only information available
at the origin. The lowest-MAE model is selected, and its 80% interval is the 10th-90th percentile of
its own backtest errors per horizon — interval width is learned from how wrong the method has been.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor

from .stats import inv_logit, logit

PHI = 0.8
HORIZONS = (1, 2)
ORIGINS = (2020, 2021, 2022, 2023, 2024)
MIN_POINTS = 5
MIN_BASE = 1000
FEATURES = ["gap", "retention_w", "attraction_w", "dprev"]
MODELS = ("naive", "drift", "damped_trend", "ensemble", "leading_indicator")


def _panel(tech_year: pd.DataFrame) -> pd.DataFrame:
    """Tech-year panel with leading-indicator features and the next-wave logit change as target."""
    p = tech_year[tech_year.base_n >= MIN_BASE].sort_values(["tech_id", "survey_year"]).copy()
    p["L"] = logit(p.share_used_w)
    p["gap"] = logit(p.share_wanted_w) - p.L
    grp = p.groupby("tech_id")
    p["dprev"] = np.where(grp.survey_year.shift(1) == p.survey_year - 1, p.L - grp.L.shift(1), np.nan)
    p["target"] = np.where(grp.survey_year.shift(-1) == p.survey_year + 1, grp.L.shift(-1) - p.L, np.nan)
    return p


def _fit_indicator(panel: pd.DataFrame, max_year: int) -> HuberRegressor | None:
    # a training row (t -> t+1) is usable only once wave t+1 exists, i.e. t + 1 <= max_year
    train = panel[(panel.survey_year + 1 <= max_year)].dropna(subset=[*FEATURES, "target"])
    if len(train) < 50:
        return None
    return HuberRegressor(alpha=1.0, epsilon=1.35, max_iter=500).fit(train[FEATURES], train.target)


def _indicator_path(row: pd.Series, model: HuberRegressor | None, h: int) -> float:
    """Iterate the one-step model h times, holding structural features fixed and updating momentum."""
    level, dprev = row.L, row.dprev
    if model is None or pd.isna(row[["gap", "retention_w", "attraction_w"]]).any():
        return level  # no leading information -> naive
    for _ in range(h):
        x = pd.DataFrame([[row.gap, row.retention_w, row.attraction_w, 0.0 if pd.isna(dprev) else dprev]],
                         columns=FEATURES)
        step = float(model.predict(x)[0])
        level, dprev = level + step, step
    return level


def _predict(y: np.ndarray, x: np.ndarray, model: str, h: int) -> float:
    if model == "naive":
        return y[-1]
    if model == "drift":
        k = min(4, len(y) - 1)
        return y[-1] + h * (y[-1] - y[-1 - k]) / k
    if model == "damped_trend":
        xs, ys = x[-5:], y[-5:]
        slope, intercept = np.polyfit(xs, ys, 1)
        return intercept + slope * xs[-1] + slope * sum(PHI**i for i in range(1, h + 1))
    if model == "ensemble":
        return 0.5 * (_predict(y, x, "naive", h) + _predict(y, x, "damped_trend", h))
    raise ValueError(model)


def _contiguous(panel: pd.DataFrame) -> dict[int, pd.DataFrame]:
    out = {}
    for tech_id, g in panel.groupby("tech_id"):
        years = g.survey_year.to_numpy()
        breaks = np.where(np.diff(years) != 1)[0]
        out[tech_id] = g.iloc[breaks[-1] + 1 if len(breaks) else 0:]
    return out


def backtest(panel: pd.DataFrame) -> pd.DataFrame:
    series = _contiguous(panel)
    rows = []
    for origin in ORIGINS:
        indicator = _fit_indicator(panel, origin)
        for tech_id, g in series.items():
            hist = g[g.survey_year <= origin]
            if len(hist) < 4 or hist.survey_year.iloc[-1] != origin:
                continue
            y, x = hist.L.to_numpy(), hist.survey_year.to_numpy(dtype=float)
            for h in HORIZONS:
                future = g[g.survey_year == origin + h]
                if future.empty:
                    continue
                actual = float(future.share_used_w.iloc[0])
                for model in MODELS:
                    pred = (_indicator_path(hist.iloc[-1], indicator, h) if model == "leading_indicator"
                            else _predict(y, x, model, h))
                    rows.append({"tech_id": tech_id, "origin": origin, "horizon": h, "model": model,
                                 "actual": actual, "pred": float(inv_logit(pred)),
                                 "logit_error": float(logit(actual) - pred)})
    return pd.DataFrame(rows)


def summarise(bt: pd.DataFrame) -> pd.DataFrame:
    bt = bt.assign(abs_err_pp=100 * (bt.pred - bt.actual).abs(), sq_err_pp=(100 * (bt.pred - bt.actual)) ** 2)
    summary = bt.groupby(["model", "horizon"]).agg(n=("abs_err_pp", "size"), mae_pp=("abs_err_pp", "mean"),
                                                    rmse_pp=("sq_err_pp", lambda s: float(np.sqrt(s.mean())))).reset_index()
    naive = summary[summary.model == "naive"].set_index("horizon").mae_pp
    summary["skill_vs_naive"] = 1 - summary.mae_pp / summary.horizon.map(naive)
    summary["selected"] = summary.model == summary.groupby("model").mae_pp.mean().idxmin()
    return summary


def indicator_coefficients(panel: pd.DataFrame) -> pd.DataFrame:
    """Leading-indicator effects on the full panel (robust fit), for the methodology page."""
    model = _fit_indicator(panel, int(panel.survey_year.max()))
    if model is None:
        return pd.DataFrame(columns=["feature", "coefficient"])
    return pd.DataFrame({"feature": FEATURES, "coefficient": model.coef_})


def forecast(panel: pd.DataFrame, model: str, bt: pd.DataFrame) -> pd.DataFrame:
    errors = bt[bt.model == model]
    bands = {h: errors[errors.horizon == h].logit_error.quantile([0.1, 0.9]).to_numpy() for h in HORIZONS}
    latest = int(panel.survey_year.max())
    indicator = _fit_indicator(panel, latest) if model == "leading_indicator" else None
    rows = []
    for tech_id, g in _contiguous(panel).items():
        if len(g) < MIN_POINTS or g.survey_year.iloc[-1] != latest:
            continue
        for r in g.itertuples():
            rows.append({"tech_id": tech_id, "tech": r.tech, "category": r.category, "survey_year": int(r.survey_year),
                         "share": r.share_used_w, "lo80": r.share_used_w_lo, "hi80": r.share_used_w_hi, "kind": "actual"})
        y, x = g.L.to_numpy(), g.survey_year.to_numpy(dtype=float)
        for h in HORIZONS:
            point = (_indicator_path(g.iloc[-1], indicator, h) if model == "leading_indicator"
                     else _predict(y, x, model, h))
            lo_e, hi_e = bands[h]
            rows.append({"tech_id": tech_id, "tech": g.tech.iloc[0], "category": g.category.iloc[0],
                         "survey_year": latest + h, "share": float(inv_logit(point)),
                         "lo80": float(inv_logit(point + lo_e)), "hi80": float(inv_logit(point + hi_e)),
                         "kind": "forecast"})
    return pd.DataFrame(rows).assign(model=model)


def run(con) -> dict:
    panel = _panel(con.execute("SELECT * FROM mart.tech_year").df())
    bt = backtest(panel)
    summary = summarise(bt)
    chosen = summary.loc[summary.selected, "model"].iloc[0]
    outputs = {"tech_forecast": forecast(panel, chosen, bt), "forecast_backtest": summary,
               "forecast_indicator": indicator_coefficients(panel)}
    for name, frame in outputs.items():
        con.register("_f", frame)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    best_h1 = summary[(summary.selected) & (summary.horizon == 1)].iloc[0]
    return {"model": chosen, "series": int(outputs["tech_forecast"].tech_id.nunique()),
            "mae_pp_h1": round(float(best_h1.mae_pp), 3), "skill_vs_naive_h1": round(float(best_h1.skill_vs_naive), 3)}
