from __future__ import annotations

import asyncio

import pytest

from agent_runtime.knowledge.contracts import EvidenceEgressDenialReason, EvidenceStageKind, KnowledgeEvidenceContext
from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryOutput, KnowledgeSummaryPoint, SummaryOutcome
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import ModelTaskResult
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.evidence_helpers import evidence_input, synthetic_catalog
from tests.helpers import ManualCancellationSignal
from tests.model_helpers import call_with_model_context


class FakeGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, definition: object, input: object, context: object) -> ModelTaskResult[KnowledgeSummaryOutput]:
        del definition, input, context
        self.calls += 1
        return ModelTaskResult(
            output=KnowledgeSummaryOutput(
                outcome=SummaryOutcome.ANSWER,
                points=(KnowledgeSummaryPoint(evidence_ref="e1", quote="税务政策正文"),),
            )
        )


def _context() -> KnowledgeEvidenceContext:
    return KnowledgeEvidenceContext(
        request_id="req-1", correlation_id="corr-1", subject="user-1",
        deadline_monotonic=asyncio.get_running_loop().time() + 5,
        cancellation=ManualCancellationSignal(),
    )


@pytest.mark.asyncio
async def test_evidence_stage_builds_extractive_local_result_and_stops_core_egress() -> None:
    gateway = FakeGateway()
    stage = DefaultKnowledgeEvidenceStage(
        catalog=synthetic_catalog(), guard=QuestionEgressGuard(), context=ModelCallContextAccessor(),
        gateway=gateway,  # type: ignore[arg-type]
        definition=KnowledgeSummaryTaskV1.definition(),
    )

    result = await call_with_model_context(
        lambda: stage.build_result(input=evidence_input(), context=_context(), timeout_s=4)
    )

    assert result.kind is EvidenceStageKind.SUCCESS
    assert result.domain_result is not None and result.domain_result["answerSummary"] == "1. 税务政策正文"
    assert result.egress is not None and result.egress.disposition.value == "not_applicable"
    assert gateway.calls == 1


@pytest.mark.asyncio
async def test_question_denied_is_fail_closed_before_catalog_and_model() -> None:
    gateway = FakeGateway()
    stage = DefaultKnowledgeEvidenceStage(
        catalog=synthetic_catalog(), guard=QuestionEgressGuard(), context=ModelCallContextAccessor(),
        gateway=gateway,  # type: ignore[arg-type]
        definition=KnowledgeSummaryTaskV1.definition(),
    )

    result = await stage.build_result(input=evidence_input(question_denied=True), context=_context(), timeout_s=4)

    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
    assert result.denial_reason is EvidenceEgressDenialReason.QUESTION_DENIED
    assert gateway.calls == 0

