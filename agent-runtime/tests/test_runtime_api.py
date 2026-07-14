"""当前路由/计划运行时接口的集成测试。"""

import logging

from fastapi.testclient import TestClient

from app.contracts.models import ExecutablePlan, QueryAgentPlan, RouteDecision
from app.core.errors import RuntimeProviderError
from app.core.runtime_planning import get_plan_planner, get_route_planner
from app.core.settings import Settings, get_settings
from app.main import create_app


def _settings() -> Settings:
    return Settings(
        llm_base_url="https://test.example.com/v1",
        llm_api_key="test-api-key-for-testing",
        llm_model="test-model",
        llm_timeout_seconds=5.0,
        runtime_shared_key="test-shared-key-for-integration-test",
    )


def _metadata(operation: str) -> dict:
    return {
        "operation": operation,
        "providerAttempts": 1,
        "repairAttempts": 0,
        "repairDurationMs": 0,
        "totalDurationMs": 1,
        "terminationReason": "COMPLETED",
        "deadlineReached": False,
        "repairLimitReached": False,
    }


def _route_request() -> dict:
    return {
        "requestId": "flow-001",
        "contractVersion": "1.0.0",
        "message": "查询姓名包含张的员工",
        "history": [{"role": "USER", "content": "查询员工"}],
        "profileBehavior": {"instructions": ["信息不足时请求澄清"], "locale": "zh-CN"},
        "capabilities": [{
            "capabilityId": "query.search",
            "planKind": "QUERY",
            "description": "查询结构化业务记录",
            "applicability": ["用户要求检索记录"],
            "exclusions": ["不执行写操作"],
            "domainMode": "REQUIRED",
            "allowedDomains": ["employee"],
        }],
        "domains": [{
            "domain": "employee",
            "aliases": ["员工"],
            "description": "员工主数据",
        }],
        "absoluteDeadline": "2099-01-01T00:00:00Z",
        "repairLimit": 1,
    }


def _plan_request() -> dict:
    return {
        "requestId": "flow-001",
        "contractVersion": "1.0.0",
        "message": "查询姓名包含张的员工",
        "history": [{"role": "USER", "content": "查询员工"}],
        "capabilityId": "query.search",
        "planKind": "QUERY",
        "capability": _route_request()["capabilities"][0],
        "inputSchemaRef": "#/components/schemas/QueryAgentPlan",
        "domain": "employee",
        "domainSchema": {
            "domain": "employee",
            "fields": [{
                "field": "name",
                "aliases": ["姓名"],
                "type": "STRING",
                "operators": ["EQ", "CONTAINS"],
                "aggregateFunctions": [],
                "formatHint": None,
            }],
            "defaultSelectFields": ["name"],
            "sortFields": [],
            "defaultSize": 20,
            "maxSize": 100,
        },
        "contextViews": [],
        "absoluteDeadline": "2099-01-01T00:00:00Z",
        "repairLimit": 1,
    }


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"X-Agent-Runtime-Key": "test-shared-key-for-integration-test"}


class TestRoutePlanApi:
    def test_missing_key_returns_target_error_body(self):
        response = _client().post("/runtime/v1/route", json=_route_request())

        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "AUTHENTICATION_FAILED"
        assert body["metadata"]["operation"] == "ROUTE"
        assert body["metadata"]["terminationReason"] == "AUTHENTICATION_REJECTED"
        assert body["diagnosticId"]

    def test_route_returns_decision(self):
        class StubRoutePlanner:
            async def route(self, request):
                return RouteDecision(
                    outcomeType="DECISION",
                    requestId=request.request_id,
                    capabilityId="query.search",
                    domain="employee",
                    metadata=_metadata("ROUTE"),
                )

        client = _client()
        client.app.dependency_overrides[get_route_planner] = lambda: StubRoutePlanner()

        response = client.post("/runtime/v1/route", json=_route_request(), headers=_auth_headers())

        assert response.status_code == 200
        assert response.json()["outcomeType"] == "DECISION"
        assert response.json()["capabilityId"] == "query.search"

    def test_plan_returns_executable_query_plan(self):
        class StubPlanPlanner:
            async def plan(self, request):
                return ExecutablePlan(
                    outcomeType="EXECUTABLE",
                    requestId=request.request_id,
                    plan=QueryAgentPlan(
                        planKind="QUERY",
                        query={"filters": [], "selectFields": ["name"], "sorts": None, "page": 1, "size": 20},
                    ),
                    metadata=_metadata("PLAN"),
                )

        client = _client()
        client.app.dependency_overrides[get_plan_planner] = lambda: StubPlanPlanner()

        response = client.post("/runtime/v1/plan", json=_plan_request(), headers=_auth_headers())

        assert response.status_code == 200
        assert response.json()["outcomeType"] == "EXECUTABLE"
        assert response.json()["plan"]["planKind"] == "QUERY"

    def test_invalid_plan_request_returns_target_error_body(self):
        response = _client().post(
            "/runtime/v1/plan",
            json={"requestId": "flow-001"},
            headers=_auth_headers(),
        )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == "CONTRACT_INVALID"
        assert body["metadata"]["operation"] == "PLAN"
        assert body["metadata"]["terminationReason"] == "VALIDATION_REJECTED"

    def test_error_response_logs_internal_detail(self, caplog):
        class FailingPlanPlanner:
            async def plan(self, request):
                raise RuntimeProviderError("LLM provider error: APIConnectionError", request.request_id)

        client = _client()
        client.app.dependency_overrides[get_plan_planner] = lambda: FailingPlanPlanner()

        with caplog.at_level(logging.ERROR, logger="agent_runtime.errors"):
            response = client.post("/runtime/v1/plan", json=_plan_request(), headers=_auth_headers())

        assert response.status_code == 503
        assert response.json()["message"] == "LLM provider error"
        assert "LLM provider error: APIConnectionError" in caplog.text
        assert "diagnosticId=runtime-" in caplog.text
