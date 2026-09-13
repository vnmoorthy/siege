#!/usr/bin/env bash
# One-shot: build the frontend and run the API on :8000 (serves the built UI).
set -euo pipefail
cd "$(dirname "$0")"
( cd frontend && npm run build )
source .venv/bin/activate
cd backend && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
