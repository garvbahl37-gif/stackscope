# ---------- dashboard build ----------
FROM node:24-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---------- runtime: FastAPI + DuckDB + LightGBM ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STACKSCOPE_ROOT=/app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY config/ config/
RUN pip install --no-cache-dir .
COPY --from=web /web/dist web/dist
# The warehouse and trained models are build outputs of `make pipeline` (the image never sees raw data or secrets)
COPY data/warehouse/stackscope.duckdb data/warehouse/stackscope.duckdb
COPY data/models/ data/models/
COPY data/raw/manifest.json data/raw/manifest.json
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "stackscope.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
