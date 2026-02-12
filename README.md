# Deep Research (Single-User Local Edition)

## Run backend (uv + Python 3.12)

```bash
./scripts/run_backend.sh
```

## Run frontend

```bash
./scripts/run_frontend.sh
```

## Test and build

```bash
uv venv --python 3.12 .venv --clear
source .venv/bin/activate
uv pip install -e 'backend[dev]'
ruff check backend tests
pytest tests/unit tests/integration
cd frontend && npm run build
```

## Current status

Local alpha workflow is complete:
- Task lifecycle + FSM + DAG planner
- Retrieval + evidence management
- Analyst conflict detection + vote resolution
- Writer report generation (`.md` + `.bib`)
- MCP minimal execution API
- Frontend six-state workflow console

See `docs/LOCAL_RELEASE.md` for release details.
