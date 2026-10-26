PY ?= .venv/bin/python

.PHONY: setup test build api web

setup:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

test:
	$(PY) -m pytest -q

build:
	$(PY) -m nba.build --out out/

api:
	$(PY) -m uvicorn api.app:app --reload --port 8000

web:
	cd web && npm install && npm run dev
