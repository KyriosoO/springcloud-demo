"""Synthetic counterexamples for DR-KEV-003/026, not a live UAT replay.

No source text, gold, model response or external dependency is used. The first
two fixtures reproduce only observed order/document-group shapes. Their bytes,
scores and source metadata are synthetic, so they cannot prove answer quality.
"""
from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION, DomainCandidateCount, PathRef, RetrievalPath,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeCandidate
from tests.evidence_helpers import evidence_input
from tests.retrieval_helpers import candidate


def select(groups, domains, *, anchors=(), text_repeat=1):
    source = evidence_input()
    items = tuple(RankedKnowledgeCandidate(
        candidate=replace(candidate(chunk=f"c{rank}", domain=domain, rank=rank,
                                    content=f"合成公开片段{rank}。" * text_repeat),
                          document_id=f"d{group}"),
        domain_ids=(domain,), rerank_score=float(-rank), rank=rank,
        coverage_anchor=rank in anchors,
    ) for rank, (group, domain) in enumerate(zip(groups, domains, strict=True), 1))
    selected_domains = tuple(dict.fromkeys(domains))
    source = replace(source, selected_domain_ids=selected_domains,
        quality_version=KNOWLEDGE_QUALITY_VERSION,
        batch=replace(source.batch, candidates=items),
        coverage=replace(source.coverage, successful_paths=tuple(
            PathRef(logical_domain_id=domain, path=path)
            for domain in selected_domains for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)),
            candidate_count_by_domain=tuple(
            DomainCandidateCount(logical_domain_id=domain, count=domains.count(domain))
            for domain in selected_domains)))
    return DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="Compare the explicitly requested public clauses.",
        limits=KnowledgeEvidenceLimits.quality_v1())


def selected_ranks(result):
    assert result.sufficient and result.bundle is not None
    assert result.bundle.maximal_summary_input_bytes < 32768
    return tuple(item.rank for item in result.bundle.evidence)


def test_eighth_slot_stops_ninth_even_when_its_document_quota_has_room():
    # Observed run-04 shape, not original content or a reproduction of its bytes.
    groups = (1, 2, 3, 4, 5, 6, 7, 4, 5, 3, 2, 8, 5, 6, 9, 10, 11, 6, 5, 12)
    domains = ("tax.policy",) * 2 + ("tax.law",) * 2 + ("tax.policy", "tax.law") * 8
    result = select(groups, domains, anchors=(1, 2, 3, 4))
    assert selected_ranks(result) == tuple(range(1, 9))
    assert sum(item.document_id == "d5" for item in result.bundle.evidence) == 1
    assert 9 not in selected_ranks(result)


def test_fourth_same_document_clause_is_skipped_despite_spare_total_and_bytes():
    # A focused-rerank counterfactual: policy rank four is global rank seven.
    groups = (1, 10, 1, 11, 1, 12, 1, 13, 2, 14)
    domains = ("tax.policy", "tax.law") * 5
    result = select(groups, domains, anchors=(1, 2))
    assert selected_ranks(result) == (1, 2, 3, 4, 5, 6, 8, 9)
    assert sum(item.document_id == "d1" for item in result.bundle.evidence) == 3
    assert 7 not in selected_ranks(result)


@pytest.mark.parametrize("clauses", [3, 4, 5])
def test_domain_coverage_is_not_proof_of_complete_clause_coverage(clauses):
    # Generic non-tax example: the selector has no required-answer-clause input.
    result = select((1,) * clauses, ("tax.policy",) * clauses, anchors=(1,))
    assert selected_ranks(result) == tuple(range(1, min(clauses, 3) + 1))
    assert result.bundle.coverage.missing_domain_ids == ()
    assert len(result.bundle.evidence) == min(clauses, 3)
    assert (len(result.bundle.evidence) == clauses) is (clauses <= 3)


def test_mandatory_anchors_cannot_bypass_document_quota():
    # Two anchors per domain may share one document. They must not bypass its
    # quota merely because the overall two-domain anchor-count bound is met.
    result = select((1, 1, 1, 1), ("tax.policy",) * 2 + ("tax.law",) * 2,
                    anchors=(1, 2, 3, 4))
    assert not result.sufficient and result.bundle is None


def test_mandatory_anchor_cannot_bypass_byte_budget():
    result = select((1, 2, 3, 4), ("tax.policy",) * 2 + ("tax.law",) * 2,
                    anchors=(1, 2, 3, 4), text_repeat=500)
    assert not result.sufficient and result.bundle is None


def test_all_current_limits_remain_unchanged():
    limits = KnowledgeEvidenceLimits.quality_v1()
    assert (limits.max_evidence, limits.max_per_document, limits.max_summary_input_bytes,
            limits.max_summary_points, limits.max_quote_chars, limits.max_domain_result_bytes) == (
                8, 3, 32768, 5, 512, 32768)
