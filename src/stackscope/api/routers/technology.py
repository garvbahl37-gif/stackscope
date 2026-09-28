"""Technology adoption, positioning, forecasts, market structure and retention flows."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..db import cached

router = APIRouter(prefix="/tech", tags=["technology"])

METRICS = {
    "adoption": ("share_used_w", "share_used_w_lo", "share_used_w_hi"),
    "adoption_raw": ("share_used", "share_used_lo", "share_used_hi"),
    "desire": ("share_wanted_w", None, None),
    "retention": ("retention_w", None, None),
    "attraction": ("attraction_w", None, None),
    "net_desire": ("net_desire_w", None, None),
}


def _techs(csv: str) -> tuple[str, ...]:
    techs = tuple(t.strip() for t in csv.split(",") if t.strip())
    if not techs or len(techs) > 12:
        raise HTTPException(400, "Pass 1-12 comma-separated technology names")
    return techs


@router.get("/trends")
def trends(techs: str = Query(..., description="Comma-separated technology names"),
           metric: Literal["adoption", "adoption_raw", "desire", "retention", "attraction", "net_desire"] = "adoption") -> dict:
    value, lo, hi = METRICS[metric]
    names = _techs(techs)
    placeholders = ", ".join("?" for _ in names)
    rows = cached(f"""
        SELECT tech, category, survey_year, {value} AS value,
               {lo or 'NULL'} AS lo, {hi or 'NULL'} AS hi, base_n
        FROM mart.tech_year WHERE tech IN ({placeholders}) ORDER BY tech, survey_year""", names)
    notes = cached(f"SELECT tech, note FROM core.dim_technology WHERE tech IN ({placeholders}) AND note IS NOT NULL", names)
    stats = cached(f"""SELECT tech, odds_growth, odds_growth_lo, odds_growth_hi, q_value, trend, n_points
                       FROM mart.tech_trend WHERE tech IN ({placeholders})""", names)
    series = {}
    for r in rows:
        series.setdefault(r["tech"], {"tech": r["tech"], "category": r["category"], "points": []})["points"].append(
            {"year": r["survey_year"], "value": r["value"], "lo": r["lo"], "hi": r["hi"], "n": r["base_n"]})
    return {"metric": metric, "series": [series[t] for t in names if t in series], "notes": notes, "stats": stats}


@router.get("/quadrant")
def quadrant(category: str = "language") -> dict:
    rows = cached("""SELECT survey_year, tech, share_used_w AS adoption, share_used_w_lo AS adoption_lo,
                            share_used_w_hi AS adoption_hi, momentum, retention_w AS retention, attraction_w AS attraction,
                            net_desire_w AS net_desire, quadrant, base_n, adoption_threshold
                     FROM mart.tech_quadrant WHERE category = ? ORDER BY survey_year, tech""", (category,))
    if not rows:
        raise HTTPException(404, f"No quadrant for category '{category}'")
    years = sorted({r["survey_year"] for r in rows})
    return {"category": category, "years": years, "points": rows}


@router.get("/radar")
def radar() -> dict:
    blips = cached("SELECT * FROM mart.tech_radar ORDER BY blip")
    return {"blips": blips, "sectors": ["Languages", "Frameworks", "Data & AI", "Platforms & Tools"],
            "rings": ["Adopt", "Trial", "Assess", "Hold"]}


@router.get("/forecast")
def forecast(techs: str = Query(...)) -> dict:
    names = _techs(techs)
    placeholders = ", ".join("?" for _ in names)
    rows = cached(f"""SELECT tech, category, survey_year, share, lo80, hi80, kind, model
                      FROM mart.tech_forecast WHERE tech IN ({placeholders}) ORDER BY tech, survey_year""", names)
    backtest = cached("SELECT * FROM mart.forecast_backtest ORDER BY horizon, mae_pp")
    indicator = cached("SELECT * FROM mart.forecast_indicator")
    series = {}
    for r in rows:
        series.setdefault(r["tech"], {"tech": r["tech"], "category": r["category"], "points": []})["points"].append(r)
    return {"series": [series[t] for t in names if t in series], "backtest": backtest, "indicator": indicator,
            "forecastable": [r["tech"] for r in cached("SELECT DISTINCT tech FROM mart.tech_forecast ORDER BY 1")]}


@router.get("/movers")
def movers(category: str | None = None, year: int | None = None) -> dict:
    year = year or cached("SELECT max(survey_year) AS y FROM mart.tech_yoy")[0]["y"]
    cat_filter = "AND category = ?" if category else ""
    params = (year, category) if category else (year,)
    rows = cached(f"""SELECT tech, category, prev_share_used_w, share_used_w, delta_pp, q_value, significant
                      FROM mart.tech_yoy WHERE survey_year = ? {cat_filter} ORDER BY delta_pp DESC""", params)
    return {"year": year, "rows": rows}


@router.get("/selection")
def selection(category: str = "language") -> dict:
    """Mean options ticked per respondent per year (questionnaire-effect diagnostic)."""
    return {"category": category,
            "rows": cached("SELECT * FROM mart.selection_intensity WHERE category = ? ORDER BY survey_year", (category,))}


@router.get("/trajectories")
def trajectories(category: str | None = None) -> dict:
    where = "WHERE category = ?" if category else ""
    rows = cached(f"""SELECT * FROM mart.tech_trend {where} ORDER BY odds_growth DESC NULLS LAST""",
                  (category,) if category else ())
    return {"rows": rows}


@router.get("/concentration")
def concentration(category: str = "cloud") -> dict:
    hhi = cached("SELECT * FROM mart.market_concentration WHERE category = ? ORDER BY survey_year", (category,))
    shares = cached("""
        WITH ranked AS (
            SELECT survey_year, tech, mindshare,
                   max(mindshare) OVER (PARTITION BY tech) AS best
            FROM mart.tech_mindshare WHERE category = ?),
        top AS (SELECT tech FROM ranked GROUP BY tech ORDER BY max(best) DESC LIMIT 7)
        SELECT survey_year, CASE WHEN tech IN (SELECT tech FROM top) THEN tech ELSE 'Others' END AS tech,
               sum(mindshare) AS mindshare
        FROM ranked GROUP BY ALL ORDER BY survey_year, mindshare DESC""", (category,))
    return {"category": category, "hhi": hhi, "shares": shares}


@router.get("/retention")
def retention(category: str = "language", year: int | None = None, top: int = 8) -> dict:
    year = year or cached("SELECT max(survey_year) AS y FROM mart.tech_switching")[0]["y"]
    leaderboard = cached("""
        SELECT tech, retention_w AS retention, attraction_w AS attraction, share_used_w AS adoption, users_asked_want,
               1 - retention_w AS churn
        FROM mart.tech_year WHERE category = ? AND survey_year = ? AND users_asked_want >= 300
        ORDER BY retention_w DESC""", (category, year))
    sources = cached("""SELECT from_tech, max(from_churners) AS churners FROM mart.tech_switching
                        WHERE category = ? AND survey_year = ? GROUP BY 1 ORDER BY churners DESC LIMIT ?""", (category, year, top))
    names = tuple(s["from_tech"] for s in sources)
    if not names:
        return {"year": year, "category": category, "leaderboard": leaderboard, "flows": [], "net": []}
    placeholders = ", ".join("?" for _ in names)
    flows = cached(f"""SELECT from_tech, to_tech, n, share_of_churners, from_churn_rate, destination_rank
                       FROM mart.tech_switching WHERE category = ? AND survey_year = ? AND from_tech IN ({placeholders})
                         AND destination_rank <= 5
                       ORDER BY from_tech, destination_rank""", (category, year, *names))
    net = cached("""SELECT from_tech, to_tech, flow_forward, flow_backward, net_flow, net_ratio
                    FROM mart.tech_net_migration WHERE category = ? AND survey_year = ?
                    ORDER BY net_flow DESC LIMIT 15""", (category, year))
    return {"year": year, "category": category, "leaderboard": leaderboard, "flows": flows, "net": net}


@router.get("/profile/{tech}")
def profile(tech: str) -> dict:
    info = cached("SELECT * FROM core.dim_technology WHERE tech = ?", (tech,))
    if not info:
        raise HTTPException(404, f"Unknown technology '{tech}'")
    return {
        "info": info[0],
        "series": cached("""SELECT survey_year, share_used_w, share_used_w_lo, share_used_w_hi, share_wanted_w,
                                   retention_w, attraction_w, rank_in_category, base_n
                            FROM mart.tech_year WHERE tech = ? ORDER BY survey_year""", (tech,)),
        "trend": (cached("SELECT * FROM mart.tech_trend WHERE tech = ?", (tech,)) or [None])[0],
        "quadrant": cached("SELECT survey_year, quadrant, momentum FROM mart.tech_quadrant WHERE tech = ? ORDER BY 1", (tech,)),
        "premium": cached("SELECT scope, premium, premium_lo, premium_hi, q_value, significant FROM mart.skill_premium WHERE tech = ?", (tech,)),
        "leaving_to": cached("""SELECT to_tech, n, share_of_churners FROM mart.tech_switching
                                WHERE from_tech = ? AND survey_year = (SELECT max(survey_year) FROM mart.tech_switching)
                                ORDER BY n DESC LIMIT 5""", (tech,)),
        "arriving_from": cached("""SELECT from_tech, n FROM mart.tech_switching
                                   WHERE to_tech = ? AND survey_year = (SELECT max(survey_year) FROM mart.tech_switching)
                                   ORDER BY n DESC LIMIT 5""", (tech,)),
        "paired_with": cached("""SELECT consequent AS tech, confidence, lift FROM mart.assoc_rules
                                 WHERE antecedent = ? AND survey_year = (SELECT max(survey_year) FROM mart.assoc_rules)
                                 ORDER BY confidence * lift DESC LIMIT 8""", (tech,)),
    }
