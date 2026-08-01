from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request
from starlette.types import Message

from agent_runtime.api.cancellation import MutableCancellationSignal, watch_disconnect
from agent_runtime.api.ingress import invoke_agent
from agent_runtime.api.limits import RuntimeRequestLimiter
from agent_runtime.api.models import RuntimeInvokeRequest
from agent_runtime.capability_api.contracts import CancellationSource
from tests.api_helpers import CapturingInvoker, runtime_request


def _request(message_type: str = "http.request") -> Request:
    async def receive() -> Message:
        if message_type == "http.disconnect":
            return {"type": "http.disconnect"}
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/", "headers": []}, receive)


@pytest.mark.asyncio
async def test_disconnect_publishes_one_upstream_cancel() -> None:
    signal = MutableCancellationSignal()

    await watch_disconnect(_request("http.disconnect"), signal, 0.001)

    assert signal.is_cancelled()
    assert await signal.wait_cancelled() is CancellationSource.UPSTREAM_CANCEL


@pytest.mark.asyncio
async def test_outer_cancellation_propagates_and_releases_limiter() -> None:
    release = asyncio.Event()
    invoker = CapturingInvoker(release=release)
    limiter = RuntimeRequestLimiter(1)
    payload = RuntimeInvokeRequest.model_validate(runtime_request())
    task = asyncio.create_task(
        invoke_agent(
            _request(),
            payload,
            "Bearer synthetic.jwt",
            "1",
            invoker,
            limiter,
        )
    )
    await invoker.started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert limiter.in_flight == 0
