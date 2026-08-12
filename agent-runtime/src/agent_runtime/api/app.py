from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeAlias, cast

from fastapi import FastAPI, Header, Request

from agent_runtime.api.errors import RuntimeProtocolExceptionHandlers
from agent_runtime.api.health import router as health_router
from agent_runtime.api.ingress import RuntimeInvoker, invoke_agent
from agent_runtime.api.limits import MaxBodyBytesMiddleware, RuntimeRequestLimiter
from agent_runtime.api.models import RuntimeInvokeRequest, RuntimeInvokeResponse
from agent_runtime.api.settings import RuntimeHttpSettings

RuntimeFactory: TypeAlias = Callable[[], RuntimeInvoker | Awaitable[RuntimeInvoker]]


def create_app(settings: RuntimeHttpSettings, runtime_factory: RuntimeFactory) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        app.state.ready = False
        created = runtime_factory()
        runtime = await created if inspect.isawaitable(created) else created
        if not callable(getattr(runtime, "ainvoke", None)):
            raise TypeError("runtime.factory_invalid")
        app.state.runtime = runtime
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            app.state.runtime = None
            close = getattr(runtime, "aclose", None)
            if close is not None:
                closed = close()
                if not inspect.isawaitable(closed):
                    raise TypeError("runtime.aclose_invalid")
                await closed

    app = FastAPI(
        title="Single Agent Runtime Internal API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    limiter = RuntimeRequestLimiter(settings.max_in_flight)
    app.state.ready = False
    app.state.runtime = None
    app.state.limiter = limiter

    RuntimeProtocolExceptionHandlers.install(app)
    app.add_middleware(MaxBodyBytesMiddleware, max_body_bytes=settings.max_body_bytes)

    @app.post(
        "/internal/v1/agent-runs:invoke",
        response_model=RuntimeInvokeResponse,
        response_model_by_alias=True,
        status_code=200,
    )
    async def invoke_route(
        request: Request,
        payload: RuntimeInvokeRequest,
        authorization: str = Header(alias="Authorization"),
        x_agent_contract_version: str = Header(alias="X-Agent-Contract-Version"),
    ) -> RuntimeInvokeResponse:
        runtime = cast(RuntimeInvoker, request.app.state.runtime)
        if not request.app.state.ready or runtime is None:
            raise RuntimeError("runtime.not_ready")
        return await invoke_agent(
            request,
            payload,
            authorization,
            x_agent_contract_version,
            runtime,
            limiter,
            disconnect_poll_s=settings.disconnect_poll_ms / 1000,
        )

    app.include_router(health_router)

    return app
