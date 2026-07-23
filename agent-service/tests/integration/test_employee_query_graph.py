from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent_service.api.schemas import AgentExecuteRequest
from agent_service.capabilities.business.models import EmployeeQueryResponse
from agent_service.graph.builder import build_agent_graph
from agent_service.graph.types import GraphDependencies
from agent_service.observability.security_audit import BoundedLocalAuditSink
from agent_service.planning.planner import P1RuleBasedPlanner
from agent_service.security.models import AuthUpperBound, SubjectRef, TrustedIdentity
from agent_service.security.policy import PolicyProvider, load_policy


class EmployeeSpy:
    def __init__(self) -> None:
        self.calls = 0

    async def query(self, request, authorization, deadline):
        self.calls += 1
        return EmployeeQueryResponse.model_validate(
            {
                "requestId": request.request_id,
                "items": [{"position": "Engineer", "workBaseSi": "SHANGHAI"}],
                "page": {"number": 0, "size": 20},
                "total": 1,
                "observedAt": datetime.now(UTC),
                "sourceVersion": None,
            }
        )


def _input(message: str):
    now = datetime.now(UTC)
    return {
        "request_id": uuid4(),
        "request_input": AgentExecuteRequest(message=message),
        "deadline_at": now + timedelta(seconds=10),
        "trusted_identity": TrustedIdentity(
            subject=SubjectRef(type="USER", id="dylan"),
            tenantRef="tenant-main",
            identityEvidenceVersion="identity-1",
            validUntil=now + timedelta(minutes=1),
        ),
        "auth_upper_bound": AuthUpperBound(
            permissionCodes={"agent-admin"},
            allowedCapabilityIds={"query.search"},
            allowedDomains={"employee"},
            filterableFields={"employee": {"position", "workBaseSi"}},
            displayableFields={"employee": {"position", "workBaseSi"}},
            allowedOperators={
                "employee.position": {"EQ", "IN"},
                "employee.workBaseSi": {"EQ", "IN"},
            },
            allowedFunctions={},
            authEvidenceVersion="auth-1",
        ),
    }


@pytest.mark.asyncio
async def test_employee_query_executes_one_capability(settings):
    employee = EmployeeSpy()
    graph = build_agent_graph(
        GraphDependencies(
            settings=settings,
            policy_provider=PolicyProvider(load_policy(settings.policy_path)),
            planner=P1RuleBasedPlanner(),
            employee_client=employee,
            audit_sink=BoundedLocalAuditSink(),
        )
    )
    result = await graph.ainvoke(_input("查询上海员工职位"))
    assert employee.calls == 1
    assert result["secured_result"]["capability"] == "QUERY"


@pytest.mark.asyncio
async def test_clarify_path_has_zero_employee_calls(settings):
    employee = EmployeeSpy()
    graph = build_agent_graph(
        GraphDependencies(
            settings=settings,
            policy_provider=PolicyProvider(load_policy(settings.policy_path)),
            planner=P1RuleBasedPlanner(),
            employee_client=employee,
            audit_sink=BoundedLocalAuditSink(),
        )
    )
    result = await graph.ainvoke(_input("你好"))
    assert employee.calls == 0
    assert result["secured_result"]["type"] == "CLARIFICATION"
