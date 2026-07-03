"""当前路由/计划契约的运行时规划行为测试。"""

import pytest

from app.contracts.models import PlanRequest, RouteRequest
from app.core.errors import RuntimePlanError
from app.core.runtime_planning import RuntimePlanPlanner, RuntimeRoutePlanner, _parse_plan, _parse_route
from tests.test_runtime_api import _plan_request, _route_request


class StubLlmClient:
    def __init__(self, raw: str):
        self.raw = raw

    async def generate_plan_json(self, system_prompt, user_payload):
        return self.raw


@pytest.mark.asyncio
async def test_route_planner_maps_invalid_llm_output_to_contract_error():
    planner = RuntimeRoutePlanner(StubLlmClient("[]"))

    with pytest.raises(RuntimePlanError) as error:
        await planner.route(RouteRequest.model_validate(_route_request()))

    assert error.value.code == "CONTRACT_INVALID"
    assert error.value.request_id == "flow-001"


@pytest.mark.asyncio
async def test_plan_planner_maps_invalid_llm_output_to_contract_error():
    planner = RuntimePlanPlanner(StubLlmClient('{"outcomeType":"EXECUTABLE"}'))

    with pytest.raises(RuntimePlanError) as error:
        await planner.plan(PlanRequest.model_validate(_plan_request()))

    assert error.value.code == "CONTRACT_INVALID"
    assert error.value.request_id == "flow-001"


def test_route_request_id_mismatch_rejected():
    request = RouteRequest.model_validate(_route_request())

    with pytest.raises(ValueError, match="requestId mismatch"):
        _parse_route(
            '{"outcomeType":"DECISION","requestId":"other","capabilityId":"query.search",'
            '"domain":"employee","metadata":{"operation":"ROUTE","providerAttempts":1,'
            '"repairAttempts":0,"repairDurationMs":0,"totalDurationMs":1,'
            '"terminationReason":"COMPLETED","deadlineReached":false,"repairLimitReached":false}}',
            request,
        )


def test_route_can_return_query_preview_decision():
    request_payload = _route_request()
    request_payload["capabilities"] = [{
        "capabilityId": "query.preview",
        "planKind": "QUERY",
        "description": "预览结构化业务记录",
        "applicability": ["用户要求预览记录样例"],
        "exclusions": ["不执行写操作"],
        "domainMode": "REQUIRED",
        "allowedDomains": ["employee"],
    }]
    request = RouteRequest.model_validate(request_payload)

    outcome = _parse_route(
        '{"outcomeType":"DECISION","requestId":"flow-001","capabilityId":"query.preview",'
        '"domain":"employee","metadata":{"operation":"ROUTE","providerAttempts":1,'
        '"repairAttempts":0,"repairDurationMs":0,"totalDurationMs":1,'
        '"terminationReason":"COMPLETED","deadlineReached":false,"repairLimitReached":false}}',
        request,
    )

    assert outcome.capability_id == "query.preview"
    assert outcome.domain == "employee"


def test_plan_for_query_preview_still_returns_query_agent_plan():
    request_payload = _plan_request()
    request_payload["capabilityId"] = "query.preview"
    request_payload["capability"]["capabilityId"] = "query.preview"
    request = PlanRequest.model_validate(request_payload)

    outcome = _parse_plan(
        """
        {
          "outcomeType": "EXECUTABLE",
          "requestId": "flow-001",
          "plan": {
            "planKind": "QUERY",
            "query": {
              "filters": [{"field": "name", "operator": "CONTAINS", "value": "张"}],
              "selectFields": ["name"],
              "page": 1,
              "size": 5
            }
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
    assert outcome.plan.query.size == 5


def test_plan_clarification_is_typed_and_has_no_question():
    request = PlanRequest.model_validate(_plan_request())
    outcome = _parse_plan(
        """
        {
          "outcomeType": "CLARIFICATION",
          "requestId": "flow-001",
          "reasonCode": "VALUE_REQUIRED",
          "args": {"argType": "VALUE_CHOICES", "field": "name", "values": []},
          "metadata": {
            "operation": "PLAN",
            "providerAttempts": 1,
            "repairAttempts": 0,
            "repairDurationMs": 0,
            "totalDurationMs": 1,
            "terminationReason": "CLARIFICATION",
            "deadlineReached": false,
            "repairLimitReached": false
          }
        }
        """,
        request,
    )

    assert outcome.reason_code.value == "VALUE_REQUIRED"
    assert not hasattr(outcome, "question")
