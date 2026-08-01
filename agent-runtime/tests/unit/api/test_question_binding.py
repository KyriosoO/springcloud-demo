from __future__ import annotations

import httpx
import pytest
import logging

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from tests.api_helpers import CapturingInvoker, runtime_request


@pytest.mark.asyncio
async def test_ingress_binds_one_unchanged_question_to_graph_and_context() -> None:
    invoker = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(), lambda: invoker)
    transport = httpx.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            response = await client.post(
                "/internal/v1/agent-runs:invoke",
                json=runtime_request(question="  税务政策  "),
                headers={
                    "Authorization": "Bearer synthetic.jwt.value",
                    "X-Agent-Contract-Version": "1",
                },
            )

    assert response.status_code == 200
    assert invoker.questions == ["  税务政策  "]
    assert invoker.scopes[0].context.original_question == "  税务政策  "
    assert invoker.scopes[0].context.subject_id == "dylan"
    assert repr(invoker.scopes[0].context.user_token) == "<redacted>"


@pytest.mark.asyncio
async def test_runtime_log_contains_only_safe_metadata(caplog: pytest.LogCaptureFixture) -> None:
    invoker = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(), lambda: invoker)
    transport = httpx.ASGITransport(app=app)
    secret_token = "sensitive.jwt.value"
    secret_question = "sensitive question body"

    with caplog.at_level(logging.INFO, logger="agent_runtime.api.ingress"):
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
                response = await client.post(
                    "/internal/v1/agent-runs:invoke",
                    json=runtime_request(question=secret_question),
                    headers={
                        "Authorization": f"Bearer {secret_token}",
                        "X-Agent-Contract-Version": "1",
                    },
                )

    assert response.status_code == 200
    rendered = caplog.text
    assert secret_token not in rendered
    assert secret_question not in rendered
