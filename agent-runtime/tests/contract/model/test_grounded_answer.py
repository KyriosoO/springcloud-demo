from __future__ import annotations

import json

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.graph.state import (
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.contracts import StructuredFinishKind, StructuredModelResponse
from agent_runtime.model.settings import ModelSettings
from tests.model_helpers import AcceptGroundingPolicy, FakeStructuredModelTransport, call_with_model_context


QUESTION = "现行增值税政策是什么"
PAYLOAD = {
    "schema_version": 1,
    "facts": [
        {
            "fact_id": "fact-0001",
            "value": "ACTIVE",
            "source": {"record_ref": "record-0001", "field_id": "status"},
        }
    ],
    "coverage": {"truncated": False},
}


def _response(body: dict[str, object]) -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content=json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        tool_calls=(),
        usage_total_tokens=18,
    )


async def _generate(response: StructuredModelResponse, policy: AcceptGroundingPolicy):
    transport = FakeStructuredModelTransport(response)
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": policy},
    )
    decision = await call_with_model_context(
        lambda: components.answer_generator(
            AnswerGenerationInput(
                question=QUESTION,
                capability_id="test.query",
                safe_payload=PAYLOAD,
            )
        ),
        question=QUESTION,
    )
    return decision, transport


@pytest.mark.asyncio
async def test_accepts_only_candidate_accepted_by_capability_policy() -> None:
    policy = AcceptGroundingPolicy()

    decision, transport = await _generate(
        _response(
            {
                "answer": "状态为 ACTIVE [fact-0001]。",
                "used_fact_ids": ["fact-0001"],
                "unsupported_claims": [],
            }
        ),
        policy,
    )

    assert decision.kind is AnswerGenerationDecisionKind.ANSWER
    assert decision.answer_text == "状态为 ACTIVE [fact-0001]。"
    assert policy.calls == 1
    assert policy.inputs[0].candidate.used_fact_ids == ("fact-0001",)
    assert transport.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {
            "answer": "未知事实",
            "used_fact_ids": ["fact-9999"],
            "unsupported_claims": [],
        },
        {
            "answer": "含未支持主张",
            "used_fact_ids": ["fact-0001"],
            "unsupported_claims": ["invented"],
        },
        {
            "answer": "https://untrusted.example",
            "used_fact_ids": ["fact-0001"],
            "unsupported_claims": [],
        },
        {
            "answer": "额外字段",
            "used_fact_ids": ["fact-0001"],
            "unsupported_claims": [],
            "extra": "forbidden",
        },
    ],
)
async def test_common_schema_fact_subset_and_output_rules_fail_closed(body: dict[str, object]) -> None:
    decision, _ = await _generate(_response(body), AcceptGroundingPolicy())

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy",
    [
        AcceptGroundingPolicy(accepted=False),
        AcceptGroundingPolicy(failure=RuntimeError("sensitive provider body")),
    ],
)
async def test_policy_rejection_or_exception_discards_entire_candidate(
    policy: AcceptGroundingPolicy,
) -> None:
    decision, _ = await _generate(
        _response(
            {
                "answer": "状态为 ACTIVE [fact-0001]。",
                "used_fact_ids": ["fact-0001"],
                "unsupported_claims": [],
            }
        ),
        policy,
    )

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.answer_text is None
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT


@pytest.mark.asyncio
async def test_policy_returning_an_untyped_decision_fails_closed() -> None:
    class InvalidPolicy:
        def validate(self, input: object) -> object:
            del input
            return object()

    transport = FakeStructuredModelTransport(
        _response(
            {
                "answer": "状态为 ACTIVE [fact-0001]。",
                "used_fact_ids": ["fact-0001"],
                "unsupported_claims": [],
            }
        )
    )
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": InvalidPolicy()},  # type: ignore[dict-item]
    )

    decision = await call_with_model_context(
        lambda: components.answer_generator(
            AnswerGenerationInput(
                question=QUESTION,
                capability_id="test.query",
                safe_payload=PAYLOAD,
            )
        ),
        question=QUESTION,
    )

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
