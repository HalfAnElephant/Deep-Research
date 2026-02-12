#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e 'backend[dev]'
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
