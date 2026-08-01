from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from agent_runtime.api.app import create_app
from agent_runtime.api.models import RuntimeInvokeRequest, RuntimeInvokeResponse
from agent_runtime.api.settings import RuntimeHttpSettings
from tests.api_helpers import CapturingInvoker, runtime_request

FIXTURES = Path(__file__).resolve().parents[3] / "agent-contracts" / "fixtures"


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_python_models_consume_shared_internal_fixtures() -> None:
    request = RuntimeInvokeRequest.model_validate(_fixture("internal-request-valid.json"))
    response = RuntimeInvokeResponse.model_validate(_fixture("internal-response-success.json"))

    assert request.contract_version == 1
    assert response.status.value == "success"
    with pytest.raises(ValidationError):
        RuntimeInvokeRequest.model_validate(_fixture("internal-request-unknown-field.json"))
    with pytest.raises(ValidationError):
        RuntimeInvokeResponse.model_validate(_fixture("internal-response-invalid-enum.json"))
    with pytest.raises(ValidationError):
        RuntimeInvokeResponse.model_validate(_fixture("internal-response-success-with-failure.json"))


@pytest.mark.asyncio
async def test_protocol_errors_are_finite_and_do_not_expose_validation_details() -> None:
    invoker = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(), lambda: invoker)
    transport = httpx.ASGITransport(app=app)
    base_headers = {"Authorization": "Bearer synthetic.jwt.value"}

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            missing = await client.post(
                "/internal/v1/agent-runs:invoke",
                json=runtime_request(),
                headers=base_headers,
            )
            conflict = await client.post(
                "/internal/v1/agent-runs:invoke",
                json=runtime_request(),
                headers={**base_headers, "X-Agent-Contract-Version": "2"},
            )
            unknown = await client.post(
                "/internal/v1/agent-runs:invoke",
                json=runtime_request(forbidden=True),
                headers={**base_headers, "X-Agent-Contract-Version": "1"},
            )

    assert missing.status_code == 400
    assert conflict.status_code == 409
    assert unknown.status_code == 400
    assert missing.json() == {"contractVersion": 1, "code": "runtime.protocol_error"}
    assert set(unknown.json()) == {"contractVersion", "code"}
    assert invoker.calls == 0
