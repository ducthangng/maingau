PY ?= .venv/bin/python

.PHONY: setup test build api fresh web

setup:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

test:
	$(PY) -m pytest -q

build:
	$(PY) -m nba.build --out out/

api:
	$(PY) -m uvicorn api.app:app --reload --port 8000

# API from a fresh demo state (state files moved to out/_reset_<time>/, Knowledge Base rebuilt)
fresh:
	PY=$(PY) scripts/fresh_api.sh

web:
	cd web && npm install && npm run dev
