from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, KnowledgePolicyCatalogError
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch, RankedKnowledgeCandidate
from tests.evidence_helpers import evidence_input, synthetic_catalog
from tests.retrieval_helpers import candidate


def test_integrity_selection_and_three_layer_policy_build_minimal_summary_input() -> None:
    source = evidence_input()
    verified = EvidenceIntegrityVerifier().verify(input=source)
    selection = DeterministicEvidenceSelector().select(
        candidates=verified,
        input=source,
        minimized_question="现行增值税政策是什么",
        limits=KnowledgeEvidenceLimits.v1(),
    )

    assert selection.sufficient and selection.bundle is not None
    assert selection.bundle.evidence[0].evidence_id.startswith("ev-")
    decision = KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=synthetic_catalog())
    assert decision.allowed and decision.summary_input is not None
    assert decision.snapshot_fingerprint is not None and len(decision.snapshot_fingerprint) == 64
    assert decision.snapshot_fingerprint != synthetic_catalog().snapshot.canonical_fingerprint
    payload_item = decision.summary_input.evidence[0]
    assert payload_item.evidence_ref == "e1"
    assert not hasattr(payload_item, "document_id")
    assert not hasattr(payload_item, "source_url")
    assert not hasattr(payload_item, "policy_ref")


def test_integrity_rejects_snapshot_or_domain_order_drift() -> None:
    source = evidence_input()
    only = source.batch.candidates[0]
    drifted = replace(
        source,
        batch=RankedKnowledgeBatch(
            candidates=(replace(only, domain_ids=("tax.law", "tax.policy")),),
            profile_version=source.batch.profile_version,
            index_snapshot_ids=source.batch.index_snapshot_ids,
        ),
    )
    with pytest.raises(ValueError, match="knowledge.evidence_integrity_failed"):
        EvidenceIntegrityVerifier().verify(input=drifted)

    missing_snapshot = replace(
        source,
        batch=replace(source.batch, index_snapshot_ids=("b" * 64,)),
    )
    with pytest.raises(ValueError, match="knowledge.evidence_integrity_failed"):
        EvidenceIntegrityVerifier().verify(input=missing_snapshot)


def test_second_selection_pass_skips_saturated_document_without_skipping_later_document() -> None:
    source = evidence_input()
    first = candidate(chunk="c1", rank=1, content="第一段")
    second = candidate(chunk="c2", rank=2, content="第二段")
    third = replace(candidate(chunk="c3", rank=3, content="第三段"), document_id="d2")
    batch = RankedKnowledgeBatch(
        candidates=tuple(
            RankedKnowledgeCandidate(candidate=item, domain_ids=("tax.policy",), rerank_score=1.0 / rank, rank=rank)
            for rank, item in enumerate((first, second, third), 1)
        ),
        profile_version="tax-knowledge-search-v1",
        index_snapshot_ids=("a" * 64,),
    )
    source = replace(source, batch=batch)

    selection = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source),
        input=source,
        minimized_question="现行增值税政策是什么",
        limits=KnowledgeEvidenceLimits(
            max_evidence=8,
            max_per_document=1,
            max_summary_input_bytes=32768,
            max_summary_points=5,
            max_quote_chars=512,
            max_domain_result_bytes=32768,
        ),
    )

    assert selection.bundle is not None
    assert tuple(item.document_id for item in selection.bundle.evidence) == ("d1", "d2")


def test_synthetic_policy_catalog_rejects_unverified_fingerprint() -> None:
    snapshot = synthetic_catalog().snapshot
    with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_catalog_invalid"):
        KnowledgeEgressPolicyCatalog(replace(snapshot, canonical_fingerprint="f" * 64))
