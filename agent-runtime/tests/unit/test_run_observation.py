from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal

import pytest

from agent_runtime.business.contracts import BusinessHttpRequest
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse, UserJwtBusinessHttpClient
from agent_runtime.business.wire_json import BusinessWireJsonEncoder, ExactDecimal
from agent_runtime.model.contracts import (
    ModelCallContext,
    ModelTaskDefinition,
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryOutput, KnowledgeSummaryPoint, SummaryOutcome
from agent_runtime.knowledge.contracts import (
    DomainSelection,
    RewriteCandidate,
    RewriteCandidateSource,
    RewriteMode,
    RewriteResult,
)
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.observation import (
    RunObservationCollector,
    current_observation,
    knowledge_http_request_view,
    observation_scope,
    record_plan,
    safe_business_relative_path,
)
from tests.helpers import ManualCancellationSignal, scope
from tests.model_helpers import FakeStructuredModelTransport


@dataclass(frozen=True, slots=True)
class PlanInput:
    question: str


def _definition() -> ModelTaskDefinition[PlanInput, dict[str, object]]:
    def build_request(value: PlanInput) -> StructuredModelRequest:
        return StructuredModelRequest(
            task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
            task_version="business-query-plan-test-v1",
            system_instruction="Return one JSON QueryPlan.",
            user_payload_json=(
                '{"catalog_snapshot_id":"v1","question":"' + value.question + '"}'
            ),
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=128,
        )

    def parse_response(_: StructuredModelResponse) -> dict[str, object]:
        return {
            "domain": "employee",
            "action": "employee.search",
            "arguments": {"filters": []},
        }

    return ModelTaskDefinition(
        task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
        task_version="business-query-plan-test-v1",
        input_type=PlanInput,
        max_input_bytes=1024,
        timeout_ms=1000,
        max_output_tokens=128,
        build_request=build_request,
        parse_response=parse_response,
    )


@pytest.mark.asyncio
async def test_observation_is_request_scoped_and_records_parsed_model_contract_only() -> None:
    response = StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content='{"raw":"must-not-be-recorded"}',
        tool_calls=(),
        usage_total_tokens=20,
    )
    definition = _definition()
    gateway = BoundedStructuredModelGateway(
        transport=FakeStructuredModelTransport(response),
        definitions=(definition,),
        max_concurrency=1,
    )
    assert current_observation() is None

    with observation_scope() as collector:
        result = await gateway.generate(
            definition=definition,
            input=PlanInput("上海员工"),
            context=ModelCallContext(
                request_id="req-1",
                correlation_id="corr-1",
                deadline_monotonic=asyncio.get_running_loop().time() + 5,
            ),
        )
        record_plan(
            plan_type="business_query_plan",
            source="llm",
            validation_status="accepted",
            plan=result.output,
        )
        snapshot = collector.snapshot()

    assert current_observation() is None
    assert snapshot.model_calls[0]["request"]["input"]["question"] == "上海员工"
    assert snapshot.model_calls[0]["status"] == "succeeded"
    assert "structuredOutput" not in snapshot.model_calls[0]
    assert "must-not-be-recorded" not in repr(snapshot)
    assert snapshot.plans[0]["validationStatus"] == "accepted"


class FakeBusinessTransport:
    async def send(self, _: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        return FakeDomainHttpResponse(status_code=200, content_type="application/json", body=b"{}")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_business_downstream_view_redacts_protected_values_and_preserves_exact_decimal() -> None:
    body = BusinessWireJsonEncoder().encode(
        {
            "transId": "TX-SECRET",
            "amount": ExactDecimal.from_decimal(Decimal("12.30")),
        },
        max_bytes=4096,
    )
    client = UserJwtBusinessHttpClient(transport=FakeBusinessTransport(), max_response_bytes=1024)

    with observation_scope() as collector:
        await client.execute(
            request=BusinessHttpRequest(method="POST", relative_path="/txn/search", query=(), json_body=body),
            user_token=scope().context.user_token,
            call_deadline=asyncio.get_running_loop().time() + 2,
            cancellation=ManualCancellationSignal(),
        )
        snapshot = collector.snapshot()

    call = snapshot.downstream_calls[0]
    assert call["target"] == "mq-procedure-service"
    assert call["operation"] == "transaction.search"
    assert call["request"]["body"] == {"amount": "12.3", "transId": "<protected>"}
    assert call["request"]["exactDecimalJsonNumbers"] is True
    assert "header.payload.signature" not in repr(snapshot)


def test_knowledge_downstream_view_hides_vectors_and_document_content() -> None:
    search = knowledge_http_request_view(
        "/es/knowledge/search",
        b'{"logicalDomainId":"tax.policy","queryVector":[0.1,0.2],"queryText":"VAT"}',
    )
    rerank = knowledge_http_request_view(
        "/rerank",
        b'{"query":"VAT","documents":["secret body"],"top_n":1,"normalize":true}',
    )

    assert search["queryVector"] == {"present": True, "dimensions": 2, "valuesDisplayed": False}
    assert rerank["documentCount"] == 1
    assert rerank["documentContentDisplayed"] is False
    assert "secret body" not in repr(rerank)


@pytest.mark.asyncio
async def test_knowledge_summary_observation_hides_evidence_content_and_quotes() -> None:
    def build_request(_: PlanInput) -> StructuredModelRequest:
        return StructuredModelRequest(
            task_id=ModelTaskId.KNOWLEDGE_SUMMARY,
            task_version="4",
            system_instruction="Return evidence refs.",
            user_payload_json=(
                '{"question":"税务政策","evidence":['
                '{"evidence_ref":"e1","domain_ids":["tax.policy"],"content":"secret body"}]}'
            ),
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=128,
        )

    definition = ModelTaskDefinition(
        task_id=ModelTaskId.KNOWLEDGE_SUMMARY,
        task_version="4",
        input_type=PlanInput,
        max_input_bytes=1024,
        timeout_ms=1000,
        max_output_tokens=128,
        build_request=build_request,
        parse_response=lambda _: KnowledgeSummaryOutput(
            outcome=SummaryOutcome.ANSWER,
            points=(KnowledgeSummaryPoint(evidence_ref="e1", quote="secret quote"),),
        ),
    )
    gateway = BoundedStructuredModelGateway(
        transport=FakeStructuredModelTransport(StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"answer"}',
            tool_calls=(),
            usage_total_tokens=10,
        )),
        definitions=(definition,),
        max_concurrency=1,
    )

    with observation_scope() as collector:
        await gateway.generate(
            definition=definition,
            input=PlanInput("税务政策"),
            context=ModelCallContext(
                request_id="req-2",
                correlation_id="corr-2",
                deadline_monotonic=asyncio.get_running_loop().time() + 5,
            ),
        )
        snapshot = collector.snapshot()

    assert "secret body" not in repr(snapshot)
    assert "secret quote" not in repr(snapshot)
    assert snapshot.model_calls[0]["request"]["input"]["evidence"][0]["evidenceRef"] == "e1"
    assert "structuredOutput" not in snapshot.model_calls[0]


def test_employee_nested_sensitive_filter_values_are_redacted() -> None:
    from agent_runtime.observation import business_http_request_view

    view = business_http_request_view(
        "/employees/es/search",
        b'{"filters":[{"field":"chineseName","operator":"contains","value":"Alice"}],'
        b'"from":0,"keyword":"Alice","size":20,"sorts":[]}',
        (),
    )

    assert view["body"]["filters"][0]["value"] == "<protected>"
    assert view["body"]["keyword"] == "<protected>"
    assert "Alice" not in repr(view)


def test_employee_contact_address_lists_are_redacted_from_diagnostics() -> None:
    from agent_runtime.observation import business_http_request_view

    view = business_http_request_view(
        "/employees/es/search",
        b'{"filters":[{"field":"contactAddress","operator":"containsAny",'
        b'"values":["Shanghai secret street","Zhejiang secret street"]}],'
        b'"from":0,"size":20,"sorts":[]}',
        (),
    )

    assert view["body"]["filters"][0]["values"] == "<protected>"
    assert "secret street" not in repr(view)


def test_plan_sensitive_filter_value_is_redacted_by_the_general_projection() -> None:
    with observation_scope() as collector:
        record_plan(
            plan_type="business_query_plan",
            source="llm",
            validation_status="accepted",
            plan={
                "domain": "employee",
                "action": "employee.search",
                "arguments": {
                    "filters": [
                        {
                            "field": "chinese_name",
                            "operator": "eq",
                            "value": {"literal": "Alice"},
                        }
                    ]
                },
            },
        )
        snapshot = collector.snapshot()

    value = snapshot.plans[0]["plan"]["arguments"]["filters"][0]["value"]
    assert value == "<protected>"
    assert "Alice" not in repr(snapshot)


def test_knowledge_plan_builder_records_the_actual_runtime_plan() -> None:
    rewrite = RewriteResult(
        original_question="税务政策",
        selected_query="税务政策",
        candidates=(RewriteCandidate(
            text="税务政策",
            source=RewriteCandidateSource.ORIGINAL_FALLBACK,
            ordinal=1,
        ),),
        mode=RewriteMode.ORIGINAL_FALLBACK,
        question_policy_version="question-egress-v1",
        question_egress_denied=False,
    )
    settings = KnowledgeSettings.from_env(
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"}
    )

    with observation_scope() as collector:
        plan = KnowledgeRetrievalPlanBuilder().build(
            rewrite=rewrite,
            domains=DomainSelection(
                selected_domain_ids=("tax.policy",),
                catalog_version="tax-domain-catalog-v1",
                reason_codes=("policy",),
            ),
            settings=settings,
        )
        snapshot = collector.snapshot()

    assert len(plan.items) == 2
    assert snapshot.plans[0]["type"] == "knowledge_retrieval_plan"
    assert snapshot.plans[0]["plan"]["selected_domain_ids"] == ["tax.policy"]


def test_legacy_employee_identifier_is_not_exposed_in_observed_path() -> None:
    assert safe_business_relative_path("/employees/SYNTHETIC-EMPLOYEE-001") == "/employees/<protected>"


@pytest.mark.asyncio
async def test_projection_limit_cannot_turn_a_successful_model_call_into_failure() -> None:
    def build_request(_: PlanInput) -> StructuredModelRequest:
        return StructuredModelRequest(
            task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
            task_version="large-v1",
            system_instruction="S" * 8192,
            user_payload_json='{"value":"' + ("x" * 60_000) + '"}',
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=64,
        )

    definition = ModelTaskDefinition(
        task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
        task_version="large-v1",
        input_type=PlanInput,
        max_input_bytes=65_536,
        timeout_ms=1000,
        max_output_tokens=64,
        build_request=build_request,
        parse_response=lambda _: {"domain": "unsupported", "action": "unsupported", "arguments": {}},
    )
    transport = FakeStructuredModelTransport(StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content="{}",
        tool_calls=(),
        usage_total_tokens=1,
    ))
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)

    with observation_scope() as collector:
        result = await gateway.generate(
            definition=definition,
            input=PlanInput("x"),
            context=ModelCallContext(
                request_id="req-3",
                correlation_id="corr-3",
                deadline_monotonic=asyncio.get_running_loop().time() + 5,
            ),
        )
        snapshot = collector.snapshot()

    assert result.output is not None
    assert transport.calls == 1
    assert snapshot.model_calls[0]["request"] == {"projectionStatus": "unavailable"}
    assert snapshot.model_calls[0]["status"] == "succeeded"


def test_snapshot_overhead_cannot_break_an_observed_success() -> None:
    collector = RunObservationCollector()
    request = StructuredModelRequest(
        task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
        task_version="large-v2",
        system_instruction="S" * 8_192,
        user_payload_json='{"value":"' + ("x" * 57_150) + '"}',
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=64,
    )

    sequence = collector.start_model_call(request)
    collector.finish_model_call(sequence)
    snapshot = collector.snapshot()

    assert snapshot.model_calls[0]["status"] == "succeeded"
    assert snapshot.model_calls[0]["request"] == {"projectionStatus": "unavailable"}


def test_snapshot_has_a_total_response_budget() -> None:
    collector = RunObservationCollector()
    request = StructuredModelRequest(
        task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
        task_version="bounded-v1",
        system_instruction="S" * 8_192,
        user_payload_json='{"value":"' + ("x" * 20_000) + '"}',
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=64,
    )
    for _ in range(8):
        collector.finish_model_call(collector.start_model_call(request))
    for _ in range(4):
        collector.record_plan(
            plan_type="business_query_plan",
            source="llm",
            validation_status="accepted",
            plan={"value": "p" * 20_000},
        )
    for _ in range(32):
        collector.start_downstream_call(
            target="employee-service",
            operation="employee.search",
            method="POST",
            relative_path="/employees/es/search",
            request={"value": "d" * 2_000},
        )

    snapshot = collector.snapshot()
    encoded = json.dumps(snapshot.__dict__ if hasattr(snapshot, "__dict__") else {
        "modelCalls": snapshot.model_calls,
        "plans": snapshot.plans,
        "downstreamCalls": snapshot.downstream_calls,
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    assert len(encoded) <= 65_536
    assert "projectionStatus" in encoded.decode("utf-8")
