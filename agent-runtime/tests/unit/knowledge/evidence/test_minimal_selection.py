from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import (
    DomainCandidateCount, FailedPath, PathFailureKind, PathRef, RetrievalCoverage, RetrievalPath,
)
from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityError
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, MinimalKnowledgeEvidenceInput
from agent_runtime.knowledge.evidence.minimal_selection import (
    MinimalEvidenceIntegrityVerifier, MinimalEvidenceSelector,
)
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput, KnowledgeQueryMode,
)
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgePlanBuilder, MinimalRetrievalSettings
from agent_runtime.knowledge.retrieval.contracts import PathRank
from agent_runtime.knowledge.retrieval.minimal_ranking import MinimalRankedBatch, MinimalRankedCandidate
from agent_runtime.model.question_policy import QUESTION_EGRESS_POLICY_VERSION
from tests.retrieval_helpers import candidate


def minimal_input(
    specs: tuple[tuple[str, str, str], ...] = (("d1", "tax.policy", "税务政策正文"),),
    *, domains: tuple[str, ...] = ("tax.policy",), mode: KnowledgeQueryMode = KnowledgeQueryMode.LOOKUP,
) -> MinimalKnowledgeEvidenceInput:
    question = KnowledgeQueryIntentInput(minimized_question="查询税务政策与法律原文")
    intent = KnowledgeQueryIntent(query_mode=mode, selected_domain_ids=domains,
        missing_conditions=(), outcome=KnowledgeIntentOutcome.SEARCH)
    plan = MinimalKnowledgePlanBuilder().build(question=question, intent=intent, settings=MinimalRetrievalSettings())
    ranked = tuple(MinimalRankedCandidate(
        candidate=replace(candidate(chunk=f"c{rank}", domain=domain, rank=rank, content=content), document_id=document),
        domain_ids=(domain,), path_ranks=(PathRank(logical_domain_id=domain, path=RetrievalPath.KEYWORD, rank=rank),),
        rerank_score=1.0 / rank, rank=rank,
    ) for rank, (document, domain, content) in enumerate(specs, 1))
    coverage = RetrievalCoverage(
        successful_paths=tuple(PathRef(logical_domain_id=domain, path=path)
            for domain in domains for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)),
        no_result_paths=(), failed_paths=(),
        candidate_count_by_domain=tuple(DomainCandidateCount(logical_domain_id=domain,
            count=sum(item.domain_ids == (domain,) for item in ranked)) for domain in domains),
        complete=True,
    )
    return MinimalKnowledgeEvidenceInput(
        question=question, intent=intent, plan=plan, coverage=coverage,
        question_policy_version=QUESTION_EGRESS_POLICY_VERSION, question_egress_denied=False,
        batch=MinimalRankedBatch(candidates=ranked, profile_version="tax-knowledge-search-v1",
            index_snapshot_ids=("a" * 64,)),
    )


def select(source: MinimalKnowledgeEvidenceInput):
    verified = MinimalEvidenceIntegrityVerifier().verify(input=source)
    return MinimalEvidenceSelector().select(candidates=verified, input=source,
        minimized_question=source.question.minimized_question, limits=KnowledgeEvidenceLimits.minimal_v1())


def test_domain_opportunity_then_global_fill_preserves_rank_and_fourth_same_document():
    specs = tuple(("d1", "tax.policy", f"税务政策正文{index}") for index in range(1, 9))
    specs += (("d2", "tax.law", "税收法律原文"),)
    result = select(minimal_input(specs, domains=("tax.policy", "tax.law")))
    assert result.sufficient and result.bundle is not None
    assert len(result.bundle.evidence) == 8
    assert [item.rank for item in result.bundle.evidence] == [1, 2, 3, 4, 5, 6, 7, 9]
    assert result.bundle.evidence[3].document_id == "d1"
    assert result.bundle.coverage.missing_domain_ids == ()
    assert len({item.evidence_id for item in result.bundle.evidence}) == 8


def test_mode_and_all_metadata_count_toward_fixed_byte_budget_without_truncation():
    body = "税" * 4096
    source = minimal_input(tuple((f"d{rank}", "tax.policy", body) for rank in range(1, 4)))
    result = select(source)
    assert result.sufficient and result.bundle is not None
    assert len(result.bundle.evidence) == 2
    assert all(item.content == body for item in result.bundle.evidence)
    assert result.bundle.maximal_summary_input_bytes <= 32768


@pytest.mark.parametrize("fault", ["late_hash", "bad_source", "duplicate_identity", "snapshot", "mode", "question", "path", "failed_path_type", "rank_from_failed_path", "rank_from_no_result_path"])
def test_complete_ranked_batch_is_verified_before_any_selection(fault):
    source = minimal_input(tuple((f"d{rank}", "tax.policy", f"税务政策正文{rank}") for rank in range(1, 10)))
    ranked = list(source.batch.candidates)
    if fault == "late_hash":
        ranked[8] = replace(ranked[8], candidate=replace(ranked[8].candidate, content_sha256="f" * 64))
    elif fault == "bad_source":
        ranked[8] = replace(ranked[8], candidate=replace(ranked[8].candidate, source_url="\x00secret"))
    elif fault == "duplicate_identity":
        ranked[8] = replace(ranked[8], candidate=replace(ranked[0].candidate, source_rank=9))
    elif fault == "snapshot":
        ranked[8] = replace(ranked[8], candidate=replace(ranked[8].candidate, index_snapshot_id="b" * 64))
    elif fault == "mode":
        source = replace(source, intent=replace(source.intent, query_mode=KnowledgeQueryMode.EXPLANATION))
    elif fault == "question":
        source = replace(source, question=KnowledgeQueryIntentInput(minimized_question="查询增值税政策"))
    elif fault == "path":
        ranked[8] = replace(ranked[8], path_ranks=(PathRank(
            logical_domain_id="tax.law", path=RetrievalPath.KEYWORD, rank=9),))
    elif fault == "failed_path_type":
        source = replace(source, coverage=replace(source.coverage,
            failed_paths=(PathRef(logical_domain_id="tax.policy", path=RetrievalPath.KEYWORD),)))
    elif fault == "rank_from_failed_path":
        source = replace(source, coverage=replace(source.coverage,
            successful_paths=(PathRef(logical_domain_id="tax.policy", path=RetrievalPath.VECTOR),),
            failed_paths=(FailedPath(logical_domain_id="tax.policy", path=RetrievalPath.KEYWORD,
                failure_kind=PathFailureKind.DOWNSTREAM_FAILURE),), complete=False))
    elif fault == "rank_from_no_result_path":
        source = replace(source, coverage=replace(source.coverage,
            successful_paths=(PathRef(logical_domain_id="tax.policy", path=RetrievalPath.VECTOR),),
            no_result_paths=(PathRef(logical_domain_id="tax.policy", path=RetrievalPath.KEYWORD),)))
    if fault in {"late_hash", "bad_source", "duplicate_identity", "snapshot", "path"}:
        source = replace(source, batch=replace(source.batch, candidates=tuple(ranked)))
    with pytest.raises(EvidenceIntegrityError):
        select(source)


def test_missing_selected_domain_is_insufficient_even_when_other_domain_has_evidence():
    source = minimal_input((("d1", "tax.policy", "税务政策正文"),), domains=("tax.policy", "tax.law"))
    result = select(source)
    assert not result.sufficient and result.bundle is None
