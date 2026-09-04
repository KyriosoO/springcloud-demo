"""Bounded domain-local reranking inside the existing retrieval stage."""
from __future__ import annotations

import asyncio
from collections import deque
import math

from agent_runtime.knowledge.contracts import KnowledgeRetrievalPlan, RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import (
    FusedCandidate, PathCandidateSet, RankedKnowledgeCandidate, RerankPort,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion


async def rank_by_domain(
    *, plan: KnowledgeRetrievalPlan, sets: tuple[PathCandidateSet, ...],
    fused: tuple[FusedCandidate, ...], fusion: ReciprocalRankFusion,
    rerank: RerankPort, deadline: float, final_candidates: int,
) -> tuple[RankedKnowledgeCandidate, ...]:
    def identity(item: FusedCandidate) -> tuple[str, str]:
        return item.candidate.document_id, item.candidate.chunk_id
    canonical = {identity(item): item for item in fused}
    domains = plan.selected_domain_ids
    local = {domain: fusion.fuse(tuple(item for item in sets if item.logical_domain_id == domain))
             for domain in domains}
    queries = {item.logical_domain_id: item.query_text for item in plan.items}

    async def score_domain(domain: str) -> list[tuple[tuple[str, str], float]]:
        candidates = local[domain]
        if not candidates:
            return []
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
                or {item.candidate_index for item in scores} != set(range(len(candidates)))
                or any(type(item.score) not in (int, float) or not math.isfinite(item.score) for item in scores)):
            raise ValueError("knowledge.invalid_rerank_scores")
        by_index = {item.candidate_index: item.score for item in scores}
        ordered = sorted(enumerate(candidates),
                         key=lambda pair: (-by_index[pair[0]], -pair[1].rrf_score, pair[1].candidate.chunk_id))
        return [(identity(item), by_index[index]) for index, item in ordered]

    # The local model has bounded capacity; do not overlap this request's domains.
    # Cancellation propagates immediately and never starts the next domain.
    lists = [await score_domain(domain) for domain in domains]
    ordered_by_domain = dict(zip(domains, lists, strict=True))
    selected: list[tuple[tuple[str, str], float, bool]] = []
    seen: set[tuple[str, str]] = set()

    def add(key: tuple[str, str], score: float, anchor: bool) -> None:
        if key not in seen and len(selected) < final_candidates:
            seen.add(key)
            selected.append((key, score, anchor))

    # Only path-owned rank signals; neither gold nor document IDs enter selection.
    for domain in domains:
        ranked = ordered_by_domain[domain]
        if not ranked:
            continue
        scores = dict(ranked)
        keyword = next((item for item in local[domain]
                        if any(path.path is RetrievalPath.KEYWORD and path.rank == 1 for path in item.path_ranks)), None)
        if keyword is not None:
            add(identity(keyword), scores[identity(keyword)], True)
        add(ranked[0][0], ranked[0][1], True)
    queues = {}
    for domain in domains:
        ranked = ordered_by_domain[domain]
        scores = dict(ranked)
        keyword_ranks = {
            identity(item): path.rank for item in local[domain] for path in item.path_ranks
            if path.path is RetrievalPath.KEYWORD
        }
        keyword_keys = sorted(keyword_ranks, key=lambda key: (keyword_ranks[key], key[1]))
        mixed: list[tuple[tuple[str, str], float]] = []
        local_seen = set(seen)
        for offset in range(max(len(keyword_keys), len(ranked))):
            choices = ([keyword_keys[offset]] if offset < len(keyword_keys) else [])
            choices += ([ranked[offset][0]] if offset < len(ranked) else [])
            for key in choices:
                if key not in local_seen:
                    local_seen.add(key)
                    mixed.append((key, scores[key]))
        queues[domain] = deque(mixed)
    # Cross-domain raw BGE scores are not comparable. Each turn emits a new item.
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
