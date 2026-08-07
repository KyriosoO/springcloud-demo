from __future__ import annotations

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.contracts import StructuredFinishKind, StructuredModelResponse
from agent_runtime.model.settings import ModelSettings
from tests.helpers import descriptor
from tests.model_helpers import AcceptGroundingPolicy, FakeStructuredModelTransport


def _safe_payload() -> JsonObject:
    return {
        "schema_version": 1,
        "facts": (
            {"fact_id": "fact-0001", "value": "ACTIVE", "source": {"field_id": "status"}},
        ),
    }


@pytest.mark.asyncio
async def test_denied_or_unknown_action_question_never_calls_transport() -> None:
    transport = FakeStructuredModelTransport()
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
    )

    for question in ("员工编号 E-1001 的税务信息", "今天天气如何"):
        decision = await components.action_selector(
            CapabilitySelectionInput(question=question, descriptors=(descriptor(),))
        )
        assert decision.kind is CapabilitySelectionDecisionKind.FAILURE
        assert decision.failure is not None
        assert decision.failure.kind is ModelNodeFailureKind.INPUT_DENIED

    assert transport.calls == 0


@pytest.mark.asyncio
async def test_denied_answer_question_never_calls_transport_or_policy() -> None:
    transport = FakeStructuredModelTransport()
    policy = AcceptGroundingPolicy()
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": policy},
    )

    decision = await components.answer_generator(
        AnswerGenerationInput(
            question="税务政策，联系电话 13800138000",
            capability_id="test.query",
            safe_payload=_safe_payload(),
        )
    )

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INPUT_DENIED
    assert transport.calls == 0
    assert policy.calls == 0


@pytest.mark.asyncio
async def test_missing_bound_context_fails_closed_before_transport() -> None:
    transport = FakeStructuredModelTransport(
        StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"answer":"x","used_fact_ids":["fact-0001"],"unsupported_claims":[]}',
            tool_calls=(),
            usage_total_tokens=None,
        )
    )
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": AcceptGroundingPolicy()},
    )

    decision = await components.answer_generator(
        AnswerGenerationInput(
            question="现行增值税政策是什么",
            capability_id="test.query",
            safe_payload=_safe_payload(),
        )
    )

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 0
