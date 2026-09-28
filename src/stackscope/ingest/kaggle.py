"""Bronze layer — pull raw survey microdata from Kaggle and record a provenance manifest.

Auth uses the KAGGLE_API_TOKEN environment variable (read from the git-ignored .env file).
Downloads are idempotent: a year is skipped when its file already exists, unless force=True.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .. import settings

MANIFEST = settings.RAW_DIR / "manifest.json"


def _kaggle_bin() -> str:
    venv_bin = Path(sys.executable).parent / "kaggle"
    if venv_bin.exists():
        return str(venv_bin)
    found = shutil.which("kaggle")
    if not found:
        raise RuntimeError("Kaggle CLI not found — install the project dependencies first.")
    return found


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def raw_file(year: int) -> Path:
    cfg = settings.sources()["survey"][year]
    return settings.RAW_DIR / str(year) / cfg["file"]


def download_year(year: int, force: bool = False) -> Path:
    cfg = settings.sources()["survey"][year]
    target = raw_file(year)
    if target.exists() and not force:
        return target
    if not os.environ.get("KAGGLE_API_TOKEN") and not (Path.home() / ".kaggle").exists():
        raise RuntimeError("Set KAGGLE_API_TOKEN in .env (see .env.example) to download the survey data.")
    dest = settings.RAW_DIR / str(year)
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [_kaggle_bin(), "datasets", "download", cfg["kaggle"], "-p", str(dest), "--unzip", "-q"]
    if force:
        cmd.append("--force")
    subprocess.run(cmd, check=True, env=os.environ.copy())
    if not target.exists():
        raise FileNotFoundError(f"{cfg['kaggle']} did not contain {cfg['file']}")
    return target


def download_all(force: bool = False) -> dict:
    settings.load_env()
    settings.ensure_dirs()
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for year in settings.survey_years():
        path = download_year(year, force=force)
        entry = manifest.get(str(year), {})
        stat = path.stat()
        if force or entry.get("bytes") != stat.st_size:
            entry = {
                "kaggle_ref": settings.sources()["survey"][year]["kaggle"],
                "file": str(path.relative_to(settings.DATA_DIR)),
                "bytes": stat.st_size,
                "sha256": sha256(path),
                "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        manifest[str(year)] = entry
        print(f"  [bronze] {year}: {entry['bytes'] / 1e6:,.1f} MB  sha256={entry['sha256'][:12]}…")
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    return manifest
