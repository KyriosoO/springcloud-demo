from __future__ import annotations

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.graph.state import (
    ActionSelectionDecision,
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.contracts import (
    StructuredFinishKind,
    StructuredModelResponse,
    StructuredToolCall,
)
from agent_runtime.model.deepseek.tools import UNSUPPORTED_TOOL_NAME, project_capability_tools
from agent_runtime.model.settings import ModelSettings
from tests.helpers import descriptor
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


QUESTION = "查询员工列表支持哪些条件"


def _response(*calls: StructuredToolCall, content: str | None = None) -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.TOOL_CALLS,
        content=content,
        tool_calls=tuple(calls),
        usage_total_tokens=11,
    )


async def _select(
    response: StructuredModelResponse,
) -> tuple[ActionSelectionDecision, FakeStructuredModelTransport]:
    transport = FakeStructuredModelTransport(response)
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
    )
    selected = await call_with_model_context(
        lambda: components.action_selector(
            ActionSelectionInput(question=QUESTION, descriptors=(descriptor(),))
        ),
        question=QUESTION,
    )
    return selected, transport


@pytest.mark.asyncio
async def test_single_registered_tool_becomes_untrusted_action_candidate() -> None:
    tool_name = project_capability_tools((descriptor(),)).tools[0].name

    decision, transport = await _select(
        _response(StructuredToolCall(name=tool_name, arguments_json='{"value":"x"}'))
    )

    assert decision.kind is ActionSelectionDecisionKind.CANDIDATE
    assert decision.candidate is not None
    assert decision.candidate.capability_id == "test.query"
    assert decision.candidate.arguments == {"value": "x"}
    assert transport.calls == 1
    assert transport.requests[0].tools[-1].name == UNSUPPORTED_TOOL_NAME
    assert "http" not in transport.requests[0].system_instruction.casefold()
    assert transport.requests[0].task_version == "action-selection-v2"
    assert "conform exactly" in transport.requests[0].system_instruction
    assert "empty JSON object" in transport.requests[0].system_instruction


@pytest.mark.asyncio
async def test_fixed_unsupported_tool_produces_unsupported_decision() -> None:
    decision, transport = await _select(
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json="{}"))
    )

    assert decision.kind is ActionSelectionDecisionKind.UNSUPPORTED
    assert transport.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _response(StructuredToolCall(name="cap_unknown_000000000000", arguments_json="{}")),
        _response(
            StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json="{}"),
            StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json="{}"),
        ),
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json='{"extra":1}')),
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json='{"x":1,"x":2}')),
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json="{}"), content="prose"),
    ],
)
async def test_unknown_multiple_conflicting_or_invalid_tool_output_fails_closed(
    response: StructuredModelResponse,
) -> None:
    decision, transport = await _select(response)

    assert decision.kind is ActionSelectionDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 1


def test_tool_names_are_deterministic_unique_and_irreversible() -> None:
    projection = project_capability_tools((descriptor("employee.query"), descriptor("transaction.query")))
    repeated = project_capability_tools((descriptor("employee.query"), descriptor("transaction.query")))

    assert projection.tools == repeated.tools
    assert len({tool.name for tool in projection.tools}) == 3
    assert all("." not in tool.name for tool in projection.tools)
    assert projection.capability_by_tool == repeated.capability_by_tool
