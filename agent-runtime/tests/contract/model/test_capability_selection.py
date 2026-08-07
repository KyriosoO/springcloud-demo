from __future__ import annotations

from dataclasses import fields

import pytest

from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
    CapabilitySelectionNode,
)
from agent_runtime.graph.state import ModelNodeFailure, ModelNodeFailureKind
from tests.helpers import descriptor


class IdOnlySelector:
    def __init__(self, decision: CapabilitySelectionDecision) -> None:
        self.decision = decision

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        return self.decision


def test_candidate_decision_contains_only_canonical_id_and_no_arguments() -> None:
    decision = CapabilitySelectionDecision(
        kind=CapabilitySelectionDecisionKind.CANDIDATE,
        capability_id="knowledge.query",
    )

    assert {item.name for item in fields(CapabilitySelectionDecision)} == {
        "kind",
        "capability_id",
        "failure",
    }
    assert not hasattr(decision, "arguments")
    assert not hasattr(decision, "candidate")
    assert not hasattr(decision, "final_outcome")


@pytest.mark.parametrize(
    "values",
    [
        {"kind": CapabilitySelectionDecisionKind.CANDIDATE},
        {"kind": CapabilitySelectionDecisionKind.CANDIDATE, "capability_id": ""},
        {
            "kind": CapabilitySelectionDecisionKind.CANDIDATE,
            "capability_id": "knowledge.query",
            "failure": ModelNodeFailure(kind=ModelNodeFailureKind.INVALID_OUTPUT),
        },
        {"kind": CapabilitySelectionDecisionKind.UNSUPPORTED, "capability_id": "knowledge.query"},
        {"kind": CapabilitySelectionDecisionKind.FAILURE},
    ],
)
def test_mutually_exclusive_decision_branches_reject_invalid_shapes(values: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="core.invalid_model_node_decision"):
        CapabilitySelectionDecision(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_selector_protocol_accepts_only_selection_input_and_id_only_decision() -> None:
    expected = CapabilitySelectionDecision(
        kind=CapabilitySelectionDecisionKind.CANDIDATE,
        capability_id="knowledge.query",
    )
    selector: CapabilitySelectionNode = IdOnlySelector(expected)
    selection_input = CapabilitySelectionInput(
        question="tax policy",
        descriptors=(descriptor("knowledge.query"),),
    )

    actual = await selector(selection_input)

    assert actual is expected
    assert {item.name for item in fields(CapabilitySelectionInput)} == {"question", "descriptors"}
