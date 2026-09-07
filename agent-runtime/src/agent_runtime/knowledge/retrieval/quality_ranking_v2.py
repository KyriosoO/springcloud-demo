"""Domain coverage followed by bounded domain-local semantic relevance."""
from __future__ import annotations

import asyncio
from collections import deque
import math

from agent_runtime.knowledge.contracts import KnowledgeRetrievalPlan
from agent_runtime.knowledge.retrieval.contracts import (
    FusedCandidate, PathCandidateSet, RankedKnowledgeCandidate, RerankPort,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion


async def rank_by_domain_v2(
    *, plan: KnowledgeRetrievalPlan, sets: tuple[PathCandidateSet, ...],
    fused: tuple[FusedCandidate, ...], fusion: ReciprocalRankFusion,
    rerank: RerankPort, deadline: float, final_candidates: int,
) -> tuple[RankedKnowledgeCandidate, ...]:
    def identity(item: FusedCandidate) -> tuple[str, str]:
        return item.candidate.document_id, item.candidate.chunk_id

    canonical = {identity(item): item for item in fused}
    domains = plan.selected_domain_ids
    queries = {item.logical_domain_id: item.query_text for item in plan.items}
    queues: dict[str, deque[tuple[tuple[str, str], float]]] = {}
    # V1冻结源码保留；本版本仍逐域串行调用，取消后不会启动下一域。
    for domain in domains:
        candidates = fusion.fuse(tuple(item for item in sets if item.logical_domain_id == domain))
        if not candidates:
            queues[domain] = deque()
            continue
        if len(candidates) > 40:
            raise ValueError("knowledge.invalid_domain_candidate_count")
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("knowledge.rerank_deadline")
        scores = await rerank.rerank(
            query=queries[domain], candidates=tuple(item.candidate for item in candidates),
            timeout_s=min(5.0, remaining),
        )
        if (len(scores) != len(candidates)
                or any(type(item.candidate_index) is not int for item in scores)
                or {item.candidate_index for item in scores} != set(range(len(candidates)))
                or any(type(item.score) not in (int, float) or not math.isfinite(item.score) for item in scores)):
            raise ValueError("knowledge.invalid_rerank_scores")
        by_index = {item.candidate_index: item.score for item in scores}
        ordered = sorted(enumerate(candidates),
                         key=lambda pair: (-by_index[pair[0]], -pair[1].rrf_score, pair[1].candidate.chunk_id))
        queues[domain] = deque((identity(item), by_index[index]) for index, item in ordered)

    selected: list[tuple[tuple[str, str], float, bool]] = []
    seen: set[tuple[str, str]] = set()

    def add(key: tuple[str, str], score: float, anchor: bool) -> None:
        if key not in seen and len(selected) < final_candidates:
            seen.add(key)
            selected.append((key, score, anchor))

    # 每域只强制保留语义首位；关键词候选仍在同一融合候选池内。
    for domain in domains:
        if queues[domain]:
            key, score = queues[domain][0]
            add(key, score, True)
    while any(queues.values()) and len(selected) < final_candidates:
        for domain in domains:
            while queues[domain]:
                key, score = queues[domain].popleft()
                if key not in seen:
                    add(key, score, False)
                    break
    return tuple(RankedKnowledgeCandidate(
        candidate=canonical[key].candidate,
        domain_ids=tuple(domain for domain in domains if domain in canonical[key].domain_ids),
        rerank_score=score, rank=rank, coverage_anchor=anchor,
    ) for rank, (key, score, anchor) in enumerate(selected, 1))
