from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate,
    FusedCandidate,
    PathCandidateSet,
    PathRank,
)


def _identity(item: AuthorizedKnowledgeCandidate | FusedCandidate) -> tuple[str, str]:
    candidate = item.candidate if isinstance(item, FusedCandidate) else item
    return candidate.document_id, candidate.chunk_id


def _same_candidate(left: AuthorizedKnowledgeCandidate, right: AuthorizedKnowledgeCandidate) -> bool:
    ignored = {"domain_id", "source_rank"}
    fields = left.__dataclass_fields__
    return all(getattr(left, name) == getattr(right, name) for name in fields if name not in ignored)


class ReciprocalRankFusion:
    def fuse(self, results: tuple[PathCandidateSet, ...]) -> tuple[FusedCandidate, ...]:
        fused: dict[tuple[str, str], FusedCandidate] = {}
        order: dict[tuple[str, str], int] = {}
        next_order = 0
        for result in results:
            if tuple(item.source_rank for item in result.candidates) != tuple(range(1, len(result.candidates) + 1)):
                raise ValueError("knowledge.invalid_provider_result")
            identities = tuple(_identity(item) for item in result.candidates)
            if len(set(identities)) != len(identities):
                raise ValueError("knowledge.invalid_provider_result")
            for candidate in result.candidates:
                identity = _identity(candidate)
                path_rank = PathRank(
                    logical_domain_id=result.logical_domain_id,
                    path=result.path,
                    rank=candidate.source_rank,
                )
                score = 1.0 / (60 + candidate.source_rank)
                existing = fused.get(identity)
                if existing is None:
                    order[identity] = next_order
                    next_order += 1
                    fused[identity] = FusedCandidate(
                        candidate=candidate,
                        domain_ids=(candidate.domain_id,),
                        path_ranks=(path_rank,),
                        rrf_score=score,
                    )
                else:
                    if not _same_candidate(existing.candidate, candidate):
                        raise ValueError("knowledge.candidate_conflict")
                    domain_ids = existing.domain_ids
                    if candidate.domain_id not in domain_ids:
                        domain_ids += (candidate.domain_id,)
                    fused[identity] = replace(
                        existing,
                        domain_ids=domain_ids,
                        path_ranks=existing.path_ranks + (path_rank,),
                        rrf_score=existing.rrf_score + score,
                    )
        return tuple(
            sorted(
                fused.values(),
                key=lambda item: (-item.rrf_score, item.candidate.chunk_id, order[_identity(item)]),
            )
        )
