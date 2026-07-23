from typing import Protocol

import httpx

from agent_service.api.errors import AgentError, AgentErrorCode, AgentFailure
from agent_service.capabilities.business.models import EmployeeQueryRequest, EmployeeQueryResponse
from agent_service.clients.service_token import CallTokenIssuer
from agent_service.config.models import Settings
from agent_service.graph.deadline import Deadline
from agent_service.security.models import EffectiveAuthorization


class EmployeeClient(Protocol):
    async def query(
        self,
        request: EmployeeQueryRequest,
        authorization: EffectiveAuthorization,
        deadline: Deadline,
    ) -> EmployeeQueryResponse: ...


class HttpEmployeeClient:
    def __init__(
        self,
        settings: Settings,
        token_issuer: CallTokenIssuer,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = str(settings.employee_query_url)
        self._issuer = token_issuer
        self._client = client or httpx.AsyncClient(follow_redirects=False)

    async def query(
        self,
        request: EmployeeQueryRequest,
        authorization: EffectiveAuthorization,
        deadline: Deadline,
    ) -> EmployeeQueryResponse:
        deadline.require_remaining()
        token = self._issuer.issue_employee_delegated_token(request, authorization, __import__(
            "datetime"
        ).datetime.now(__import__("datetime").UTC))
        try:
            response = await self._client.post(
                self._url,
                json=request.model_dump(by_alias=True, mode="json"),
                headers={"Authorization": f"Bearer {token}"},
                timeout=deadline.remaining_seconds(),
            )
        except httpx.TimeoutException as exc:
            raise _failure(AgentErrorCode.TIMEOUT, True) from exc
        except httpx.HTTPError as exc:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE, True) from exc
        if response.status_code == 403:
            raise _failure(AgentErrorCode.FORBIDDEN)
        if response.status_code != 200:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE, response.status_code >= 500)
        try:
            result = EmployeeQueryResponse.model_validate(response.json())
        except ValueError as exc:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE) from exc
        if result.request_id != request.request_id:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE)
        deadline.require_remaining()
        return result


def _failure(code: AgentErrorCode, retryable: bool = False) -> AgentFailure:
    return AgentFailure(AgentError(code=code, message="Employee service failed.", retryable=retryable))
