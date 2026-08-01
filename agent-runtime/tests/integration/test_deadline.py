from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from starlette.requests import Request
from starlette.types import Message

from agent_runtime.api.ingress import invoke_agent
from agent_runtime.api.limits import RuntimeRequestLimiter
from agent_runtime.api.models import RuntimeInvokeRequest
from agent_runtime.capability_api.contracts import CapabilityStatus
from tests.api_helpers import CapturingInvoker, FixedClocks, runtime_request


def _request() -> Request:
    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/", "headers": []}, receive)


@pytest.mark.asyncio
async def test_runtime_uses_smaller_absolute_and_relative_budget_minus_guard() -> None:
    invoker = CapturingInvoker()
    payload = RuntimeInvokeRequest.model_validate(
        runtime_request(deadlineEpochMs=6000, remainingTimeoutMs=10000)
    )

    response = await invoke_agent(
        _request(),
        payload,
        "Bearer synthetic.jwt",
        "1",
        invoker,
        RuntimeRequestLimiter(1),
        clocks=FixedClocks(epoch=1000, monotonic_value=10.0),
    )

    assert response.status is CapabilityStatus.UNSUPPORTED
    assert invoker.calls == 1
    assert invoker.scopes[0].context.deadline_monotonic == pytest.approx(14.9)


@pytest.mark.asyncio
async def test_exhausted_deadline_returns_semantic_timeout_without_invoker() -> None:
    invoker = CapturingInvoker()
    payload = RuntimeInvokeRequest.model_validate(
        runtime_request(deadlineEpochMs=1100, remainingTimeoutMs=1000)
    )

    response = await invoke_agent(
        _request(),
        payload,
        "Bearer synthetic.jwt",
        "1",
        invoker,
        RuntimeRequestLimiter(1),
        clocks=FixedClocks(epoch=1000, monotonic_value=10.0),
    )

    assert response.status is CapabilityStatus.TIMEOUT
    assert response.failure is not None
    assert response.failure.code == "core.deadline_exhausted"
    assert invoker.calls == 0
