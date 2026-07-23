from typing import TypedDict
from datetime import datetime
from uuid import UUID

from agent_service.api.errors import AgentError
from agent_service.api.schemas import AgentExecuteRequest
from agent_service.capabilities.business.models import EmployeeQueryRequest, EmployeeQueryResponse
from agent_service.planning.models import PlanCandidate
from agent_service.security.models import (
    AuthUpperBound,
    EffectiveAuthorization,
    PlanningAuthorization,
    TrustedIdentity,
)


class AgentState(TypedDict, total=False):
    request_id: UUID
    request_input: AgentExecuteRequest
    deadline_at: datetime
    trusted_identity: TrustedIdentity
    auth_upper_bound: AuthUpperBound
    planning_authorization: PlanningAuthorization
    plan_candidate: PlanCandidate
    validated_query: EmployeeQueryRequest
    effective_authorization: EffectiveAuthorization
    employee_result: EmployeeQueryResponse
    error: AgentError
    safe_response: dict[str, object]
    secured_result: dict[str, object]
    safe_error: AgentError


class AgentGraphInput(TypedDict):
    request_id: UUID
    request_input: AgentExecuteRequest
    deadline_at: datetime
    trusted_identity: TrustedIdentity
    auth_upper_bound: AuthUpperBound


class AgentGraphOutput(TypedDict, total=False):
    request_id: UUID
    secured_result: dict[str, object]
    safe_error: AgentError
