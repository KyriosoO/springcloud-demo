# Agent Runtime

Python 3.12 + FastAPI + LangGraph runtime service for Agent route and plan
operations. Java remains the source of truth for runtime contracts; Python
models are generated from `agent-api/src/main/resources/openapi/agent-runtime-openapi.json`.

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

- `POST /runtime/v1/route` — Select a capability/domain or return a typed clarification (requires `X-Agent-Runtime-Key`)
- `POST /runtime/v1/plan` — Generate a typed executable plan or return a typed clarification for the selected capability (requires `X-Agent-Runtime-Key`)
- `GET /health` — Health check
