"""DR-KRET-202: independent per-domain ranking and provenance-preserving rotation."""
from __future__ import annotations

from dataclasses import dataclass, field
import math

from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate, FusedCandidate, PathCandidateSet, PathRank, RerankScore,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion


@dataclass(frozen=True, slots=True, kw_only=True)
class MinimalRankedCandidate:
    candidate: AuthorizedKnowledgeCandidate = field(repr=False)
    domain_ids: tuple[str, ...]
    path_ranks: tuple[PathRank, ...]
    rerank_score: float
    rank: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MinimalRankedBatch:
    candidates: tuple[MinimalRankedCandidate, ...] = field(repr=False)
    profile_version: str
    index_snapshot_ids: tuple[str, ...]


def domain_pool(sets: tuple[PathCandidateSet, ...], domain: str) -> tuple[FusedCandidate, ...]:
    fused = ReciprocalRankFusion().fuse(tuple(item for item in sets if item.logical_domain_id == domain))
    if len(fused) > 40:
        raise ValueError("knowledge.invalid_domain_pool")
    return tuple(sorted(fused, key=lambda item: (-item.rrf_score, item.candidate.chunk_id, item.candidate.document_id)))


def order_domain(pool: tuple[FusedCandidate, ...], scores: tuple[RerankScore, ...]) -> tuple[tuple[FusedCandidate, float], ...]:
    if type(scores) is not tuple or len(scores) != len(pool):
        raise ValueError("knowledge.invalid_rerank")
    seen: set[int] = set()
    ranked: list[tuple[FusedCandidate, float]] = []
    for score in scores:
        if (not isinstance(score, RerankScore) or type(score.candidate_index) is not int
                or score.candidate_index in seen or not 0 <= score.candidate_index < len(pool)
                or type(score.score) not in (int, float)):
            raise ValueError("knowledge.invalid_rerank")
        try:
            value = float(score.score)
        except OverflowError as exc:
            raise ValueError("knowledge.invalid_rerank") from exc
        # The current normalize=True adapter contract requires finite numbers, not an invented threshold.
        if not math.isfinite(value):
            raise ValueError("knowledge.invalid_rerank")
        seen.add(score.candidate_index)
        ranked.append((pool[score.candidate_index], value))
    return tuple(sorted(ranked, key=lambda item: (-item[1], -item[0].rrf_score,
        item[0].candidate.chunk_id, item[0].candidate.document_id)))


def round_robin(
    queues: tuple[tuple[tuple[FusedCandidate, float], ...], ...],
    all_candidates: tuple[FusedCandidate, ...],
) -> tuple[MinimalRankedCandidate, ...]:
    """No score comparison across pools and no anchors, quotas or gold-derived hints."""
    by_id = {(item.candidate.document_id, item.candidate.chunk_id): item for item in all_candidates}
    seen: set[tuple[str, str]] = set()
    offsets = [0] * len(queues)
    result: list[MinimalRankedCandidate] = []
    while len(result) < 20:
        progressed = False
        for index, queue in enumerate(queues):
            while offsets[index] < len(queue):
                item, score = queue[offsets[index]]
                offsets[index] += 1
                identity = (item.candidate.document_id, item.candidate.chunk_id)
                if identity in seen:
                    continue
                source = by_id[identity]
                seen.add(identity)
                result.append(MinimalRankedCandidate(candidate=source.candidate, domain_ids=source.domain_ids,
                    path_ranks=source.path_ranks, rerank_score=score, rank=len(result) + 1))
                progressed = True
                break
            if len(result) == 20:
                break
        if not progressed:
            break
    return tuple(result)
