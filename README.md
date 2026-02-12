# Deep Research (Single-User Local Edition)

## Run backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e backend[dev]
uvicorn app.main:app --app-dir backend --reload
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

## Current status

Phase 0 scaffold is in place. Core workflow APIs and agents are implemented in subsequent phases.
