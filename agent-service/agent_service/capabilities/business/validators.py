from agent_service.api.errors import AgentError, AgentErrorCode, AgentFailure
from agent_service.capabilities.business.models import (
    EmployeeField,
    EmployeeQueryRequest,
    EmployeeQueryResponse,
    QueryOperator,
)
from agent_service.security.models import EffectiveAuthorization, PlanningAuthorization


def validate_employee_query_payload(
    payload: dict[str, object],
    authorization: PlanningAuthorization,
    request_id: object,
    deadline_at: object,
) -> EmployeeQueryRequest:
    try:
        request = EmployeeQueryRequest.model_validate(
            {"requestId": request_id, "deadlineAt": deadline_at, **payload}
        )
    except ValueError as exc:
        raise _invalid() from exc
    allowed_filter = authorization.filter_fields.get("EMPLOYEE", frozenset())
    allowed_display = authorization.display_fields.get("EMPLOYEE", frozenset())
    allowed_sort = authorization.sort_fields.get("EMPLOYEE", frozenset())
    if any(item.field.value not in allowed_filter for item in request.filters):
        raise _invalid()
    if any(item.value not in allowed_display for item in request.select):
        raise _invalid()
    if any(item.field.value not in allowed_sort for item in request.sorts):
        raise _invalid()
    for item in request.filters:
        if not item.values or len(item.values) > (1 if item.operator is QueryOperator.EQ else 50):
            raise _invalid()
        if any(not value.strip() or len(value) > 200 for value in item.values):
            raise _invalid()
    return request


def project_employee_result(
    response: EmployeeQueryResponse,
    authorization: EffectiveAuthorization,
    selected: tuple[EmployeeField, ...],
) -> dict[str, object]:
    del authorization
    result = response.model_dump(by_alias=True, mode="json")
    allowed = {field.value for field in selected}
    result["items"] = [
        {key: value for key, value in item.items() if key in allowed} for item in result["items"]
    ]
    return dict(result)


def _invalid() -> AgentFailure:
    return AgentFailure(
        AgentError(
            code=AgentErrorCode.MODEL_OUTPUT_INVALID,
            message="The proposed query is invalid.",
            reason_code="QUERY_CONTRACT_INVALID",
        )
    )
