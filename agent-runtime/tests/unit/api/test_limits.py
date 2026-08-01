from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from agent_runtime.api.app import create_app
from agent_runtime.api.limits import RuntimeCapacityExceeded, RuntimeRequestLimiter
from agent_runtime.api.settings import RuntimeHttpSettings
from tests.api_helpers import CapturingInvoker, runtime_request


@pytest.mark.asyncio
async def test_limiter_is_atomic_and_releases_exactly_once() -> None:
    limiter = RuntimeRequestLimiter(1)
    lease = await limiter.try_acquire()

    with pytest.raises(RuntimeCapacityExceeded):
        await limiter.try_acquire()
    await lease.release()
    await lease.release()

    assert limiter.in_flight == 0


@pytest.mark.asyncio
async def test_body_and_media_type_fail_before_runtime() -> None:
    invoker = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(max_body_bytes=4096), lambda: invoker)
    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer synthetic.jwt", "X-Agent-Contract-Version": "1"}

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            too_large = await client.post(
                "/internal/v1/agent-runs:invoke",
                content=b"{" + b"x" * 4096 + b"}",
                headers={**headers, "Content-Type": "application/json"},
            )
            wrong_type = await client.post(
                "/internal/v1/agent-runs:invoke",
                content=b"{}",
                headers={**headers, "Content-Type": "text/plain"},
            )

    assert too_large.status_code == 413
    assert wrong_type.status_code == 415
    assert invoker.calls == 0
    assert too_large.json() == {"contractVersion": 1, "code": "runtime.protocol_error"}


@pytest.mark.asyncio
async def test_chunked_body_limit_fails_before_runtime() -> None:
    invoker = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(max_body_bytes=4096), lambda: invoker)
    transport = httpx.ASGITransport(app=app)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"{" + b"x" * 2048
        yield b"x" * 2049 + b"}"

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            response = await client.post(
                "/internal/v1/agent-runs:invoke",
                content=chunks(),
                headers={
                    "Authorization": "Bearer synthetic.jwt",
                    "X-Agent-Contract-Version": "1",
                    "Content-Type": "application/json",
                },
            )

    assert response.status_code == 413
    assert invoker.calls == 0


@pytest.mark.asyncio
async def test_capacity_returns_429_without_second_invocation() -> None:
    invoker = CapturingInvoker()
    app = create_app(RuntimeHttpSettings(max_in_flight=1), lambda: invoker)
    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer synthetic.jwt", "X-Agent-Contract-Version": "1"}

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
            existing = await app.state.limiter.try_acquire()
            second = await client.post(
                "/internal/v1/agent-runs:invoke",
                json=runtime_request(requestId="req-second"),
                headers=headers,
            )
            await existing.release()

    assert second.status_code == 429
    assert invoker.calls == 0
    assert app.state.limiter.in_flight == 0
