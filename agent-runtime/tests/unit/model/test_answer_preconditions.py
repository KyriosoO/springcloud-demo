from __future__ import annotations

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.graph.state import (
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.settings import ModelSettings
from tests.model_helpers import AcceptGroundingPolicy, FakeStructuredModelTransport, call_with_model_context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"schema_version": 1, "facts": ()},
        {"schema_version": 2, "facts": ({"fact_id": "fact-0001"},)},
        {"schema_version": 1, "facts": ({"value": "missing-id"},)},
        {
            "schema_version": 1,
            "facts": ({"fact_id": "fact-0001"}, {"fact_id": "fact-0001"}),
        },
    ],
)
async def test_invalid_safe_payload_is_zero_call(payload: JsonObject) -> None:
    transport = FakeStructuredModelTransport()
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": AcceptGroundingPolicy()},
    )

    decision = await call_with_model_context(
        lambda: components.answer_generator(
            AnswerGenerationInput(
                question="现行增值税政策是什么",
                capability_id="test.query",
                safe_payload=payload,
            )
        )
    )

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_missing_capability_grounding_policy_is_zero_call() -> None:
    transport = FakeStructuredModelTransport()
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
    )
    payload: JsonObject = {"schema_version": 1, "facts": ({"fact_id": "fact-0001"},)}

    decision = await call_with_model_context(
        lambda: components.answer_generator(
            AnswerGenerationInput(
                question="现行增值税政策是什么",
                capability_id="test.query",
                safe_payload=payload,
            )
        )
    )

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 0
