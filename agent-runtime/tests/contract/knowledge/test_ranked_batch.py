from __future__ import annotations

from dataclasses import fields

from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch, RankedKnowledgeCandidate
from tests.retrieval_helpers import candidate


def test_ranked_batch_preserves_evidence_identity_without_auth_or_egress_decision() -> None:
    batch = RankedKnowledgeBatch(
        candidates=(RankedKnowledgeCandidate(candidate=candidate(), domain_ids=("tax.policy",), rerank_score=1.0, rank=1),),
        profile_version="tax-knowledge-search-v1", index_snapshot_ids=("a" * 64,),
    )

    assert batch.candidates[0].candidate.policy_ref == "policy-doc-v1"
    names = {item.name for item in fields(RankedKnowledgeBatch)}
    assert not names & {"jwt", "roles", "acl", "egress_allowed"}

