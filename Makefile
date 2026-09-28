# StackScope — common tasks. Run `make help` for the list.
PY      := .venv/bin/python
APP     := stackscope.api.main:app

.PHONY: help setup pipeline data api web-dev web-build serve test test-unit lint notebook docker-build docker-up clean

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
	.venv/bin/ruff check src tests
	cd web && npm run typecheck

notebook:        ## re-execute the analysis notebook in place
	$(PY) -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_analysis_walkthrough.ipynb

docker-build: web-build ## build the container (needs a built warehouse in data/)
	docker build -t stackscope .

docker-up:       ## run the container on :8000
	docker compose up

clean:           ## remove build artefacts (keeps downloaded raw data)
	rm -rf data/silver data/warehouse data/marts data/models reports/bi web/dist
