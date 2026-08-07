from __future__ import annotations

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus, EgressDisposition, ModelEgressResult
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.contracts import (
    DomainCandidateCount,
    EvidenceStageKind,
    EvidenceStageResult,
    KnowledgeQueryArguments,
    PathRef,
    RetrievalCoverage,
    RetrievalPath,
    RetrievalStageKind,
    RetrievalStageResult,
    RewriteCandidate,
    RewriteCandidateSource,
    RewriteMode,
    RewriteResult,
    RewriteStageKind,
    RewriteStageResult,
)
from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector
from agent_runtime.knowledge.fakes import FakeEvidenceStage, FakeRetrievalStage, FakeRewriteStage
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.settings import KnowledgeSettings
from tests.helpers import scope


@pytest.mark.asyncio
async def test_flow_passes_opaque_batch_and_strips_token_from_evidence_context() -> None:
    settings = KnowledgeSettings.from_env(
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"}
    )
    rewrite = FakeRewriteStage(
        RewriteStageResult(
            kind=RewriteStageKind.SUCCESS,
            rewrite=RewriteResult(
                original_question="现行增值税政策是什么",
                selected_query="现行增值税政策",
                candidates=(RewriteCandidate(text="现行增值税政策", source=RewriteCandidateSource.MODEL, ordinal=1),),
                mode=RewriteMode.MODEL,
                question_policy_version="question-egress-v1",
                question_egress_denied=False,
            ),
        )
    )
    batch = object()
    coverage = RetrievalCoverage(
        successful_paths=(
            PathRef(logical_domain_id="tax.policy", path=RetrievalPath.KEYWORD),
            PathRef(logical_domain_id="tax.policy", path=RetrievalPath.VECTOR),
        ),
        no_result_paths=(), failed_paths=(),
        candidate_count_by_domain=(DomainCandidateCount(logical_domain_id="tax.policy", count=1),),
        complete=True,
    )
    retrieval = FakeRetrievalStage[object](
        RetrievalStageResult(kind=RetrievalStageKind.SUCCESS, batch=batch, coverage=coverage)
    )
    evidence = FakeEvidenceStage[object](
        EvidenceStageResult(
            kind=EvidenceStageKind.SUCCESS,
            domain_result={"answer": "受控摘要"},
            egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        )
    )
    capability = KnowledgeQueryCapability[object](
        settings=settings,
        enabled_domains=build_tax_domain_catalog().enabled(settings.enabled_domain_ids),
        rewriter=rewrite,
        selector=DeterministicDomainSelector(),
        planner=KnowledgeRetrievalPlanBuilder(),
        retrieval=retrieval,
        evidence=evidence,
    )

    result = await capability.handle(KnowledgeQueryArguments(), scope("现行增值税政策是什么").context)

    assert result.status is CapabilityStatus.SUCCESS
    assert evidence.inputs[0].batch is batch
    assert hasattr(retrieval.contexts[0], "user_token")
    assert not hasattr(evidence.contexts[0], "user_token")
    assert not hasattr(evidence.contexts[0], "original_question")


def test_coverage_rejects_duplicate_domain_counts_and_non_boolean_complete() -> None:
    settings = KnowledgeSettings.from_env(
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"}
    )
    capability = KnowledgeQueryCapability[object](
        settings=settings,
        enabled_domains=build_tax_domain_catalog().enabled(settings.enabled_domain_ids),
        rewriter=FakeRewriteStage(RewriteStageResult(kind=RewriteStageKind.FAILURE)),
        selector=DeterministicDomainSelector(),
        planner=KnowledgeRetrievalPlanBuilder(),
        retrieval=FakeRetrievalStage[object](RetrievalStageResult(kind=RetrievalStageKind.NO_RESULT)),
        evidence=FakeEvidenceStage[object](EvidenceStageResult(kind=EvidenceStageKind.NO_RESULT)),
    )
    rewrite = RewriteResult(
        original_question="税务政策", selected_query="税务政策",
        candidates=(RewriteCandidate(text="税务政策", source=RewriteCandidateSource.MODEL, ordinal=1),),
        mode=RewriteMode.MODEL, question_policy_version="question-egress-v1", question_egress_denied=False,
    )
    domains = DeterministicDomainSelector().select(
        original_question="税务政策",
        enabled_domains=build_tax_domain_catalog().enabled(settings.enabled_domain_ids),
    )
    plan = KnowledgeRetrievalPlanBuilder().build(rewrite=rewrite, domains=domains, settings=settings)
    paths = tuple(PathRef(logical_domain_id=item.logical_domain_id, path=item.path) for item in plan.items)
    duplicate_counts = RetrievalCoverage(
        successful_paths=(), no_result_paths=paths, failed_paths=(),
        candidate_count_by_domain=(
            DomainCandidateCount(logical_domain_id="tax.policy", count=0),
            DomainCandidateCount(logical_domain_id="tax.policy", count=0),
        ),
        complete=True,
    )
    non_boolean = RetrievalCoverage(
        successful_paths=(), no_result_paths=paths, failed_paths=(),
        candidate_count_by_domain=(DomainCandidateCount(logical_domain_id="tax.policy", count=0),),
        complete=1,  # type: ignore[arg-type]
    )

    assert not capability._valid_coverage(duplicate_counts, plan, require_candidates=False)
    assert not capability._valid_coverage(non_boolean, plan, require_candidates=False)
