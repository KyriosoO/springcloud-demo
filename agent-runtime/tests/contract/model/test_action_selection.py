from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.capability_api.contracts import CapabilityDescriptor, JsonObject, canonical_json_bytes
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import ModelNodeFailureKind
from agent_runtime.model.contracts import (
    StructuredFinishKind,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolCall,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.dto import project_deepseek_request
from agent_runtime.model.deepseek.tools import (
    UNSUPPORTED_CAPABILITY_ID,
    InvalidCapabilityCatalog,
    project_capability_catalog,
)
from agent_runtime.model.settings import ModelSettings
from tests.helpers import descriptor
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


QUESTION = "查询交易记录支持哪些条件"


def _catalog_ids(catalog: JsonObject) -> tuple[str, ...]:
    entries = catalog.get("capabilities")
    assert isinstance(entries, tuple)
    identifiers: list[str] = []
    for entry in entries:
        assert isinstance(entry, Mapping)
        capability_id = entry.get("capability_id")
        assert isinstance(capability_id, str)
        identifiers.append(capability_id)
    return tuple(identifiers)


def _response(
    content: str | None,
    *,
    finish_kind: StructuredFinishKind = StructuredFinishKind.STOP,
    tool_calls: tuple[StructuredToolCall, ...] = (),
) -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=finish_kind,
        content=content,
        tool_calls=tool_calls,
        usage_total_tokens=11,
    )


async def _select(
    response: StructuredModelResponse,
    *,
    descriptors: tuple[CapabilityDescriptor, ...] | None = None,
    question: str = QUESTION,
) -> tuple[CapabilitySelectionDecision, FakeStructuredModelTransport]:
    transport = FakeStructuredModelTransport(response)
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
    )
    selected = await call_with_model_context(
        lambda: components.action_selector(
            CapabilitySelectionInput(
                question=question,
                descriptors=descriptors or (descriptor(),),
            )
        ),
        question=question,
    )
    return selected, transport


@pytest.mark.asyncio
async def test_exact_json_id_becomes_provider_neutral_candidate() -> None:
    decision, transport = await _select(_response(' \n {"capability_id":"test.query"}\t'))

    assert decision.kind is CapabilitySelectionDecisionKind.CANDIDATE
    assert decision.capability_id == "test.query"
    assert transport.calls == 1
    request = transport.requests[0]
    assert request.task_version == "action-selection-v4"
    assert request.tools == ()
    assert request.tool_mode is StructuredToolMode.NONE
    assert request.output_mode is StructuredOutputMode.JSON_OBJECT
    assert "JSON" in request.system_instruction
    assert '{"capability_id":"knowledge.query"}' in request.system_instruction
    assert "argument_schema" not in request.user_payload_json
    provider_payload = project_deepseek_request(request).payload
    assert provider_payload["response_format"] == {"type": "json_object"}
    assert "tools" not in provider_payload
    assert "tool_choice" not in provider_payload


@pytest.mark.asyncio
async def test_fixed_unsupported_id_produces_unsupported_decision() -> None:
    decision, transport = await _select(
        _response('{"capability_id":"agent_unsupported"}')
    )

    assert decision.kind is CapabilitySelectionDecisionKind.UNSUPPORTED
    assert transport.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _response('{"capability_id":"unknown.query"}'),
        _response('{"capability_id":"TEST.QUERY"}'),
        _response('{"capability_id":" test.query"}'),
        _response('{"capability_id":"test.query","extra":1}'),
        _response('{"capability_id":"test.query","capability_id":"test.query"}'),
        _response('{"capability_id":1}'),
        _response('{}'),
        _response('[]'),
        _response('prose {"capability_id":"test.query"}'),
        _response(''),
        _response('   '),
        _response(
            None,
            finish_kind=StructuredFinishKind.TOOL_CALLS,
            tool_calls=(StructuredToolCall(name="legacy_tool", arguments_json="{}"),),
        ),
    ],
)
async def test_non_exact_json_id_output_fails_closed(response: StructuredModelResponse) -> None:
    decision, transport = await _select(response)

    assert decision.kind is CapabilitySelectionDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 1


def test_catalog_is_stable_sorted_and_excludes_execution_schema() -> None:
    employee = descriptor("employee.detail", aliases=("员工详情", "employee profile"))
    transaction = descriptor("transaction.search", aliases=("交易查询",))
    changed_schema = replace(
        employee,
        argument_schema={
            "type": "object",
            "properties": {"employee_identifier": {"type": "string"}},
            "required": ("employee_identifier",),
            "additionalProperties": False,
        },
    )

    first = project_capability_catalog((transaction, employee))
    repeated = project_capability_catalog((changed_schema, transaction))

    assert first == repeated
    encoded = canonical_json_bytes(first)
    assert b"employee_identifier" not in encoded
    assert _catalog_ids(first) == (
        "employee.detail",
        "transaction.search",
        UNSUPPORTED_CAPABILITY_ID,
    )
    assert hashlib.sha256(encoded).digest() == hashlib.sha256(canonical_json_bytes(repeated)).digest()


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Use employee_identifier for lookup",
        "Use employeeIdentifier for lookup",
        "Call https://internal.example/query",
        "Requires ROLE_ADMIN authority",
        "Read Elasticsearch index",
        "Use EmployeeService method()",
        "Lookup E-1024",
        "Query amount ￥100.00",
    ],
)
def test_model_catalog_text_policy_rejects_unsafe_metadata(unsafe_text: str) -> None:
    unsafe = replace(descriptor(), description=unsafe_text)

    with pytest.raises(InvalidCapabilityCatalog, match="model.invalid_capability_catalog"):
        project_capability_catalog((unsafe,))


@pytest.mark.parametrize(
    "descriptors",
    [
        (replace(descriptor(), capability_id=UNSUPPORTED_CAPABILITY_ID),),
        (replace(descriptor(), capability_id="invalid"),),
        (descriptor(), descriptor()),
        (replace(descriptor(), aliases=("same alias", "same alias")),),
        (
            replace(descriptor("first.query"), aliases=("shared alias",)),
            replace(descriptor("second.query"), aliases=("shared alias",)),
        ),
    ],
)
def test_catalog_rejects_reserved_invalid_or_ambiguous_metadata(
    descriptors: tuple[CapabilityDescriptor, ...],
) -> None:
    with pytest.raises(InvalidCapabilityCatalog, match="model.invalid_capability_catalog"):
        project_capability_catalog(descriptors)


@pytest.mark.asyncio
async def test_invalid_catalog_maps_to_invalid_output_without_transport() -> None:
    unsafe = replace(descriptor(), description="Use employee_identifier")
    decision, transport = await _select(
        _response('{"capability_id":"test.query"}'),
        descriptors=(unsafe,),
    )

    assert decision.kind is CapabilitySelectionDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 0
