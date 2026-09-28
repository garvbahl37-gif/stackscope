"""Compensation benchmarks, skill premiums, workforce trends and the ML salary estimator."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import cached

router = APIRouter(prefix="/talent", tags=["talent"])

CUTS = ("country", "region", "role", "experience", "org_size", "remote", "education", "region_role", "region_experience")


@router.get("/benchmarks")
def benchmarks(cut: Literal[CUTS] = "role", year: int = 2025, region: str | None = None) -> dict:  # type: ignore[valid-type]
    params: tuple = (year, cut)
    extra = ""
    if region and cut in ("region_role", "region_experience"):
        extra, params = "AND segment = ?", (year, cut, region)
    rows = cached(f"""SELECT segment, sub_segment, n, p25_usd, median_usd, p75_usd, median_real, median_ppp, p25_ppp, p75_ppp
                      FROM mart.pay_benchmark WHERE survey_year = ? AND cut = ? {extra}
                      ORDER BY median_usd DESC""", params)
    if cut == "country":
        names = {r["iso3"]: r["country"] for r in cached("SELECT iso3, country FROM core.dim_country")}
        for r in rows:
            r["label"] = names.get(r["segment"], r["segment"])
    overall = cached("SELECT n, median_usd, median_ppp FROM mart.pay_benchmark WHERE survey_year = ? AND cut = 'all'", (year,))
    return {"cut": cut, "year": year, "rows": rows, "overall": overall[0] if overall else None}


@router.get("/map")
def pay_map(year: int = 2025) -> dict:
    rows = cached("""SELECT iso3, country, iso_numeric, region, income_group, respondents, pay_n, median_pay_usd,
                            median_pay_ppp, remote_share, ai_use_share, top_language, respondents_per_million, lon, lat
                     FROM mart.country_year WHERE survey_year = ? ORDER BY respondents DESC""", (year,))
    return {"year": year, "rows": rows}


@router.get("/premium")
def premium(scope: str = "Global") -> dict:
    rows = cached("SELECT * FROM mart.skill_premium WHERE scope = ? ORDER BY premium DESC", (scope,))
    model = cached("SELECT * FROM mart.skill_premium_model WHERE scope = ?", (scope,))
    if not rows:
        raise HTTPException(404, f"Unknown scope '{scope}'")
    scopes = [r["scope"] for r in cached("SELECT scope FROM mart.skill_premium_model")]
    return {"scope": scope, "rows": rows, "model": model[0] if model else None, "scopes": scopes}


@router.get("/trends")
def workforce_trends() -> dict:
    return {
        "real_pay": cached("SELECT * FROM mart.real_pay_trend ORDER BY survey_year"),
        "remote": cached("""SELECT survey_year, category, share_w FROM mart.workforce_mix
                            WHERE attribute = 'remote_work' ORDER BY survey_year, category"""),
        "remote_by_region": cached("SELECT * FROM mart.remote_by_region WHERE region <> 'Unknown' ORDER BY region, survey_year"),
        "pay_by_year": cached("""SELECT survey_year, n, median_usd, median_real, median_ppp FROM mart.pay_benchmark
                                 WHERE cut = 'all' ORDER BY survey_year"""),
    }


# ---------------------------------------------------------------------------------------------
# Salary estimator (LightGBM quantile models + conformal calibration + TreeSHAP)
# ---------------------------------------------------------------------------------------------
class Profile(BaseModel):
    country: str = Field("USA", description="ISO3 country code")
    dev_role: str = "Full-stack developer"
    years_code: float = Field(8, ge=0, le=60)
    work_exp: float | None = Field(None, ge=0, le=60)
    org_size: str = "100-499"
    ed_level: str = "Bachelor's"
    remote_work: str = "Hybrid"
    industry: str = "Software & IT"
    age_band: str = "25-34"
    ai_use: str = "Using"
    technologies: list[str] = Field(default_factory=list, max_length=40)


def _estimator():
    from ...analytics.salary_runtime import SalaryEstimator
    try:
        return SalaryEstimator.load()
    except FileNotFoundError as exc:
        raise HTTPException(503, "Salary model not trained yet — run `stackscope run --only analytics`.") from exc
    except OSError as exc:  # LightGBM's native library (or its OpenMP runtime) failed to load
        raise HTTPException(503, f"Salary model unavailable: {exc}") from exc


@router.get("/estimator/options")
def estimator_options() -> dict:
    est = _estimator()
    levels = est.meta["levels"]
    names = {r["iso3"]: r for r in cached("SELECT iso3, country, region FROM core.dim_country")}
    countries = [{"iso3": c, "country": names[c]["country"], "region": names[c]["region"]}
                 for c in levels["country"] if c in names]
    techs = [t.removeprefix("uses_") for t in est.meta["tech_features"]]
    cats = {r["tech"]: r["category_label"] for r in cached("SELECT tech, category_label FROM core.dim_technology")}
    return {
        "countries": sorted(countries, key=lambda c: c["country"]),
        "roles": [v for v in levels["dev_role"] if v != "Unknown"],
        "org_sizes": [v for v in ["<20", "20-99", "100-499", "500-999", "1,000-4,999", "5,000-9,999", "10,000+"] if v in levels["org_size"]],
        "education": [v for v in levels["ed_level"] if v != "Unknown"],
        "remote": [v for v in levels["remote_work"] if v != "Unknown"],
        "industries": [v for v in levels["industry"] if v != "Unknown"],
        "age_bands": [v for v in levels["age_band"] if v != "Unknown"],
        "ai_use": [v for v in levels["ai_use"] if v != "Unknown"],
        "technologies": [{"tech": t, "category": cats.get(t, "Other")} for t in techs],
        "metrics": est.meta["metrics"],
        "importance": cached("SELECT * FROM ml.salary_group_importance ORDER BY mean_abs_shap DESC"),
        "top_features": cached("SELECT label, grp, mean_abs_shap FROM (SELECT label, \"group\" AS grp, mean_abs_shap FROM ml.salary_feature_importance) ORDER BY mean_abs_shap DESC LIMIT 15"),
        "price_base_year": est.meta["price_base_year"],
    }


@router.post("/estimate")
def estimate(profile: Profile) -> dict:
    est = _estimator()
    payload = profile.model_dump()
    region = cached("SELECT region FROM core.dim_country WHERE iso3 = ?", (profile.country,))
    payload["region"] = region[0]["region"] if region else None
    result = est.predict(payload)
    bench = cached("""SELECT median_usd, n FROM mart.pay_benchmark
                      WHERE cut = 'country' AND segment = ? AND survey_year = 2025""", (profile.country,))
    result["country_median"] = bench[0]["median_usd"] if bench else None
    return result
