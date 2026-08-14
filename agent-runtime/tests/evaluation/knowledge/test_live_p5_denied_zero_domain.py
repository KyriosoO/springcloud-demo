from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest

from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    FailureSource,
)
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.contracts import (
    EvidenceStageResult,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
    KnowledgeEvidenceStage,
    KnowledgeQueryArguments,
    KnowledgeQuestionRewriteStage,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    KnowledgeRetrievalStage,
    RetrievalStageResult,
)
from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.rewrite import (
    KnowledgeQuestionRewriter,
    KnowledgeRewriteInput,
    KnowledgeRewriteOutput,
    KnowledgeRewriteTaskV1,
)
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import ModelTaskResult
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.question_policy import QUESTION_EGRESS_POLICY_VERSION
from tests.evaluation.knowledge.executor import IdentityQuestionRewriter
from tests.evaluation.knowledge.contracts import EvaluationCase
from tests.evaluation.knowledge.live_executor import LiveKnowledgeEvaluationCaseExecutor
from tests.evaluation.knowledge.run_evaluation import load_dataset
from tests.helpers import scope


DATASET_V2 = Path(__file__).with_name("representative_questions.v2.jsonl")
POLICY_VERSION = QUESTION_EGRESS_POLICY_VERSION
DENIAL_CODE = "knowledge.rewrite_input_denied"


class FakeModelTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        *,
        definition: object,
        input: KnowledgeRewriteInput,
        context: object,
    ) -> ModelTaskResult[KnowledgeRewriteOutput]:
        del definition, input, context
        self.calls += 1
        raise AssertionError("security-negative input must not reach the model transport")


class ForbiddenRetrievalStage(KnowledgeRetrievalStage[object]):
    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[object]:
        del plan, context, timeout_s
        self.calls += 1
        raise AssertionError("zero-domain input must not reach retrieval")


class ForbiddenEvidenceStage(KnowledgeEvidenceStage[object]):
    def __init__(self) -> None:
        self.calls = 0

    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[object],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult:
        del input, context, timeout_s
        self.calls += 1
        raise AssertionError("zero-domain input must not reach evidence")


def _settings() -> KnowledgeSettings:
    return KnowledgeSettings.from_env(
        {
            "AGENT_KNOWLEDGE_ENABLED": "true",
            "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
            "AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK": "true",
        }
    )


def _primary_rewriter(transport: FakeModelTransport) -> KnowledgeQuestionRewriter:
    return KnowledgeQuestionRewriter(
        guard=QuestionEgressGuard(),
        semantic_guard=QuestionSemanticGuard(),
        gateway=transport,  # type: ignore[arg-type]
        context=ModelCallContextAccessor(),
        definition=KnowledgeRewriteTaskV1.definition(),
        max_candidates=3,
        max_retrieval_query_chars=1024,
        allow_original_fallback=True,
    )


def _capability(
    *,
    rewriter: KnowledgeQuestionRewriteStage,
    retrieval: ForbiddenRetrievalStage,
    evidence: ForbiddenEvidenceStage,
) -> KnowledgeQueryCapability[object]:
    settings = _settings()
    return KnowledgeQueryCapability(
        settings=settings,
        enabled_domains=build_tax_domain_catalog().enabled(settings.enabled_domain_ids),
        rewriter=rewriter,
        selector=DeterministicDomainSelector(),
        planner=KnowledgeRetrievalPlanBuilder(),
        retrieval=retrieval,
        evidence=evidence,
    )


def _security_cases() -> tuple[EvaluationCase, ...]:
    _, _, cases = load_dataset(DATASET_V2)
    return tuple(case for case in cases if case.category == "security_negative")


def _pack_with_strict_live_executor(
    *,
    variant: Literal["primary", "rewrite_ablation"],
    case: EvaluationCase,
    result: CapabilityResult,
) -> object:
    executor = cast(Any, object.__new__(LiveKnowledgeEvaluationCaseExecutor))
    executor.variant = variant
    executor.model_transport = SimpleNamespace(rewrite_calls=0, summary_calls=0)
    executor.retrieval = SimpleNamespace(last_plan=None, last_result=None)
    executor.search = SimpleNamespace(results={}, requests=[])
    executor.fusion = SimpleNamespace(last_fused=())
    executor.embedding = SimpleNamespace(calls=0)
    executor.rerank = SimpleNamespace(calls=0)
    executor.rewriter = SimpleNamespace(last_result=None)
    return executor._pack_result(
        case=case,
        before={"rewrite": 0, "summary": 0, "embedding": 0, "rerank": 0},
        result_box=[result],
    )


@pytest.mark.parametrize("variant", ("primary", "rewrite_ablation"))
@pytest.mark.parametrize("case", _security_cases(), ids=lambda case: cast(EvaluationCase, case).case_id)
@pytest.mark.asyncio
async def test_v2_security_negative_is_policy_denied_before_zero_domain(
    variant: Literal["primary", "rewrite_ablation"],
    case: EvaluationCase,
) -> None:
    transport = FakeModelTransport()
    retrieval = ForbiddenRetrievalStage()
    evidence = ForbiddenEvidenceStage()
    rewriter: KnowledgeQuestionRewriteStage = (
        _primary_rewriter(transport) if variant == "primary" else IdentityQuestionRewriter()
    )
    capability = _capability(rewriter=rewriter, retrieval=retrieval, evidence=evidence)

    result = await capability.handle(KnowledgeQueryArguments(), scope(case.question).context)
    packed = cast(Any, _pack_with_strict_live_executor(variant=variant, case=case, result=result))

    assert result.status is CapabilityStatus.MODEL_EGRESS_DENIED
    assert result.failure is not None
    assert result.failure.code == DENIAL_CODE
    assert result.failure.source is FailureSource.POLICY
    assert result.egress.disposition is EgressDisposition.DENIED
    assert result.egress.policy_version == POLICY_VERSION
    assert result.egress.reason_code == DENIAL_CODE
    assert packed.result.terminal_status == CapabilityStatus.MODEL_EGRESS_DENIED.value
    assert packed.result.model_call_counts.rewrite == 0
    assert packed.result.model_call_counts.summary == 0
    assert transport.calls == 0
    assert retrieval.calls == evidence.calls == 0


@pytest.mark.asyncio
async def test_non_denied_zero_domain_remains_no_result() -> None:
    transport = FakeModelTransport()
    retrieval = ForbiddenRetrievalStage()
    evidence = ForbiddenEvidenceStage()
    capability = _capability(
        rewriter=IdentityQuestionRewriter(),
        retrieval=retrieval,
        evidence=evidence,
    )

    result = await capability.handle(
        KnowledgeQueryArguments(),
        scope("员工列表支持哪些字段？").context,
    )

    assert result.status is CapabilityStatus.NO_RESULT
    assert result.failure is None
    assert result.egress.disposition is EgressDisposition.NOT_APPLICABLE
    assert result.domain_result is not None
    assert result.domain_result["reason"] == "no_matching_domain"
    assert transport.calls == 0
    assert retrieval.calls == evidence.calls == 0
