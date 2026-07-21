"""当前路由/计划规划解析测试。"""

from app.core.runtime_planning import _parse_plan, _parse_route
from tests.test_runtime_api import _plan_request, _route_request
from app.contracts.models import PlanRequest, RouteRequest


def test_parse_target_route_decision():
    request = RouteRequest.model_validate(_route_request())
    outcome = _parse_route(
        """
        {
          "outcomeType": "DECISION",
          "requestId": "flow-001",
          "capabilityId": "query.search",
          "domain": "employee",
          "metadata": {
            "operation": "ROUTE",
            "providerAttempts": 1,
            "repairAttempts": 0,
            "repairDurationMs": 0,
            "totalDurationMs": 1,
            "terminationReason": "COMPLETED",
            "deadlineReached": false,
            "repairLimitReached": false
          }
        }
        """,
        request,
    )

    assert outcome.capability_id == "query.search"
    assert outcome.domain == "employee"


def test_parse_target_plan_executable():
    request = PlanRequest.model_validate(_plan_request())
    outcome = _parse_plan(
        """
        {
          "outcomeType": "EXECUTABLE",
          "requestId": "flow-001",
          "plan": {
            "planKind": "QUERY",
            "query": {"filters": [], "selectFields": ["name"], "page": 1, "size": 20}
          },
          "metadata": {
            "operation": "PLAN",
            "providerAttempts": 1,
            "repairAttempts": 0,
            "repairDurationMs": 0,
            "totalDurationMs": 1,
            "terminationReason": "COMPLETED",
            "deadlineReached": false,
            "repairLimitReached": false
          }
        }
        """,
        request,
    )

    assert outcome.plan.plan_kind == "QUERY"
    assert outcome.metadata.operation.value == "PLAN"
