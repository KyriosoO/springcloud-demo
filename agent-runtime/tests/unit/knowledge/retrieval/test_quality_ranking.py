from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION, RetrievalPath, RetrievalPlanItem, RetrievalStageKind
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.retrieval.contracts import PathResultKind, PathRetrievalResult, RerankScore
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.evidence_helpers import evidence_input
from tests.retrieval_helpers import candidate
from tests.unit.knowledge.retrieval.test_stage import FakeEmbedding, _context_and_plan


class DomainSearch:
    def __init__(self, *, denied=False):
        self.calls = []
        self.denied = denied

    async def search(self, *, request, context, timeout_s):
        self.calls.append(request)
        if self.denied and request.logical_domain_id == "tax.law":
            return PathRetrievalResult(kind=PathResultKind.FORBIDDEN, logical_domain_id=request.logical_domain_id,
                                       retrieval_profile_id=request.retrieval_profile_id, path=request.path)
        items = tuple(replace(candidate(
            chunk=f"{request.logical_domain_id}-{i}", domain=request.logical_domain_id, rank=i,
            content=f"公开税务原文{i}",
        ), document_id=f"doc-{request.logical_domain_id}-{i}") for i in range(1, 5))
        return PathRetrievalResult(kind=PathResultKind.CANDIDATES, logical_domain_id=request.logical_domain_id,
            retrieval_profile_id=request.retrieval_profile_id, path=request.path,
            profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
            read_policy_version="tax-public-authenticated-v1", candidates=items)


class DomainRerank:
    def __init__(self):
        self.queries = []

    async def rerank(self, *, query, candidates, timeout_s):
        self.queries.append(query)
        return tuple(RerankScore(candidate_index=i, score=float(i)) for i in range(len(candidates)))


def multi_plan():
    context, baseline = _context_and_plan()
    plan = replace(baseline, selected_domain_ids=("tax.policy", "tax.law"), quality_version=KNOWLEDGE_QUALITY_VERSION,
        items=tuple(RetrievalPlanItem(logical_domain_id=domain, path=path, query_text=query,
            candidate_limit=20, ordinal=i)
            for i, (domain, query, path) in enumerate(
                ((domain, query, path) for domain, query in (("tax.policy", "住宿服务政策"), ("tax.law", "住宿服务增值税法"))
                 for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)), 1)))
    return context, plan


@pytest.mark.asyncio
async def test_each_domain_uses_own_query_and_retains_keyword_and_semantic_anchors():
    context, plan = multi_plan()
    embedding, search, rerank = FakeEmbedding(), DomainSearch(), DomainRerank()
    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=embedding, rerank=rerank).execute(
        plan=plan, context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert embedding.calls == 2 and len(search.calls) == 4
    assert rerank.queries == ["住宿服务政策", "住宿服务增值税法"]
    assert [item.candidate.chunk_id for item in result.batch.candidates[:4]] == [
        "tax.policy-1", "tax.policy-4", "tax.law-1", "tax.law-4"]
    assert [item.coverage_anchor for item in result.batch.candidates] == [True] * 4 + [False] * 4
    assert [item.candidate.chunk_id for item in result.batch.candidates[4:]] == [
        "tax.policy-2", "tax.law-2", "tax.policy-3", "tax.law-3"]
    source = replace(evidence_input(), batch=result.batch, coverage=result.coverage,
                     selected_domain_ids=plan.selected_domain_ids, quality_version=KNOWLEDGE_QUALITY_VERSION)
    selected = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="住宿服务政策与增值税法", limits=KnowledgeEvidenceLimits.v1())
    assert selected.sufficient
    assert [item.chunk_id for item in selected.bundle.evidence[:4]] == [
        "tax.policy-1", "tax.policy-4", "tax.law-1", "tax.law-4"]


@pytest.mark.asyncio
async def test_explicit_domain_denial_precedes_rerank_and_is_not_a_fallback_trigger():
    context, plan = multi_plan()
    search, rerank = DomainSearch(denied=True), DomainRerank()
    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=FakeEmbedding(), rerank=rerank).execute(
        plan=plan, context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.FORBIDDEN
    assert len(search.calls) == 4 and not rerank.queries


@pytest.mark.asyncio
async def test_identical_queries_share_one_embedding_but_not_cross_query_scores():
    context, plan = multi_plan()
    plan = replace(plan, items=tuple(replace(item, query_text="住宿服务税率") for item in plan.items))
    embedding, rerank = FakeEmbedding(), DomainRerank()
    result = await DefaultKnowledgeRetrievalStage(search=DomainSearch(), embedding=embedding, rerank=rerank).execute(
        plan=plan, context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert embedding.calls == 1 and len(rerank.queries) == 2


@pytest.mark.asyncio
async def test_unknown_quality_strategy_fails_before_any_dependency_call():
    context, plan = multi_plan()
    search, embedding, rerank = DomainSearch(), FakeEmbedding(), DomainRerank()
    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=embedding, rerank=rerank).execute(
        plan=replace(plan, quality_version="invented"), context=context, timeout_s=4)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE
    assert not search.calls and embedding.calls == 0 and not rerank.queries


def test_missing_selected_domain_evidence_is_not_sufficient():
    source = replace(evidence_input(), selected_domain_ids=("tax.policy", "tax.law"), quality_version=KNOWLEDGE_QUALITY_VERSION)
    selected = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="住宿政策与增值税法", limits=KnowledgeEvidenceLimits.v1())
    assert not selected.sufficient and selected.bundle is None


def test_unfittable_mandatory_anchor_fails_instead_of_silently_substituting():
    source = evidence_input()
    source = replace(source, quality_version=KNOWLEDGE_QUALITY_VERSION,
                     batch=replace(source.batch, candidates=(replace(source.batch.candidates[0], coverage_anchor=True),)))
    selected = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="税务政策", limits=replace(KnowledgeEvidenceLimits.v1(), max_summary_input_bytes=1))
    assert not selected.sufficient and selected.bundle is None


def test_oversized_optional_candidate_does_not_hide_a_later_small_candidate():
    source = evidence_input()
    first = replace(source.batch.candidates[0], coverage_anchor=True)
    large = replace(first, rank=2, coverage_anchor=False,
                    candidate=replace(candidate(chunk="c2", content="税务" * 2000), document_id="d2"))
    small = replace(first, rank=3, coverage_anchor=False,
                    candidate=replace(candidate(chunk="c3", content="附加政策"), document_id="d3"))
    source = replace(source, quality_version=KNOWLEDGE_QUALITY_VERSION,
                     batch=replace(source.batch, candidates=(first, large, small)))
    selected = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="税务政策", limits=replace(KnowledgeEvidenceLimits.v1(), max_summary_input_bytes=1200))
    assert selected.sufficient
    assert tuple(item.chunk_id for item in selected.bundle.evidence) == ("c1", "c3")


@pytest.mark.parametrize("quality, expected", [(False, 2), (True, 3)])
def test_same_document_quota_is_versioned_without_expanding_other_limits(quality, expected):
    source = evidence_input()
    items = tuple(replace(source.batch.candidates[0], rank=i,
                          candidate=candidate(chunk=f"c{i}", rank=i)) for i in range(1, 5))
    source = replace(source, quality_version=KNOWLEDGE_QUALITY_VERSION if quality else None,
                     batch=replace(source.batch, candidates=items))
    limits = KnowledgeEvidenceLimits.quality_v1() if quality else KnowledgeEvidenceLimits.v1()
    assert replace(limits, max_per_document=2) == KnowledgeEvidenceLimits.v1()
    result = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="公开政策", limits=limits)
    assert result.sufficient
    assert tuple(item.chunk_id for item in result.bundle.evidence) == tuple(f"c{i}" for i in range(1, expected + 1))


@pytest.mark.asyncio
async def test_rerank_domains_do_not_overlap_and_cancellation_prevents_next_domain():
    class BlockingRerank(DomainRerank):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()
            self.active = 0

        async def rerank(self, **kwargs):
            self.active += 1
            assert self.active == 1
            self.queries.append(kwargs["query"])
            self.entered.set()
            try:
                await self.release.wait()
                return tuple(RerankScore(candidate_index=i, score=float(i)) for i in range(len(kwargs["candidates"])))
            finally:
                self.active -= 1

    context, plan = multi_plan()
    rerank = BlockingRerank()
    task = asyncio.create_task(DefaultKnowledgeRetrievalStage(
        search=DomainSearch(), embedding=FakeEmbedding(), rerank=rerank).execute(plan=plan, context=context, timeout_s=4))
    await asyncio.wait_for(rerank.entered.wait(), timeout=1)
    await asyncio.sleep(0)
    assert rerank.queries == ["住宿服务政策"]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert rerank.active == 0 and rerank.queries == ["住宿服务政策"]
