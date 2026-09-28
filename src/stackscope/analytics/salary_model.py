"""Salary estimator — gradient-boosted quantile regression with conformal calibration and SHAP.

  * Three LightGBM models predict the 10th, 50th and 90th percentile of ln(pay, constant 2025 USD)
    from country, experience, role, company, education, work arrangement, industry and tech stack.
  * Conformalized Quantile Regression (Romano et al., 2019) widens the P10-P90 band by a margin
    learned on a held-out calibration split, giving a finite-sample coverage guarantee (~80%).
  * Explanations are exact TreeSHAP contributions from LightGBM (`pred_contrib`), aggregated into
    human-readable feature groups for the dashboard's "why this estimate" waterfall.

Splits (stratified by survey year): 65% train / 10% early-stopping / 10% calibration / 15% test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache

import lightgbm as lgb
import numpy as np
import pandas as pd

from .. import settings

YEARS = (2023, 2024, 2025)
TECH_CATEGORIES = ("language", "database", "cloud", "webframe", "devops")
N_TECH_FEATURES = 60
TOP_COUNTRIES = 60
QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
ALPHA = 0.2  # 1 - target coverage
CATEGORICAL = ["country", "region", "dev_role", "org_size", "ed_level", "remote_work", "industry", "age_band", "ai_use"]
NUMERIC = ["years_code", "work_exp", "survey_year", "n_languages", "n_technologies"]
GROUPS = {
    "country": "Location", "region": "Location", "years_code": "Experience", "work_exp": "Experience",
    "age_band": "Experience", "dev_role": "Role", "org_size": "Company", "industry": "Company",
    "ed_level": "Education", "remote_work": "Work arrangement", "ai_use": "AI usage", "survey_year": "Survey year",
    "n_languages": "Tech stack", "n_technologies": "Tech stack",
}
PARAMS = dict(learning_rate=0.05, num_leaves=63, min_child_samples=40, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=settings.RANDOM_SEED, num_threads=0,
              deterministic=True, force_row_wise=True)   # bit-for-bit reproducible across runs


def conformal_margin(lower: np.ndarray, upper: np.ndarray, y: np.ndarray, alpha: float) -> float:
    """CQR margin: the finite-sample (1 - alpha) quantile of max(lower - y, y - upper) on a calibration set.

    Widening [lower, upper] by this margin guarantees >= 1 - alpha marginal coverage on exchangeable data.
    """
    scores = np.maximum(lower - y, y - upper)
    n = len(scores)
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level, method="higher"))


def _paths():
    d = settings.MODELS_DIR
    return {q: d / f"salary_{q}.txt" for q in QUANTILES} | {"meta": d / "salary_meta.json"}


def load_frame(con) -> tuple[pd.DataFrame, list[str]]:
    years = ", ".join(map(str, YEARS))
    cats = ", ".join(f"'{c}'" for c in TECH_CATEGORIES)
    people = con.execute(f"""
        SELECT r.resp_key, r.survey_year, r.iso3, r.region, r.dev_role, r.org_size, r.ed_level, r.remote_work,
               r.industry, r.age_band, r.ai_use, r.years_code, r.work_exp, r.comp_usd_real
        FROM core.fact_respondent AS r
        WHERE r.in_pay_benchmark AND r.survey_year IN ({years}) AND r.years_code IS NOT NULL
          AND r.resp_key IN (SELECT resp_key FROM core.bridge_answered WHERE field_group = 'language' AND side = 'used')
        ORDER BY r.resp_key
    """).df()
    usage = con.execute(f"""
        SELECT u.resp_key, t.tech, t.category FROM core.bridge_tech_usage AS u
        JOIN core.dim_technology AS t USING (tech_id)
        WHERE u.used AND u.survey_year IN ({years}) AND t.category IN ({cats})
    """).df()
    usage = usage[usage.resp_key.isin(people.resp_key)]
    eligible = con.execute(f"""
        SELECT t.tech FROM core.tech_year_group AS g JOIN core.dim_technology AS t USING (tech_id)
        WHERE g.survey_year IN ({years}) AND t.category IN ({cats})
        GROUP BY t.tech HAVING count(DISTINCT g.survey_year) = {len(YEARS)}
    """).df().tech
    # most-used eligible technologies; ties broken alphabetically so the feature set is stable run to run
    counts = usage[usage.tech.isin(eligible)].groupby("tech").size().reset_index(name="n")
    top_techs = counts.sort_values(["n", "tech"], ascending=[False, True]).tech.head(N_TECH_FEATURES).tolist()
    flags = (usage[usage.tech.isin(top_techs)].assign(v=1)
             .pivot_table(index="resp_key", columns="tech", values="v", aggfunc="max", fill_value=0))
    per_person = usage.groupby("resp_key").agg(
        n_languages=("category", lambda s: int((s == "language").sum())), n_technologies=("tech", "size"))
    frame = people.set_index("resp_key").join(per_person).join(flags.add_prefix("uses_"))
    for col in [f"uses_{t}" for t in top_techs] + ["n_languages", "n_technologies"]:
        frame[col] = frame[col].fillna(0).astype("int8" if col.startswith("uses_") else "int16")
    return frame.sort_index().reset_index(), top_techs


def _prepare(frame: pd.DataFrame, levels: dict[str, list[str]], tech_cols: list[str]) -> pd.DataFrame:
    X = pd.DataFrame(index=frame.index)
    for col in CATEGORICAL:
        source = "iso3" if col == "country" else col
        values = frame[source].astype("object").where(frame[source].notna(), "Unknown") if source in frame else "Unknown"
        values = pd.Series(values, index=frame.index)
        values = values.where(values.isin(levels[col]), "Other" if col == "country" else "Unknown")
        X[col] = pd.Categorical(values, categories=levels[col])
    for col in NUMERIC:
        X[col] = pd.to_numeric(frame[col], errors="coerce") if col in frame else np.nan
    for col in tech_cols:
        X[col] = frame[col].astype("int8") if col in frame else 0
    return X


def _levels(frame: pd.DataFrame) -> dict[str, list[str]]:
    levels = {}
    for col in CATEGORICAL:
        if col == "country":
            top = frame.iso3.value_counts().head(TOP_COUNTRIES).index.tolist()
            levels[col] = sorted(top) + ["Other", "Unknown"]
        else:
            levels[col] = sorted(frame[col].dropna().astype(str).unique().tolist()) + ["Unknown"]
    return levels


def _split(frame: pd.DataFrame) -> pd.Series:
    rng = np.random.default_rng(settings.RANDOM_SEED)
    split = pd.Series("train", index=frame.index)
    for _, idx in frame.groupby("survey_year").groups.items():
        idx = np.array(idx)
        rng.shuffle(idx)
        n = len(idx)
        cuts = np.cumsum([int(0.65 * n), int(0.10 * n), int(0.10 * n)])
        split.loc[idx[cuts[0]:cuts[1]]] = "valid"
        split.loc[idx[cuts[1]:cuts[2]]] = "calib"
        split.loc[idx[cuts[2]:]] = "test"
    return split


def train(con) -> dict:
    frame, top_techs = load_frame(con)
    tech_cols = [f"uses_{t}" for t in top_techs]
    levels = _levels(frame)
    X = _prepare(frame, levels, tech_cols)
    y = np.log(frame.comp_usd_real.to_numpy())
    split = _split(frame)
    parts = {name: (X[split == name], y[(split == name).to_numpy()]) for name in ("train", "valid", "calib", "test")}

    models, paths = {}, _paths()
    settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, q in QUANTILES.items():
        model = lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=4000, **PARAMS)
        model.fit(parts["train"][0], parts["train"][1], eval_X=(parts["valid"][0],), eval_y=(parts["valid"][1],),
                  eval_metric="quantile", callbacks=[lgb.early_stopping(150, verbose=False)])
        models[name] = model.booster_
        model.booster_.save_model(str(paths[name]), num_iteration=model.best_iteration_)

    def predict(split_name):
        Xs = parts[split_name][0]
        return {k: m.predict(Xs, num_iteration=m.best_iteration) for k, m in models.items()}

    # --- conformal calibration (CQR) ------------------------------------------------------
    cal = predict("calib")
    y_cal = parts["calib"][1]
    n_cal = len(y_cal)
    margin = conformal_margin(cal["p10"], cal["p90"], y_cal, ALPHA)

    # --- evaluation on the untouched test split --------------------------------------------
    te = predict("test")
    y_te = parts["test"][1]
    lo, hi = te["p10"] - margin, te["p90"] + margin
    resid = te["p50"] - y_te
    train_frame = frame[split == "train"]
    baseline = (train_frame.assign(ly=np.log(train_frame.comp_usd_real)).groupby(["iso3", "survey_year"]).ly.median())
    global_med = float(np.median(np.log(train_frame.comp_usd_real)))
    test_frame = frame[split == "test"]
    base_pred = np.array([baseline.get((i, yr), global_med) for i, yr in zip(test_frame.iso3, test_frame.survey_year, strict=True)])

    def r2(pred):
        return float(1 - np.sum((y_te - pred) ** 2) / np.sum((y_te - y_te.mean()) ** 2))

    metrics = {
        "n_train": int(len(parts["train"][1])), "n_valid": int(len(parts["valid"][1])),
        "n_calib": int(n_cal), "n_test": int(len(y_te)),
        "r2_log": r2(te["p50"]), "r2_log_baseline": r2(base_pred),
        "mae_log": float(np.mean(np.abs(resid))), "mae_log_baseline": float(np.mean(np.abs(base_pred - y_te))),
        "median_ape": float(np.median(np.abs(np.expm1(resid)))),
        "median_ape_baseline": float(np.median(np.abs(np.expm1(base_pred - y_te)))),
        "coverage_raw": float(np.mean((y_te >= te["p10"]) & (y_te <= te["p90"]))),
        "coverage_conformal": float(np.mean((y_te >= lo) & (y_te <= hi))),
        "target_coverage": 1 - ALPHA, "conformal_margin_log": margin,
        "median_interval_ratio": float(np.median(np.exp(hi - lo))),
        "best_iterations": {k: int(m.best_iteration) for k, m in models.items()},
    }

    # --- global explanations (TreeSHAP on a test sample) ------------------------------------
    sample = parts["test"][0].sample(min(6000, len(parts["test"][0])), random_state=settings.RANDOM_SEED)
    contrib = models["p50"].predict(sample, pred_contrib=True, num_iteration=models["p50"].best_iteration)
    feature_names = list(sample.columns)
    importance = pd.DataFrame({"feature": feature_names, "mean_abs_shap": np.abs(contrib[:, :-1]).mean(axis=0)})
    importance["group"] = importance.feature.map(lambda f: "Tech stack" if f.startswith("uses_") else GROUPS.get(f, "Other"))
    importance["label"] = importance.feature.str.replace("uses_", "", regex=False)
    group_importance = importance.groupby("group", as_index=False).mean_abs_shap.sum().sort_values("mean_abs_shap", ascending=False)
    group_importance["share"] = group_importance.mean_abs_shap / group_importance.mean_abs_shap.sum()

    meta = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"), "years": list(YEARS),
        "price_base_year": settings.BASE_PRICE_YEAR, "categorical": CATEGORICAL, "numeric": NUMERIC,
        "tech_features": tech_cols, "levels": levels, "feature_order": feature_names,
        "conformal_margin_log": margin, "alpha": ALPHA, "metrics": metrics, "groups": GROUPS,
        "best_iterations": metrics["best_iterations"],
    }
    paths["meta"].write_text(json.dumps(meta, indent=2))

    metrics_rows = pd.DataFrame([{"metric": k, "value": float(v)} for k, v in metrics.items() if not isinstance(v, dict)])
    for name, df in (("salary_model_metrics", metrics_rows), ("salary_feature_importance", importance),
                     ("salary_group_importance", group_importance)):
        con.register("_f", df)
        con.execute(f"CREATE OR REPLACE TABLE ml.{name} AS SELECT * FROM _f")
        con.unregister("_f")
    SalaryEstimator.load.cache_clear()
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items() if k != "best_iterations"}


class SalaryEstimator:
    """Loads the trained artifacts and serves calibrated, explained predictions (used by the API)."""

    def __init__(self, meta: dict, boosters: dict[str, lgb.Booster]):
        self.meta = meta
        self.boosters = boosters

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> SalaryEstimator:
        paths = _paths()
        meta = json.loads(paths["meta"].read_text())
        boosters = {q: lgb.Booster(model_file=str(paths[q])) for q in QUANTILES}
        return cls(meta, boosters)

    def _frame(self, profile: dict) -> pd.DataFrame:
        row = {col: profile.get(col) for col in ("region", "dev_role", "org_size", "ed_level", "remote_work",
                                                   "industry", "age_band", "ai_use")}
        row["iso3"] = profile.get("country")
        row["years_code"] = profile.get("years_code")
        row["work_exp"] = profile.get("work_exp", profile.get("years_code"))
        row["survey_year"] = profile.get("survey_year", max(self.meta["years"]))
        techs = set(profile.get("technologies", []))
        for col in self.meta["tech_features"]:
            row[col] = int(col.removeprefix("uses_") in techs)
        row["n_languages"] = profile.get("n_languages", len(techs))
        row["n_technologies"] = profile.get("n_technologies", len(techs))
        frame = pd.DataFrame([row])
        return _prepare(frame, self.meta["levels"], self.meta["tech_features"])[self.meta["feature_order"]]

    def predict(self, profile: dict) -> dict:
        X = self._frame(profile)
        preds = {q: float(b.predict(X)[0]) for q, b in self.boosters.items()}
        margin = self.meta["conformal_margin_log"]
        lo, mid, hi = preds["p10"] - margin, preds["p50"], preds["p90"] + margin
        lo, hi = min(lo, mid), max(hi, mid)
        contrib = self.boosters["p50"].predict(X, pred_contrib=True)[0]
        base = float(contrib[-1])
        groups: dict[str, float] = {}
        for feature, value in zip(self.meta["feature_order"], contrib[:-1], strict=True):
            group = "Tech stack" if feature.startswith("uses_") else self.meta["groups"].get(feature, "Other")
            groups[group] = groups.get(group, 0.0) + float(value)
        techs = [(f.removeprefix("uses_"), float(v)) for f, v in zip(self.meta["feature_order"], contrib[:-1], strict=True)
                 if f.startswith("uses_") and X.iloc[0][f] == 1]
        return {
            "p10": float(np.exp(lo)), "p50": float(np.exp(mid)), "p90": float(np.exp(hi)),
            "baseline": float(np.exp(base)),
            "contributions": sorted(({"group": g, "log_effect": v, "multiplier": float(np.exp(v))} for g, v in groups.items()),
                                    key=lambda d: -abs(d["log_effect"])),
            "tech_effects": sorted(({"tech": t, "multiplier": float(np.exp(v))} for t, v in techs), key=lambda d: -d["multiplier"]),
            "price_base_year": self.meta["price_base_year"],
            "coverage": self.meta["metrics"]["coverage_conformal"],
        }
