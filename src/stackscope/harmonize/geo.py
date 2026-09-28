"""Country harmonisation: 254 raw spellings (9 years) -> ISO3 + analysis region + World Bank income group."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

import country_converter as coco
import pandas as pd

from ..ingest.external import fetch_wb_countries

logging.getLogger("country_converter").setLevel(logging.ERROR)

MANUAL_ISO3 = {"Azerbaidjan": "AZE", "Moldavia": "MDA", "Tadjikistan": "TJK", "Polynesia (French)": "PYF"}
NOT_A_COUNTRY = {"Nomadic", "Other Country (Not Listed Above)", "I prefer not to say", "Netherlands Antilles",
                 "S. Georgia & S. Sandwich Isls."}

# UN M49 sub-regions rolled up into ten analysis regions (finer than World Bank regions for Europe/Asia).
UN_TO_ANALYSIS = {
    "Northern America": "North America",
    "South America": "Latin America", "Central America": "Latin America", "Caribbean": "Latin America",
    "Western Europe": "Western Europe", "Northern Europe": "Western Europe", "Southern Europe": "Western Europe",
    "Eastern Europe": "Eastern Europe & Central Asia", "Central Asia": "Eastern Europe & Central Asia",
    "Western Asia": "Middle East & North Africa", "Northern Africa": "Middle East & North Africa",
    "Eastern Africa": "Sub-Saharan Africa", "Western Africa": "Sub-Saharan Africa",
    "Middle Africa": "Sub-Saharan Africa", "Southern Africa": "Sub-Saharan Africa",
    "Southern Asia": "South Asia", "Eastern Asia": "East Asia", "South-eastern Asia": "Southeast Asia",
    "Australia and New Zealand": "Oceania", "Melanesia": "Oceania", "Micronesia": "Oceania", "Polynesia": "Oceania",
}
REGION_OVERRIDES = {"IRN": "Middle East & North Africa"}
ANALYSIS_REGIONS = ["North America", "Western Europe", "Eastern Europe & Central Asia", "South Asia", "East Asia",
                    "Southeast Asia", "Latin America", "Middle East & North Africa", "Sub-Saharan Africa", "Oceania"]
NON_WB_META = {"TWN": {"income_group": "High income", "lon": 121.56, "lat": 25.04, "capital": "Taipei"}}

_ISO3 = re.compile(r"^[A-Z]{3}$")


def build_country_dim(raw_names: Iterable[str]) -> pd.DataFrame:
    """Return one row per raw country label with iso3, display name, region, income group, coordinates."""
    names = sorted({n for n in raw_names if isinstance(n, str)})
    cc = coco.CountryConverter()
    converted = cc.convert(names, to="ISO3", not_found=None)
    iso_by_name = {}
    for name, iso in zip(names, converted, strict=True):
        if name in NOT_A_COUNTRY:
            iso_by_name[name] = None
        elif name in MANUAL_ISO3:
            iso_by_name[name] = MANUAL_ISO3[name]
        else:
            iso_by_name[name] = iso if isinstance(iso, str) and _ISO3.match(iso) else None

    isos = sorted({i for i in iso_by_name.values() if i})
    meta = pd.DataFrame({
        "iso3": isos,
        "country": cc.convert(isos, src="ISO3", to="name_short"),
        "iso_numeric": cc.convert(isos, src="ISO3", to="ISOnumeric"),
        "un_region": cc.convert(isos, src="ISO3", to="UNregion"),
    })
    meta["region"] = meta.apply(lambda r: REGION_OVERRIDES.get(r.iso3, UN_TO_ANALYSIS.get(r.un_region)), axis=1)
    wb = fetch_wb_countries()[["iso3", "income_group", "capital", "lon", "lat"]]
    meta = meta.merge(wb, on="iso3", how="left")
    for iso, extra in NON_WB_META.items():
        for key, value in extra.items():
            meta.loc[meta.iso3 == iso, key] = value
    meta["iso_numeric"] = pd.to_numeric(meta["iso_numeric"], errors="coerce").astype("Int64")

    lookup = pd.DataFrame({"country_raw": list(iso_by_name), "iso3": list(iso_by_name.values())})
    return lookup.merge(meta, on="iso3", how="left")
