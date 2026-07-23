from typing import Protocol

import httpx

from agent_service.api.errors import AgentError, AgentErrorCode, AgentFailure
from agent_service.clients.auth_models import AuthorizationResolveRequest, ResolvedAuthorization
from agent_service.clients.service_token import CallTokenIssuer
from agent_service.config.models import Settings
from agent_service.graph.deadline import Deadline


class AuthClient(Protocol):
    async def resolve_authorization(
        self, request: AuthorizationResolveRequest, deadline: Deadline
    ) -> ResolvedAuthorization: ...


class HttpAuthClient:
    def __init__(
        self,
        settings: Settings,
        token_issuer: CallTokenIssuer,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = str(settings.auth_authorization_url)
        self._token_issuer = token_issuer
        self._client = client or httpx.AsyncClient(follow_redirects=False)

    async def resolve_authorization(
        self, request: AuthorizationResolveRequest, deadline: Deadline
    ) -> ResolvedAuthorization:
        deadline.require_remaining()
        service_token = await self._token_issuer.issue_service_token(request.request_id, deadline)
        try:
            response = await self._client.post(
                self._url,
                json={
                    **request.model_dump(
                        by_alias=True, mode="json", exclude={"user_bearer_token"}
                    ),
                    "userBearerToken": request.user_bearer_token.get_secret_value(),
                },
                headers={"Authorization": f"Bearer {service_token}"},
                timeout=deadline.remaining_seconds(),
            )
        except httpx.TimeoutException as exc:
            raise _failure(AgentErrorCode.TIMEOUT, True) from exc
        except httpx.HTTPError as exc:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE, True) from exc
        if response.status_code == 401:
            raise _failure(AgentErrorCode.UNAUTHORIZED)
        if response.status_code == 403:
            raise _failure(AgentErrorCode.FORBIDDEN)
        if response.status_code != 200:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE, response.status_code >= 500)
        try:
            return ResolvedAuthorization.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise _failure(AgentErrorCode.UPSTREAM_UNAVAILABLE) from exc


def _failure(code: AgentErrorCode, retryable: bool = False) -> AgentFailure:
    return AgentFailure(AgentError(code=code, message="Authorization service failed.", retryable=retryable))
