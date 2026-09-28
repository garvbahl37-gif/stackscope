"""Macro-economic reference data: World Bank (PPP, GDP, population, country metadata) and FRED CPI.

Results are cached as CSV under data/external/ — delete a file to force a refresh.
"""

from __future__ import annotations

import io
import time

import pandas as pd
import requests

from .. import settings

TIMEOUT = 60


def _get(url: str, params: dict | None = None, retries: int = 3) -> requests.Response:
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_wb_countries() -> pd.DataFrame:
    path = settings.EXTERNAL_DIR / "wb_countries.csv"
    if path.exists():
        return pd.read_csv(path, keep_default_na=False, na_values=[""])
    base = settings.sources()["world_bank"]["base_url"]
    payload = _get(f"{base}/country", {"format": "json", "per_page": 500}).json()[1]
    rows = [
        {"iso3": c["id"], "iso2": c["iso2Code"], "wb_name": c["name"], "region": c["region"]["value"].strip(),
         "income_group": c["incomeLevel"]["value"].strip(), "capital": c["capitalCity"] or None,
         "lon": float(c["longitude"]) if c["longitude"] else None,
         "lat": float(c["latitude"]) if c["latitude"] else None}
        for c in payload if c["region"]["value"].strip() != "Aggregates"
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False)
    return frame


def fetch_wb_indicators() -> pd.DataFrame:
    path = settings.EXTERNAL_DIR / "wb_indicators.csv"
    if path.exists():
        return pd.read_csv(path, keep_default_na=False, na_values=[""])
    cfg = settings.sources()["world_bank"]
    start, end = cfg["years"]
    frames = []
    for code, name in cfg["indicators"].items():
        payload = _get(f"{cfg['base_url']}/country/all/indicator/{code}",
                       {"format": "json", "date": f"{start}:{end}", "per_page": 30000}).json()
        records = payload[1] or []
        frames.append(pd.DataFrame(
            [{"iso3": r["countryiso3code"], "year": int(r["date"]), "indicator": name, "value": r["value"]}
             for r in records if r["countryiso3code"] and r["value"] is not None]))
    frame = pd.concat(frames, ignore_index=True)
    frame.to_csv(path, index=False)
    return frame


def fetch_cpi() -> pd.DataFrame:
    """US CPI-U annual averages (FRED CPIAUCSL, monthly SA)."""
    path = settings.EXTERNAL_DIR / "cpi_us.csv"
    if path.exists():
        return pd.read_csv(path)
    raw = pd.read_csv(io.StringIO(_get(settings.sources()["fred"]["url"]).text))
    raw.columns = ["date", "cpi"]
    raw["year"] = pd.to_datetime(raw["date"]).dt.year
    raw["cpi"] = pd.to_numeric(raw["cpi"], errors="coerce")
    annual = raw.groupby("year").agg(cpi=("cpi", "mean"), months=("cpi", "count")).reset_index()
    annual = annual[annual.year >= 2010]
    annual.to_csv(path, index=False)
    return annual


def fetch_all() -> None:
    settings.ensure_dirs()
    countries = fetch_wb_countries()
    indicators = fetch_wb_indicators()
    cpi = fetch_cpi()
    print(f"  [external] World Bank: {len(countries)} economies, {len(indicators):,} indicator rows; "
          f"CPI {int(cpi.year.min())}-{int(cpi.year.max())}")
