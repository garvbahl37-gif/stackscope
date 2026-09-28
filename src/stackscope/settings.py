"""Project-wide paths and configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("STACKSCOPE_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.environ.get("STACKSCOPE_DATA", ROOT / "data"))

RAW_DIR = DATA_DIR / "raw"
EXTERNAL_DIR = DATA_DIR / "external"
SILVER_DIR = DATA_DIR / "silver"
WAREHOUSE_PATH = Path(os.environ.get("STACKSCOPE_DB", DATA_DIR / "warehouse" / "stackscope.duckdb"))
MARTS_DIR = DATA_DIR / "marts"
MODELS_DIR = DATA_DIR / "models"
REPORTS_DIR = ROOT / "reports"

SQL_DIR = Path(__file__).resolve().parent / "warehouse" / "sql"

# Constant-dollar base year for inflation adjustment.
BASE_PRICE_YEAR = 2025
RANDOM_SEED = 42


def load_env() -> None:
    """Load KEY=VALUE pairs from ROOT/.env into the process environment (without overriding)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@lru_cache(maxsize=1)
def sources() -> dict:
    with open(CONFIG_DIR / "sources.yml") as fh:
        return yaml.safe_load(fh)


def survey_years() -> list[int]:
    return sorted(int(y) for y in sources()["survey"])


def ensure_dirs() -> None:
    for d in (RAW_DIR, EXTERNAL_DIR, SILVER_DIR, WAREHOUSE_PATH.parent, MARTS_DIR, MODELS_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
