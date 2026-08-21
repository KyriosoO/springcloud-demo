from __future__ import annotations

import asyncio

from agent_runtime.knowledge.contracts import (
    DomainCandidateCount,
    FailedPath,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    PathFailureKind,
    PathRef,
    RetrievalCoverage,
    RetrievalPath,
    RetrievalStageCode,
    RetrievalStageKind,
    RetrievalStageResult,
)
from agent_runtime.knowledge.retrieval.contracts import (
    EmbeddingPort,
    KnowledgePathRequest,
    KnowledgeSearchPort,
    PathCandidateSet,
    PathResultFailure,
    PathResultKind,
    PathRetrievalResult,
    RankedKnowledgeBatch,
    RankedKnowledgeCandidate,
    RerankPort,
)
from agent_runtime.knowledge.retrieval.es_adapter import PROFILE_BY_DOMAIN
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.http import RetrievalTransportError


class DefaultKnowledgeRetrievalStage:
    __slots__ = ("_embedding", "_final_candidates", "_fusion", "_rerank", "_search")

    def __init__(
        self,
        *,
        search: KnowledgeSearchPort,
        embedding: EmbeddingPort,
        rerank: RerankPort,
        fusion: ReciprocalRankFusion | None = None,
        final_candidates: int = 20,
    ) -> None:
        if not 3 <= final_candidates <= 20:
            raise ValueError("knowledge.invalid_final_candidates")
        self._search = search
        self._embedding = embedding
        self._rerank = rerank
        self._fusion = fusion or ReciprocalRankFusion()
        self._final_candidates = final_candidates

    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[RankedKnowledgeBatch]:
        loop = asyncio.get_running_loop()
        deadline = min(context.deadline_monotonic - 0.1, loop.time() + timeout_s)
        if deadline <= loop.time():
            return RetrievalStageResult(kind=RetrievalStageKind.TIMEOUT, stage_code=RetrievalStageCode.RETRIEVAL_TIMEOUT)
        try:
            async with asyncio.timeout_at(deadline):
                return await self._execute(plan=plan, context=context, deadline=deadline)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return RetrievalStageResult(kind=RetrievalStageKind.TIMEOUT, stage_code=RetrievalStageCode.RETRIEVAL_TIMEOUT)
        except Exception:
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT)

    async def _execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        deadline: float,
    ) -> RetrievalStageResult[RankedKnowledgeBatch]:
        vector: tuple[float, ...] | None = None
        vector_failure: PathFailureKind | None = None
        if any(item.path is RetrievalPath.VECTOR for item in plan.items):
            try:
                vector = await self._embedding.embed(
                    text=plan.items[0].query_text,
                    timeout_s=min(3.0, deadline - asyncio.get_running_loop().time()),
                )
            except TimeoutError:
                vector_failure = PathFailureKind.TIMEOUT
            except Exception:
                vector_failure = PathFailureKind.DOWNSTREAM_FAILURE

        calls: list[asyncio.Task[PathRetrievalResult]] = []
        call_ordinals: list[int] = []
        synthetic: dict[int, PathRetrievalResult] = {}
        for index, item in enumerate(plan.items):
            if item.path is RetrievalPath.VECTOR and vector_failure is not None:
                synthetic[index] = PathRetrievalResult(
                    kind=PathResultKind.TIMEOUT if vector_failure is PathFailureKind.TIMEOUT else PathResultKind.FAILURE,
                    logical_domain_id=item.logical_domain_id,
                    retrieval_profile_id=PROFILE_BY_DOMAIN[item.logical_domain_id],
                    path=item.path,
                    failure=PathResultFailure.RETRIEVAL_FAILURE if vector_failure is PathFailureKind.DOWNSTREAM_FAILURE else None,
                )
                continue
            request = KnowledgePathRequest(
                logical_domain_id=item.logical_domain_id,
                retrieval_profile_id=PROFILE_BY_DOMAIN[item.logical_domain_id],
                path=item.path,
                query_text=item.query_text if item.path is RetrievalPath.KEYWORD else None,
                query_vector=vector if item.path is RetrievalPath.VECTOR else None,
                candidate_limit=item.candidate_limit,
            )
            calls.append(
                asyncio.create_task(
                    self._search.search(
                        request=request,
                        context=context,
                        timeout_s=min(5.0, deadline - asyncio.get_running_loop().time()),
                    )
                )
            )
            call_ordinals.append(index)
        try:
            raw = await asyncio.gather(*calls) if calls else []
        finally:
            for task in calls:
                if not task.done():
                    task.cancel()
            if calls:
                await asyncio.gather(*calls, return_exceptions=True)
        results = dict(synthetic)
        results.update(zip(call_ordinals, raw))
        ordered = tuple(results[index] for index in range(len(plan.items)))

        for item, path_result in zip(plan.items, ordered, strict=True):
            if (
                path_result.logical_domain_id != item.logical_domain_id
                or path_result.retrieval_profile_id != PROFILE_BY_DOMAIN[item.logical_domain_id]
                or path_result.path is not item.path
                or (path_result.kind is PathResultKind.CANDIDATES and not path_result.candidates)
                or (path_result.kind is not PathResultKind.CANDIDATES and path_result.candidates)
            ):
                return RetrievalStageResult(
                    kind=RetrievalStageKind.DOWNSTREAM_FAILURE,
                    stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT,
                )

        if any(item.kind is PathResultKind.FORBIDDEN for item in ordered):
            return RetrievalStageResult(kind=RetrievalStageKind.FORBIDDEN, stage_code=RetrievalStageCode.DOMAIN_FORBIDDEN)
        if any(item.failure is PathResultFailure.READ_DECISION_UNVERIFIABLE for item in ordered):
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.READ_DECISION_UNVERIFIABLE)
        if any(item.failure is PathResultFailure.READ_AUTHORITY_FAILURE for item in ordered):
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.READ_AUTHORITY_FAILURE)

        candidate_sets: list[PathCandidateSet] = []
        successful: list[PathRef] = []
        no_result: list[PathRef] = []
        failed: list[FailedPath] = []
        for path_result in ordered:
            ref = PathRef(logical_domain_id=path_result.logical_domain_id, path=path_result.path)
            if path_result.kind is PathResultKind.CANDIDATES:
                if not path_result.profile_version or not path_result.index_snapshot_id or not path_result.read_policy_version:
                    return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT)
                if any(
                    candidate.domain_id != path_result.logical_domain_id
                    or candidate.index_snapshot_id != path_result.index_snapshot_id
                    or candidate.read_policy_version != path_result.read_policy_version
                    for candidate in path_result.candidates
                ):
                    return RetrievalStageResult(
                        kind=RetrievalStageKind.DOWNSTREAM_FAILURE,
                        stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT,
                    )
                successful.append(ref)
                candidate_sets.append(
                    PathCandidateSet(
                        logical_domain_id=path_result.logical_domain_id,
                        retrieval_profile_id=path_result.retrieval_profile_id,
                        path=path_result.path,
                        profile_version=path_result.profile_version,
                        index_snapshot_id=path_result.index_snapshot_id,
                        read_policy_version=path_result.read_policy_version,
                        truncated=path_result.truncated,
                        candidates=path_result.candidates,
                    )
                )
            elif path_result.kind is PathResultKind.NO_RESULT:
                no_result.append(ref)
            elif path_result.kind is PathResultKind.TIMEOUT:
                failed.append(FailedPath(logical_domain_id=path_result.logical_domain_id, path=path_result.path, failure_kind=PathFailureKind.TIMEOUT))
            else:
                failed.append(FailedPath(logical_domain_id=path_result.logical_domain_id, path=path_result.path, failure_kind=PathFailureKind.DOWNSTREAM_FAILURE))

        profile_snapshots: dict[tuple[str, str], tuple[str, str, str]] = {}
        for candidate_set in candidate_sets:
            key = (candidate_set.logical_domain_id, candidate_set.retrieval_profile_id)
            snapshot = (
                candidate_set.profile_version,
                candidate_set.index_snapshot_id,
                candidate_set.read_policy_version,
            )
            existing = profile_snapshots.setdefault(key, snapshot)
            if existing != snapshot:
                return RetrievalStageResult(
                    kind=RetrievalStageKind.DOWNSTREAM_FAILURE,
                    stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT,
                )

        fused = self._fusion.fuse(tuple(candidate_sets))
        if not fused:
            counts = tuple(DomainCandidateCount(logical_domain_id=domain, count=0) for domain in plan.selected_domain_ids)
            coverage = RetrievalCoverage(
                successful_paths=tuple(successful),
                no_result_paths=tuple(no_result),
                failed_paths=tuple(failed),
                candidate_count_by_domain=counts,
                complete=not failed,
            )
            if failed:
                code = RetrievalStageCode.RETRIEVAL_TIMEOUT if any(item.failure_kind is PathFailureKind.TIMEOUT for item in failed) else RetrievalStageCode.RETRIEVAL_FAILURE
                return RetrievalStageResult(kind=RetrievalStageKind.TIMEOUT if code is RetrievalStageCode.RETRIEVAL_TIMEOUT else RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=code)
            return RetrievalStageResult(kind=RetrievalStageKind.NO_RESULT, coverage=coverage)
        rerank_candidates = tuple(item.candidate for item in fused)
        try:
            scores = await self._rerank.rerank(
                query=plan.items[0].query_text,
                candidates=rerank_candidates,
                timeout_s=min(5.0, deadline - asyncio.get_running_loop().time()),
            )
        except TimeoutError:
            return RetrievalStageResult(kind=RetrievalStageKind.TIMEOUT, stage_code=RetrievalStageCode.RERANK_TIMEOUT)
        except RetrievalTransportError:
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.RERANK_FAILURE)
        except Exception:
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT)
        if {item.candidate_index for item in scores} != set(range(len(fused))):
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT)
        score_by_index = {item.candidate_index: item.score for item in scores}
        ordered_fused = sorted(
            enumerate(fused),
            key=lambda pair: (-score_by_index[pair[0]], -pair[1].rrf_score, pair[1].candidate.chunk_id),
        )[: self._final_candidates]
        ranked = tuple(
            RankedKnowledgeCandidate(
                candidate=item.candidate,
                domain_ids=item.domain_ids,
                rerank_score=score_by_index[index],
                rank=rank,
            )
            for rank, (index, item) in enumerate(ordered_fused, 1)
        )
        profile_versions = {item.profile_version for item in candidate_sets}
        if len(profile_versions) != 1:
            return RetrievalStageResult(kind=RetrievalStageKind.DOWNSTREAM_FAILURE, stage_code=RetrievalStageCode.INVALID_PROVIDER_RESULT)
        snapshots = tuple(dict.fromkeys(item.index_snapshot_id for item in candidate_sets))
        batch = RankedKnowledgeBatch(candidates=ranked, profile_version=next(iter(profile_versions)), index_snapshot_ids=snapshots)
        counts = tuple(
            DomainCandidateCount(logical_domain_id=domain, count=sum(domain in item.domain_ids for item in ranked))
            for domain in plan.selected_domain_ids
        )
        coverage = RetrievalCoverage(
            successful_paths=tuple(successful),
            no_result_paths=tuple(no_result),
            failed_paths=tuple(failed),
            candidate_count_by_domain=counts,
            complete=not failed,
        )
        return RetrievalStageResult(kind=RetrievalStageKind.SUCCESS, batch=batch, coverage=coverage)
