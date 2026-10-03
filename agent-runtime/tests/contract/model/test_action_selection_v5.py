from __future__ import annotations

from dataclasses import replace
import json

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import ModelNodeFailureKind
from agent_runtime.model.contracts import (
    ModelInputDenied,
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolCall,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.action_selector import (
    ACTION_SELECTION_SYSTEM_INSTRUCTION,
    ActionSelectionTaskInput,
    build_action_selection_task_definition,
)
from agent_runtime.model.deepseek.action_selector_v5 import (
    ACTION_SELECTION_V5_SYSTEM_INSTRUCTION,
    TASK_VERSION,
    build_action_selection_v5_task_definition,
)
from agent_runtime.model.deepseek.tools import project_capability_catalog
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.helpers import descriptor
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


def test_v5_binds_both_definition_and_request_without_changing_v4_framing() -> None:
    input = ActionSelectionTaskInput(
        minimized_question="查找2099年的税收政策原文及出处",
        catalog=project_capability_catalog((descriptor("knowledge.query"),)),
    )
    legacy = build_action_selection_task_definition(timeout_ms=8000)
    current = build_action_selection_v5_task_definition(timeout_ms=8000)
    old_request, request = legacy.build_request(input), current.build_request(input)
    assert current.task_version == request.task_version == TASK_VERSION
    assert request.task_id is ModelTaskId.ACTION_SELECTION
    assert request == replace(old_request, task_version=TASK_VERSION,
                              system_instruction=ACTION_SELECTION_V5_SYSTEM_INSTRUCTION)
    assert legacy.task_version == old_request.task_version == "action-selection-v4"
    assert old_request.system_instruction == ACTION_SELECTION_SYSTEM_INSTRUCTION
    assert current.parse_response is not None
    assert current.timeout_ms == 8000 and current.max_input_bytes == 65536
    assert current.max_output_tokens == request.max_output_tokens == 512
    assert request.tools == () and request.tool_mode is StructuredToolMode.NONE
    assert request.output_mode is StructuredOutputMode.JSON_OBJECT
    assert json.loads(request.user_payload_json)["question"] == input.minimized_question
    assert "does not decide document existence" in request.system_instruction
    assert "outside every supplied capability" in request.system_instruction


def test_v5_reuses_input_size_denial_instead_of_truncating() -> None:
    definition = build_action_selection_v5_task_definition(timeout_ms=8000, max_input_bytes=32)
    with pytest.raises(ModelInputDenied, match="model.action_input_too_large"):
        definition.build_request(ActionSelectionTaskInput(
            minimized_question="税" * 64,
            catalog=project_capability_catalog((descriptor("knowledge.query"),)),
        ))


@pytest.mark.parametrize("mismatch", ["task", "input"])
@pytest.mark.parametrize("provider", [ModelProvider.STUB, ModelProvider.DEEPSEEK])
def test_wrong_definition_fails_before_provider_client_creation(monkeypatch, mismatch: str, provider) -> None:
    definition = build_action_selection_v5_task_definition(timeout_ms=8000)
    invalid = (replace(definition, task_id=ModelTaskId.KNOWLEDGE_SUMMARY) if mismatch == "task"
               else replace(definition, input_type=dict))
    allocations = 0

    def forbidden_client(settings: object) -> object:
        nonlocal allocations
        allocations += 1
        raise AssertionError("invalid definition allocated provider client")

    monkeypatch.setattr("agent_runtime.bootstrap.build_deepseek_http_client", forbidden_client)
    settings = ModelSettings(provider=provider, api_key=(
        ModelApiKey("synthetic-test-only") if provider is ModelProvider.DEEPSEEK else None))
    with pytest.raises(ValueError, match="model.action_task_definition_invalid"):
        LocalModelCompositionRoot.build(settings=settings, grounding_policies={},
                                       action_selection_definition=invalid)
    assert allocations == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("content,kind", [
    ('{"capability_id":"knowledge.query"}', CapabilitySelectionDecisionKind.CANDIDATE),
    ('{"capability_id":"agent_unsupported"}', CapabilitySelectionDecisionKind.UNSUPPORTED),
    ('{"capability_id":"unknown.query"}', CapabilitySelectionDecisionKind.FAILURE),
    ('{"capability_id":"knowledge.query","reason":"found"}', CapabilitySelectionDecisionKind.FAILURE),
    ('{"capability_id":"knowledge.query","capability_id":"knowledge.query"}', CapabilitySelectionDecisionKind.FAILURE),
    ('{"capability_id":1}', CapabilitySelectionDecisionKind.FAILURE),
    ('text {"capability_id":"knowledge.query"}', CapabilitySelectionDecisionKind.FAILURE),
    ('{}', CapabilitySelectionDecisionKind.FAILURE),
])
async def test_v5_preserves_catalog_exact_decode_and_unsupported_without_repair(content: str, kind) -> None:
    transport = FakeStructuredModelTransport(StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP, content=content, tool_calls=(), usage_total_tokens=0))
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(), transport=transport, grounding_policies={},
        action_selection_definition=build_action_selection_v5_task_definition(timeout_ms=8000),
    )
    question = "查找2099年的税收政策原文及出处"
    try:
        decision = await call_with_model_context(lambda: components.action_selector(
            CapabilitySelectionInput(question=question, descriptors=(descriptor("knowledge.query"),))),
            question=question)
    finally:
        await components.aclose()
    assert decision.kind is kind
    assert transport.calls == 1 and transport.requests[0].task_version == TASK_VERSION
    if kind is CapabilitySelectionDecisionKind.FAILURE:
        assert decision.failure is not None and decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT


@pytest.mark.parametrize("response", [
    StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content='',
                            tool_calls=(), usage_total_tokens=0),
    StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
                            tool_calls=(StructuredToolCall(name="invented", arguments_json="{}"),),
                            usage_total_tokens=0),
])
def test_v5_keeps_response_framing_fail_closed(response: StructuredModelResponse) -> None:
    from agent_runtime.model.contracts import InvalidModelOutput
    with pytest.raises(InvalidModelOutput, match="model.action_response_invalid"):
        build_action_selection_v5_task_definition(timeout_ms=8000).parse_response(response)
