"""Serving-time salary estimator: the trained LightGBM models, scored through LightGBM's C API.

Training (salary_model.py) needs pandas, NumPy and the LightGBM Python package, which pulls in SciPy.
Serving needs none of them. This module loads the saved model files with ctypes and scores one profile at a
time, which keeps the API small enough for a serverless function. Features are encoded exactly as in
training (category level -> code, numeric -> float, tech flag -> 0/1), so predictions and TreeSHAP
contributions are identical to `lightgbm.Booster.predict` (tests/test_salary_runtime.py checks both).
"""

from __future__ import annotations

import ctypes
import importlib.util
import json
import math
import sys
from functools import lru_cache
from pathlib import Path

from .. import settings

QUANTILE_NAMES = ("p10", "p50", "p90")

# Constants from LightGBM's c_api.h
_DTYPE_FLOAT64 = 1
_PREDICT_NORMAL = 0
_PREDICT_CONTRIB = 3


def model_paths() -> dict[str, Path]:
    d = settings.MODELS_DIR
    return {q: d / f"salary_{q}.txt" for q in QUANTILE_NAMES} | {"meta": d / "salary_meta.json"}


def _library_path() -> Path:
    # find_spec locates the installed package without importing it (importing it would load SciPy)
    spec = importlib.util.find_spec("lightgbm")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("LightGBM is not installed")
    name = {"darwin": "lib_lightgbm.dylib", "win32": "lib_lightgbm.dll"}.get(sys.platform, "lib_lightgbm.so")
    return Path(next(iter(spec.submodule_search_locations))) / "lib" / name


def _load_openmp() -> None:
    """lib_lightgbm links the GNU OpenMP runtime (libgomp.so.1), which Vercel's Python runtime lacks.

    Use the system copy when there is one, else the copy bundled with the deployment (api/lib). Once a
    library with that SONAME is loaded, the dynamic linker reuses it for lib_lightgbm's dependency.
    """
    if not sys.platform.startswith("linux"):
        return
    try:
        ctypes.CDLL("libgomp.so.1", mode=ctypes.RTLD_GLOBAL)
    except OSError:
        bundled = settings.ROOT / "api" / "lib" / "libgomp.so.1"
        if bundled.exists():
            ctypes.CDLL(str(bundled), mode=ctypes.RTLD_GLOBAL)


@lru_cache(maxsize=1)
def _lib() -> ctypes.CDLL:
    _load_openmp()
    lib = ctypes.CDLL(str(_library_path()))
    lib.LGBM_GetLastError.restype = ctypes.c_char_p
    return lib


def _check(code: int) -> None:
    if code != 0:
        raise RuntimeError(f"LightGBM: {_lib().LGBM_GetLastError().decode()}")


class NativeBooster:
    """A saved LightGBM model, loaded through the C API; scores one row of float64 features at a time."""

    def __init__(self, model_file: Path | str):
        self._lib = _lib()
        self._handle = ctypes.c_void_p()
        iterations = ctypes.c_int()
        _check(self._lib.LGBM_BoosterCreateFromModelfile(str(model_file).encode(), ctypes.byref(iterations),
                                                         ctypes.byref(self._handle)))
        n_features = ctypes.c_int()
        _check(self._lib.LGBM_BoosterGetNumFeature(self._handle, ctypes.byref(n_features)))
        self.num_feature = n_features.value

    def _predict(self, row: list[float], predict_type: int) -> list[float]:
        if len(row) != self.num_feature:
            raise ValueError(f"expected {self.num_feature} features, got {len(row)}")
        data = (ctypes.c_double * len(row))(*row)
        out_len = ctypes.c_int64()
        # start_iteration=0, num_iteration=-1: every tree in the file, as lightgbm.Booster.predict does
        _check(self._lib.LGBM_BoosterCalcNumPredict(self._handle, 1, predict_type, 0, -1, ctypes.byref(out_len)))
        out = (ctypes.c_double * out_len.value)()
        _check(self._lib.LGBM_BoosterPredictForMat(
            self._handle, data, _DTYPE_FLOAT64, 1, len(row), 1, predict_type, 0, -1, b"num_threads=1",
            ctypes.byref(out_len), out))
        return list(out[:out_len.value])

    def predict(self, row: list[float]) -> float:
        return self._predict(row, _PREDICT_NORMAL)[0]

    def contributions(self, row: list[float]) -> list[float]:
        """TreeSHAP contribution per feature, followed by the expected value (the model's baseline)."""
        return self._predict(row, _PREDICT_CONTRIB)

    def __del__(self):
        if getattr(self, "_handle", None) is not None and self._handle.value:
            self._lib.LGBM_BoosterFree(self._handle)


def encode_profile(profile: dict, meta: dict) -> list[float]:
    """One feature row in model order, encoded as salary_model._prepare encodes the training frame."""
    techs = set(profile.get("technologies") or [])
    raw = {col: profile.get(col) for col in meta["categorical"]}
    # Defaults apply only to absent keys: an explicit None stays missing (NaN), as for respondents who
    # skipped the question.
    raw |= {
        "years_code": profile.get("years_code"),
        "work_exp": profile.get("work_exp", profile.get("years_code")),
        "survey_year": profile.get("survey_year", max(meta["years"])),
        "n_languages": profile.get("n_languages", len(techs)),
        "n_technologies": profile.get("n_technologies", len(techs)),
    }
    row = []
    for feature in meta["feature_order"]:
        if feature in meta["categorical"]:
            levels = meta["levels"][feature]
            value = raw[feature] if raw[feature] is not None else "Unknown"
            if value not in levels:
                value = "Other" if feature == "country" else "Unknown"
            row.append(float(levels.index(value)))
        elif feature.startswith("uses_"):
            row.append(1.0 if feature.removeprefix("uses_") in techs else 0.0)
        else:
            try:
                row.append(float(raw[feature]))
            except (TypeError, ValueError):
                row.append(math.nan)
    return row


class SalaryEstimator:
    """Loads the trained artefacts and serves calibrated, explained predictions (used by the API)."""

    def __init__(self, meta: dict, boosters: dict[str, NativeBooster]):
        self.meta = meta
        self.boosters = boosters

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> SalaryEstimator:
        paths = model_paths()
        meta = json.loads(paths["meta"].read_text())
        return cls(meta, {q: NativeBooster(paths[q]) for q in QUANTILE_NAMES})

    def predict(self, profile: dict) -> dict:
        row = encode_profile(profile, self.meta)
        preds = {q: b.predict(row) for q, b in self.boosters.items()}
        margin = self.meta["conformal_margin_log"]
        lo, mid, hi = preds["p10"] - margin, preds["p50"], preds["p90"] + margin
        lo, hi = min(lo, mid), max(hi, mid)
        contrib = self.boosters["p50"].contributions(row)
        base = contrib[-1]
        features = list(zip(self.meta["feature_order"], row, contrib[:-1], strict=True))
        groups: dict[str, float] = {}
        for feature, _, value in features:
            group = "Tech stack" if feature.startswith("uses_") else self.meta["groups"].get(feature, "Other")
            groups[group] = groups.get(group, 0.0) + value
        techs = [(f.removeprefix("uses_"), v) for f, x, v in features if f.startswith("uses_") and x == 1.0]
        return {
            "p10": math.exp(lo), "p50": math.exp(mid), "p90": math.exp(hi),
            "baseline": math.exp(base),
            "contributions": sorted(({"group": g, "log_effect": v, "multiplier": math.exp(v)} for g, v in groups.items()),
                                    key=lambda d: -abs(d["log_effect"])),
            "tech_effects": sorted(({"tech": t, "multiplier": math.exp(v)} for t, v in techs), key=lambda d: -d["multiplier"]),
            "price_base_year": self.meta["price_base_year"],
            "coverage": self.meta["metrics"]["coverage_conformal"],
        }
