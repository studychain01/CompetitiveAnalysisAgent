# BattleScope

Monorepo for the competitive intelligence agent: **Next.js** (`apps/web`) and **Python** (`apps/api`).

## Prerequisites

- Node.js 20+
- Python 3.11+
- Optional: [uv](https://docs.astral.sh/uv/) for faster Python env management

## Web app

```bash
npm install
npm run dev:web
```

Open [http://localhost:3000](http://localhost:3000).

## API (FastAPI + LangGraph scaffold)

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# or: pip install -r requirements.txt && pip install -e .
pytest
uvicorn battlescope_api.main:app --reload --port 8000
```

The LangGraph `intake` node is **async**; call it with `await graph.ainvoke({...})` (see `tests/test_graph_smoke.py`).

Health check: [http://localhost:8000/health](http://localhost:8000/health).

Phase 0 harness: JSON line logging (`log_setup`), retrying `ToolClient`, `parse_llm_json`, and `tests/fixtures/`. **IntakeProfiler** (`graph/nodes/intake.py`) calls Tavily + Firecrawl + OpenAI when keys are set, with heuristic fallback when not.

**LangSmith:** add `LANGSMITH_TRACING=true` / `LANGSMITH_TRACING_V2=true` or `LANGCHAIN_TRACING_V2=true`, plus `LANGSMITH_API_KEY` / `LANGCHAIN_API_KEY` and project vars to `apps/api/.env`. On import, `settings.py` runs `load_dotenv(apps/api/.env)` so those variables reach `os.environ` (LangSmith reads the environment directly, not only Pydantic fields). `@traceable` spans live in `tools/tavily_client.py`, `firecrawl_client.py`, and `llm.py`.

Copy `apps/api/.env.example` to `apps/api/.env` and add API keys when you wire Tavily, Firecrawl, and your LLM provider.

## Layout

- `apps/web` — Next.js UI
- `apps/api` — Python package `battlescope_api` (FastAPI entry, LangGraph under `graph/`)
