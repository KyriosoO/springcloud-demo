from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import (
    EvidenceEgressDenialReason,
    EvidenceStageKind,
    KnowledgeEvidenceContext,
    RewriteMode,
    RewriteStageKind,
)
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryOutput,
    KnowledgeSummaryPoint,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.rewrite import (
    KnowledgeQuestionRewriter,
    KnowledgeRewriteInput,
    KnowledgeRewriteOutput,
    KnowledgeRewriteTaskV1,
)
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import ModelTaskResult
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.evidence_helpers import evidence_input, synthetic_catalog
from tests.helpers import ManualCancellationSignal
from tests.model_helpers import call_with_model_context


class RewriteGateway:
    def __init__(self) -> None:
        self.calls = 0
        self.inputs: list[KnowledgeRewriteInput] = []

    async def generate(
        self,
        *,
        definition: object,
        input: KnowledgeRewriteInput,
        context: object,
    ) -> ModelTaskResult[KnowledgeRewriteOutput]:
        del definition, context
        self.calls += 1
        self.inputs.append(input)
        return ModelTaskResult(output=KnowledgeRewriteOutput(candidates=(input.minimized_question,)))


class EvidenceGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        *,
        definition: object,
        input: object,
        context: object,
    ) -> ModelTaskResult[KnowledgeSummaryOutput]:
        del definition, input, context
        self.calls += 1
        return ModelTaskResult(
            output=KnowledgeSummaryOutput(
                outcome=SummaryOutcome.ANSWER,
                points=(KnowledgeSummaryPoint(evidence_ref="e1", quote="合成税务政策正文"),),
            )
        )


def _evidence_context() -> KnowledgeEvidenceContext:
    return KnowledgeEvidenceContext(
        request_id="req-question-egress",
        correlation_id="corr-question-egress",
        subject="synthetic-user",
        deadline_monotonic=asyncio.get_running_loop().time() + 5,
        cancellation=ManualCancellationSignal(),
    )


def _rewriter(gateway: RewriteGateway) -> KnowledgeQuestionRewriter:
    return KnowledgeQuestionRewriter(
        guard=QuestionEgressGuard(),
        semantic_guard=QuestionSemanticGuard(),
        gateway=gateway,  # type: ignore[arg-type]
        context=ModelCallContextAccessor(),
        definition=KnowledgeRewriteTaskV1.definition(),
        max_candidates=3,
        max_retrieval_query_chars=1024,
        allow_original_fallback=True,
    )


@pytest.mark.asyncio
async def test_public_knowledge_question_reaches_only_the_fake_rewrite_gateway() -> None:
    gateway = RewriteGateway()
    rewriter = _rewriter(gateway)

    result = await call_with_model_context(
        lambda: rewriter.rewrite(original_question="  现行增值税政策是什么  ", timeout_s=4),
        question="现行增值税政策是什么",
    )

    assert result.kind is RewriteStageKind.SUCCESS
    assert result.rewrite is not None
    assert result.rewrite.mode is RewriteMode.MODEL
    assert result.rewrite.question_egress_denied is False
    assert gateway.calls == 1
    assert gateway.inputs == [
        KnowledgeRewriteInput(minimized_question="现行增值税政策是什么", max_candidates=3)
    ]


@pytest.mark.parametrize(
    "question",
    (
        "税务政策是什么，身份证号 11010519491231002X",
        "今天天气如何",
    ),
)
@pytest.mark.asyncio
async def test_denied_or_unknown_knowledge_question_propagates_zero_call_to_evidence(question: str) -> None:
    rewrite_gateway = RewriteGateway()
    rewritten = await _rewriter(rewrite_gateway).rewrite(original_question=question, timeout_s=4)

    assert rewritten.kind is RewriteStageKind.SUCCESS
    assert rewritten.rewrite is not None
    assert rewritten.rewrite.mode is RewriteMode.ORIGINAL_FALLBACK
    assert rewritten.rewrite.question_egress_denied is True
    assert rewrite_gateway.calls == 0

    summary_gateway = EvidenceGateway()
    stage = DefaultKnowledgeEvidenceStage(
        catalog=synthetic_catalog(),
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=summary_gateway,  # type: ignore[arg-type]
        definition=KnowledgeSummaryTaskV1.definition(),
    )
    evidence = evidence_input()
    result = await stage.build_result(
        input=replace(
            evidence,
            original_question=question,
            selected_query=rewritten.rewrite.selected_query,
            question_policy_version=rewritten.rewrite.question_policy_version,
            question_egress_denied=rewritten.rewrite.question_egress_denied,
        ),
        context=_evidence_context(),
        timeout_s=4,
    )

    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
    assert result.denial_reason is EvidenceEgressDenialReason.QUESTION_DENIED
    assert summary_gateway.calls == 0
