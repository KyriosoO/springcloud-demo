from __future__ import annotations

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import ModelNodeFailureKind
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
) -> tuple[CapabilitySelectionDecision, FakeStructuredModelTransport]:
    transport = FakeStructuredModelTransport(response)
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
    )
    selected = await call_with_model_context(
        lambda: components.action_selector(
            CapabilitySelectionInput(question=QUESTION, descriptors=(descriptor(),))
        ),
        question=QUESTION,
    )
    return selected, transport


@pytest.mark.asyncio
async def test_single_registered_tool_becomes_capability_id_only_decision() -> None:
    tool_name = project_capability_tools((descriptor(),)).tools[0].name

    decision, transport = await _select(
        _response(StructuredToolCall(name=tool_name, arguments_json="{}"))
    )

    assert decision.kind is CapabilitySelectionDecisionKind.CANDIDATE
    assert decision.capability_id == "test.query"
    assert transport.calls == 1
    assert transport.requests[0].tools[-1].name == UNSUPPORTED_TOOL_NAME
    assert "http" not in transport.requests[0].system_instruction.casefold()
    assert transport.requests[0].task_version == "action-selection-v3"
    assert "exactly an empty JSON object" in transport.requests[0].system_instruction
    assert "identifiers" in transport.requests[0].system_instruction


@pytest.mark.asyncio
async def test_fixed_unsupported_tool_produces_unsupported_decision() -> None:
    decision, transport = await _select(
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json="{}"))
    )

    assert decision.kind is CapabilitySelectionDecisionKind.UNSUPPORTED
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
        _response(StructuredToolCall(name=project_capability_tools((descriptor(),)).tools[0].name, arguments_json='{"value":"x"}')),
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json='{"x":1,"x":2}')),
        _response(StructuredToolCall(name=UNSUPPORTED_TOOL_NAME, arguments_json="{}"), content="prose"),
    ],
)
async def test_unknown_multiple_conflicting_or_invalid_tool_output_fails_closed(
    response: StructuredModelResponse,
) -> None:
    decision, transport = await _select(response)

    assert decision.kind is CapabilitySelectionDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 1


def test_tool_names_are_deterministic_unique_and_irreversible() -> None:
    employee = descriptor("employee.detail", aliases=("员工详情",))
    transaction = descriptor("transaction.search", aliases=("交易查询",))
    projection = project_capability_tools((transaction, employee))
    repeated = project_capability_tools((employee, transaction))

    assert projection.tools == repeated.tools
    assert len({tool.name for tool in projection.tools}) == 3
    assert all("." not in tool.name for tool in projection.tools)
    assert projection.capability_by_tool == repeated.capability_by_tool
    assert [projection.capability_by_tool[tool.name] for tool in projection.tools[:-1]] == [
        "employee.detail",
        "transaction.search",
    ]
    assert all(
        tool.arguments_schema
        == {"type": "object", "properties": {}, "required": (), "additionalProperties": False}
        for tool in projection.tools
    )
    assert "员工详情" in projection.tools[0].description
