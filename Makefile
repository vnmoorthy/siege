.PHONY: setup dev backend frontend build test lab
setup:            ## create venv, install backend + frontend deps
	uv venv .venv && . .venv/bin/activate && uv pip install -e ".[dev,lab]" && cd frontend && npm install
backend:          ## run the API (serves frontend/dist when built)
	. .venv/bin/activate && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
frontend:         ## vite dev server with proxy to :8000
	cd frontend && npm run dev
build:            ## production frontend build
	cd frontend && npm run build
test:             ## backend tests (mock mode, no keys needed)
	. .venv/bin/activate && cd backend && python -m pytest -q
lab:              ## marimo analysis notebook
	. .venv/bin/activate && marimo run notebooks/siege_lab.py
dev: build backend
