from __future__ import annotations

import pytest

from agent_runtime.knowledge.contracts import RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import PathCandidateSet
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from tests.retrieval_helpers import candidate


def _set(path: RetrievalPath, items: tuple[object, ...]) -> PathCandidateSet:
    return PathCandidateSet(
        logical_domain_id="tax.policy", retrieval_profile_id="tax-policy-v1", path=path,
        profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
        read_policy_version="tax-public-authenticated-v1", truncated=False,
        candidates=items,  # type: ignore[arg-type]
    )


def test_rrf_uses_rank_and_deduplicates_stably() -> None:
    item = candidate()
    fused = ReciprocalRankFusion().fuse((_set(RetrievalPath.KEYWORD, (item,)), _set(RetrievalPath.VECTOR, (item,))))

    assert len(fused) == 1
    assert fused[0].rrf_score == pytest.approx(2 / 61)
    assert tuple(rank.path for rank in fused[0].path_ranks) == (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)


def test_conflicting_duplicate_candidate_fails_closed() -> None:
    with pytest.raises(ValueError, match="candidate_conflict"):
        ReciprocalRankFusion().fuse(
            (_set(RetrievalPath.KEYWORD, (candidate(),)), _set(RetrievalPath.VECTOR, (candidate(content="不同正文"),)))
        )

