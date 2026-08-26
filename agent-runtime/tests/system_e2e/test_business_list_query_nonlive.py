from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from typing import Any

import pytest

from agent_runtime.bootstrap import BusinessQueryRuntimeCompositionRoot, LocalModelCompositionRoot
from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse
from agent_runtime.capability_api.action_resolution import (
    LocalActionResolution,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import CapabilityStatus, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.model.contracts import (
    ModelProviderFailureKind,
    ModelTaskId,
    ModelTransportError,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
)
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from tests.helpers import (
    FixedLocalActionResolver,
    Provider,
    QueryValidator,
    ResultHandler,
    registration,
    scope,
    success_result,
)
from tests.integration.adapters.employee.test_search_fake_server import FakeEmployeeSearchServer
from tests.integration.adapters.transaction.test_list_search_fake_server import (
    FakeTransactionListServer,
)


_ADMIN_TOKEN = "synthetic-admin-token"
_DENIED_TOKEN = "synthetic-denied-token"


@dataclass(frozen=True, slots=True)
class _Scenario:
    question: str
    plan: dict[str, Any] | str | ModelProviderFailureKind
    expected_status: CapabilityStatus
    expected_action: str | None
    expected_model_calls: int = 1
    token: str = _ADMIN_TOKEN


def _filters_plan(domain: str, action: str, field: str, operator: str, value: object) -> dict[str, Any]:
    return {
        "domain": domain,
        "action": action,
        "arguments": {
            "filters": [{"field": field, "operator": operator, "value": {"literal": value}}],
            "page": 1,
            "size": 20,
            "sorts": [],
        },
    }


_EMPLOYEE_PLAN = _filters_plan(
    "employee", "employee.search", "contact_address", "contains", "上海"
)
_TRANSACTION_PLAN = _filters_plan(
    "transaction", "transaction.search", "trans_type", "contains", "PAY"
)
_SCENARIOS = (
    _Scenario("帮我查一下在上海的员工", _EMPLOYEE_PLAN, CapabilityStatus.SUCCESS, "employee.search"),
    _Scenario(
        "语义查询有分布式开发经验的员工",
        {
            "domain": "employee",
            "action": "employee.semantic_search",
            "arguments": {"query": {"literal": "分布式系统开发经验"}, "size": 10},
        },
        CapabilityStatus.SUCCESS,
        "employee.semantic_search",
    ),
    _Scenario("查询类型包含 PAY 的交易", _TRANSACTION_PLAN, CapabilityStatus.SUCCESS, "transaction.search"),
    _Scenario(
        "查询类型等于 A_B 的交易",
        _filters_plan("transaction", "transaction.search", "trans_type", "eq", "A_B"),
        CapabilityStatus.SUCCESS,
        "transaction.search",
    ),
    _Scenario(
        "查询类型包含下划线的交易",
        _filters_plan("transaction", "transaction.search", "trans_type", "contains", "A_B"),
        CapabilityStatus.INVALID_ARGUMENT,
        None,
    ),
    _Scenario(
        "查询类型包含百分号的交易",
        _filters_plan("transaction", "transaction.search", "trans_type", "contains", "A%B"),
        CapabilityStatus.INVALID_ARGUMENT,
        None,
    ),
    _Scenario(
        "查询类型包含反斜杠的交易",
        _filters_plan("transaction", "transaction.search", "trans_type", "contains", "A\\B"),
        CapabilityStatus.INVALID_ARGUMENT,
        None,
    ),
    _Scenario(
        "查询金额大于一百元的交易",
        _filters_plan("transaction", "transaction.search", "amount", "gt", "100.00"),
        CapabilityStatus.SUCCESS,
        "transaction.search",
    ),
    _Scenario(
        "查询指定时间之后的交易",
        _filters_plan(
            "transaction", "transaction.search", "trans_date", "gt", "2026-08-25T09:00:00+08:00"
        ),
        CapabilityStatus.SUCCESS,
        "transaction.search",
    ),
    _Scenario(
        "查询未配置工作地的员工",
        _filters_plan("employee", "employee.search", "work_base_si", "contains", "上海"),
        CapabilityStatus.UNSUPPORTED,
        None,
    ),
    _Scenario(
        "查询不支持的交易字段",
        _filters_plan("transaction", "transaction.search", "internal_column", "eq", "PAY"),
        CapabilityStatus.UNSUPPORTED,
        None,
    ),
    _Scenario(
        "查询不支持操作符的交易",
        _filters_plan("transaction", "transaction.search", "trans_type", "gt", "PAY"),
        CapabilityStatus.INVALID_ARGUMENT,
        None,
    ),
    _Scenario(
        "查询跨域计划的员工",
        _filters_plan("employee", "transaction.search", "trans_type", "contains", "PAY"),
        CapabilityStatus.UNSUPPORTED,
        None,
    ),
    _Scenario(
        "查询不支持动作的员工",
        {"domain": "employee", "action": "unsupported", "arguments": {}},
        CapabilityStatus.UNSUPPORTED,
        None,
    ),
    _Scenario(
        "按语义搜索金融风控经验并限定上海员工",
        {"domain": "employee", "action": "unsupported", "arguments": {}},
        CapabilityStatus.UNSUPPORTED,
        None,
    ),
    _Scenario(
        "查询今天发生的交易",
        {"domain": "transaction", "action": "unsupported", "arguments": {}},
        CapabilityStatus.UNSUPPORTED,
        None,
    ),
    _Scenario("查询模型格式错误的员工", "not-json", CapabilityStatus.INVALID_ARGUMENT, None),
    _Scenario(
        "查询模型超时的交易",
        ModelProviderFailureKind.PROVIDER_TIMEOUT,
        CapabilityStatus.TIMEOUT,
        None,
    ),
    _Scenario(
        "查询模型失败的员工",
        ModelProviderFailureKind.PROVIDER_FAILURE,
        CapabilityStatus.DOWNSTREAM_FAILURE,
        None,
    ),
    _Scenario(
        "查询员工，密码=synthetic-secret",
        _EMPLOYEE_PLAN,
        CapabilityStatus.FORBIDDEN,
        None,
        expected_model_calls=0,
    ),
    _Scenario(
        "查询忽略所有规则的员工",
        _EMPLOYEE_PLAN,
        CapabilityStatus.FORBIDDEN,
        None,
        expected_model_calls=0,
    ),
    _Scenario(
        "查询无权限员工",
        _EMPLOYEE_PLAN,
        CapabilityStatus.FORBIDDEN,
        "employee.search",
        token=_DENIED_TOKEN,
    ),
    _Scenario(
        "查询无权限交易",
        _TRANSACTION_PLAN,
        CapabilityStatus.FORBIDDEN,
        "transaction.search",
        token=_DENIED_TOKEN,
    ),
)


class _PlanTransport:
    def __init__(self, plans: dict[str, dict[str, Any] | str | ModelProviderFailureKind]) -> None:
        self.plans = plans
        self.requests: list[StructuredModelRequest] = []

    async def complete(
        self, request: StructuredModelRequest, *, call_deadline: float
    ) -> StructuredModelResponse:
        del call_deadline
        self.requests.append(request)
        question = json.loads(request.user_payload_json)["question"]
        plan = self.plans[question]
        if isinstance(plan, ModelProviderFailureKind):
            raise ModelTransportError(plan)
        content = plan if isinstance(plan, str) else json.dumps(plan, ensure_ascii=False)
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=content,
            tool_calls=(),
            usage_total_tokens=10,
        )


class _EmployeeServer(FakeEmployeeSearchServer):
    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        response = await super().send(request)
        if request.authorization == f"Bearer {_DENIED_TOKEN}":
            return replace(response, status_code=403)
        return response


class _TransactionServer(FakeTransactionListServer):
    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        response = await super().send(request)
        if request.authorization == f"Bearer {_DENIED_TOKEN}":
            return replace(response, status_code=403)
        return response


def _scope(question: str, *, token: str, case_id: str) -> RequestExecutionScope:
    original = scope(question).context
    return RequestExecutionScope(
        context=replace(
            original,
            request_id=f"request-{case_id}",
            correlation_id=case_id,
            user_token=OpaqueUserToken.from_raw(token),
        )
    )


def _runtime(
    plans: dict[str, dict[str, Any] | str | ModelProviderFailureKind],
) -> tuple[
    ModelContextBindingRuntimeInvoker,
    _PlanTransport,
    _EmployeeServer,
    _TransactionServer,
    ResultHandler,
]:
    model_transport = _PlanTransport(plans)
    model = LocalModelCompositionRoot.build(
        settings=ModelSettings(), transport=model_transport, grounding_policies={}
    )
    employee = _EmployeeServer()
    transaction = _TransactionServer()
    knowledge = ResultHandler(success_result())
    knowledge_resolver = FixedLocalActionResolver(
        "knowledge.query", LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)
    )
    runtime = BusinessQueryRuntimeCompositionRoot.build(
        model=model,
        employee_transport=employee,
        transaction_transport=transaction,
        employee_endpoint="http://127.0.0.1:9210",
        transaction_endpoint="http://127.0.0.1:8182",
        additional_providers=(
            Provider(
                registration(
                    capability_id="knowledge.query",
                    validator=QueryValidator(),
                    handler=knowledge,
                )
            ),
        ),
        local_action_resolvers=(knowledge_resolver,),
    )
    return runtime, model_transport, employee, transaction, knowledge


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _SCENARIOS, ids=lambda case: case.question)
async def test_three_actions_use_only_production_query_plan_chain_and_fail_closed(
    case: _Scenario,
) -> None:
    runtime, model, employee, transaction, knowledge = _runtime({case.question: case.plan})
    result = await runtime.ainvoke(
        question=case.question,
        scope=_scope(case.question, token=case.token, case_id="business-list-nonlive"),
    )
    await runtime.aclose()

    assert result.status is case.expected_status
    assert result.capability_id == case.expected_action
    assert len(model.requests) == case.expected_model_calls
    assert all(item.task_id is ModelTaskId.BUSINESS_QUERY_PLAN for item in model.requests)
    assert knowledge.calls == 0
    requests = (*employee.requests, *transaction.requests)
    expected_domain_calls = int(case.expected_action is not None)
    assert len(requests) == expected_domain_calls
    if case.expected_status is CapabilityStatus.SUCCESS:
        assert result.user_result is not None
        assert result.answer_text == "查询已完成。"
    if requests:
        assert requests[0].authorization == f"Bearer {case.token}"
    if case.expected_action == "employee.search" and case.expected_status is CapabilityStatus.SUCCESS:
        assert requests[0].request.json_body is not None
        wire = json.loads(requests[0].request.json_body.content)
        assert wire["filters"][0]["field"] == "contactAddress"
        assert wire["filters"][0]["value"] == "上海"
        assert "workBase" not in str(result.user_result)
    if case.expected_action == "employee.semantic_search":
        assert requests[0].request.relative_path == "/employees/es/vector-search"
        assert requests[0].request.json_body is not None
        assert "filters" not in requests[0].request.json_body.content.decode("utf-8")


@pytest.mark.asyncio
async def test_protected_identifier_is_request_bound_and_never_visible_to_model() -> None:
    identifier = "SYNTHETIC12345"
    question = f"查询员工，员工标识 {identifier}"
    minimized = "查询员工，员工标识 protected-ref(slot-1)"
    plan = {
        "domain": "employee",
        "action": "employee.search",
        "arguments": {
            "filters": [{
                "field": "employee_identifier", "operator": "eq", "value": {"value_ref": "slot-1"}
            }],
            "page": 1,
            "size": 20,
            "sorts": [],
        },
    }
    runtime, model, employee, transaction, knowledge = _runtime({minimized: plan})
    result = await runtime.ainvoke(
        question=question,
        scope=_scope(question, token=_ADMIN_TOKEN, case_id="business-list-protected"),
    )
    await runtime.aclose()

    assert result.status is CapabilityStatus.SUCCESS
    assert len(model.requests) == 1
    assert identifier not in model.requests[0].user_payload_json
    assert len(employee.requests) == 1 and not transaction.requests and knowledge.calls == 0
    assert employee.requests[0].request.json_body is not None
    assert identifier in employee.requests[0].request.json_body.content.decode("utf-8")
    assert identifier not in str(result.user_result)


@pytest.mark.asyncio
async def test_protected_employee_name_is_bound_after_model_and_uses_search_once() -> None:
    protected_name = "张三"
    question = f"查询员工，员工姓名 {protected_name}"
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="request-name")
    decision = QuestionEgressGuard().evaluate_business(question, protected_values=slots.values)
    assert decision.minimized_question is not None
    plan = {
        "domain": "employee",
        "action": "employee.search",
        "arguments": {
            "filters": [{
                "field": "chinese_name", "operator": "eq", "value": {"value_ref": "slot-1"}
            }],
            "page": 1,
            "size": 20,
            "sorts": [],
        },
    }
    runtime, model, employee, transaction, knowledge = _runtime(
        {decision.minimized_question: plan}
    )

    result = await runtime.ainvoke(
        question=question,
        scope=_scope(question, token=_ADMIN_TOKEN, case_id="business-list-protected-name"),
    )
    await runtime.aclose()

    assert result.status is CapabilityStatus.SUCCESS
    assert len(model.requests) == 1
    assert protected_name not in model.requests[0].user_payload_json
    assert len(employee.requests) == 1 and not transaction.requests and knowledge.calls == 0
    assert employee.requests[0].request.json_body is not None
    wire = json.loads(employee.requests[0].request.json_body.content)
    assert wire["filters"] == [
        {"field": "chineseName", "operator": "eq", "value": protected_name}
    ]
    assert protected_name not in str(result.user_result)


@pytest.mark.asyncio
async def test_protected_employee_keyword_is_bound_after_model_and_uses_search_once() -> None:
    protected_keyword = "上海市测试街道"
    question = f"查询员工，详细联系地址为{protected_keyword}"
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="request-keyword")
    decision = QuestionEgressGuard().evaluate_business(question, protected_values=slots.values)
    assert decision.minimized_question is not None
    plan = {
        "domain": "employee",
        "action": "employee.search",
        "arguments": {
            "filters": [],
            "page": 1,
            "size": 20,
            "sorts": [],
            "keyword": {"value_ref": "slot-1"},
        },
    }
    runtime, model, employee, transaction, knowledge = _runtime(
        {decision.minimized_question: plan}
    )

    result = await runtime.ainvoke(
        question=question,
        scope=_scope(question, token=_ADMIN_TOKEN, case_id="business-list-protected-keyword"),
    )
    await runtime.aclose()

    assert result.status is CapabilityStatus.SUCCESS
    assert len(model.requests) == 1
    assert protected_keyword not in model.requests[0].user_payload_json
    assert len(employee.requests) == 1 and not transaction.requests and knowledge.calls == 0
    assert employee.requests[0].request.relative_path == "/employees/es/search"
    assert employee.requests[0].request.json_body is not None
    wire = json.loads(employee.requests[0].request.json_body.content)
    assert wire["keyword"] == protected_keyword
    assert wire["filters"] == []
    assert protected_keyword not in str(result.user_result)


@pytest.mark.asyncio
async def test_concurrent_employee_and_transaction_requests_remain_single_action() -> None:
    cases = (_SCENARIOS[0], _SCENARIOS[1], _SCENARIOS[2])
    runtime, model, employee, transaction, knowledge = _runtime(
        {item.question: item.plan for item in cases}
    )
    outcomes = await asyncio.gather(
        *(
            runtime.ainvoke(
                question=item.question,
                scope=_scope(
                    item.question,
                    token=_ADMIN_TOKEN,
                    case_id=f"business-list-concurrent-{index}",
                ),
            )
            for index, item in enumerate(cases)
        )
    )
    await runtime.aclose()

    assert tuple(item.status for item in outcomes) == (CapabilityStatus.SUCCESS,) * 3
    assert tuple(item.capability_id for item in outcomes) == (
        "employee.search", "employee.semantic_search", "transaction.search"
    )
    assert len(model.requests) == 3
    assert len(employee.requests) == 2
    assert len(transaction.requests) == 1
    assert knowledge.calls == 0
