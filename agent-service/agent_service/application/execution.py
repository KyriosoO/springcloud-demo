from datetime import UTC, datetime
from uuid import UUID
from pydantic import SecretStr

from agent_service.api.errors import AgentFailure
from agent_service.api.schemas import (
    AgentErrorResponse,
    AgentExecuteRequest,
    AgentExecuteResponse,
)
from agent_service.clients.auth import AuthClient
from agent_service.clients.auth_models import AuthorizationResolveRequest
from agent_service.clients.auth_models import ResolvedAuthorization
from agent_service.graph.deadline import Deadline
from agent_service.graph.runtime import run_graph
from agent_service.graph.state import AgentGraphInput, AgentGraphOutput


class AgentExecution:
    def __init__(self, auth_client: AuthClient, graph: object, maximum_timeout_ms: int) -> None:
        self._auth_client = auth_client
        self._graph = graph
        self._maximum_timeout_ms = maximum_timeout_ms

    async def execute(
        self,
        request_id: UUID,
        received_at: datetime,
        request: AgentExecuteRequest,
        bearer_token: str,
    ) -> AgentExecuteResponse | AgentErrorResponse:
        timeout_ms = request.timeout_ms or min(10000, self._maximum_timeout_ms)
        deadline = Deadline.from_timeout(received_at, timeout_ms, self._maximum_timeout_ms)
        try:
            resolved = await self._auth_client.resolve_authorization(
                AuthorizationResolveRequest(
                    requestId=request_id,
                    userBearerToken=SecretStr(bearer_token),
                    requestedAt=received_at.astimezone(UTC),
                    deadline=deadline.at,
                ),
                deadline,
            )
            graph_output = await run_graph(
                self._graph,
                self.to_initial_state(request_id, request, resolved, deadline),
            )
            return self.to_response(graph_output)
        except AgentFailure as exc:
            return AgentErrorResponse(
                requestId=request_id,
                code=exc.error.code,
                message=exc.error.message,
                retryable=exc.error.retryable,
            )

    def to_initial_state(
        self,
        request_id: UUID,
        request: AgentExecuteRequest,
        resolved: ResolvedAuthorization,
        deadline: Deadline,
    ) -> AgentGraphInput:
        return AgentGraphInput(
            request_id=request_id,
            request_input=request,
            deadline_at=deadline.at,
            trusted_identity=resolved.trusted_identity,
            auth_upper_bound=resolved.auth_upper_bound,
        )

    def to_response(
        self, graph_output: AgentGraphOutput
    ) -> AgentExecuteResponse | AgentErrorResponse:
        if "safe_error" in graph_output:
            error = graph_output["safe_error"]
            return AgentErrorResponse(
                requestId=graph_output["request_id"],
                code=error.code,
                message=error.message,
                retryable=error.retryable,
            )
        result = graph_output["secured_result"]
        raw_citations = result.get("citations", ())
        raw_warnings = result.get("warnings", ())
        citations = tuple(raw_citations) if isinstance(raw_citations, (list, tuple)) else ()
        warnings = (
            tuple(str(value) for value in raw_warnings)
            if isinstance(raw_warnings, (list, tuple))
            else ()
        )
        return AgentExecuteResponse(
            requestId=graph_output["request_id"],
            type=str(result["type"]),
            capability=str(result["capability"]) if result.get("capability") else None,
            data=result.get("data"),
            citations=citations,
            warnings=warnings,
        )
