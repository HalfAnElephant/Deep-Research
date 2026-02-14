# Local Alpha Release Guide

## 1. Requirements

- `uv` installed and available in PATH
- Node.js 20+
- npm 10+

## 2. Backend

```bash
./scripts/run_backend.sh
```

If startup shows `No supported WebSocket library detected`, reinstall backend deps:

```bash
source .venv/bin/activate
uv pip install -e 'backend[dev]'
```

Backend URL: `http://127.0.0.1:8000`
OpenAPI: `http://127.0.0.1:8000/docs`

## 3. Frontend

```bash
./scripts/run_frontend.sh
```

Frontend URL: `http://127.0.0.1:5173`

## 4. Test and Build

```bash
uv venv --python 3.12 .venv --clear
source .venv/bin/activate
uv pip install -e 'backend[dev]'
ruff check backend tests
pytest tests/unit tests/integration
cd frontend && npm run build
```

## 5. Notes

- This release is single-user local mode only.
- Queue services, Docker deployment, and multi-user access are intentionally deferred.
