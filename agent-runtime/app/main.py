"""
FastAPI application factory.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.runtime_api import router as runtime_router
from app.core.errors import RuntimeAuthError, RuntimePlanError, RuntimeProviderError, RuntimeTimeoutError
from app.core.settings import get_settings


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例，注册路由和异常处理器。"""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期管理：启动时预加载 settings。"""
        settings_provider = app.dependency_overrides.get(get_settings, get_settings)
        settings_provider()
        yield

    app = FastAPI(
        title="Agent Runtime",
        description="P0 Employee QUERY/CLARIFY Plan Generator",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Health check
    @app.get("/health")
    async def health() -> JSONResponse:
        """健康检查端点。"""
        return JSONResponse({"status": "UP"})

    # Register routers
    app.include_router(runtime_router, prefix="/runtime/v1")

    # Exception handlers
    @app.exception_handler(RuntimePlanError)
    async def handle_plan_error(request: Request, exc: RuntimePlanError) -> JSONResponse:
        """捕获 RuntimePlanError，返回 422。"""
        return _error(422, exc.code, exc.safe_message, exc.request_id)

    @app.exception_handler(RuntimeAuthError)
    async def handle_auth_error(request: Request, exc: RuntimeAuthError) -> JSONResponse:
        """捕获 RuntimeAuthError，返回 401。"""
        return _error(401, "RUNTIME_AUTH_ERROR", "Authentication failed")

    @app.exception_handler(RuntimeProviderError)
    async def handle_provider_error(request: Request, exc: RuntimeProviderError) -> JSONResponse:
        """捕获 RuntimeProviderError，返回 502。"""
        return _error(502, "RUNTIME_PROVIDER_ERROR", "LLM provider error", exc.request_id)

    @app.exception_handler(RuntimeTimeoutError)
    async def handle_timeout_error(request: Request, exc: RuntimeTimeoutError) -> JSONResponse:
        """捕获 RuntimeTimeoutError，返回 504。"""
        return _error(504, "RUNTIME_TIMEOUT", "LLM call timed out", exc.request_id)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        """捕获 RequestValidationError，返回 400。"""
        return _error(400, "RUNTIME_INVALID_REQUEST", "Request validation failed")

    return app


def _error(
    status: int,
    code: str,
    message: str,
    request_id: str | None = None,
) -> JSONResponse:
    """构造标准错误响应的辅助函数。"""
    from app.contracts.models import RuntimeErrorResponse
    return JSONResponse(
        status_code=status,
        content=RuntimeErrorResponse(
            code=code,
            message=message,
            request_id=request_id,
        ).model_dump(by_alias=True),
    )


app = create_app()
