"""The serving runtime (ctypes over LightGBM's C API) must reproduce the LightGBM Python API exactly."""

import math

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from stackscope import settings
from stackscope.analytics.salary_runtime import NativeBooster, SalaryEstimator, encode_profile


@pytest.fixture(scope="module")
def toy_model(tmp_path_factory):
    rng = np.random.default_rng(0)
    n = 2000
    levels = ["a", "b", "c", "Unknown"]
    X = pd.DataFrame({
        "city": pd.Categorical(rng.choice(levels, n), categories=levels),
        "years": np.where(rng.random(n) < 0.1, np.nan, rng.uniform(0, 30, n)),
        "uses_x": rng.integers(0, 2, n).astype("int8"),
    })
    y = X.city.cat.codes * 0.3 + np.nan_to_num(X.years) * 0.05 + X.uses_x * 0.2 + rng.normal(0, 0.1, n)
    model = lgb.LGBMRegressor(objective="quantile", alpha=0.5, n_estimators=60, num_leaves=15, verbose=-1)
    model.fit(X, y)
    path = tmp_path_factory.mktemp("model") / "toy.txt"
    model.booster_.save_model(str(path))
    return path, X


def test_native_booster_matches_lightgbm(toy_model):
    path, X = toy_model
    reference, native = lgb.Booster(model_file=str(path)), NativeBooster(path)
    sample = X.sample(200, random_state=1)
    expected = reference.predict(sample)
    expected_contrib = reference.predict(sample, pred_contrib=True)
    rows = np.column_stack([sample.city.cat.codes, sample.years, sample.uses_x]).astype(float).tolist()
    for row, pred, contrib in zip(rows, expected, expected_contrib, strict=True):
        assert native.predict(row) == pred
        assert native.contributions(row) == contrib.tolist()


def test_native_booster_rejects_wrong_width(toy_model):
    with pytest.raises(ValueError, match="expected 3 features"):
        NativeBooster(toy_model[0]).predict([1.0, 2.0])


def test_encode_profile_follows_training_rules():
    meta = {"categorical": ["country", "dev_role"], "years": [2024, 2025],
            "levels": {"country": ["IND", "USA", "Other", "Unknown"], "dev_role": ["Data", "Web", "Unknown"]},
            "feature_order": ["country", "dev_role", "years_code", "work_exp", "survey_year", "n_languages",
                              "n_technologies", "uses_Go", "uses_Rust"]}
    row = encode_profile({"country": "FRA", "dev_role": None, "years_code": 5, "technologies": ["Go"]}, meta)
    assert row[:2] == [2.0, 2.0]                    # unseen country -> Other; missing role -> Unknown
    assert row[2:5] == [5.0, 5.0, 2025.0]           # work_exp defaults to years_code; latest survey year
    assert row[5:] == [1.0, 1.0, 1.0, 0.0]
    explicit_none = encode_profile({"country": "USA", "years_code": 5, "work_exp": None}, meta)
    assert explicit_none[0] == 1.0 and math.isnan(explicit_none[3])   # an explicit None stays missing


@pytest.mark.integration
@pytest.mark.skipif(not settings.WAREHOUSE_PATH.exists() or not (settings.MODELS_DIR / "salary_meta.json").exists(),
                    reason="warehouse or salary model not built (run `make pipeline`)")
def test_serving_encoder_matches_training_encoder():
    """Rows encoded one profile at a time must equal the pandas training frame, and score identically."""
    from stackscope.analytics.salary_model import _prepare, load_frame
    from stackscope.api.db import connection

    est = SalaryEstimator.load()
    meta = est.meta
    cur = connection().cursor()
    try:
        frame, _ = load_frame(cur)
    finally:
        cur.close()
    sample = frame.sample(300, random_state=0).reset_index(drop=True)
    X = _prepare(sample, meta["levels"], meta["tech_features"])[meta["feature_order"]]
    encoded = np.column_stack([X[f].cat.codes if f in meta["categorical"] else X[f] for f in meta["feature_order"]])
    expected = lgb.Booster(model_file=str(settings.MODELS_DIR / "salary_p50.txt")).predict(X)
    for i, rec in enumerate(sample.to_dict("records")):
        profile = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in rec.items()}
        profile["country"] = profile.pop("iso3")
        profile["technologies"] = [f.removeprefix("uses_") for f in meta["tech_features"] if rec[f] == 1]
        row = encode_profile(profile, meta)
        np.testing.assert_array_equal(np.array(row), encoded[i].astype(float))   # NaN-aware
        assert est.boosters["p50"].predict(row) == expected[i]
