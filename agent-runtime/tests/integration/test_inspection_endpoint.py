from __future__ import annotations

import httpx
import pytest

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from tests.api_helpers import CapturingInvoker, runtime_request


@pytest.mark.asyncio
async def test_inspection_endpoint_reuses_runtime_and_returns_direct_empty_views() -> None:
    runtime = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(), lambda: runtime)
    transport = httpx.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            response = await client.post(
                "/internal/v1/agent-runs:inspect",
                headers={
                    "Authorization": "Bearer header.payload.signature",
                    "X-Agent-Contract-Version": "1",
                },
                json=runtime_request(),
            )

    assert response.status_code == 200
    body = response.json()
    assert body["requestId"] == runtime_request()["requestId"]
    assert body["modelCalls"] == []
    assert body["plans"] == []
    assert body["downstreamCalls"] == []
    assert runtime.calls == 1
