# StackScope — common tasks. Run `make help` for the list.
PY      := .venv/bin/python
APP     := stackscope.api.main:app

.PHONY: help setup pipeline data api web-dev web-build serve test test-unit lint notebook docker-build docker-up \
        deploy-check deploy-preview deploy clean

help:            ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-13s\033[0m %s\n", $$1, $$2}'

setup:           ## create the Python env and install web dependencies
	uv venv --python 3.12 .venv
	uv pip install -e ".[dev]"
	cd web && npm ci

pipeline:        ## download data and build everything (warehouse, analytics, quality gate, reports)
	.venv/bin/stackscope run

data:            ## only download raw survey + macro data
	.venv/bin/stackscope run --only ingest
	.venv/bin/stackscope run --only external

api:             ## run the API with auto-reload on :8000
	.venv/bin/uvicorn $(APP) --reload --reload-dir src --port 8000

web-dev:         ## run the Vite dev server on :5173 (proxies /api to :8000)
	cd web && npm run dev

web-build:       ## type-check and build the dashboard into web/dist
	cd web && npm run build

serve: web-build ## serve API + built dashboard from one process on :8000
	.venv/bin/uvicorn $(APP) --port 8000

test:            ## all tests (integration tests need the built warehouse)
	$(PY) -m pytest

test-unit:       ## unit tests only (no data needed)
	$(PY) -m pytest -m "not integration"

lint:            ## ruff + TypeScript type-check
	.venv/bin/ruff check src tests api
	cd web && npm run typecheck

notebook:        ## re-execute the analysis notebook in place
	$(PY) -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_analysis_walkthrough.ipynb

docker-build: web-build ## build the container (needs a built warehouse in data/)
	docker build -t stackscope .

docker-up:       ## run the container on :8000
	docker compose up

deploy-check:    ## check the deployable artefacts: warehouse under Vercel's 100 MB per-file upload limit, models built
	@$(PY) -c "import os, sys; w = 'data/warehouse/stackscope.duckdb'; ok = os.path.exists(w) and os.path.getsize(w) < 100_000_000 and os.path.exists('data/models/salary_meta.json'); print('deploy artefacts ok' if ok else 'run make pipeline first (warehouse missing, over 100 MB, or model not trained)'); sys.exit(not ok)"

deploy-preview: deploy-check ## deploy a preview to Vercel (uploads the local warehouse and models)
	vercel deploy

deploy: deploy-check ## deploy to Vercel production
	vercel deploy --prod

clean:           ## remove build artefacts (keeps downloaded raw data)
	rm -rf data/silver data/warehouse data/marts data/models reports/bi web/dist
