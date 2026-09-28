"""Load the canonical technology taxonomy and expand it into a (question group, raw label) lookup."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
import yaml

from .. import settings
from .schema import FIELD_GROUPS


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(settings.CONFIG_DIR / "tech_taxonomy.yml") as fh:
        return yaml.safe_load(fh)


def categories() -> dict[str, str]:
    return dict(_load()["categories"])


def excluded_labels() -> set[str]:
    return set(_load()["excluded"])


@lru_cache(maxsize=1)
def catalog() -> pd.DataFrame:
    """One row per canonical technology: tech, category, category_label, note."""
    rows = []
    cats = categories()
    for category, entries in _load()["technologies"].items():
        for entry in entries:
            entry = {"name": entry} if isinstance(entry, str) else entry
            rows.append({"tech": entry["name"], "category": category, "category_label": cats[category],
                         "note": entry.get("note")})
    frame = pd.DataFrame(rows)
    dupes = frame[frame.tech.duplicated()].tech.tolist()
    if dupes:
        raise ValueError(f"Duplicate canonical technology names: {dupes}")
    return frame


@lru_cache(maxsize=1)
def alias_frame() -> pd.DataFrame:
    """Expanded lookup: one row per (field_group, raw_label) -> tech. Raises on ambiguity."""
    rows = []
    for category, entries in _load()["technologies"].items():
        for entry in entries:
            entry = {"name": entry} if isinstance(entry, str) else entry
            aliases = entry.get("aliases", [entry["name"]])
            groups = entry.get("fields", FIELD_GROUPS)
            for group in groups:
                for alias in aliases:
                    rows.append({"field_group": group, "raw_label": str(alias), "tech": entry["name"],
                                 "category": category})
    frame = pd.DataFrame(rows)
    clash = frame.groupby(["field_group", "raw_label"]).tech.nunique()
    clash = clash[clash > 1]
    if not clash.empty:
        raise ValueError(f"Ambiguous aliases (same label -> several technologies): {clash.index.tolist()}")
    return frame.drop_duplicates(["field_group", "raw_label"]).reset_index(drop=True)
