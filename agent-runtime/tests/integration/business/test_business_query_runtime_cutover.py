from __future__ import annotations

import json

import httpx
import pytest

from agent_runtime.bootstrap import (
    BusinessQueryRuntimeCompositionRoot,
    LocalModelCompositionRoot,
)
from agent_runtime.business.contracts import (
    BusinessHttpRequest,
    BusinessTransportFailure,
    BusinessTransportFailureKind,
)
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    HttpxBusinessDomainTransport,
)
from agent_runtime.business.wire_json import BusinessWireJsonEncoder
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import (
    ModelProviderFailureKind,
    ModelTaskId,
    ModelTransportError,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
)
from agent_runtime.model.settings import ModelSettings
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from tests.helpers import scope
from tests.integration.adapters.employee.test_search_fake_server import (
    FakeEmployeeSearchServer,
)
from tests.integration.adapters.transaction.test_list_search_fake_server import (
    FakeTransactionListServer,
)


class _QueryPlanTransport:
    def __init__(self) -> None:
        self.requests: list[StructuredModelRequest] = []
        self.failure: ModelTransportError | None = None

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del call_deadline
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        payload = json.loads(request.user_payload_json)
        question = payload["question"]
        if "未配置" in question:
            plan: dict[str, object] = {
                "domain": "employee",
                "action": "employee.search",
                "arguments": {
                    "filters": [{
                        "field": "work_base_si", "operator": "contains",
                        "value": {"literal": "上海"},
                    }],
                    "page": 1,
                    "size": 20,
                    "sorts": [],
                },
            }
        elif "不支持" in question:
            plan = {"domain": "employee", "action": "unsupported", "arguments": {}}
        elif "语义" in question:
            plan = {
                "domain": "employee",
                "action": "employee.semantic_search",
                "arguments": {
                    "query": {"literal": "分布式系统开发经验"},
                    "size": 20,
                },
            }
        elif "交易" in question:
            plan = {
                "domain": "transaction",
                "action": "transaction.search",
                "arguments": {
                    "filters": [{
                        "field": "trans_type", "operator": "contains",
                        "value": {"literal": "PAY"},
                    }],
                    "page": 1,
                    "size": 20,
                    "sorts": [],
                },
            }
        else:
            plan = {
                "domain": "employee",
                "action": "employee.search",
                "arguments": {
                    "filters": [{
                        "field": "contact_address", "operator": "contains",
                        "value": {"literal": "上海"},
                    }],
                    "page": 1,
                    "size": 20,
                    "sorts": [],
                },
            }
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=json.dumps(plan, ensure_ascii=False),
            tool_calls=(),
            usage_total_tokens=10,
        )


def _runtime(
    *,
    model_transport: _QueryPlanTransport | None = None,
    employee_status: int = 200,
    transaction_status: int = 200,
) -> tuple[
    ModelContextBindingRuntimeInvoker,
    _QueryPlanTransport,
    FakeEmployeeSearchServer,
    FakeTransactionListServer,
]:
    model_transport = model_transport or _QueryPlanTransport()
    employee = FakeEmployeeSearchServer(status=employee_status)
    transaction = FakeTransactionListServer(status=transaction_status)
    model = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=model_transport,
        grounding_policies={},
    )
    runtime = BusinessQueryRuntimeCompositionRoot.build(
        model=model,
        employee_transport=employee,
        transaction_transport=transaction,
        employee_endpoint="http://127.0.0.1:9210",
        transaction_endpoint="http://127.0.0.1:8182",
    )
    return runtime, model_transport, employee, transaction


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "action", "path"),
    (
        ("帮我查一下在上海的员工", "employee.search", "/employees/es/search"),
        (
            "语义查询具备分布式系统开发经验的员工",
            "employee.semantic_search",
            "/employees/es/vector-search",
        ),
        ("查询类型包含 PAY 的交易", "transaction.search", "/txn/search"),
    ),
)
async def test_cutover_registers_only_three_list_actions_and_executes_one(
    question: str,
    action: str,
    path: str,
) -> None:
    runtime, model, employee, transaction = _runtime()

    result = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()

    assert result.status is CapabilityStatus.SUCCESS
    assert result.capability_id == action
    assert result.answer_text == "查询已完成。"
    assert result.user_result is not None
    assert len(model.requests) == 1
    assert model.requests[0].task_id is ModelTaskId.BUSINESS_QUERY_PLAN
    catalog = json.loads(model.requests[0].user_payload_json)["catalog"]
    assert {item["action"] for item in catalog["actions"]} == {
        "employee.search", "employee.semantic_search", "transaction.search",
    }
    assert "employee.detail" not in model.requests[0].user_payload_json
    assert "work_base" not in model.requests[0].user_payload_json
    requests = (*employee.requests, *transaction.requests)
    assert len(requests) == 1
    assert requests[0].request.relative_path == path
    if action == "employee.search":
        assert requests[0].request.json_body is not None
        wire = json.loads(requests[0].request.json_body.content)
        assert wire["filters"][0]["field"] == "contactAddress"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "status"),
    (
        ("查询未配置工作地的员工", CapabilityStatus.UNSUPPORTED),
        ("查询不支持条件的员工", CapabilityStatus.UNSUPPORTED),
    ),
)
async def test_invalid_and_unsupported_plan_never_calls_domain_or_fallback(
    question: str,
    status: CapabilityStatus,
) -> None:
    runtime, model, employee, transaction = _runtime()
    result = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()

    assert result.status is status
    assert len(model.requests) == 1
    assert not employee.requests
    assert not transaction.requests


@pytest.mark.asyncio
async def test_model_failure_and_service_forbidden_do_not_fall_back() -> None:
    model_transport = _QueryPlanTransport()
    model_transport.failure = ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)
    runtime, _, employee, transaction = _runtime(model_transport=model_transport)
    question = "帮我查一下在上海的员工"
    result = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert not employee.requests
    assert not transaction.requests

    runtime, model, employee, transaction = _runtime(employee_status=403)
    result = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()
    assert result.status is CapabilityStatus.FORBIDDEN
    assert len(model.requests) == 1
    assert len(employee.requests) == 1
    assert not transaction.requests


@pytest.mark.asyncio
async def test_stub_entrypoint_remains_disabled_without_reading_optional_key() -> None:
    runtime = build_runtime({"LLM_API_KEY": "must-not-be-read"})
    question = "帮我查一下在上海的员工"
    result = await runtime.ainvoke(question=question, scope=scope(question))

    assert result.status is CapabilityStatus.UNSUPPORTED


@pytest.mark.asyncio
async def test_production_http_transport_is_fixed_and_response_bounded() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{}",
        )

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9210",
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )
    transport = HttpxBusinessDomainTransport(
        base_endpoint="http://127.0.0.1:9210",
        allowed_paths=frozenset({"/employees/es/search"}),
        max_response_bytes=16,
        client=client,
    )
    body = BusinessWireJsonEncoder().encode({}, max_bytes=1024)
    response = await transport.send(
        FakeDomainHttpRequest(
            request=BusinessHttpRequest(
                method="POST", relative_path="/employees/es/search", query=(), json_body=body
            ),
            authorization="Bearer synthetic-token",
            content_type="application/json",
        )
    )
    assert response.body == b"{}"
    assert len(requests) == 1
    assert requests[0].headers["Authorization"] == "Bearer synthetic-token"

    with pytest.raises(BusinessTransportFailure) as error:
        await transport.send(
            FakeDomainHttpRequest(
                request=BusinessHttpRequest(
                    method="POST", relative_path="/employees/es/vector-search", query=(), json_body=body
                ),
                authorization="Bearer synthetic-token",
            )
        )
    assert error.value.kind is BusinessTransportFailureKind.PROTOCOL
    assert len(requests) == 1
    await transport.aclose()
    assert client.is_closed
