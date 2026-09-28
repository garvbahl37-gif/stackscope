"""StackScope API — FastAPI application.

    uvicorn stackscope.api.main:app --reload            (dev, http://localhost:8000/docs)

When the React build exists at web/dist it is served from the same origin, so one process runs the
whole product in production.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import settings
from .db import scalar
from .routers import insight, overview, sql_lab, talent, technology

app = FastAPI(
    title="StackScope API",
    version="1.0.0",
    description="Developer technology market intelligence — 9 survey waves, 664k respondents. "
                "Adoption, positioning, retention, compensation, personas, GenAI and data quality.",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

for router in (overview.router, technology.router, talent.router, insight.router, sql_lab.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["overview"])
def health() -> dict:
    return {"status": "ok", "respondents": scalar("SELECT count(*) FROM core.fact_respondent"),
            "warehouse": str(settings.WAREHOUSE_PATH.name)}


DIST = Path(settings.ROOT) / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
