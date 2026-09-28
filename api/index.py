"""Vercel entrypoint: the StackScope FastAPI app as a Python function.

vercel.json rewrites every /api/* request here, and Vercel's CDN serves the React build. The function
bundle carries the read-only DuckDB warehouse and the trained salary models (see .vercelignore).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stackscope.api.main import app  # noqa: E402

__all__ = ["app"]
