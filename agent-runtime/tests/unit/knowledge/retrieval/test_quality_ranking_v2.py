from dataclasses import replace
import asyncio

import pytest

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V2, DomainCandidateCount, RetrievalStageKind,
)
from agent_runtime.knowledge.evidence.builder import (
    DeterministicEvidenceSelector, EvidenceIntegrityError, EvidenceIntegrityVerifier,
)
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeCandidate, RerankScore
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.evidence_helpers import evidence_input
from tests.retrieval_helpers import candidate
from tests.unit.knowledge.retrieval.test_quality_ranking import DomainRerank, DomainSearch, multi_plan
from tests.unit.knowledge.retrieval.test_stage import FakeEmbedding


@pytest.mark.asyncio
@pytest.mark.parametrize("same_parent", [False, True])
async def test_semantic_order_and_domain_coverage_replace_keyword_occupancy(same_parent):
    class ParentSearch(DomainSearch):
        async def search(self, **kwargs):
            result = await super().search(**kwargs)
            if same_parent:
                result = replace(result, candidates=tuple(replace(item, document_id=item.domain_id)
                                                         for item in result.candidates))
            return result

    context, plan = multi_plan()
    plan = replace(plan, quality_version=KNOWLEDGE_QUALITY_VERSION_V2)
    embedding, search, rerank = FakeEmbedding(), ParentSearch(), DomainRerank()
    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=embedding, rerank=rerank).execute(
        plan=plan, context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert embedding.calls == 2 and len(search.calls) == 4 and len(rerank.queries) == 2
    assert [item.candidate.chunk_id for item in result.batch.candidates] == [
        f"{domain}-{i}" for i in (4, 3, 2, 1) for domain in plan.selected_domain_ids]
    assert [item.coverage_anchor for item in result.batch.candidates] == [True] * 2 + [False] * 6
    source = replace(evidence_input(), batch=result.batch, coverage=result.coverage,
                     selected_domain_ids=plan.selected_domain_ids, quality_version=KNOWLEDGE_QUALITY_VERSION_V2)
    selected = select(source)
    assert selected.sufficient and len(selected.bundle.evidence) == 8
    assert selected.bundle.coverage.missing_domain_ids == ()
    if same_parent:
        assert sum(item.document_id == "tax.policy" for item in selected.bundle.evidence) == 4


def select(source, limits=None):
    return DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="公开条款查询", limits=limits or KnowledgeEvidenceLimits.quality_v2())


def same_parent_source(count, *, repeat=1):
    source = evidence_input()
    items = tuple(RankedKnowledgeCandidate(
        candidate=replace(candidate(chunk=f"c{i}", rank=i, content=f"公开合成条款{i}。" * repeat), document_id="same-parent"),
        domain_ids=("tax.policy",), rerank_score=float(-i), rank=i, coverage_anchor=i == 1,
    ) for i in range(1, count + 1))
    return replace(source, quality_version=KNOWLEDGE_QUALITY_VERSION_V2,
        batch=replace(source.batch, candidates=items), coverage=replace(source.coverage,
            candidate_count_by_domain=(DomainCandidateCount(logical_domain_id="tax.policy", count=count),)))


@pytest.mark.parametrize("count", [3, 4, 5, 8, 9, 20])
def test_same_parent_relevance_is_bounded_by_total_not_historical_quota(count):
    selected = select(same_parent_source(count))
    assert selected.sufficient
    assert [item.rank for item in selected.bundle.evidence] == list(range(1, min(count, 8) + 1))
    assert selected.bundle.maximal_summary_input_bytes <= 32768


def test_large_optional_clauses_cannot_exceed_byte_budget():
    selected = select(same_parent_source(8, repeat=400))
    assert selected.sufficient and len(selected.bundle.evidence) < 8
    assert selected.bundle.maximal_summary_input_bytes <= 32768


@pytest.mark.parametrize("limits", [KnowledgeEvidenceLimits.v1(), KnowledgeEvidenceLimits.quality_v1(),
                                  replace(KnowledgeEvidenceLimits.quality_v2(), max_evidence=9)])
def test_v2_rejects_mismatched_or_expanded_limits(limits):
    with pytest.raises(EvidenceIntegrityError, match="limits_version_mismatch"):
        select(same_parent_source(4), limits)


def test_unknown_version_and_excessive_anchors_are_rejected():
    source = same_parent_source(4)
    with pytest.raises(EvidenceIntegrityError, match="unknown_quality_version"):
        select(replace(source, quality_version="unknown"))
    with pytest.raises(EvidenceIntegrityError, match="evidence_integrity_failed"):
        select(replace(source, batch=replace(source.batch, candidates=tuple(
            replace(item, coverage_anchor=True) for item in source.batch.candidates))))


@pytest.mark.asyncio
async def test_denial_still_precedes_v2_rerank():
    context, plan = multi_plan()
    search, rerank = DomainSearch(denied=True), DomainRerank()
    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=FakeEmbedding(), rerank=rerank).execute(
        plan=replace(plan, quality_version=KNOWLEDGE_QUALITY_VERSION_V2), context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.FORBIDDEN
    assert len(search.calls) == 4 and rerank.queries == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["nan", "duplicate", "boolean_index", "cancel"])
async def test_bad_rerank_or_cancel_never_starts_next_domain(failure):
    class InvalidRerank:
        calls = 0

        async def rerank(self, *, query, candidates, timeout_s):
            self.calls += 1
            if failure == "cancel":
                raise asyncio.CancelledError()
            return tuple(RerankScore(candidate_index=(True if failure == "boolean_index" else
                                                      0 if failure == "duplicate" else i),
                                    score=float("nan") if failure == "nan" else 1.0)
                         for i in range(len(candidates)))

    context, plan = multi_plan()
    rerank = InvalidRerank()
    operation = DefaultKnowledgeRetrievalStage(search=DomainSearch(), embedding=FakeEmbedding(), rerank=rerank).execute(
        plan=replace(plan, quality_version=KNOWLEDGE_QUALITY_VERSION_V2), context=context, timeout_s=4)
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await operation
    else:
        assert (await operation).kind is RetrievalStageKind.DOWNSTREAM_FAILURE
    assert rerank.calls == 1


def test_v2_changes_only_parent_quota_and_keeps_historical_limits():
    legacy = KnowledgeEvidenceLimits.v1()
    assert KnowledgeEvidenceLimits.quality_v1() == replace(legacy, max_per_document=3)
    assert KnowledgeEvidenceLimits.quality_v2() == replace(legacy, max_per_document=8)


@pytest.mark.asyncio
async def test_shared_domain_top_is_emitted_once_without_losing_a_rotation_turn():
    class SharedSearch(DomainSearch):
        async def search(self, **kwargs):
            result = await super().search(**kwargs)
            return replace(result, candidates=tuple(
                replace(item, document_id="shared", chunk_id="shared") if item.source_rank == 4 else item
                for item in result.candidates))

    context, plan = multi_plan()
    result = await DefaultKnowledgeRetrievalStage(
        search=SharedSearch(), embedding=FakeEmbedding(), rerank=DomainRerank()).execute(
        plan=replace(plan, quality_version=KNOWLEDGE_QUALITY_VERSION_V2), context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert [item.candidate.chunk_id for item in result.batch.candidates] == [
        "shared", "tax.policy-3", "tax.law-3", "tax.policy-2", "tax.law-2", "tax.policy-1", "tax.law-1"]
    assert result.batch.candidates[0].domain_ids == ("tax.policy", "tax.law")
    assert sum(item.coverage_anchor for item in result.batch.candidates) == 1


@pytest.mark.asyncio
async def test_equal_scores_use_rrf_then_stable_chunk_order():
    class TiedRerank(DomainRerank):
        async def rerank(self, *, query, candidates, timeout_s):
            return tuple(RerankScore(candidate_index=i, score=1.0) for i in range(len(candidates)))

    context, plan = multi_plan()
    result = await DefaultKnowledgeRetrievalStage(
        search=DomainSearch(), embedding=FakeEmbedding(), rerank=TiedRerank()).execute(
        plan=replace(plan, quality_version=KNOWLEDGE_QUALITY_VERSION_V2), context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert [item.candidate.chunk_id for item in result.batch.candidates] == [
        f"{domain}-{i}" for i in (1, 2, 3, 4) for domain in plan.selected_domain_ids]
