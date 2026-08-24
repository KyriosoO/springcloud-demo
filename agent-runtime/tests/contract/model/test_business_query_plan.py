from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.model.contracts import (
    BusinessQueryPlanTaskInput,
    InvalidModelOutput,
    ModelCallContext,
    ModelInputDenied,
    ModelProviderFailureKind,
    ModelTaskId,
    ModelTransportError,
    QuestionEgressDisposition,
    QuestionEgressReasonCode,
    StructuredFinishKind,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.action_selector import build_action_selection_task_definition
from agent_runtime.model.deepseek.business_query_plan import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
    DeepSeekBusinessQueryPlanGenerator,
    build_business_query_plan_task_definition,
    decode_business_query_plan_output,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import (
    BUSINESS_QUESTION_EGRESS_POLICY_VERSION,
    QuestionEgressGuard,
)
from agent_runtime.model.settings import ModelSettings
from tests.model_helpers import FakeStructuredModelTransport


SNAPSHOT_ID = "snapshot-001"


def _catalog() -> JsonObject:
    return {
        "schema_version": 1,
        "snapshot_id": SNAPSHOT_ID,
        "actions": (
            {
                "domain": "employee",
                "action": "employee.detail",
                "fields": (
                    {
                        "logical_name": "employee_identifier",
                        "description": "single protected employee identifier",
                        "value_type": "identifier",
                        "operators": ("eq",),
                        "input_exposure": "protected_ref",
                        "required": True,
                        "max_text_chars": 64,
                    },
                ),
                "combination_rules": (),
                "limits": {},
            },
        ),
        "unsupported": {
            "domain": "unsupported",
            "action": "unsupported",
            "arguments": {},
        },
    }


def _input(*, question: str = "查看员工详情，身份证号 protected-ref(slot-1)") -> BusinessQueryPlanTaskInput:
    return BusinessQueryPlanTaskInput(
        minimized_question=question,
        catalog=_catalog(),
        catalog_snapshot_id=SNAPSHOT_ID,
    )


def _response(content: str) -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content=content,
        tool_calls=(),
        usage_total_tokens=12,
    )


def _context() -> ModelCallContext:
    return ModelCallContext(
        request_id="request-001",
        correlation_id="correlation-001",
        deadline_monotonic=asyncio.get_running_loop().time() + 10,
    )


def test_task_input_freezes_catalog_and_rejects_snapshot_mismatch() -> None:
    input = _input()

    assert input.catalog["snapshot_id"] == SNAPSHOT_ID
    with pytest.raises(ModelInputDenied, match="model.business_catalog_snapshot_mismatch"):
        BusinessQueryPlanTaskInput(
            minimized_question="查询交易",
            catalog=_catalog(),
            catalog_snapshot_id="snapshot-002",
        )


def test_task_request_is_no_tools_exact_json_and_model_safe() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    request = definition.build_request(_input())
    payload = json.loads(request.user_payload_json)

    assert request.task_id is ModelTaskId.BUSINESS_QUERY_PLAN
    assert request.task_version == BUSINESS_QUERY_PLAN_TASK_VERSION
    assert request.tools == ()
    assert request.tool_mode is StructuredToolMode.NONE
    assert request.output_mode is StructuredOutputMode.JSON_OBJECT
    assert set(payload) == {"catalog", "catalog_snapshot_id", "question"}
    assert payload["catalog_snapshot_id"] == SNAPSHOT_ID
    assert "654322199307261222" not in request.user_payload_json
    for required in ("domain", "action", "arguments", "unsupported", "value_ref"):
        assert required in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION
    for prohibited in ("SQL", "ES DSL", "URL", "JWT", "second action", "fallback"):
        assert prohibited in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION


def test_provider_decoder_returns_only_resource_bounded_json_object() -> None:
    decoded = decode_business_query_plan_output(
        _response(
            '{"domain":"employee","action":"employee.detail",'
            '"arguments":{"employee_identifier":{"value_ref":"slot-1"}}}'
        ),
        max_output_bytes=16384,
        max_json_depth=8,
        max_collection_items=128,
    )

    assert decoded["domain"] == "employee"
    assert decoded["action"] == "employee.detail"


@pytest.mark.parametrize(
    "content",
    [
        "```json\n{}\n```",
        "prefix {}",
        '{"domain":"employee","domain":"transaction","action":"unsupported","arguments":{}}',
        '{"domain":"employee","action":"unsupported","arguments":{"x":{"literal":null}}}',
        '{"domain":"transaction","action":"transaction.search","arguments":{"size":{"literal":1.0}}}',
        "[]",
    ],
)
def test_provider_decoder_rejects_non_exact_or_forbidden_json(content: str) -> None:
    with pytest.raises(InvalidModelOutput):
        decode_business_query_plan_output(
            _response(content),
            max_output_bytes=16384,
            max_json_depth=8,
            max_collection_items=128,
        )


@pytest.mark.parametrize(
    ("content", "max_output_bytes", "max_json_depth", "max_collection_items"),
    [
        ("{}", 1, 8, 128),
        ('{"a":{"b":{"c":1}}}', 16384, 2, 128),
        ('{"a":[1,2,3]}', 16384, 8, 2),
    ],
)
def test_provider_decoder_enforces_resource_limits(
    content: str,
    max_output_bytes: int,
    max_json_depth: int,
    max_collection_items: int,
) -> None:
    with pytest.raises(InvalidModelOutput):
        decode_business_query_plan_output(
            _response(content),
            max_output_bytes=max_output_bytes,
            max_json_depth=max_json_depth,
            max_collection_items=max_collection_items,
        )


def test_business_guard_redacts_protected_value_without_selecting_action() -> None:
    raw_identifier = "654322199307261222"
    guard = QuestionEgressGuard()

    decision = guard.evaluate_business(
        f"请查看员工详情，身份证号 {raw_identifier}",
        protected_values={"slot-1": raw_identifier},
    )

    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.policy_version == BUSINESS_QUESTION_EGRESS_POLICY_VERSION
    assert decision.minimized_question is not None
    assert raw_identifier not in decision.minimized_question
    assert "protected-ref(slot-1)" in decision.minimized_question
    assert "employee.detail" not in decision.minimized_question


@pytest.mark.parametrize(
    ("question", "protected_values", "reason"),
    [
        (
            "请查看员工详情，身份证号 654322199307261222",
            {},
            QuestionEgressReasonCode.SENSITIVE_INPUT,
        ),
        (
            "请查看员工详情，凭证 sk-secret-token-123456",
            {"slot-1": "sk-secret-token-123456"},
            QuestionEgressReasonCode.SENSITIVE_INPUT,
        ),
        ("今天天气如何", {}, QuestionEgressReasonCode.UNKNOWN_INPUT),
    ],
)
def test_business_guard_fails_closed_without_exposing_sensitive_values(
    question: str,
    protected_values: dict[str, str],
    reason: QuestionEgressReasonCode,
) -> None:
    decision = QuestionEgressGuard().evaluate_business(
        question,
        protected_values=protected_values,
    )

    assert decision.disposition is QuestionEgressDisposition.DENIED
    assert decision.reason_code is reason
    assert decision.minimized_question is None
    assert question not in repr(decision)


@pytest.mark.asyncio
async def test_generator_uses_registered_task_once_and_returns_decoded_object() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    transport = FakeStructuredModelTransport(
        _response('{"domain":"unsupported","action":"unsupported","arguments":{}}')
    )
    generator = DeepSeekBusinessQueryPlanGenerator(
        gateway=BoundedStructuredModelGateway(
            transport=transport,
            definitions=(definition,),
            max_concurrency=1,
        ),
        definition=definition,
    )

    output = await generator.generate(_input(question="帮我查看上海的员工"), context=_context())

    assert output == {"domain": "unsupported", "action": "unsupported", "arguments": {}}
    assert transport.calls == 1


@pytest.mark.asyncio
async def test_generator_propagates_finite_provider_failure_without_retry() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    transport = FakeStructuredModelTransport(
        failure=ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)
    )
    generator = DeepSeekBusinessQueryPlanGenerator(
        gateway=BoundedStructuredModelGateway(
            transport=transport,
            definitions=(definition,),
            max_concurrency=1,
        ),
        definition=definition,
    )

    with pytest.raises(ModelTransportError) as captured:
        await generator.generate(_input(), context=_context())

    assert captured.value.kind is ModelProviderFailureKind.PROVIDER_FAILURE
    assert transport.calls == 1


@pytest.mark.asyncio
async def test_model_composition_registers_business_generator_without_using_id_only_task() -> None:
    transport = FakeStructuredModelTransport(
        _response('{"domain":"unsupported","action":"unsupported","arguments":{}}')
    )
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
    )
    try:
        output = await components.business_query_plan_generator.generate(
            _input(question="帮我查看上海的员工"),
            context=_context(),
        )
    finally:
        await components.aclose()

    assert output["action"] == "unsupported"
    assert transport.calls == 1
    assert transport.requests[0].task_id is ModelTaskId.BUSINESS_QUERY_PLAN
    assert build_action_selection_task_definition(timeout_ms=8000).task_version == "action-selection-v4"


@pytest.mark.asyncio
async def test_wrong_business_input_type_is_denied_before_transport() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    transport = FakeStructuredModelTransport()
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )

    result = await gateway.generate(
        definition=definition,
        input=cast(BusinessQueryPlanTaskInput, {"question": "查询员工"}),
        context=_context(),
    )

    assert result.failure_kind is ModelProviderFailureKind.INPUT_DENIED
    assert transport.calls == 0
