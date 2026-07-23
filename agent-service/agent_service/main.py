from datetime import UTC, datetime
from uuid import uuid4
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from agent_service.api.routes import router
from agent_service.application.execution import AgentExecution
from agent_service.clients.auth import HttpAuthClient
from agent_service.clients.employee import HttpEmployeeClient
from agent_service.clients.service_token import CallTokenIssuer
from agent_service.config.models import Settings
from agent_service.config.security import load_security_settings, validate_security_settings
from agent_service.graph.builder import build_agent_graph
from agent_service.graph.types import GraphDependencies
from agent_service.observability.security_audit import BoundedLocalAuditSink
from agent_service.planning.planner import P1RuleBasedPlanner
from agent_service.security.policy import PolicyProvider, load_policy


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_security_settings()
    validate_security_settings(resolved)
    issuer = CallTokenIssuer(resolved)
    auth_client = HttpAuthClient(resolved, issuer)
    employee_client = HttpEmployeeClient(resolved, issuer)
    graph = build_agent_graph(
        GraphDependencies(
            settings=resolved,
            policy_provider=PolicyProvider(load_policy(resolved.policy_path)),
            planner=P1RuleBasedPlanner(),
            employee_client=employee_client,
            audit_sink=BoundedLocalAuditSink(),
        )
    )
    application = FastAPI(title="agent-service", version="0.1.0")
    application.state.agent_execution = AgentExecution(
        auth_client, graph, resolved.max_timeout_ms
    )

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid4()
        request.state.received_at = datetime.now(UTC)
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", uuid4())
        return JSONResponse(
            status_code=400,
            content={
                "requestId": str(request_id),
                "code": "INVALID_REQUEST",
                "message": "Request validation failed.",
                "retryable": False,
            },
        )

    application.include_router(router)
    return application


app = create_app()
