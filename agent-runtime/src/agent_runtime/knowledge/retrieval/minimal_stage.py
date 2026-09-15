"""Unwired replacement strategy for DR-KRET-201..203; owns no clients or model tasks."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import hashlib
import math
import re
from typing import TypeVar

from agent_runtime.knowledge.contracts import (
    DomainCandidateCount, FailedPath, KnowledgeRetrievalContext, PathFailureKind, PathRef,
    RetrievalCoverage, RetrievalPath, RetrievalPlanItem, RetrievalStageCode,
    RetrievalStageKind, RetrievalStageResult,
)
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgeRetrievalPlan, MinimalRetrievalSettings
from agent_runtime.knowledge.retrieval.contracts import (
    EmbeddingPort, KnowledgePathRequest, KnowledgeSearchPort, PathCandidateSet,
    PathResultFailure, PathResultKind, PathRetrievalResult, RerankPort,
)
from agent_runtime.knowledge.retrieval.es_adapter import PROFILE_BY_DOMAIN
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.http import RetrievalTransportError
from agent_runtime.knowledge.retrieval.minimal_ranking import (
    MinimalRankedBatch, domain_pool, order_domain, round_robin,
)


T = TypeVar("T")
# Same fixed version accepted by the existing typed ES adapter; not a deployment override.
PROFILE_VERSION = "tax-knowledge-search-v1"


class _StageFailure(Exception):
    def __init__(self, code: RetrievalStageCode) -> None:
        self.code = code


def _failure(code: RetrievalStageCode) -> RetrievalStageResult[MinimalRankedBatch]:
    if code is RetrievalStageCode.DOMAIN_FORBIDDEN:
        kind = RetrievalStageKind.FORBIDDEN
    elif code in (RetrievalStageCode.RETRIEVAL_TIMEOUT, RetrievalStageCode.RERANK_TIMEOUT):
        kind = RetrievalStageKind.TIMEOUT
    else:
        kind = RetrievalStageKind.DOWNSTREAM_FAILURE
    return RetrievalStageResult(kind=kind, stage_code=code)


def _remaining(deadline: float) -> float:
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise TimeoutError
    return min(5.0, remaining)


async def _bounded(call: Callable[[float], Awaitable[T]], deadline: float) -> T:
    timeout = _remaining(deadline)
    cutoff = asyncio.get_running_loop().time() + timeout
    async with asyncio.timeout(timeout) as timeout_scope:
        result = await call(timeout)
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError
    # A port that swallows cancellation must not turn a late response into success.
    if timeout_scope.expired() or asyncio.get_running_loop().time() >= cutoff:
        raise TimeoutError
    return result


def _terminal(results: tuple[PathRetrievalResult, ...]) -> RetrievalStageCode | None:
    if any(item.kind is PathResultKind.FORBIDDEN for item in results):
        return RetrievalStageCode.DOMAIN_FORBIDDEN
    for failure, code in (
        (PathResultFailure.READ_DECISION_UNVERIFIABLE, RetrievalStageCode.READ_DECISION_UNVERIFIABLE),
        (PathResultFailure.READ_AUTHORITY_FAILURE, RetrievalStageCode.READ_AUTHORITY_FAILURE),
        (PathResultFailure.INVALID_PROVIDER_RESULT, RetrievalStageCode.INVALID_PROVIDER_RESULT),
    ):
        if any(item.failure is failure for item in results):
            return code
    return None


def _candidate_set(result: PathRetrievalResult) -> PathCandidateSet:
    if (result.profile_version != PROFILE_VERSION or type(result.index_snapshot_id) is not str
            or re.fullmatch(r"[0-9a-f]{64}", result.index_snapshot_id) is None
            or type(result.read_policy_version) is not str
            or re.fullmatch(r"[A-Za-z0-9._:-]{1,256}", result.read_policy_version) is None
            or type(result.truncated) is not bool or type(result.candidates) is not tuple
            or len(result.candidates) > 20 or result.failure is not None
            or (result.kind is PathResultKind.CANDIDATES) != bool(result.candidates)):
        raise ValueError("knowledge.invalid_provider_result")
    for rank, candidate in enumerate(result.candidates, start=1):
        if (type(candidate.source_rank) is not int or candidate.source_rank != rank
                or candidate.domain_id != result.logical_domain_id
                or candidate.index_snapshot_id != result.index_snapshot_id
                or candidate.read_policy_version != result.read_policy_version
                or candidate.content_sha256 != hashlib.sha256(candidate.content.encode("utf-8")).hexdigest()):
            raise ValueError("knowledge.invalid_provider_result")
    return PathCandidateSet(logical_domain_id=result.logical_domain_id,
        retrieval_profile_id=result.retrieval_profile_id, path=result.path,
        profile_version=result.profile_version, index_snapshot_id=result.index_snapshot_id,
        read_policy_version=result.read_policy_version, truncated=result.truncated, candidates=result.candidates)


class MinimalKnowledgeRetrievalStage:
    """Request-local work only; existing Runtime still owns HTTP client shutdown."""

    def __init__(self, *, search: KnowledgeSearchPort, embedding: EmbeddingPort,
                 rerank: RerankPort, settings: MinimalRetrievalSettings) -> None:
        self._search = search
        self._embedding = embedding
        self._rerank = rerank
        self._settings = settings

    async def execute(self, *, plan: MinimalKnowledgeRetrievalPlan, context: KnowledgeRetrievalContext,
                      timeout_s: float) -> RetrievalStageResult[MinimalRankedBatch]:
        # Reject malformed/mismatched plans before starting even the cancellation watcher.
        if type(plan) is not MinimalKnowledgeRetrievalPlan:
            raise ValueError("knowledge.minimal_plan_invalid")
        plan.validate(self._settings)
        if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("knowledge.invalid_timeout")
        if (type(context.deadline_monotonic) not in (int, float)
                or not math.isfinite(context.deadline_monotonic)):
            raise ValueError("knowledge.invalid_timeout")
        if context.cancellation.is_cancelled():
            raise asyncio.CancelledError
        deadline = min(context.deadline_monotonic - 0.1,
            asyncio.get_running_loop().time() + min(timeout_s, self._settings.retrieval_timeout_s))
        work = asyncio.create_task(self._execute(plan, context, deadline))
        cancelled = asyncio.create_task(context.cancellation.wait_cancelled())
        try:
            await asyncio.wait((work, cancelled), return_when=asyncio.FIRST_COMPLETED)
            if cancelled.done() or context.cancellation.is_cancelled():
                raise asyncio.CancelledError
            return work.result()
        finally:
            for task in (work, cancelled):
                if not task.done():
                    task.cancel()
            await asyncio.gather(work, cancelled, return_exceptions=True)

    async def _execute(self, plan: MinimalKnowledgeRetrievalPlan, context: KnowledgeRetrievalContext,
                       deadline: float) -> RetrievalStageResult[MinimalRankedBatch]:
        try:
            return await self._retrieve(plan, context, deadline)
        except _StageFailure as exc:
            return _failure(exc.code)
        except TimeoutError:
            return _failure(RetrievalStageCode.RETRIEVAL_TIMEOUT)
        except (ValueError, UnicodeError):
            return _failure(RetrievalStageCode.INVALID_PROVIDER_RESULT)

    async def _retrieve(self, plan: MinimalKnowledgeRetrievalPlan, context: KnowledgeRetrievalContext,
                        deadline: float) -> RetrievalStageResult[MinimalRankedBatch]:
        vector: tuple[float, ...] | None = None
        vector_failure = PathResultKind.FAILURE
        try:
            vector = await _bounded(lambda timeout: self._embedding.embed(text=plan.original_question,
                timeout_s=timeout), deadline)
            if (type(vector) is not tuple or len(vector) != 1024
                    or any(type(value) is not float or not math.isfinite(value) for value in vector)):
                raise ValueError("knowledge.invalid_embedding")
        except TimeoutError:
            vector_failure = PathResultKind.TIMEOUT
        except RetrievalTransportError:
            pass  # Ordinary embedding failure is a failed vector path, never another query.
        _remaining(deadline)
        tasks = [asyncio.create_task(self._path(item, vector, vector_failure, context, deadline)) for item in plan.items]
        pending = set(tasks)
        results: dict[asyncio.Task[PathRetrievalResult], PathRetrievalResult] = {}
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                invalid: ValueError | None = None
                for task in done:
                    try:
                        results[task] = task.result()
                    except ValueError as exc:
                        invalid = exc
                terminal = _terminal(tuple(results.values()))
                if terminal is not None:
                    raise _StageFailure(terminal)
                if invalid is not None:
                    raise invalid
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        ordered = tuple(results[task] for task in tasks)
        sets = tuple(_candidate_set(item) for item in ordered
                     if item.kind in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT))
        snapshots: dict[str, tuple[str, str, str]] = {}
        for item in sets:
            snapshot = (item.profile_version, item.index_snapshot_id, item.read_policy_version)
            if snapshots.setdefault(item.logical_domain_id, snapshot) != snapshot:
                raise ValueError("knowledge.snapshot_conflict")
        # Validate EVERY candidate across ALL paths/domains before domain pools or top20 selection.
        fused = ReciprocalRankFusion().fuse(sets)
        coverage = RetrievalCoverage(
            successful_paths=tuple(PathRef(logical_domain_id=item.logical_domain_id, path=item.path)
                for item in ordered if item.kind is PathResultKind.CANDIDATES),
            no_result_paths=tuple(PathRef(logical_domain_id=item.logical_domain_id, path=item.path)
                for item in ordered if item.kind is PathResultKind.NO_RESULT),
            failed_paths=tuple(FailedPath(logical_domain_id=item.logical_domain_id, path=item.path,
                failure_kind=PathFailureKind.TIMEOUT if item.kind is PathResultKind.TIMEOUT else PathFailureKind.DOWNSTREAM_FAILURE)
                for item in ordered if item.kind in (PathResultKind.FAILURE, PathResultKind.TIMEOUT)),
            candidate_count_by_domain=tuple(DomainCandidateCount(logical_domain_id=domain,
                count=sum(domain in item.domain_ids for item in fused)) for domain in plan.selected_domain_ids),
            complete=all(item.kind in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT) for item in ordered),
        )
        if not fused and coverage.complete:
            return RetrievalStageResult(kind=RetrievalStageKind.NO_RESULT, coverage=coverage)
        if coverage.failed_paths and (not all(item.count for item in coverage.candidate_count_by_domain)
                or sum(item.count for item in coverage.candidate_count_by_domain) < self._settings.min_partial_candidates):
            return _failure(RetrievalStageCode.RETRIEVAL_FAILURE)
        queues = []
        for domain in plan.selected_domain_ids:
            pool = domain_pool(sets, domain)
            if not pool:
                continue
            try:
                scores = await _bounded(lambda timeout: self._rerank.rerank(query=plan.original_question,
                    candidates=tuple(item.candidate for item in pool), timeout_s=timeout), deadline)
                queues.append(order_domain(pool, scores))
            except TimeoutError as exc:
                raise _StageFailure(RetrievalStageCode.RERANK_TIMEOUT) from exc
            except (RetrievalTransportError, ValueError) as exc:
                raise _StageFailure(RetrievalStageCode.RERANK_FAILURE) from exc
        _remaining(deadline)
        ranked = round_robin(tuple(queues), fused)
        batch = MinimalRankedBatch(candidates=ranked, profile_version=PROFILE_VERSION,
            index_snapshot_ids=tuple(dict.fromkeys(item.index_snapshot_id for item in sets)))
        return RetrievalStageResult(kind=RetrievalStageKind.SUCCESS, batch=batch, coverage=coverage)

    async def _path(self, item: RetrievalPlanItem, vector: tuple[float, ...] | None,
                    vector_failure: PathResultKind, context: KnowledgeRetrievalContext,
                    deadline: float) -> PathRetrievalResult:
        if item.path is RetrievalPath.VECTOR and vector is None:
            return PathRetrievalResult(kind=vector_failure, logical_domain_id=item.logical_domain_id,
                retrieval_profile_id=PROFILE_BY_DOMAIN[item.logical_domain_id], path=item.path)
        request = KnowledgePathRequest(logical_domain_id=item.logical_domain_id,
            retrieval_profile_id=PROFILE_BY_DOMAIN[item.logical_domain_id], path=item.path,
            query_text=item.query_text if item.path is RetrievalPath.KEYWORD else None,
            query_vector=vector if item.path is RetrievalPath.VECTOR else None, candidate_limit=20)
        try:
            result = await _bounded(lambda timeout: self._search.search(request=request,
                context=context, timeout_s=timeout), deadline)
        except TimeoutError:
            result = PathRetrievalResult(kind=PathResultKind.TIMEOUT, logical_domain_id=item.logical_domain_id,
                retrieval_profile_id=request.retrieval_profile_id, path=item.path)
        except RetrievalTransportError:
            result = PathRetrievalResult(kind=PathResultKind.FAILURE, logical_domain_id=item.logical_domain_id,
                retrieval_profile_id=request.retrieval_profile_id, path=item.path,
                failure=PathResultFailure.RETRIEVAL_FAILURE)
        if (not isinstance(result, PathRetrievalResult) or not isinstance(result.kind, PathResultKind)
                or result.logical_domain_id != request.logical_domain_id
                or result.retrieval_profile_id != request.retrieval_profile_id or result.path is not request.path
                or result.failure is not None and not isinstance(result.failure, PathResultFailure)
                or result.kind not in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT) and result.candidates != ()):
            raise ValueError("knowledge.invalid_provider_result")
        return result
