from __future__ import annotations

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
    HybridActionSelectionNode,
)
from agent_runtime.graph.state import (
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    ActionSelectionInvalidCode,
)


class SelectorSpy:
    def __init__(self, decision: CapabilitySelectionDecision) -> None:
        self._decision = decision
        self.calls = 0

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        self.calls += 1
        return self._decision


def _node(selector: SelectorSpy) -> HybridActionSelectionNode:
    employee = employee_detail_definition()
    transaction = transaction_search_definition()
    return HybridActionSelectionNode(
        descriptors=(employee.descriptor, transaction.descriptor),
        resolvers=(employee.local_action_resolver, transaction.local_action_resolver),
        capability_selector=selector,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected_id", "expected_arguments"),
    [
        (
            "查询员工详情 员工标识=ABCDE",
            "employee.detail",
            {"employee_identifier": "ABCDE"},
        ),
        (
            "查询交易 交易类型=PAY，金额>100.10",
            "transaction.search",
            {"trans_type": "PAY", "amount_gt": "100.10"},
        ),
    ],
)
async def test_domain_local_candidate_skips_model_selection(
    question: str,
    expected_id: str,
    expected_arguments: dict[str, object],
) -> None:
    selector = SelectorSpy(
        CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)
    )
    node = _node(selector)

    decision = await node(
        ActionSelectionInput(
            question=question,
            descriptors=(employee_detail_definition().descriptor, transaction_search_definition().descriptor),
        )
    )

    assert decision.kind is ActionSelectionDecisionKind.CANDIDATE
    assert decision.candidate is not None
    assert decision.candidate.capability_id == expected_id
    assert decision.candidate.arguments == expected_arguments
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_recognized_invalid_business_question_does_not_fall_back_to_model() -> None:
    selector = SelectorSpy(
        CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)
    )
    node = _node(selector)

    decision = await node(
        ActionSelectionInput(
            question="查询交易 金额=1.000",
            descriptors=(employee_detail_definition().descriptor, transaction_search_definition().descriptor),
        )
    )

    assert decision.kind is ActionSelectionDecisionKind.INVALID_ARGUMENT
    assert decision.invalid_code is ActionSelectionInvalidCode.LOCAL_ACTION_INVALID
    assert selector.calls == 0
