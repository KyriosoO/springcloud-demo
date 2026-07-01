"""
Integration tests for the runtime API endpoint (multi-domain, with mocked dependencies).
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.settings import get_settings, Settings
from app.core.graph import get_plan_graph
from app.core.errors import RuntimeProviderError, RuntimeTimeoutError
from app.contracts.models import (
    AgentCapabilityDescriptor,
    AgentCapabilityExecutionMode,
    AgentCapabilityRiskLevel,
    AgentFieldType,
    AgentIntent,
    AgentOperator,
    AgentPlan,
    AgentQuerySpec,
    CapabilityContextSpec,
    CapabilityContractRef,
    CapabilityDomainScope,
    RuntimeDomainSchema,
    RuntimeFieldSchema,
)


def _employee_schema() -> dict:
    return {
        "domain": "employee",
        "aliases": ["员工", "employee"],
        "fields": [
            {"name": "chineseName", "aliases": ["姓名"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
            {"name": "memberNo", "aliases": ["工号"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
            {"name": "position", "aliases": ["岗位"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
            {"name": "contactAddress", "aliases": ["地址"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
            {"name": "idCardNo", "aliases": ["身份证号"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
            {"name": "phoneNo", "aliases": ["手机号"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
            {"name": "email", "aliases": ["邮箱"], "operators": ["EQ", "CONTAINS", "STARTS_WITH", "IN"], "type": "STRING"},
        ],
        "defaultSelectFields": ["chineseName", "memberNo", "position"],
        "maxFilters": 5,
        "defaultSize": 20,
        "maxSize": 100,
        "maxResultWindow": 10000,
    }


def _transaction_schema() -> dict:
    return {
        "domain": "transaction",
        "aliases": ["交易", "交易记录", "交易流水", "transaction"],
        "fields": [
            {"name": "transId", "aliases": ["交易号", "交易ID"], "operators": ["EQ"], "type": "STRING"},
            {"name": "transType", "aliases": ["交易类型", "类型"], "operators": ["EQ", "CONTAINS"], "type": "STRING"},
            {"name": "transDate", "aliases": ["交易时间", "交易日期"], "operators": ["GT", "LT"], "type": "INSTANT", "formatHint": "ISO-8601 datetime with timezone"},
            {"name": "amount", "aliases": ["金额", "交易金额"], "operators": ["EQ", "GT", "LT"], "type": "DECIMAL"},
        ],
        "defaultSelectFields": ["transId", "transType", "transDate", "amount"],
        "maxFilters": 5,
        "defaultSize": 20,
        "maxSize": 100,
        "maxResultWindow": 10000,
    }


def _query_search_capability() -> dict:
    """query.search capability descriptor，employee domain。"""
    return {
        "capabilityId": "query.search",
        "intent": "QUERY",
        "displayName": "Search records",
        "description": "Search records in a supported domain.",
        "domainScopes": [{"domain": "employee", "enabled": True, "reasonCode": None}],
        "riskLevel": "READ_ONLY",
        "executionMode": "IMMEDIATE",
        "inputContract": {"schema": "AgentPlan.query", "version": "1.0"},
        "outputContract": {"schema": "AgentQueryResult", "version": "1.0"},
        "context": {"reads": ["previousQuery"], "writes": ["RuntimeQueryContext"]},
        "permissions": ["domain", "field.filter", "field.display"],
        "enabled": True,
    }


def _clarify_capability() -> dict:
    """clarify.ask capability descriptor。"""
    return {
        "capabilityId": "clarify.ask",
        "intent": "CLARIFY",
        "displayName": "Ask for clarification",
        "description": "Ask the user for missing search criteria.",
        "domainScopes": [],
        "riskLevel": "READ_ONLY",
        "executionMode": "IMMEDIATE",
        "inputContract": {"schema": "ClarifySpec", "version": "1.0"},
        "outputContract": {"schema": "AgentChatResponse.CLARIFY", "version": "1.0"},
        "context": {"reads": [], "writes": []},
        "permissions": ["agent.access"],
        "enabled": True,
    }


def _aggregate_capability() -> dict:
    """aggregate.compute capability descriptor，transaction domain。"""
    return {
        "capabilityId": "aggregate.compute",
        "intent": "AGGREGATE",
        "displayName": "Compute aggregate",
        "description": "Compute aggregate metrics over records.",
        "domainScopes": [{"domain": "transaction", "enabled": True, "reasonCode": None}],
        "riskLevel": "READ_ONLY",
        "executionMode": "IMMEDIATE",
        "inputContract": {"schema": "AgentPlan.aggregate", "version": "1.0"},
        "outputContract": {"schema": "AgentAggregateResult", "version": "1.0"},
        "context": {"reads": [], "writes": ["RuntimeAggregateContext"]},
        "permissions": ["domain", "field.filter", "field.display"],
        "enabled": True,
    }


@pytest.fixture
def client(monkeypatch):
    """Override settings for test."""
    test_settings = Settings(
        llm_base_url="https://test.example.com/v1",
        llm_api_key="test-api-key-for-testing",
        llm_model="test-model",
        llm_timeout_seconds=5.0,
        runtime_shared_key="test-shared-key-for-integration-test",
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


class TestHealth:
    def test_health_returns_up(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "UP"}


class TestSettings:
    def test_route_confidence_threshold_uses_documented_env_name(self, monkeypatch):
        monkeypatch.setenv("AGENT_LLM_BASE_URL", "http://localhost")
        monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
        monkeypatch.setenv("AGENT_LLM_MODEL", "test-model")
        monkeypatch.setenv("AGENT_RUNTIME_SHARED_KEY", "test-key-at-least-16")
        monkeypatch.setenv("AGENT_ROUTE_CONFIDENCE_THRESHOLD", "0.9")
        monkeypatch.delenv("AGENT_AGENT_ROUTE_CONFIDENCE_THRESHOLD", raising=False)

        assert Settings().route_confidence_threshold == 0.9


class TestAuth:
    def test_missing_key_returns_401(self, client):
        resp = client.post("/runtime/v1/plans/generate", json={})
        assert resp.status_code == 401

    def test_wrong_key_returns_401(self, client):
        resp = client.post(
            "/runtime/v1/plans/generate",
            json={},
            headers={"X-Agent-Runtime-Key": "wrong-key-xxxxxxxx"},
        )
        assert resp.status_code == 401


class TestPlanGenerate:
    def _valid_request(self):
        return {
            "requestId": "test-001",
            "message": "查询岗位是HRM的员工",
            "domainSchemas": [_employee_schema()],
            "capabilities": [_query_search_capability(), _clarify_capability()],
        }

    def _multi_domain_request(self):
        return {
            "requestId": "test-001",
            "message": "查询金额大于100的交易",
            "domainSchemas": [_employee_schema(), _transaction_schema()],
            "capabilities": [_query_search_capability(), _clarify_capability(), _aggregate_capability()],
        }

    def _auth_headers(self):
        return {"X-Agent-Runtime-Key": "test-shared-key-for-integration-test"}

    def test_invalid_json_returns_400(self, client):
        resp = client.post(
            "/runtime/v1/plans/generate",
            content="not json",
            headers={**self._auth_headers(), "Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_unauthenticated_rejected(self, client):
        """Without shared key, entire endpoint returns 401."""
        resp = client.post("/runtime/v1/plans/generate", json=self._valid_request())
        assert resp.status_code == 401

    def test_valid_request_returns_same_request_id(self, client):
        class StubGraph:
            async def ainvoke(self, state):
                return {
                    **state,
                    "plan": AgentPlan(
                        plan_version="1.0",
                        intent=AgentIntent.QUERY,
                        domain="employee",
                        query=AgentQuerySpec(
                            filters=[{"field": "position", "operator": "EQ", "value": "HRM"}],
                            select_fields=["chineseName", "position"],
                            page=1,
                            size=20,
                        ),
                    ),
                }

        client.app.dependency_overrides[get_plan_graph] = lambda: StubGraph()
        resp = client.post(
            "/runtime/v1/plans/generate",
            json=self._valid_request(),
            headers=self._auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["requestId"] == "test-001"
        assert resp.json()["plan"]["intent"] == "QUERY"

    @pytest.mark.parametrize(
        ("error", "status", "code"),
        [
            (RuntimeProviderError("provider failed"), 502, "RUNTIME_PROVIDER_ERROR"),
            (RuntimeTimeoutError("provider timed out"), 504, "RUNTIME_TIMEOUT"),
        ],
    )
    def test_runtime_errors_include_request_id(self, client, error, status, code):
        class StubGraph:
            async def ainvoke(self, state):
                raise error

        client.app.dependency_overrides[get_plan_graph] = lambda: StubGraph()
        resp = client.post(
            "/runtime/v1/plans/generate",
            json=self._valid_request(),
            headers=self._auth_headers(),
        )

        assert resp.status_code == status
        assert resp.json() == {
            "code": code,
            "message": (
                "LLM provider error"
                if status == 502
                else "LLM call timed out"
            ),
            "requestId": "test-001",
        }

    def test_invalid_plan_error_includes_request_id(self, client):
        class StubGraph:
            async def ainvoke(self, state):
                return {**state, "route_validation_errors": ["invalid"]}

        client.app.dependency_overrides[get_plan_graph] = lambda: StubGraph()
        resp = client.post(
            "/runtime/v1/plans/generate",
            json=self._valid_request(),
            headers=self._auth_headers(),
        )

        assert resp.status_code == 422
        assert resp.json()["code"] == "RUNTIME_PLAN_INVALID"
        assert resp.json()["requestId"] == "test-001"

    def test_multi_domain_request_accepted(self, client):
        class StubGraph:
            async def ainvoke(self, state):
                return {
                    **state,
                    "plan": AgentPlan(
                        plan_version="1.0",
                        intent=AgentIntent.QUERY,
                        domain="transaction",
                        query=AgentQuerySpec(
                            filters=[{"field": "amount", "operator": "GT", "value": "100"}],
                            size=20,
                        ),
                    ),
                }

        client.app.dependency_overrides[get_plan_graph] = lambda: StubGraph()
        resp = client.post(
            "/runtime/v1/plans/generate",
            json=self._multi_domain_request(),
            headers=self._auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["plan"]["domain"] == "transaction"

    def test_empty_domain_schemas_rejected(self, client):
        resp = client.post(
            "/runtime/v1/plans/generate",
            json={
                "requestId": "test-001",
                "message": "test",
                "domainSchemas": [],
                "capabilities": [],
            },
            headers=self._auth_headers(),
        )
        assert resp.status_code == 400
