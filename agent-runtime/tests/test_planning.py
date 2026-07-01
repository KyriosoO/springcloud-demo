"""
Tests for plan parsing and validation (multi-domain, without LLM).
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
    AggregateFunction,
    AggregateMetricSpec,
    AggregateSpec,
    CapabilityContextSpec,
    CapabilityContractRef,
    CapabilityDomainScope,
    ClarifySpec,
    validate_agent_plan_intent_shape,
    PlanGenerateRequest,
    RuntimeDomainSchema,
    RuntimeFieldSchema,
    RuntimeQueryContext,
)
from app.contracts.models import RuntimeRole, RuntimeTurn
from app.core.planning import (
    build_user_payload,
    build_query_payload,
    build_aggregate_payload,
    build_clarify_plan,
    parse_plan,
    parse_route_decision,
    validate_plan_against_request,
    validate_route_decision,
    validate_query_plan_against_route,
    validate_aggregate_plan_against_route,
    schema_by_domain,
)
from app.core.route_models import RouteDecision


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


def _employee_capability() -> AgentCapabilityDescriptor:
    """创建一个 query.search capability descriptor，employee + transaction domain。"""
    scope_emp = CapabilityDomainScope(domain="employee", enabled=True)
    scope_txn = CapabilityDomainScope(domain="transaction", enabled=True)
    return AgentCapabilityDescriptor(
        capability_id="query.search",
        intent=AgentIntent.QUERY,
        display_name="Search records",
        description="Search records in a supported domain.",
        domain_scopes=[scope_emp, scope_txn],
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
    return [_employee_capability(), _clarify_capability(), _aggregate_capability()]


def _make_request(message: str) -> PlanGenerateRequest:
    return PlanGenerateRequest(
        request_id="test-001",
        message=message,
        domain_schemas=[_employee_schema()],
        capabilities=_standard_capabilities(),
    )


def _make_multi_request(message: str) -> PlanGenerateRequest:
    return PlanGenerateRequest(
        request_id="test-001",
        message=message,
        domain_schemas=[_employee_schema(), _transaction_schema()],
        capabilities=_standard_capabilities(),
    )


class TestBuildUserPayload:
    def test_uses_domain_schemas_list(self):
        request = _make_request("岗位是 HRM")
        request.recent_turns = [
            RuntimeTurn(role=RuntimeRole.USER, content="帮我查员工"),
        ]

        payload = build_user_payload(request)

        assert set(payload) == {"message", "recentTurns", "previousQuery", "domainSchemas", "capabilities", "planVersion"}
        assert payload["recentTurns"] == [{"role": "USER", "content": "帮我查员工"}]
        assert len(payload["domainSchemas"]) == 1
        assert payload["domainSchemas"][0]["domain"] == "employee"
        assert payload["domainSchemas"][0]["defaultSelectFields"] == [
            "chineseName", "memberNo", "position",
        ]
        assert payload["planVersion"] == "1.0"

    def test_multi_domain_schemas_in_payload(self):
        request = _make_multi_request("查询金额大于100的交易")
        payload = build_user_payload(request)
        assert len(payload["domainSchemas"]) == 2
        domains = [s["domain"] for s in payload["domainSchemas"]]
        assert domains == ["employee", "transaction"]


class TestSchemaByDomain:
    def test_finds_existing_domain(self):
        request = _make_multi_request("test")
        schema = schema_by_domain(request, "transaction")
        assert schema is not None
        assert schema.domain == "transaction"

    def test_returns_none_for_unknown(self):
        request = _make_multi_request("test")
        schema = schema_by_domain(request, "inventory")
        assert schema is None


class TestParsePlan:
    """JSON → AgentPlan parsing."""

    def test_query_plan(self):
        raw = json.dumps({
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
        plan = parse_plan(raw)
        assert plan.intent == AgentIntent.QUERY
        assert plan.query is not None
        assert plan.query.filters[0].field == "position"

    def test_transaction_query_gte_lt(self):
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "QUERY",
            "domain": "transaction",
            "query": {
                "filters": [
                    {"field": "amount", "operator": "GT", "value": "100"},
                    {"field": "amount", "operator": "LT", "value": "1000"},
                ],
                "size": 20,
            },
            "clarify": None,
        })
        plan = parse_plan(raw)
        assert plan.domain == "transaction"
        operators = [f.operator for f in plan.query.filters]
        assert AgentOperator.GT in operators
        assert AgentOperator.LT in operators

    def test_clarify_null_domain(self):
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "CLARIFY",
            "domain": None,
            "query": None,
            "clarify": {"question": "无法判断你的领域，请说明是员工还是交易？"},
        })
        plan = parse_plan(raw)
        assert plan.intent == AgentIntent.CLARIFY
        assert plan.domain is None

    def test_clarify_plan(self):
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "CLARIFY",
            "domain": "employee",
            "query": None,
            "clarify": {"question": "请提供更多条件。"},
        })
        plan = parse_plan(raw)
        assert plan.intent == AgentIntent.CLARIFY
        assert plan.clarify.question == "请提供更多条件。"

    def test_position_eq_parses_correctly(self):
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "QUERY",
            "domain": "employee",
            "query": {
                "filters": [{"field": "position", "operator": "EQ", "value": "HRM"}],
                "selectFields": ["chineseName"],
                "size": 20,
            },
            "clarify": None,
        })
        plan = parse_plan(raw)
        f = plan.query.filters[0]
        assert f.field == "position"
        assert f.operator == AgentOperator.EQ
        assert f.value == "HRM"

    def test_in_parsed_correctly(self):
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "QUERY",
            "domain": "employee",
            "query": {
                "filters": [{"field": "memberNo", "operator": "IN", "values": ["E001", "E002"]}],
                "size": 20,
            },
            "clarify": None,
        })
        plan = parse_plan(raw)
        f = plan.query.filters[0]
        assert f.operator == AgentOperator.IN
        assert f.values == ["E001", "E002"]

    def test_query_null_domain_rejected(self):
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "QUERY",
            "domain": None,
            "query": {
                "filters": [{"field": "amount", "operator": "GT", "value": "100"}],
                "size": 20,
            },
            "clarify": None,
        })
        with pytest.raises(ValueError):
            parse_plan(raw)


class TestValidatePlanAgainstRequest:
    """Additional semantic-level checks — multi-domain."""

    # --- Employee tests (existing) ---

    def test_employee_query_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="employee",
            query=AgentQuerySpec(
                filters=[{"field": "position", "operator": "EQ", "value": "HRM"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_request("test"))
        assert errors == []

    def test_empty_replace_query_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="employee",
            query=AgentQuerySpec(filters=[], size=20),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_request("test"))
        assert any("filter" in e for e in errors)

    def test_replace_query_with_remove_fields_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="employee",
            query=AgentQuerySpec(
                filters=[{"field": "position", "operator": "EQ", "value": "HRM"}],
                remove_fields=["position"],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_request("test"))
        assert any("removeFields" in e for e in errors)

    def test_unknown_select_field_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="employee",
            query=AgentQuerySpec(
                filters=[{"field": "position", "operator": "EQ", "value": "HRM"}],
                select_fields=["salary"],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_request("test"))
        assert any("selectField" in e for e in errors)

    def test_select_fields_count_exceeds_10_rejected(self):
        """Generated model's max_length=10 rejects at construction. Confirms OpenAPI/maxItems contract."""
        with pytest.raises(Exception, match="at most 10"):
            AgentPlan(
                plan_version="1.0",
                intent=AgentIntent.QUERY,
                domain="employee",
                query=AgentQuerySpec(
                    filters=[{"field": "position", "operator": "EQ", "value": "test"}],
                    select_fields=[f"field_{i}" for i in range(11)],
                    size=20,
                ),
                clarify=None,
            )

    def test_clarify_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain="employee",
            clarify=ClarifySpec(question="P0 不支持修改操作。"),
            query=None,
        )
        errors = validate_plan_against_request(plan, _make_request("把张三岗位改成HRBP"))
        assert errors == []

    def test_unknown_field_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="employee",
            query=AgentQuerySpec(
                filters=[{"field": "salary", "operator": "EQ", "value": "10000"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_request("test"))
        assert len(errors) > 0
        assert any("salary" in e for e in errors)

    def test_reference_result_clarify_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain="employee",
            clarify=ClarifySpec(question="请重新给出查询条件。"),
            query=None,
        )
        errors = validate_plan_against_request(plan, _make_request("查刚才那些人"))
        assert errors == []

    # --- Transaction tests (new) ---

    def test_transaction_query_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="transaction",
            query=AgentQuerySpec(
                filters=[{"field": "amount", "operator": "GT", "value": "100"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("金额大于100"))
        assert errors == []

    def test_transaction_gte_lt_coexist(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="transaction",
            query=AgentQuerySpec(
                filters=[
                    {"field": "amount", "operator": "GT", "value": "100"},
                    {"field": "amount", "operator": "LT", "value": "1000"},
                ],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("金额100到1000"))
        assert errors == []

    def test_transaction_unsupported_operator_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="transaction",
            query=AgentQuerySpec(
                filters=[{"field": "transId", "operator": "GT", "value": "test"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert len(errors) > 0
        assert any("GT" in e for e in errors)

    # --- Cross-domain tests ---

    def test_unknown_domain_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="inventory",
            query=AgentQuerySpec(
                filters=[{"field": "qty", "operator": "EQ", "value": "5"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert len(errors) > 0
        assert any("Unknown" in e for e in errors)

    def test_cross_domain_employee_field_in_transaction_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="transaction",
            query=AgentQuerySpec(
                filters=[{"field": "chineseName", "operator": "EQ", "value": "张三"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert len(errors) > 0
        assert any("chineseName" in e for e in errors)

    def test_transaction_merge_with_employee_previous_rejected(self):
        request = _make_multi_request("test")
        request.previous_query = RuntimeQueryContext(
            source_turn_id="turn-001",
            domain="employee",
            filters=[{"field": "position", "operator": "EQ", "value": "HRM"}],
            select_fields=["chineseName"],
            page=1,
            size=20,
        )
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="transaction",
            query=AgentQuerySpec(
                context_mode="MERGE",
                filters=[{"field": "amount", "operator": "GT", "value": "100"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_plan_against_request(plan, request)
        assert len(errors) > 0
        assert any("MERGE domain" in e for e in errors)

    # --- CLARIFY with multi-domain ---

    def test_clarify_null_domain_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain=None,
            clarify=ClarifySpec(question="无法判断你要查询员工还是交易，请说明。"),
            query=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert errors == []

    def test_clarify_specific_domain_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain="transaction",
            clarify=ClarifySpec(question="请提供交易号或金额范围等查询条件。"),
            query=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert errors == []

    def test_clarify_unknown_domain_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain="inventory",
            clarify=ClarifySpec(question="test"),
            query=None,
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert len(errors) > 0
        assert any("Unknown CLARIFY domain" in e for e in errors)


class TestAggregatePlanning:
    """AGGREGATE semantic checks."""

    def test_transaction_aggregate_passes(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.AGGREGATE,
            domain="transaction",
            aggregate={
                "filters": [{"field": "transType", "operator": "EQ", "value": "PAY"}],
                "metrics": [
                    {"alias": "totalAmount", "function": "SUM", "field": "amount"},
                    {"alias": "countRecords", "function": "COUNT", "field": None},
                ],
                "groupByFields": ["transType"],
                "orderBy": [{"field": "totalAmount", "direction": "DESC"}],
                "maxRows": 20,
            },
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert errors == []

    def test_aggregate_order_by_unknown_field_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.AGGREGATE,
            domain="transaction",
            aggregate={
                "metrics": [{"alias": "countRecords", "function": "COUNT", "field": None}],
                "groupByFields": ["transType"],
                "orderBy": [{"field": "amount", "direction": "DESC"}],
            },
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert any("orderBy field" in e for e in errors)

    def test_employee_sum_string_metric_rejected(self):
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.AGGREGATE,
            domain="employee",
            aggregate={
                "metrics": [{"alias": "bad", "function": "SUM", "field": "position"}],
            },
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert any("DECIMAL" in e for e in errors)

    def test_count_metric_with_field_rejected_by_semantic_validator(self):
        metric = AggregateMetricSpec.model_construct(
            alias="countRecords",
            function=AggregateFunction.COUNT,
            field="amount",
        )
        aggregate = AggregateSpec.model_construct(
            filters=[],
            metrics=[metric],
            group_by_fields=None,
            order_by=None,
            max_rows=None,
        )
        plan = AgentPlan.model_construct(
            plan_version="1.0",
            intent=AgentIntent.AGGREGATE,
            domain="transaction",
            query=None,
            clarify=None,
            aggregate=aggregate,
        )

        errors = validate_plan_against_request(plan, _make_multi_request("test"))

        assert any("COUNT must not specify a field" in e for e in errors)


    def test_max_trans_date_rejected_by_adapter_capability(self):
        """Java TransactionAgentAdapter.supportedFunctions("transDate") 返回 []，
        Python 应拒绝 MAX(transDate)。校验 adapter function 白名单闭环。"""
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.AGGREGATE,
            domain="transaction",
            aggregate={
                "metrics": [{"alias": "bad", "function": "MAX", "field": "transDate"}],
            },
        )
        errors = validate_plan_against_request(plan, _make_multi_request("test"))
        assert any("MAX" in e and "transDate" in e for e in errors), (
            "Expected MAX(transDate) to be rejected by adapter function whitelist, "
            f"got errors: {errors}"
        )


class TestQueryClarifyMutualExclusion:
    """QUERY and CLARIFY mutual exclusion in Pydantic."""

    def test_query_clarify_both_present_rejected(self):
        """OLD: Pydantic model_validator raised on AgentPlan(...). NOW: semantic validator runs in parse_plan().
        This test verifies the semantic path. AgentPlan(...) alone no longer raises. Use parse_plan()."""
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "QUERY",
            "domain": "employee",
            "query": {
                "filters": [{"field": "position", "operator": "EQ", "value": "HRM"}],
                "size": 20,
            },
            "clarify": {"question": "test"},
        })
        with pytest.raises(ValueError, match="QUERY requires query and forbids clarify"):
            parse_plan(raw)

    def test_aggregate_filter_wrong_shape_rejected(self):
        """IN operator with value instead of values should be rejected."""
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "AGGREGATE",
            "domain": "transaction",
            "aggregate": {
                "metrics": [{"alias": "cnt", "function": "COUNT", "field": None}],
                "filters": [{"field": "transType", "operator": "IN", "value": "PAY"}],
            },
        })
        with pytest.raises(ValueError, match="IN requires non-empty values"):
            parse_plan(raw)

    def test_aggregate_count_with_field_rejected(self):
        """COUNT with non-null field should be rejected by semantic validator."""
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "AGGREGATE",
            "domain": "transaction",
            "aggregate": {
                "metrics": [{"alias": "cnt", "function": "COUNT", "field": "amount"}],
            },
        })
        with pytest.raises(ValueError, match="COUNT must not specify a field"):
            parse_plan(raw)

    def test_aggregate_duplicate_metric_alias_rejected(self):
        """Duplicate metric aliases should be rejected."""
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "AGGREGATE",
            "domain": "transaction",
            "aggregate": {
                "metrics": [
                    {"alias": "same", "function": "COUNT", "field": None},
                    {"alias": "same", "function": "SUM", "field": "amount"},
                ],
            },
        })
        with pytest.raises(ValueError, match="alias"):
            parse_plan(raw)


class TestRoutePlanning:
    """Tests for route/query split planning functions."""

    def _make_request(self, message: str = "test") -> PlanGenerateRequest:
        return PlanGenerateRequest(
            request_id="test-001",
            message=message,
            domain_schemas=[_employee_schema()],
            capabilities=_standard_capabilities(),
        )

    def test_parse_route_decision_query(self):
        raw = json.dumps({
            "intent": "QUERY",
            "domain": "employee",
            "question": None,
            "confidence": 0.92,
            "reason": "User asks to query position."
        })
        route = parse_route_decision(raw)
        assert route.intent == AgentIntent.QUERY
        assert route.domain == "employee"
        assert route.confidence == 0.92

    def test_parse_route_decision_clarify(self):
        raw = json.dumps({
            "intent": "CLARIFY",
            "domain": None,
            "question": "请提供查询条件",
            "confidence": 0.88,
            "reason": "No criteria."
        })
        route = parse_route_decision(raw)
        assert route.intent == AgentIntent.CLARIFY
        assert route.question == "请提供查询条件"

    def test_route_decision_query_requires_domain(self):
        raw = json.dumps({
            "intent": "QUERY",
            "domain": None,
            "question": None,
            "confidence": 0.9,
        })
        with pytest.raises(Exception):
            parse_route_decision(raw)

    def test_route_decision_clarify_requires_question(self):
        raw = json.dumps({
            "intent": "CLARIFY",
            "domain": "employee",
            "question": None,
            "confidence": 0.9,
        })
        with pytest.raises(Exception):
            parse_route_decision(raw)

    def test_validate_route_decision_unknown_domain(self):
        route = RouteDecision(
            intent=AgentIntent.QUERY,
            domain="nonexistent",
            confidence=0.9,
        )
        errors = validate_route_decision(route, self._make_request())
        assert len(errors) > 0
        assert any("Unknown route domain" in e for e in errors)

    def test_build_clarify_plan(self):
        route = RouteDecision(
            intent=AgentIntent.CLARIFY,
            domain="employee",
            question="请提供查询条件",
            confidence=0.88,
        )
        plan = build_clarify_plan("test-001", route)
        assert plan.intent == AgentIntent.CLARIFY
        assert plan.domain == "employee"
        assert plan.clarify.question == "请提供查询条件"
        assert plan.query is None

    def test_build_query_payload_includes_route(self):
        request = self._make_request("查询HRM")
        route = RouteDecision(
            intent=AgentIntent.QUERY,
            domain="employee",
            confidence=0.92,
        )
        payload = build_query_payload(request, route)
        assert "route" in payload
        assert payload["route"]["intent"] == "QUERY"
        assert payload["route"]["domain"] == "employee"

    def test_validate_query_plan_against_route_passes(self):
        route = RouteDecision(intent=AgentIntent.QUERY, domain="employee", confidence=0.92)
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="employee",
            query=AgentQuerySpec(
                filters=[{"field": "position", "operator": "EQ", "value": "HRM"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_query_plan_against_route(plan, route)
        assert errors == []

    def test_validate_query_plan_domain_mismatch(self):
        route = RouteDecision(intent=AgentIntent.QUERY, domain="employee", confidence=0.92)
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.QUERY,
            domain="transaction",
            query=AgentQuerySpec(
                filters=[{"field": "amount", "operator": "GT", "value": "100"}],
                size=20,
            ),
            clarify=None,
        )
        errors = validate_query_plan_against_route(plan, route)
        assert len(errors) > 0
        assert any("domain" in e for e in errors)

    def test_validate_query_plan_non_query_intent_rejected(self):
        route = RouteDecision(intent=AgentIntent.QUERY, domain="employee", confidence=0.92)
        plan = AgentPlan(
            plan_version="1.0",
            intent=AgentIntent.CLARIFY,
            domain="employee",
            query=None,
            clarify=ClarifySpec(question="test"),
        )
        errors = validate_query_plan_against_route(plan, route)
        assert len(errors) > 0
        assert any("intent=QUERY" in e for e in errors)

    def test_validate_query_plan_clarify_not_null_rejected(self):
        """OLD: Pydantic model_validator raised on AgentPlan(...). NOW: use parse_plan() which calls the semantic validator."""
        raw = json.dumps({
            "planVersion": "1.0",
            "intent": "QUERY",
            "domain": "employee",
            "query": {
                "filters": [{"field": "position", "operator": "EQ", "value": "HRM"}],
                "size": 20,
            },
            "clarify": {"question": "test"},
        })
        with pytest.raises(ValueError, match="QUERY requires query and forbids clarify"):
            parse_plan(raw)
