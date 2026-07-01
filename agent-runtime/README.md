# Agent Runtime (P0)

Python 3.12 + FastAPI + LangGraph service that generates QUERY/CLARIFY plans.

## Setup

```powershell
cd agent-runtime
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

Copy `example.env` to `.env` and fill in real values:
- `AGENT_LLM_BASE_URL` — OpenAI-compatible API base URL
- `AGENT_LLM_API_KEY` — API key
- `AGENT_LLM_MODEL` — Model name
- `AGENT_RUNTIME_SHARED_KEY` — Must match Java's `agent.runtime.shared-key` (≥16 chars)

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 9230
```

## API

- `POST /runtime/v1/plans/generate` — Generate QUERY/CLARIFY plan (requires `X-Agent-Runtime-Key`)
- `GET /health` — Health check
