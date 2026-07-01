"""
Tests for LangGraph plan-generation graph with route/query split (mocked LLM).
"""
import json

import pytest

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
    PlanGenerateRequest,
    RuntimeDomainSchema,
    RuntimeFieldSchema,
)
from app.core.graph import (
    PlanGraphState,
    build_plan_graph,
    validate_route_node,
    validate_query_node,
    route_after_validate_route,
    route_after_validate_query,
    clarify_end_node,
)
from app.core.route_models import RouteDecision


def _employee_schema() -> RuntimeDomainSchema:
    fields = [
        RuntimeFieldSchema(name="chineseName", aliases=["姓名", "中文名"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="memberNo", aliases=["工号"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="position", aliases=["岗位"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="contactAddress", aliases=["地址"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
    ]
    return RuntimeDomainSchema(
        domain="employee",
        aliases=["员工", "employee"],
        fields=fields,
        default_select_fields=["chineseName", "memberNo", "position"],
        max_filters=5,
        default_size=20,
        max_size=100,
        max_result_window=10000,
    )


def _transaction_schema() -> RuntimeDomainSchema:
    fields = [
        RuntimeFieldSchema(name="amount", aliases=["金额"], operators=[AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT], type=AgentFieldType.DECIMAL),
    ]
    return RuntimeDomainSchema(
        domain="transaction",
        aliases=["交易", "交易记录"],
        fields=fields,
        default_select_fields=["amount"],
        max_filters=5,
        default_size=20,
        max_size=100,
        max_result_window=10000,
    )


def _make_request(message: str = "test") -> PlanGenerateRequest:
    return PlanGenerateRequest(
        request_id="test-001",
        message=message,
        domain_schemas=[_employee_schema()],
        capabilities=_standard_capabilities(),
    )


def _make_multi_request(message: str = "test") -> PlanGenerateRequest:
    return PlanGenerateRequest(
        request_id="test-001",
        message=message,
        domain_schemas=[_employee_schema(), _transaction_schema()],
        capabilities=_standard_capabilities(),
    )


def _query_search_capability() -> AgentCapabilityDescriptor:
    """创建一个 query.search capability descriptor，employee domain。"""
    scope = CapabilityDomainScope(domain="employee", enabled=True)
    return AgentCapabilityDescriptor(
        capability_id="query.search",
        intent=AgentIntent.QUERY,
        display_name="Search records",
        description="Search records in a supported domain.",
        domain_scopes=[scope],
        risk_level=AgentCapabilityRiskLevel.read_only,
        execution_mode=AgentCapabilityExecutionMode.immediate,
        input_contract=CapabilityContractRef(schema="AgentPlan.query", version="1.0"),
        output_contract=CapabilityContractRef(schema="AgentQueryResult", version="1.0"),
        context=CapabilityContextSpec(reads=["previousQuery"], writes=["RuntimeQueryContext"]),
        permissions=["domain", "field.filter", "field.display"],
        enabled=True,
    )


def _clarify_capability() -> AgentCapabilityDescriptor:
    """创建一个 clarify.ask capability descriptor。"""
    return AgentCapabilityDescriptor(
        capability_id="clarify.ask",
        intent=AgentIntent.CLARIFY,
        display_name="Ask for clarification",
        description="Ask the user for missing search criteria.",
        domain_scopes=[],
        risk_level=AgentCapabilityRiskLevel.read_only,
        execution_mode=AgentCapabilityExecutionMode.immediate,
        input_contract=CapabilityContractRef(schema="ClarifySpec", version="1.0"),
        output_contract=CapabilityContractRef(schema="AgentChatResponse.CLARIFY", version="1.0"),
        context=CapabilityContextSpec(reads=[], writes=[]),
        permissions=["agent.access"],
        enabled=True,
    )


def _aggregate_capability() -> AgentCapabilityDescriptor:
    """创建一个 aggregate.compute capability descriptor，transaction domain。"""
    scope = CapabilityDomainScope(domain="transaction", enabled=True)
    return AgentCapabilityDescriptor(
        capability_id="aggregate.compute",
        intent=AgentIntent.AGGREGATE,
        display_name="Compute aggregate",
        description="Compute aggregate metrics over records.",
        domain_scopes=[scope],
        risk_level=AgentCapabilityRiskLevel.read_only,
        execution_mode=AgentCapabilityExecutionMode.immediate,
        input_contract=CapabilityContractRef(schema="AgentPlan.aggregate", version="1.0"),
        output_contract=CapabilityContractRef(schema="AgentAggregateResult", version="1.0"),
        context=CapabilityContextSpec(reads=[], writes=["RuntimeAggregateContext"]),
        permissions=["domain", "field.filter", "field.display"],
        enabled=True,
    )


def _standard_capabilities() -> list:
    """返回标准的 capabilities 列表（query.search + clarify.ask + aggregate.compute）。"""
    return [_query_search_capability(), _clarify_capability(), _aggregate_capability()]


def _valid_route_query_output() -> str:
    return json.dumps({
        "intent": "QUERY",
        "domain": "employee",
        "question": None,
        "confidence": 0.92,
        "reason": "User asks to query position.",
    })

def _valid_route_clarify_output() -> str:
    return json.dumps({
        "intent": "CLARIFY",
        "domain": "employee",
        "question": "请提供更多查询条件。",
        "confidence": 0.88,
        "reason": "No criteria.",
    })

def _valid_query_plan_output() -> str:
    return json.dumps({
        "planVersion": "1.0",
        "intent": "QUERY",
        "domain": "employee",
        "query": {
            "filters": [{"field": "position", "operator": "EQ", "value": "HRM"}],
            "selectFields": ["chineseName", "memberNo", "position"],
            "page": 1,
            "size": 20,
        },
        "clarify": None,
    })

def _invalid_json_output() -> str:
    return "not valid json"


class TestRouteStageNodes:
    """Test route stage nodes with mock LLM outputs."""

    @pytest.mark.asyncio
    async def test_valid_route_query_passes(self, monkeypatch):
        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: None)
        monkeypatch.setattr("app.core.graph.get_settings", lambda: _mock_settings())
        state: PlanGraphState = {
            "request": _make_request("查询岗位是HRM的员工"),
            "route_raw_output": _valid_route_query_output(),
            "route_repair_attempted": False,
        }
        result = await validate_route_node(state)
        assert result.get("route_validation_errors") == []
        assert result["route_decision"].intent == AgentIntent.QUERY

    @pytest.mark.asyncio
    async def test_valid_route_clarify_passes(self, monkeypatch):
        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: None)
        monkeypatch.setattr("app.core.graph.get_settings", lambda: _mock_settings())
        state: PlanGraphState = {
            "request": _make_request("帮我查员工"),
            "route_raw_output": _valid_route_clarify_output(),
            "route_repair_attempted": False,
        }
        result = await validate_route_node(state)
        assert result.get("route_validation_errors") == []
        assert result["route_decision"].intent == AgentIntent.CLARIFY

    @pytest.mark.asyncio
    async def test_low_confidence_downgrades_to_clarify(self, monkeypatch):
        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: None)
        monkeypatch.setattr("app.core.graph.get_settings", lambda: _mock_settings(threshold=1.0))
        state: PlanGraphState = {
            "request": _make_request("test"),
            "route_raw_output": _valid_route_query_output(),
            "route_repair_attempted": False,
        }
        result = await validate_route_node(state)
        assert result.get("route_validation_errors") == []
        assert result["route_decision"].intent == AgentIntent.CLARIFY
        assert result["route_decision"].domain == "employee"
        assert result["route_decision"].question
        assert route_after_validate_route(result) == "clarify_end"


class TestQueryStageNodes:
    """Test query stage nodes with mock LLM outputs."""

    @pytest.mark.asyncio
    async def test_valid_query_plan_passes(self, monkeypatch):
        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: None)
        route = RouteDecision(intent=AgentIntent.QUERY, domain="employee", confidence=0.92)
        state: PlanGraphState = {
            "request": _make_request(),
            "route_decision": route,
            "query_raw_output": _valid_query_plan_output(),
            "query_repair_attempted": False,
        }
        result = await validate_query_node(state)
        assert result.get("query_validation_errors") == []
        assert isinstance(result.get("query_plan"), AgentPlan)

    @pytest.mark.asyncio
    async def test_query_domain_mismatch_fails(self, monkeypatch):
        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: None)
        route = RouteDecision(intent=AgentIntent.QUERY, domain="transaction", confidence=0.92)
        state: PlanGraphState = {
            "request": _make_multi_request(),
            "route_decision": route,
            "query_raw_output": _valid_query_plan_output(),
            "query_repair_attempted": False,
        }
        result = await validate_query_node(state)
        assert len(result.get("query_validation_errors", [])) > 0


class TestRouteGraphRouting:
    """Test route-graph routing logic."""

    def test_query_routes_to_query(self):
        route = RouteDecision(intent=AgentIntent.QUERY, domain="employee", confidence=0.92)
        state: PlanGraphState = {
            "request": _make_request(),
            "route_decision": route,
            "route_validation_errors": [],
            "route_repair_attempted": False,
        }
        assert route_after_validate_route(state) == "query"

    def test_clarify_routes_to_clarify_end(self):
        route = RouteDecision(intent=AgentIntent.CLARIFY, domain="employee",
                              question="请提供条件", confidence=0.88)
        state: PlanGraphState = {
            "request": _make_request(),
            "route_decision": route,
            "route_validation_errors": [],
            "route_repair_attempted": False,
        }
        assert route_after_validate_route(state) == "clarify_end"

    def test_route_errors_routes_to_repair(self):
        state: PlanGraphState = {
            "request": _make_request(),
            "route_validation_errors": ["bad"],
            "route_repair_attempted": False,
        }
        assert route_after_validate_route(state) == "route_repair"

    def test_route_errors_after_repair_routes_to_error(self):
        state: PlanGraphState = {
            "request": _make_request(),
            "route_validation_errors": ["still bad"],
            "route_repair_attempted": True,
        }
        assert route_after_validate_route(state) == "error"

    def test_unknown_future_route_intent_routes_to_error(self):
        state: PlanGraphState = {
            "request": _make_request(),
            "route_validation_errors": [],
            "route_repair_attempted": False,
        }
        assert route_after_validate_route(state) == "error"

    def test_query_valid_routes_to_end(self):
        state: PlanGraphState = {
            "request": _make_request(),
            "query_validation_errors": [],
            "query_repair_attempted": False,
        }
        assert route_after_validate_query(state) == "end"

    def test_query_errors_routes_to_repair(self):
        state: PlanGraphState = {
            "request": _make_request(),
            "query_validation_errors": ["bad"],
            "query_repair_attempted": False,
        }
        assert route_after_validate_query(state) == "query_repair"


class TestClarifyEndNode:
    @pytest.mark.asyncio
    async def test_clarify_end_builds_plan(self):
        route = RouteDecision(intent=AgentIntent.CLARIFY, domain="employee",
                              question="请提供条件", confidence=0.88)
        state: PlanGraphState = {
            "request": _make_request("帮我查员工"),
            "route_decision": route,
        }
        result = await clarify_end_node(state)
        assert result["plan"].intent == AgentIntent.CLARIFY
        assert result["plan"].clarify.question == "请提供条件"


class TestCompiledGraph:
    @pytest.mark.asyncio
    async def test_route_repairs_once_then_query_succeeds(self, monkeypatch):
        """Route fails first time, repair succeeds, then query succeeds."""
        call_count = [0]
        class StubClient:
            async def generate_plan_json(self, system_prompt, user_payload):
                call_count[0] += 1
                if call_count[0] == 1:
                    return _invalid_json_output()
                elif call_count[0] == 2:
                    return _valid_route_query_output()
                else:
                    return _valid_query_plan_output()

            async def repair_json(self, repair_system_prompt, invalid_output, validation_errors, user_payload):
                call_count[0] += 1
                return _valid_route_query_output()

        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: StubClient())
        monkeypatch.setattr("app.core.graph.get_settings", lambda: _mock_settings())
        final_state = await build_plan_graph().ainvoke({
            "request": _make_request("岗位是 HRM"),
            "route_repair_attempted": False,
            "query_repair_attempted": False,
        })
        assert "plan" in final_state, f"Expected 'plan' in final_state, got keys: {list(final_state.keys())}"
        assert final_state["plan"].intent == AgentIntent.QUERY

    @pytest.mark.asyncio
    async def test_low_confidence_query_route_ends_as_clarify(self, monkeypatch):
        class StubClient:
            async def generate_plan_json(self, system_prompt, user_payload):
                return _valid_route_query_output()

            async def repair_json(self, repair_system_prompt, invalid_output, validation_errors, user_payload):
                raise AssertionError("low-confidence route should not enter repair")

        monkeypatch.setattr("app.core.graph.get_llm_client", lambda: StubClient())
        monkeypatch.setattr("app.core.graph.get_settings", lambda: _mock_settings(threshold=1.0))
        final_state = await build_plan_graph().ainvoke({
            "request": _make_request("岗位是 HRM"),
            "route_repair_attempted": False,
            "query_repair_attempted": False,
        })

        assert final_state["plan"].intent == AgentIntent.CLARIFY
        assert final_state["plan"].domain == "employee"
        assert final_state["plan"].clarify.question


def _mock_settings(threshold: float = 0.6):
    from app.core.settings import Settings
    from pydantic import SecretStr
    return Settings(
        llm_base_url="http://localhost",
        llm_api_key=SecretStr("test-key"),
        llm_model="test-model",
        route_confidence_threshold=threshold,
        runtime_shared_key=SecretStr("test-key-at-least-16"),
    )
