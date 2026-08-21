from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import (
    EvidenceEgressDenialReason,
    EvidenceStageCode,
    EvidenceStageKind,
    KnowledgeEvidenceContext,
)
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEgressDisposition,
    KnowledgeSummaryOutput,
    KnowledgeSummaryPoint,
    SummaryOutcome,
)
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


class FailingGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, definition: object, input: object, context: object) -> ModelTaskResult[KnowledgeSummaryOutput]:
        del definition, input, context
        self.calls += 1
        raise RuntimeError("synthetic provider detail must not escape")


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

    result = await stage.build_result(
        input=replace(
            evidence_input(),
            original_question="税务政策是什么，身份证号 11010519491231002X",
            question_egress_denied=False,
        ),
        context=_context(),
        timeout_s=4,
    )

    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
    assert result.denial_reason is EvidenceEgressDenialReason.QUESTION_DENIED
    assert gateway.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_reason"),
    (
        ("document-denied", EvidenceEgressDenialReason.DOCUMENT_DENIED),
        ("policy-missing", EvidenceEgressDenialReason.POLICY_MISSING),
        ("policy-conflict", EvidenceEgressDenialReason.POLICY_CONFLICT),
    ),
)
async def test_document_policy_negative_matrix_never_calls_summary(
    scenario: str,
    expected_reason: EvidenceEgressDenialReason,
) -> None:
    gateway = FakeGateway()
    source = evidence_input()
    catalog = synthetic_catalog(
        disposition=(
            KnowledgeEgressDisposition.DENY
            if scenario == "document-denied"
            else KnowledgeEgressDisposition.ALLOW_MINIMAL
        )
    )
    if scenario in {"policy-missing", "policy-conflict"}:
        ranked = source.batch.candidates[0]
        candidate = replace(
            ranked.candidate,
            document_id="missing-document" if scenario == "policy-missing" else ranked.candidate.document_id,
            policy_ref="conflicting-policy" if scenario == "policy-conflict" else ranked.candidate.policy_ref,
        )
        source = replace(
            source,
            batch=replace(source.batch, candidates=(replace(ranked, candidate=candidate),)),
        )
    stage = DefaultKnowledgeEvidenceStage(
        catalog=catalog,
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=gateway,  # type: ignore[arg-type]
        definition=KnowledgeSummaryTaskV1.definition(),
    )

    result = await stage.build_result(input=source, context=_context(), timeout_s=4)

    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
    assert result.denial_reason is expected_reason
    assert gateway.calls == 0


@pytest.mark.asyncio
async def test_unexpected_gateway_exception_maps_to_finite_summary_failure() -> None:
    gateway = FailingGateway()
    stage = DefaultKnowledgeEvidenceStage(
        catalog=synthetic_catalog(),
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=gateway,  # type: ignore[arg-type]
        definition=KnowledgeSummaryTaskV1.definition(),
    )

    result = await call_with_model_context(
        lambda: stage.build_result(input=evidence_input(), context=_context(), timeout_s=4)
    )

    assert result.kind is EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.stage_code is EvidenceStageCode.SUMMARY_FAILURE
    assert gateway.calls == 1
