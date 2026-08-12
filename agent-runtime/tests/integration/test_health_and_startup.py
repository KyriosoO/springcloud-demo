from __future__ import annotations

import httpx
import pytest

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from tests.api_helpers import CapturingInvoker


@pytest.mark.asyncio
async def test_liveness_is_independent_and_readiness_follows_lifespan() -> None:
    calls = 0

    def factory() -> CapturingInvoker:
        nonlocal calls
        calls += 1
        return CapturingInvoker()

    app = create_app(RuntimeHttpSettings(), factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://runtime") as client:
        before_live = await client.get("/internal/health/live")
        before_ready = await client.get("/internal/health/ready")
        async with app.router.lifespan_context(app):
            during_ready = await client.get("/internal/health/ready")
        after_ready = await client.get("/internal/health/ready")

    assert before_live.status_code == 200
    assert before_ready.status_code == 503
    assert during_ready.status_code == 200
    assert after_ready.status_code == 503
    assert calls == 1


@pytest.mark.asyncio
async def test_lifespan_closes_a_managed_runtime_once() -> None:
    class ManagedInvoker(CapturingInvoker):
        def __init__(self) -> None:
            super().__init__()
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1

    runtime = ManagedInvoker()
    app = create_app(RuntimeHttpSettings(), lambda: runtime)

    async with app.router.lifespan_context(app):
        assert app.state.ready is True

    assert bool(getattr(app.state, "ready")) is False
    assert getattr(app.state, "runtime") is None
    assert runtime.close_calls == 1
