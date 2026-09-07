"""Preserve one authorized ranking opportunity per frozen evidence requirement."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import replace
import math

from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V3, KnowledgeRetrievalPlan
from agent_runtime.knowledge.evidence_requirements import validate_plan_requirements
from agent_runtime.knowledge.retrieval.contracts import (
    FusedCandidate, PathCandidateSet, RankedKnowledgeCandidate, RerankPort, RerankScore,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion


def _identity(item: FusedCandidate) -> tuple[str, str]:
    return item.candidate.document_id, item.candidate.chunk_id


async def rank_requirement_candidates(
    *, plan: KnowledgeRetrievalPlan, sets: tuple[PathCandidateSet, ...],
    fused: tuple[FusedCandidate, ...], fusion: ReciprocalRankFusion,
    rerank: RerankPort, deadline: float, final_candidates: int,
) -> tuple[RankedKnowledgeCandidate, ...]:
    if plan.quality_version != KNOWLEDGE_QUALITY_VERSION_V3 or type(final_candidates) is not int or not 4 <= final_candidates <= 20:
        raise ValueError("knowledge.invalid_requirement_ranking")
    validate_plan_requirements(
        quality_version=plan.quality_version, question_kind=plan.question_kind,
        requirements=plan.evidence_requirements, domain_ids=plan.selected_domain_ids,
    )
    # Stage supplies the already conflict-checked all-path canonical objects.
    canonical = {_identity(item): item for item in fused}
    pools = {
        domain: fusion.fuse(tuple(item for item in sets if item.logical_domain_id == domain))
        for domain in plan.selected_domain_ids
    }
    if any(len(pool) > 40 for pool in pools.values()):
        raise ValueError("knowledge.invalid_domain_candidate_count")
    queues: list[deque[tuple[tuple[str, str], float]]] = []
    for requirement in plan.evidence_requirements:
        candidates = pools[requirement.domain_id]
        if not candidates:
            queues.append(deque())
            continue
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("knowledge.rerank_deadline")
        scores = await rerank.rerank(
            query=requirement.focus, candidates=tuple(item.candidate for item in candidates),
            timeout_s=min(5.0, remaining),
        )
        if (
            type(scores) is not tuple or len(scores) != len(candidates)
            or any(type(item) is not RerankScore or type(item.candidate_index) is not int for item in scores)
            or {item.candidate_index for item in scores} != set(range(len(candidates)))
            or any(type(item.score) not in (int, float) or not math.isfinite(item.score) for item in scores)
        ):
            raise ValueError("knowledge.invalid_rerank_scores")
        by_index = {item.candidate_index: item.score for item in scores}
        ordered = sorted(enumerate(candidates), key=lambda pair: (
            -by_index[pair[0]], -pair[1].rrf_score, pair[1].candidate.chunk_id,
        ))
        queues.append(deque((_identity(item), by_index[index]) for index, item in ordered))

    selected: list[RankedKnowledgeCandidate] = []
    positions: dict[tuple[str, str], int] = {}

    def add(key: tuple[str, str], score: float, requirement_id: str | None) -> None:
        if key in positions:
            if requirement_id is not None:
                index = positions[key]
                selected[index] = replace(selected[index], requirement_ids=selected[index].requirement_ids + (requirement_id,))
            return
        item = canonical[key]
        positions[key] = len(selected)
        selected.append(RankedKnowledgeCandidate(
            candidate=item.candidate,
            domain_ids=tuple(domain for domain in plan.selected_domain_ids if domain in item.domain_ids),
            rerank_score=score, rank=len(selected) + 1,
            coverage_anchor=requirement_id is not None,
            requirement_ids=() if requirement_id is None else (requirement_id,),
        ))

    # Rank and score are fixed by first selection; later anchors only merge IDs.
    for requirement, queue in zip(plan.evidence_requirements, queues, strict=True):
        if queue:
            key, score = queue[0]
            add(key, score, requirement.requirement_id)
    while any(queues) and len(selected) < final_candidates:
        for queue in queues:
            if len(selected) == final_candidates:
                break
            while queue:
                key, score = queue.popleft()
                if key not in positions:
                    add(key, score, None)
                    break
    return tuple(selected)
