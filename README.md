# Deep Research (Single-User Local Edition)

## Run backend (uv + Python 3.12)

```bash
./scripts/run_backend.sh
```

If you see warnings like `No supported WebSocket library detected`, run:

```bash
source .venv/bin/activate
uv pip install -e 'backend[dev]'
```

## Configure API keys (`.env`)

Project root now includes a `.env` file template.
Fill only the providers you plan to use:

- LLM: `DR_OPENROUTER_API_KEY`, `DR_DEEPSEEK_API_KEY`, `DR_OPENAI_API_KEY`, `DR_ANTHROPIC_API_KEY`
- Search: `DR_SERPER_API_KEY`, `DR_SERPAPI_API_KEY`, `DR_TAVILY_API_KEY`, `DR_BRAVE_API_KEY`, `DR_BING_SUBSCRIPTION_KEY`, `DR_GOOGLE_CSE_API_KEY`, `DR_GOOGLE_CSE_CX`

Also configurable:

- `DR_DEFAULT_LLM_PROVIDER` (for example `openrouter` or `deepseek`)
- `DR_DEFAULT_LLM_MODEL`
- `DR_USE_MOCK_SOURCES` (`false` by default for real API calls, set `true` only for deterministic mock/testing mode)

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
- Built-in `ResearchAgent` / `ReportAgent` orchestration layer (ready for MCP expansion)
- MCP minimal execution API
- Chat-driven multi-session workspace:
  - Sidebar conversation list
  - Chat timeline for plan drafting/revision
  - Right-side Markdown plan editor
  - Collapsible research progress groups
  - Final report preview + Markdown download

See `docs/LOCAL_RELEASE.md` for release details.

## New conversation APIs

- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `POST /api/v1/conversations/{conversation_id}/plan/revise`
- `PUT /api/v1/conversations/{conversation_id}/plan`
- `POST /api/v1/conversations/{conversation_id}/run`
- `GET /api/v1/conversations/{conversation_id}/report/download`
