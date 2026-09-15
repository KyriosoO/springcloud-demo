from dataclasses import replace

from agent_runtime.knowledge.contracts import RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import PathCandidateSet, RerankScore
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.minimal_ranking import domain_pool, order_domain, round_robin
from tests.retrieval_helpers import candidate


def candidate_set(items, path=RetrievalPath.KEYWORD):
    return PathCandidateSet(logical_domain_id="tax.policy", retrieval_profile_id="tax-policy-v1", path=path,
        profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
        read_policy_version="tax-public-authenticated-v1", truncated=False, candidates=items)


def test_ties_use_rrf_then_chunk_then_document_not_encounter_order():
    a, b = candidate(chunk="same"), replace(candidate(chunk="same", rank=2), document_id="d0")
    # Swap source rank between paths to equalize RRF, leaving document id as final tie-break.
    sets = (candidate_set((a, b)), candidate_set((replace(b, source_rank=1), replace(a, source_rank=2)), RetrievalPath.VECTOR))
    pool = domain_pool(sets, "tax.policy")
    ranked = order_domain(pool, tuple(RerankScore(candidate_index=i, score=0.1) for i in range(len(pool))))
    assert [item[0].candidate.document_id for item in ranked] == ["d0", "d1"]
    assert all(item[0].rrf_score == 1 / 61 + 1 / 62 for item in ranked)


def test_rerank_primary_rrf_secondary_and_negative_finite_scores_not_filtered():
    sets = (candidate_set((candidate(chunk="z"), candidate(chunk="a", rank=2))),)
    pool = domain_pool(sets, "tax.policy")
    ranked = order_domain(pool, (RerankScore(candidate_index=0, score=-2), RerankScore(candidate_index=1, score=-1)))
    assert [item[0].candidate.chunk_id for item in ranked] == ["a", "z"]
    tied = order_domain(pool, (RerankScore(candidate_index=0, score=-2), RerankScore(candidate_index=1, score=-2)))
    assert [item[0].candidate.chunk_id for item in tied] == ["z", "a"]
    result = round_robin((ranked,), ReciprocalRankFusion().fuse(sets))
    assert len(result) == 2 and result[0].candidate.content == pool[1].candidate.content
