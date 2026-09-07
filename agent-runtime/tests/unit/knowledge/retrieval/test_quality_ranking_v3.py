"""DR-KRET-029: synthetic ranking scores test mechanics, never real relevance."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
import math

import pytest

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V2, KNOWLEDGE_QUALITY_VERSION_V3,
    KnowledgeEvidenceRequirement, KnowledgeQuestionKind, KnowledgeRequirementKind,
    RetrievalPath, RetrievalPlanItem, RetrievalStageKind, RetrievalStageCode,
)
from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityError, EvidenceIntegrityVerifier
from agent_runtime.knowledge.retrieval.contracts import PathResultKind, PathRetrievalResult, RerankScore
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse, RetrievalTransportError
from agent_runtime.knowledge.retrieval.quality_ranking_v3 import rank_requirement_candidates
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.evidence_helpers import evidence_input
from tests.retrieval_helpers import candidate
from tests.unit.knowledge.retrieval.test_stage import FakeEmbedding, _context_and_plan


def requirement_plan(*, domains=("tax.policy",), roles=None, requirement_domains=None):
    context, old = _context_and_plan()
    roles = roles or (KnowledgeRequirementKind.SUBJECT_SCOPE, KnowledgeRequirementKind.RULE, KnowledgeRequirementKind.TEMPORAL_SCOPE)
    requirement_domains = requirement_domains or (domains[0],) * len(roles)
    requirements = tuple(KnowledgeEvidenceRequirement(
        requirement_id=f"r{i}", domain_id=domain, kind=role, focus=f"税务依据视角{i}",
    ) for i, (domain, role) in enumerate(zip(requirement_domains, roles, strict=True), 1))
    return context, replace(old, quality_version=KNOWLEDGE_QUALITY_VERSION_V3,
        question_kind=KnowledgeQuestionKind.APPLICABILITY, evidence_requirements=requirements,
        selected_domain_ids=domains, items=tuple(RetrievalPlanItem(
            logical_domain_id=domain, path=path, query_text="税务检索" + domain,
            candidate_limit=20, ordinal=i,
        ) for i, (domain, path) in enumerate(((d, p) for d in domains for p in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)), 1)))


class Search:
    def __init__(self, *, count=20, empty_domains=(), fault=None):
        self.calls, self.count, self.empty_domains, self.fault = [], count, empty_domains, fault

    async def search(self, *, request, context, timeout_s):
        self.calls.append(request)
        domain, path = request.logical_domain_id, request.path
        if domain in self.empty_domains:
            return PathRetrievalResult(kind=PathResultKind.NO_RESULT, logical_domain_id=domain,
                                      retrieval_profile_id=request.retrieval_profile_id, path=path)
        if self.fault in {"forbidden", "all_failure", "vector_failure"} and (self.fault != "vector_failure" or path is RetrievalPath.VECTOR):
            return PathRetrievalResult(kind=PathResultKind.FORBIDDEN if self.fault == "forbidden" else PathResultKind.FAILURE,
                logical_domain_id=domain, retrieval_profile_id=request.retrieval_profile_id, path=path)
        snapshot = "b" * 64 if self.fault == "snapshot" and path is RetrievalPath.VECTOR else "a" * 64
        items = tuple(replace(candidate(chunk=f"{domain}-{path.value}-{i:02}", domain=domain, rank=i,
                                        content=f"合成税务原文{path.value}-{i:02}"),
                              document_id=f"doc-{domain}-{path.value}-{i:02}", index_snapshot_id=snapshot)
                      for i in range(1, self.count + 1))
        return PathRetrievalResult(kind=PathResultKind.CANDIDATES, logical_domain_id=domain,
            retrieval_profile_id=request.retrieval_profile_id, path=path, profile_version=(
                "wrong-version" if self.fault == "profile" and domain == "tax.law" else "tax-knowledge-search-v1"),
            index_snapshot_id=snapshot, read_policy_version="tax-public-authenticated-v1", candidates=items)


class FocusRerank:
    def __init__(self, targets=()):
        self.targets, self.calls = targets, []

    async def rerank(self, *, query, candidates, timeout_s):
        self.calls.append((query, candidates, timeout_s))
        target = self.targets[len(self.calls) - 1] if self.targets else None
        return tuple(RerankScore(candidate_index=i, score=100.0 if item.chunk_id == target else -float(i))
                     for i, item in enumerate(candidates))


async def execute(plan, context, *, search=None, rerank=None, final=20, timeout_s=4):
    search, rerank, embedding = search or Search(), rerank or FocusRerank(), FakeEmbedding()
    result = await DefaultKnowledgeRetrievalStage(search=search, rerank=rerank, embedding=embedding, final_candidates=final).execute(
        plan=plan, context=context, timeout_s=timeout_s)
    return result, search, rerank, embedding


@pytest.mark.asyncio
async def test_same_domain_different_proof_roles_keep_low_rrf_candidate_without_second_search():
    context, plan = requirement_plan()
    targets = ("tax.policy-keyword-01", "tax.policy-vector-20", "tax.policy-vector-19")
    result, search, rerank, embedding = await execute(plan, context, rerank=FocusRerank(targets))
    assert result.kind is RetrievalStageKind.SUCCESS
    assert [item.candidate.chunk_id for item in result.batch.candidates[:3]] == list(targets)
    assert [item.requirement_ids for item in result.batch.candidates[:3]] == [("r1",), ("r2",), ("r3",)]
    assert all(not item.requirement_ids and not item.coverage_anchor for item in result.batch.candidates[3:])
    assert len(result.batch.candidates) == 20
    assert [call[0] for call in rerank.calls] == [item.focus for item in plan.evidence_requirements]
    assert len(search.calls) == 2 and embedding.calls == 1 and len(rerank.calls) == 3
    assert all(len(call[1]) == 40 and 0 < call[2] <= 5 for call in rerank.calls)
    assert all(request.candidate_limit == 20 for request in search.calls)
    assert all(request.query_text not in [item.focus for item in plan.evidence_requirements] for request in search.calls)


@pytest.mark.asyncio
async def test_maximum_four_requirements_score_160_candidates_without_v2_rerank():
    domains = ("tax.policy", "tax.law")
    context, plan = requirement_plan(domains=domains, roles=tuple(KnowledgeRequirementKind),
                                     requirement_domains=("tax.policy", "tax.law", "tax.law", "tax.policy"))
    result, search, rerank, embedding = await execute(plan, context)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert len(search.calls) == 4 and embedding.calls == 2
    assert len(rerank.calls) == 4 and sum(len(call[1]) for call in rerank.calls) == 160
    assert all({item.domain_id for item in call[1]} == {requirement.domain_id}
               for call, requirement in zip(rerank.calls, plan.evidence_requirements, strict=True))
    labels = [label for item in result.batch.candidates for label in item.requirement_ids]
    assert sorted(labels) == ["r1", "r2", "r3", "r4"]
    assert all(item.coverage_anchor == bool(item.requirement_ids) for item in result.batch.candidates)
    assert tuple(item.rank for item in result.batch.candidates) == tuple(range(1, 21))


@pytest.mark.asyncio
async def test_shared_identity_merges_tags_but_keeps_canonical_domains_first_score_and_rotation():
    class SharedSearch(Search):
        async def search(self, **kwargs):
            value = await super().search(**kwargs)
            return replace(value, candidates=tuple(replace(item, document_id="shared", chunk_id="shared", content="相同公开税务原文",
                content_sha256=hashlib.sha256("相同公开税务原文".encode()).hexdigest())
                if item.source_rank == 1 else item for item in value.candidates))

    class SharedRerank(FocusRerank):
        async def rerank(self, **kwargs):
            await super().rerank(**kwargs)
            return tuple(RerankScore(candidate_index=i, score=float(len(self.calls) * 100) if item.chunk_id == "shared" else 1.0)
                         for i, item in enumerate(kwargs["candidates"]))

    context, plan = requirement_plan(domains=("tax.policy", "tax.law"),
                                     requirement_domains=("tax.law", "tax.policy", "tax.law"))
    result, _, rerank, _ = await execute(plan, context, search=SharedSearch(count=3), rerank=SharedRerank())
    assert result.kind is RetrievalStageKind.SUCCESS
    first = result.batch.candidates[0]
    assert first.requirement_ids == ("r1", "r2", "r3") and first.rerank_score == 100.0 and first.rank == 1
    assert first.domain_ids == ("tax.policy", "tax.law") and first.candidate.domain_id == "tax.policy"
    assert [item.candidate.chunk_id for item in result.batch.candidates[:5]] == [
        "shared", "tax.law-keyword-02", "tax.policy-keyword-02", "tax.law-vector-02", "tax.law-keyword-03"]
    assert len({(item.candidate.document_id, item.candidate.chunk_id) for item in result.batch.candidates}) == len(result.batch.candidates)
    assert len(rerank.calls) == 3


@pytest.mark.asyncio
async def test_lookup_single_requirement_and_ties_are_repeatable_and_no_other_domain_added():
    context, plan = requirement_plan(roles=(KnowledgeRequirementKind.RULE,))
    plan = replace(plan, question_kind=KnowledgeQuestionKind.LOOKUP)

    class Ties(FocusRerank):
        async def rerank(self, **kwargs):
            await super().rerank(**kwargs)
            return tuple(RerankScore(candidate_index=i, score=1.0) for i in reversed(range(len(kwargs["candidates"]))))

    first, search, _, _ = await execute(plan, context, search=Search(count=2), rerank=Ties())
    second, _, _, _ = await execute(plan, context, search=Search(count=2), rerank=Ties())
    assert first == second and first.kind is RetrievalStageKind.SUCCESS
    assert [item.candidate.chunk_id for item in first.batch.candidates] == [
        "tax.policy-keyword-01", "tax.policy-vector-01", "tax.policy-keyword-02", "tax.policy-vector-02"]
    assert {item.logical_domain_id for item in search.calls} == {"tax.policy"}


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [("tax.law",), ("tax.policy", "tax.law")])
async def test_empty_requirement_domain_does_not_trigger_rerank_or_fake_anchor(empty):
    context, plan = requirement_plan(domains=("tax.policy", "tax.law"),
                                     requirement_domains=("tax.policy", "tax.law", "tax.law"))
    result, search, rerank, _ = await execute(plan, context, search=Search(empty_domains=empty))
    assert len(search.calls) == 4
    if len(empty) == 2:
        assert result.kind is RetrievalStageKind.NO_RESULT and rerank.calls == []
    else:
        assert result.kind is RetrievalStageKind.SUCCESS and len(rerank.calls) == 1
        assert [label for item in result.batch.candidates for label in item.requirement_ids] == ["r1"]
        assert result.coverage.candidate_count_by_domain[1].count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,kind", [("forbidden", RetrievalStageKind.FORBIDDEN), ("snapshot", RetrievalStageKind.DOWNSTREAM_FAILURE),
    ("profile", RetrievalStageKind.DOWNSTREAM_FAILURE), ("all_failure", RetrievalStageKind.DOWNSTREAM_FAILURE)])
async def test_read_denial_snapshot_and_all_failure_precede_any_rerank(fault, kind):
    context, plan = requirement_plan(domains=("tax.policy", "tax.law"),
                                     requirement_domains=("tax.policy", "tax.law", "tax.law"))
    result, _, rerank, _ = await execute(plan, context, search=Search(fault=fault))
    assert result.kind is kind and rerank.calls == []


@pytest.mark.asyncio
async def test_one_path_failure_keeps_partial_coverage_without_extra_calls():
    context, plan = requirement_plan()
    result, search, rerank, embedding = await execute(plan, context, search=Search(fault="vector_failure"))
    assert result.kind is RetrievalStageKind.SUCCESS and not result.coverage.complete
    assert len(result.coverage.failed_paths) == 1 and len(search.calls) == 2 and embedding.calls == 1
    assert len(rerank.calls) == 3 and all(len(call[1]) == 20 for call in rerank.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["nan", "inf", "boolean_score", "boolean_index", "duplicate", "missing", "out_of_bounds", "list", "timeout", "transport", "cancel"])
async def test_bad_response_or_exception_stops_before_next_requirement(fault):
    class Invalid(FocusRerank):
        async def rerank(self, **kwargs):
            scores = await super().rerank(**kwargs)
            if fault == "cancel":
                raise asyncio.CancelledError()
            if fault == "timeout":
                raise TimeoutError()
            if fault == "transport":
                raise RetrievalTransportError("invalid_response")
            if fault == "missing":
                return scores[:-1]
            if fault == "list":
                return list(scores)
            first = scores[0]
            if fault in {"nan", "inf", "boolean_score"}:
                first = replace(first, score=True if fault == "boolean_score" else math.nan if fault == "nan" else math.inf)
            else:
                first = replace(first, candidate_index=True if fault == "boolean_index" else 1 if fault == "duplicate" else len(scores))
            return (first,) + scores[1:]

    context, plan = requirement_plan()
    rerank = Invalid()
    if fault == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await execute(plan, context, rerank=rerank)
    else:
        result, _, _, _ = await execute(plan, context, rerank=rerank)
        assert result.kind is (RetrievalStageKind.TIMEOUT if fault == "timeout" else RetrievalStageKind.DOWNSTREAM_FAILURE)
        assert result.batch is None
    assert len(rerank.calls) == 1


@pytest.mark.asyncio
async def test_cancel_waits_for_active_requirement_and_does_not_start_next():
    entered, released = asyncio.Event(), asyncio.Event()

    class Blocking(FocusRerank):
        async def rerank(self, **kwargs):
            await super().rerank(**kwargs)
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()

    context, plan = requirement_plan()
    rerank = Blocking()
    task = asyncio.create_task(execute(plan, context, rerank=rerank))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set() and len(rerank.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["duplicate_id", "missing_role", "wrong_domain", "small_final", "too_many"])
async def test_invalid_plan_or_insufficient_anchor_capacity_has_zero_dependency_calls(fault):
    context, plan = requirement_plan()
    if fault == "duplicate_id":
        plan = replace(plan, evidence_requirements=(plan.evidence_requirements[0],) * 3)
    elif fault == "missing_role":
        plan = replace(plan, evidence_requirements=plan.evidence_requirements[:2])
    elif fault == "wrong_domain":
        plan = replace(plan, evidence_requirements=tuple(replace(item, domain_id="tax.law") for item in plan.evidence_requirements))
    elif fault == "too_many":
        plan = replace(plan, evidence_requirements=plan.evidence_requirements * 2)
    result, search, rerank, embedding = await execute(plan, context, final=3 if fault == "small_final" else 20)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE
    assert search.calls == rerank.calls == [] and embedding.calls == 0


@pytest.mark.asyncio
async def test_expired_stage_has_zero_dependency_calls():
    context, plan = requirement_plan()
    result, search, rerank, embedding = await execute(plan, replace(context, deadline_monotonic=0))
    assert result.kind is RetrievalStageKind.TIMEOUT
    assert search.calls == rerank.calls == [] and embedding.calls == 0


def test_legacy_evidence_cannot_silently_ignore_requirement_tags():
    source = evidence_input()
    for version in (None, KNOWLEDGE_QUALITY_VERSION_V2):
        with pytest.raises(EvidenceIntegrityError, match="requirement_version_mismatch"):
            EvidenceIntegrityVerifier().verify(input=replace(source, quality_version=version,
                batch=replace(source.batch, candidates=(replace(source.batch.candidates[0], requirement_ids=("r1",)),))))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "text_mismatch", "missing", "http"])
async def test_actual_bge_adapter_uses_focus_and_validates_echo_before_next_requirement(fault):
    class Transport:
        def __init__(self):
            self.requests = []

        async def send(self, *, request, timeout_s):
            self.requests.append(request)
            body = json.loads(request.body)
            results = [{"index": i, "text": text, "score": float(-i)} for i, text in enumerate(body["documents"])]
            if fault == "text_mismatch":
                results[0]["text"] = "not the authorized source"
            elif fault == "missing":
                results.pop()
            return BoundedHttpResponse(status_code=503 if fault == "http" else 200,
                content_type="application/json", content_encoding=None,
                body=json.dumps({"model": BgeRerankAdapter.MODEL, "results": results}).encode())

    context, plan = requirement_plan()
    transport = Transport()
    result, _, _, _ = await execute(plan, context, search=Search(count=2), rerank=BgeRerankAdapter(transport))
    assert result.kind is (RetrievalStageKind.SUCCESS if fault is None else RetrievalStageKind.DOWNSTREAM_FAILURE)
    assert len(transport.requests) == (3 if fault is None else 1)
    for request, requirement in zip(transport.requests, plan.evidence_requirements):
        body = json.loads(request.body)
        assert body["query"] == requirement.focus and body["top_n"] == 4 and body["normalize"] is True
        assert set(body) == {"query", "documents", "top_n", "normalize"}
        assert request.relative_path == "/rerank" and len(request.body) <= 2 * 1024 * 1024
        assert not any(name.lower() == "authorization" for name, _ in request.headers)


@pytest.mark.asyncio
async def test_deadline_checked_before_next_requirement_even_when_port_returns_late():
    # Direct ranker test isolates the inter-call guard from Stage's outer timeout.
    from agent_runtime.knowledge.retrieval.contracts import FusedCandidate

    one = FusedCandidate(candidate=candidate(), domain_ids=("tax.policy",), path_ranks=(), rrf_score=1.0)

    class Pool(ReciprocalRankFusion):
        def fuse(self, values):
            return (one,)

    class Late(FocusRerank):
        async def rerank(self, **kwargs):
            value = await super().rerank(**kwargs)
            await asyncio.sleep(0.03)
            return value

    _, plan = requirement_plan()
    rerank = Late()
    with pytest.raises(TimeoutError, match="rerank_deadline"):
        await rank_requirement_candidates(plan=plan, sets=(), fused=(one,), fusion=Pool(), rerank=rerank,
            deadline=asyncio.get_running_loop().time() + 0.01, final_candidates=20)
    assert len(rerank.calls) == 1 and 0 < rerank.calls[0][2] <= 0.01


@pytest.mark.asyncio
async def test_oversized_domain_pool_is_rejected_before_any_rerank():
    from agent_runtime.knowledge.retrieval.contracts import FusedCandidate

    one = FusedCandidate(candidate=candidate(), domain_ids=("tax.policy",), path_ranks=(), rrf_score=1.0)

    class OversizedPool(ReciprocalRankFusion):
        def fuse(self, values):
            return (one,) * 41

    _, plan = requirement_plan()
    rerank = FocusRerank()
    with pytest.raises(ValueError, match="invalid_domain_candidate_count"):
        await rank_requirement_candidates(plan=plan, sets=(), fused=(one,), fusion=OversizedPool(), rerank=rerank,
            deadline=asyncio.get_running_loop().time() + 1, final_candidates=20)
    assert rerank.calls == []
