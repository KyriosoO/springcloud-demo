from typing import Protocol

from agent_service.api.schemas import AgentExecuteRequest
from agent_service.planning.models import (
    Capability,
    ClarifyPlanCandidate,
    ExecutePlanCandidate,
    PlanCandidate,
    PlanDisposition,
)
from agent_service.security.models import PlanningAuthorization


class Planner(Protocol):
    async def plan(
        self, request: AgentExecuteRequest, authorization: PlanningAuthorization
    ) -> PlanCandidate: ...


class P1RuleBasedPlanner:
    """P1-only deterministic planner seam; real model enablement is deliberately excluded."""

    async def plan(
        self, request: AgentExecuteRequest, authorization: PlanningAuthorization
    ) -> PlanCandidate:
        message = request.message.lower()
        if "QUERY" not in authorization.capabilities or "EMPLOYEE" not in authorization.domains:
            return ClarifyPlanCandidate(
                schema_version="1",
                outcome=PlanDisposition.CLARIFY,
                reason_code="CAPABILITY_NOT_AVAILABLE",
            )
        if not any(marker in message for marker in ("员工", "employee", "职位", "工作地")):
            return ClarifyPlanCandidate(
                schema_version="1",
                outcome=PlanDisposition.CLARIFY,
                reason_code="EMPLOYEE_QUERY_REQUIRED",
                option_keys=("EMPLOYEE_QUERY",),
            )
        filters: list[dict[str, object]] = []
        if "上海" in request.message or "shanghai" in message:
            filters.append({"field": "workBaseSi", "operator": "EQ", "values": ["SHANGHAI"]})
        return ExecutePlanCandidate(
            schema_version="1",
            outcome=PlanDisposition.EXECUTE,
            capability=Capability.QUERY,
            domain="EMPLOYEE",
            intent="EMPLOYEE_QUERY",
            payload={
                "filters": filters,
                "select": ["position", "workBaseSi"],
                "sorts": [{"field": "position", "direction": "ASC"}],
                "page": {"number": 0, "size": 20},
            },
        )
