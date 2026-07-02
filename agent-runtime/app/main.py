"""应用工厂。"""

from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.runtime_api import router as runtime_router
from app.core.errors import RuntimeAuthError, RuntimePlanError, RuntimeProviderError, RuntimeTimeoutError
from app.core.settings import get_settings


def create_app() -> FastAPI:
    """创建应用实例，注册路由和异常处理器。"""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期管理：启动时预加载配置。"""
        settings_provider = app.dependency_overrides.get(get_settings, get_settings)
        settings_provider()
        yield

    app = FastAPI(
        title="Agent Runtime",
        description="Agent Runtime Route/Plan Generator",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 健康检查。
    @app.get("/health")
    async def health() -> JSONResponse:
        """健康检查端点。"""
        return JSONResponse({"status": "UP"})

    # 注册路由。
    app.include_router(runtime_router, prefix="/runtime/v1")

    # 注册异常处理器。
    @app.exception_handler(RuntimePlanError)
    async def handle_plan_error(request: Request, exc: RuntimePlanError) -> JSONResponse:
        """捕获规划异常，返回 422。"""
        return _error(request, 422, exc.code, exc.safe_message, exc.request_id)

    @app.exception_handler(RuntimeAuthError)
    async def handle_auth_error(request: Request, exc: RuntimeAuthError) -> JSONResponse:
        """捕获认证异常，返回 401。"""
        return _error(request, 401, "AUTHENTICATION_FAILED", "Authentication failed")

    @app.exception_handler(RuntimeProviderError)
    async def handle_provider_error(request: Request, exc: RuntimeProviderError) -> JSONResponse:
        """捕获提供方异常，返回 502。"""
        return _error(request, 503, "PROVIDER_UNAVAILABLE", "LLM provider error", exc.request_id)

    @app.exception_handler(RuntimeTimeoutError)
    async def handle_timeout_error(request: Request, exc: RuntimeTimeoutError) -> JSONResponse:
        """捕获超时异常，返回 504。"""
        return _error(request, 504, "DEADLINE_EXCEEDED", "LLM call timed out", exc.request_id)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        """捕获请求校验异常，返回 400。"""
        return _error(request, 400, "CONTRACT_INVALID", "Request validation failed")

    return app


def _error(
    request: Request,
    status: int,
    code: str,
    message: str,
    request_id: str | None = None,
) -> JSONResponse:
    """构造标准错误响应的辅助函数。"""
    from app.contracts.models import RuntimeErrorResponse, RuntimeOperationMetadata

    operation = "PLAN" if request.url.path.endswith("/plan") else "ROUTE"
    termination = {
        "CONTRACT_INVALID": "VALIDATION_REJECTED",
        "AUTHENTICATION_FAILED": "AUTHENTICATION_REJECTED",
        "PROVIDER_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
        "DEADLINE_EXCEEDED": "DEADLINE_EXCEEDED",
        "OUTPUT_REPAIR_EXHAUSTED": "REPAIR_EXHAUSTED",
        "INTERNAL_ERROR": "INTERNAL_ERROR",
    }.get(code, "INTERNAL_ERROR")
    return JSONResponse(
        status_code=status,
        content=RuntimeErrorResponse(
            code=code,
            message=message,
            request_id=request_id,
            diagnosticId="runtime-" + uuid.uuid4().hex,
            metadata=RuntimeOperationMetadata(
                operation=operation,
                providerAttempts=0,
                repairAttempts=0,
                repairDurationMs=0,
                totalDurationMs=0,
                terminationReason=termination,
                deadlineReached=code == "DEADLINE_EXCEEDED",
                repairLimitReached=code == "OUTPUT_REPAIR_EXHAUSTED",
            ),
        ).model_dump(by_alias=True),
    )


app = create_app()
