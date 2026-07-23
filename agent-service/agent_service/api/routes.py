from typing import Annotated
from typing import cast

from fastapi import APIRouter, Depends, Header, Request, Response

from agent_service.api.errors import AgentErrorCode
from agent_service.api.schemas import AgentErrorResponse, AgentExecuteRequest, AgentExecuteResponse
from agent_service.application.execution import AgentExecution

router = APIRouter()


def get_agent_execution(request: Request) -> AgentExecution:
    return cast(AgentExecution, request.app.state.agent_execution)


@router.post(
    "/api/agent/v1/execute",
    response_model=AgentExecuteResponse | AgentErrorResponse,
)
async def execute_agent(
    http_request: Request,
    http_response: Response,
    body: AgentExecuteRequest,
    authorization: Annotated[str | None, Header()] = None,
    execution: AgentExecution = Depends(get_agent_execution),
) -> AgentExecuteResponse | AgentErrorResponse:
    request_id = http_request.state.request_id
    if authorization is None or not authorization.lower().startswith("bearer "):
        http_response.status_code = 401
        return AgentErrorResponse(
            requestId=request_id,
            code=AgentErrorCode.UNAUTHORIZED,
            message="Authentication is required.",
            retryable=False,
        )
    bearer = authorization[7:].strip()
    if not bearer:
        http_response.status_code = 401
        return AgentErrorResponse(
            requestId=request_id,
            code=AgentErrorCode.UNAUTHORIZED,
            message="Authentication is required.",
            retryable=False,
        )
    result = await execution.execute(
        request_id,
        http_request.state.received_at,
        body,
        bearer,
    )
    if isinstance(result, AgentErrorResponse):
        http_response.status_code = {
            "INVALID_REQUEST": 400,
            "UNAUTHORIZED": 401,
            "FORBIDDEN": 403,
            "UNSUPPORTED": 422,
            "TIMEOUT": 504,
            "UPSTREAM_UNAVAILABLE": 503,
        }.get(result.code, 500)
    return result
