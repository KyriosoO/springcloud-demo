"""
Tests for Pydantic contract models (multi-domain).
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.models import (
    AgentCapabilityDescriptor,
    AgentCapabilityExecutionMode,
    AgentCapabilityRiskLevel,
    AgentFieldType,
    AgentIntent,
    AgentOperator,
    AgentPlan,
    AgentQuerySpec,
    AgentAggregateSpec,
    AggregateFunction,
    CapabilityContextSpec,
    CapabilityContractRef,
    CapabilityDomainScope,
    ClarifySpec,
    PlanGenerateRequest,
    PlanGenerateResponse,
    RuntimeDomainSchema,
    RuntimeFieldSchema,
    RuntimeTurn,
)


def _employee_schema() -> RuntimeDomainSchema:
    fields = [
        RuntimeFieldSchema(name="chineseName", aliases=["姓名", "中文名"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="memberNo", aliases=["工号"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="position", aliases=["岗位"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="contactAddress", aliases=["地址"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="idCardNo", aliases=["身份证号"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="phoneNo", aliases=["手机号"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="email", aliases=["邮箱"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN], type=AgentFieldType.STRING),
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
        RuntimeFieldSchema(name="transId", aliases=["交易号", "交易ID"], operators=[AgentOperator.EQ], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="transType", aliases=["交易类型", "类型"], operators=[AgentOperator.EQ, AgentOperator.CONTAINS], type=AgentFieldType.STRING),
        RuntimeFieldSchema(name="transDate", aliases=["交易时间", "交易日期"], operators=[AgentOperator.GT, AgentOperator.LT], type=AgentFieldType.INSTANT, format_hint="ISO-8601 datetime with timezone",
                           supported_aggregate_functions=[]),
        RuntimeFieldSchema(name="amount", aliases=["金额", "交易金额"], operators=[AgentOperator.EQ, AgentOperator.GT, AgentOperator.LT], type=AgentFieldType.DECIMAL,
                           supported_aggregate_functions=[AggregateFunction.SUM, AggregateFunction.AVG, AggregateFunction.MIN, AggregateFunction.MAX]),
    ]
    return RuntimeDomainSchema(
        domain="transaction",
        aliases=["交易", "交易记录", "交易流水", "transaction"],
        fields=fields,
        default_select_fields=["transId", "transType", "transDate", "amount"],
        max_filters=5,
        default_size=20,
        max_size=100,
        max_result_window=10000,
    )


def _fixture_path(filename: str) -> Path:
    """Resolve the golden fixture from the agent-api contracts directory."""
    root = Path(__file__).parent.parent.parent
    return root / "agent-api" / "src" / "main" / "resources" / "contracts" / filename


def _query_search_capability() -> AgentCapabilityDescriptor:
    """query.search capability descriptor，employee domain。"""
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
    """clarify.ask capability descriptor。"""
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


class TestQueryPlanFixture:
    """QUERY plan fixture tests."""

    def test_query_plan_from_fixture(self):
        path = _fixture_path("query-plan-v1.json")
        assert path.exists(), f"Fixture not found: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        resp = PlanGenerateResponse.model_validate(data)
        assert resp.request_id == "turn-001"
        plan = resp.plan
        assert plan.plan_version == "1.0"
        assert plan.intent == AgentIntent.QUERY
        assert plan.domain == "employee"
        assert plan.query is not None
        assert plan.clarify is None
        assert len(plan.query.filters) == 1
        f = plan.query.filters[0]
        assert f.field == "position"
        assert f.operator == AgentOperator.EQ
        assert f.value == "HRM"
        assert plan.query.select_fields == ["chineseName", "memberNo", "position"]
        assert plan.query.page == 1
        assert plan.query.size == 20

    def test_serialize_to_java_compatible(self):
        path = _fixture_path("query-plan-v1.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        resp = PlanGenerateResponse.model_validate(data)
        dumped = json.loads(resp.model_dump_json(by_alias=True))
        assert dumped["requestId"] == "turn-001"
        assert dumped["plan"]["intent"] == "QUERY"
        assert dumped["plan"]["query"]["filters"][0]["field"] == "position"


class TestClarifyPlanFixture:
    """CLARIFY plan fixture tests."""

    def test_clarify_plan_from_fixture(self):
        path = _fixture_path("clarify-plan-v1.json")
        assert path.exists(), f"Fixture not found: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        resp = PlanGenerateResponse.model_validate(data)
        assert resp.request_id == "turn-001"
        plan = resp.plan
        assert plan.intent == AgentIntent.CLARIFY
        assert plan.query is None
        assert plan.clarify is not None
        assert plan.clarify.question == "请提供姓名、工号或岗位等查询条件。"


class TestAggregatePlanFixture:
    """AGGREGATE plan fixture tests."""

    def test_aggregate_plan_from_fixture(self):
        path = _fixture_path("aggregate-plan-v1.json")
        assert path.exists(), f"Fixture not found: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        resp = PlanGenerateResponse.model_validate(data)
        assert resp.request_id == "turn-001"
        plan = resp.plan
        assert plan.plan_version == "1.0"
        assert plan.intent == AgentIntent.AGGREGATE
        assert plan.domain == "transaction"
        assert plan.query is None
        assert plan.clarify is None
        assert plan.aggregate is not None
        assert plan.aggregate.metrics[0].function == AggregateFunction.SUM
        assert plan.aggregate.metrics[0].field == "amount"
        assert plan.aggregate.metrics[1].function == AggregateFunction.COUNT
        assert plan.aggregate.metrics[1].field is None
        assert plan.aggregate.group_by_fields == ["transType"]
        assert plan.aggregate.order_by[0].field == "totalAmount"
        assert plan.aggregate.max_rows == 20


class TestUnknownFieldRejection:
    """Verify extra=forbid behavior."""

    def test_unknown_intent_rejected(self):
        with pytest.raises(ValidationError):
            AgentPlan.model_validate({
                "planVersion": "1.0",
                "intent": "UPDATE",
                "domain": "employee",
            })

    def test_unknown_operator_rejected(self):
        with pytest.raises(ValidationError):
            AgentPlan.model_validate({
                "planVersion": "1.0",
                "intent": "QUERY",
                "domain": "employee",
                "query": {
                    "filters": [{"field": "chineseName", "operator": "REGEX", "value": "test"}],
                    "size": 20,
                }
            })

    def test_unknown_json_field_rejected(self):
        with pytest.raises(ValidationError):
            PlanGenerateResponse.model_validate({
                "requestId": "1",
                "plan": {
                    "planVersion": "1.0",
                    "intent": "QUERY",
                    "domain": "employee",
                    "query": {"filters": [], "size": 20},
                    "extraField": "unexpected",
                }
            })

    def test_aggregate_duplicate_metric_alias_rejected(self):
        """OLD: monkey-patched __init__ raised. NOW: use AgentPlan.model_validate() via parse_plan semantics.
        Test the semantic validator directly."""
        from app.contracts.semantic_validators import validate_metric_aliases_unique
        agg = AgentAggregateSpec(metrics=[
            {"alias": "same", "function": "COUNT", "field": None},
            {"alias": "same", "function": "SUM", "field": "amount"},
        ])
        with pytest.raises(ValueError, match="alias"):
            validate_metric_aliases_unique(agg)

    def test_aggregate_max_rows_above_java_max_rejected(self):
        with pytest.raises(ValidationError, match="max"):
            AgentPlan.model_validate({
                "planVersion": "1.0",
                "intent": "AGGREGATE",
                "domain": "transaction",
                "aggregate": {
                    "metrics": [{"alias": "cnt", "function": "COUNT", "field": None}],
                    "maxRows": 101,
                },
            })


class TestEnumValues:
    def test_intent_only_query_clarify(self):
        assert set(AgentIntent) == {AgentIntent.QUERY, AgentIntent.CLARIFY, AgentIntent.AGGREGATE}

    def test_operator_eight_standard(self):
        assert set(AgentOperator) == {
            AgentOperator.EQ, AgentOperator.CONTAINS,
            AgentOperator.CONTAINS_ANY, AgentOperator.STARTS_WITH,
            AgentOperator.STARTS_WITH_ANY, AgentOperator.IN,
            AgentOperator.GT, AgentOperator.LT,
        }

    def test_field_type_three_values(self):
        assert set(AgentFieldType) == {
            AgentFieldType.STRING, AgentFieldType.DECIMAL, AgentFieldType.INSTANT,
        }


class TestMultiDomainRequest:
    """Multi-domain PlanGenerateRequest."""

    def test_domain_schemas_list_accepted(self):
        req = PlanGenerateRequest(
            request_id="test-001",
            message="查询岗位是HRM的员工",
            domain_schemas=[_employee_schema(), _transaction_schema()],
            capabilities=[_query_search_capability(), _clarify_capability()],
        )
        assert len(req.domain_schemas) == 2

    def test_single_domain_schema_accepted(self):
        req = PlanGenerateRequest(
            request_id="test-001",
            message="查询岗位是HRM的员工",
            domain_schemas=[_employee_schema()],
            capabilities=[_query_search_capability(), _clarify_capability()],
        )
        assert req.domain_schemas[0].domain == "employee"

    def test_empty_domain_schemas_rejected(self):
        with pytest.raises(ValidationError, match="domain_schemas"):
            PlanGenerateRequest(
                request_id="test-001",
                message="test",
                domain_schemas=[],
                capabilities=[_query_search_capability(), _clarify_capability()],
            )

    def test_duplicate_domains_rejected(self):
        """OLD: monkey-patched __init__ raised. NOW: use the explicit semantic validator."""
        from app.contracts.semantic_validators import validate_plan_generate_request_semantics
        req = PlanGenerateRequest(
            request_id="test-001",
            message="test",
            domain_schemas=[_employee_schema(), _employee_schema()],
            capabilities=[_query_search_capability(), _clarify_capability()],
        )
        with pytest.raises(ValueError, match="Duplicate"):
            validate_plan_generate_request_semantics(req)


class TestAgentPlanDomainNullable:
    """CLARIFY domain can be null."""

    def test_clarify_null_domain_accepted(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain=None,
            clarify=ClarifySpec(question="无法判断你要查询哪个领域，请说明是员工还是交易？"),
            query=None,
        )
        assert plan.domain is None

    def test_query_null_domain_rejected(self):
        """OLD: Pydantic model_validator raised. NOW: use AgentPlan.model_validate() + semantic validator.
        AgentPlan(...) alone no longer raises. Test the semantic validator directly."""
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain=None,
            query=AgentQuerySpec(
                filters=[{"field": "amount", "operator": "GT", "value": "100"}],
                size=20,
            ),
        )
        from app.contracts.semantic_validators import validate_agent_plan_intent_shape
        with pytest.raises(ValueError, match="QUERY requires a non-null domain"):
            validate_agent_plan_intent_shape(plan)


class TestRuntimeFieldSchemaExtraFields:
    """type and formatHint are now part of RuntimeFieldSchema."""

    def test_field_schema_includes_type(self):
        schema = _employee_schema()
        for f in schema.fields:
            assert f.type == AgentFieldType.STRING

    def test_transaction_field_has_format_hint(self):
        schema = _transaction_schema()
        date_fields = [f for f in schema.fields if f.name == "transDate"]
        assert len(date_fields) == 1
        assert date_fields[0].type == AgentFieldType.INSTANT
        assert date_fields[0].format_hint is not None

    def test_domain_schema_includes_aliases(self):
        emp = _employee_schema()
        assert "员工" in emp.aliases
        txn = _transaction_schema()
        assert "交易" in txn.aliases
