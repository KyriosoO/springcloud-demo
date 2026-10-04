"""Private counted production-Stage assembly, not a real-run launcher or grant.

The outer authorized executor still owns snapshots, startup/readiness, clients,
physical proxies, journal and cleanup. This module discovers no credentials or
resources and exposes no CLI. In-memory provider data never become a verdict.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import time
from typing import Protocol

from agent_runtime.capability_api.contracts import CancellationSignal, OpaqueUserToken
from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalStageKind
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate, KnowledgePathRequest, PathResultKind, PathRetrievalResult, RerankScore,
)
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import KnowledgeHttpTransport
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage, _bounded
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_projection import ProjectedJavaPair
from tests.evaluation.knowledge.rebuild_document_number_transport import (
    AttemptLedger, CountedKnowledgeTransport, PhysicalWitness,
)


class CasePhysicalPort(Protocol):
    """Future owned proxy binds before sends and returns exact physical receipts."""
    def bind(self, *, case: p.ComparisonCase, vector: tuple[float, ...],
             keyword_sha256: tuple[tuple[str, str], ...]) -> None: ...
    def finish(self) -> tuple[PhysicalWitness, ...]: ...


async def _shared_embedding(*, case: p.ComparisonCase, transport: KnowledgeHttpTransport,
                            ledger: AttemptLedger, cancellation: CancellationSignal) -> tuple[float, ...]:
    """The shared per-case inference is cancellable too, before Stage starts."""
    adapter = BgeM3EmbeddingAdapter(CountedKnowledgeTransport(delegate=transport,
        ledger=ledger, case=case, arm="shared", kind="queryEmbedding"))
    # Reuse the production absolute-deadline/late-result check. A socket read
    # timeout alone permits endless slow chunks, and a provider that swallows
    # cancellation must not let a late embedding advance the comparison.
    deadline = asyncio.get_running_loop().time() + 3
    work = asyncio.create_task(_bounded(lambda timeout: adapter.embed(
        text=case.plan.original_question, timeout_s=timeout), deadline))
    cancelled = asyncio.create_task(cancellation.wait_cancelled())
    try:
        await asyncio.wait((work, cancelled), return_when=asyncio.FIRST_COMPLETED)
        if cancelled.done() or cancellation.is_cancelled():
            raise asyncio.CancelledError
        return work.result()
    finally:
        for task in (work, cancelled):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, cancelled, return_exceptions=True)


class _CapturedPorts:
    def __init__(self, *, case: p.ComparisonCase, arm: str, vector: tuple[float, ...],
                 context: KnowledgeRetrievalContext, ledger: AttemptLedger,
                 typed: KnowledgeHttpTransport, rerank: KnowledgeHttpTransport) -> None:
        self.case, self.arm, self.vector, self.context, self.ledger = case, arm, vector, context, ledger
        self.search_adapter = EsKnowledgeSearchAdapter(CountedKnowledgeTransport(
            delegate=typed, ledger=ledger, case=case, arm=arm, kind="typedSearch", vector=vector))
        self.rerank_transport = rerank
        self.paths: dict[tuple[str, object], PathRetrievalResult] = {}
        self.reranks: list[tuple[tuple[AuthorizedKnowledgeCandidate, ...], tuple[RerankScore, ...]]] = []
        self.embedding_used = False

    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]:
        p.require(text == self.case.plan.original_question and not self.embedding_used and timeout_s > 0,
                  "stage_embedding_drift")
        self.embedding_used = True
        return self.vector  # One shared counted inference, no per-arm reinference.

    async def search(self, *, request: KnowledgePathRequest, context: KnowledgeRetrievalContext,
                     timeout_s: float) -> PathRetrievalResult:
        key = (request.logical_domain_id, request.path)
        p.require(context is self.context and key not in self.paths, "stage_search_drift")
        result = await self.search_adapter.search(request=request, context=context, timeout_s=timeout_s)
        if result.kind not in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT):
            # The production adapter deliberately returns a terminal DTO.
            # This independent comparison forbids continued sends even for
            # a malformed HTTP200 response; peers not yet sent must stop now.
            self.ledger.abort()
        self.paths[key] = result
        return result

    async def rerank(self, *, query: str, candidates: tuple[AuthorizedKnowledgeCandidate, ...],
                     timeout_s: float) -> tuple[RerankScore, ...]:
        p.require(bool(candidates) and all(item.domain_id == candidates[0].domain_id for item in candidates),
                  "stage_rerank_domain_drift")
        adapter = ContextualBgeRerankAdapter(CountedKnowledgeTransport(delegate=self.rerank_transport,
            ledger=self.ledger, case=self.case, arm=self.arm, kind="rerank", domain=candidates[0].domain_id))
        scores = await adapter.rerank(query=query, candidates=candidates, timeout_s=timeout_s)
        self.reranks.append((candidates, scores))
        return scores

    def captured(self) -> p.ReplayArm:
        ordered = tuple(self.paths[(item.logical_domain_id, item.path)] for item in self.case.plan.items)
        scores = tuple((candidates[0].domain_id, tuple((p.CandidateRef.from_candidate(candidates[row.candidate_index]),
                                                       row.score) for row in rows))
                       for candidates, rows in self.reranks)
        return p.ReplayArm(ordered, scores)


@dataclass(frozen=True, slots=True)
class StageComparisonResult:
    """Finite trace, not a completed run, quality assessment or release result."""
    cases: tuple[p.CaseTrace, ...]
    counted_attempts: tuple[tuple[str, int], ...]
    physical_witnesses: tuple[PhysicalWitness, ...]
    evidence_kind: str = "captured_transport_stage_trace"
    quality_assessment: str = "Not assessed"
    release_allowed: bool = False
    latency_scope: str = "production_stage_excluding_shared_query_embedding"


class StageComparisonSession:
    """Once-only full selected case order, including alternating arm order.

    Production adapters retain their exact DTO decoders, and the production
    Stage retains parallel paths, RRF/domain pools/rerank/final20 and cancel.
    This never calls synthetic ReplaySession or repeats a failed request.
    """
    def __init__(self, *, pair: ProjectedJavaPair, ledger: AttemptLedger,
                 typed: tuple[KnowledgeHttpTransport, KnowledgeHttpTransport],
                 embedding: KnowledgeHttpTransport, rerank: KnowledgeHttpTransport,
                 physical: tuple[CasePhysicalPort, CasePhysicalPort]) -> None:
        p.require(type(pair) is ProjectedJavaPair and type(ledger) is AttemptLedger
                  and type(typed) is tuple and len(typed) == 2 and type(physical) is tuple and len(physical) == 2,
                  "stage_binding_invalid")
        pair.draft.__post_init__()
        self.pair, self.ledger, self.typed = pair, ledger, typed
        self.embedding, self.rerank, self.physical = embedding, rerank, physical
        self.attempted = False

    async def evaluate(self, *, token: OpaqueUserToken, cancellation: CancellationSignal) -> StageComparisonResult:
        p.require(not self.attempted and not self.ledger.view()["stopped"], "stage_session_already_attempted")
        self.attempted = True
        completed: list[p.CaseTrace] = []
        witnesses: list[PhysicalWitness] = []
        failed = False
        cancelled = False
        try:
            self.pair.verify_artifacts()
            for number, case in enumerate(self.pair.draft.cases):
                if cancellation.is_cancelled():
                    raise asyncio.CancelledError
                vector = await _shared_embedding(case=case, transport=self.embedding, ledger=self.ledger,
                                                 cancellation=cancellation)
                captures: dict[str, p.ReplayArm] = {}
                traces: dict[str, p.ArmTrace] = {}
                for arm in (p.ARMS if number % 2 == 0 else tuple(reversed(p.ARMS))):
                    if cancellation.is_cancelled():
                        raise asyncio.CancelledError
                    index = p.ARMS.index(arm)
                    proof = self.pair.proofs[index]
                    p.require(proof.arm == arm, "stage_projection_drift")
                    hashes = proof.for_case(case)
                    physical = self.physical[index]
                    physical.bind(case=case, vector=vector, keyword_sha256=hashes)
                    context = KnowledgeRetrievalContext(request_id=case.case_id, correlation_id=case.case_id,
                        subject="isolated-document-number-comparison", user_token=token,
                        deadline_monotonic=asyncio.get_running_loop().time() + 30, cancellation=cancellation)
                    ports = _CapturedPorts(case=case, arm=arm, vector=vector, context=context, ledger=self.ledger,
                        typed=self.typed[index], rerank=self.rerank)
                    started = time.perf_counter()
                    result = await MinimalKnowledgeRetrievalStage(search=ports, embedding=ports, rerank=ports,
                        settings=case.plan.settings).execute(plan=case.plan, context=context, timeout_s=20)
                    elapsed = time.perf_counter() - started
                    p.require(result.kind in (RetrievalStageKind.SUCCESS, RetrievalStageKind.NO_RESULT)
                        and result.coverage is not None and result.coverage.complete
                        and not result.coverage.failed_paths and ports.embedding_used
                        and len(ports.paths) == len(case.plan.items) and not self.ledger.view()["stopped"],
                        "stage_incomplete")
                    capture = ports.captured()
                    receipts = physical.finish()
                    expected = {(item.logical_domain_id, item.path.value) for item in case.plan.items}
                    p.require(type(receipts) is tuple and len(receipts) == len(expected)
                        and all(type(row) is PhysicalWitness and row.case_id == case.case_id and row.arm == arm
                            and row.http_status == 200 for row in receipts)
                        and {(row.domain, row.path) for row in receipts} == expected
                        and all(row.path != "keyword" or row.canonical_sha256 == dict(hashes)[row.domain]
                                for row in receipts), "stage_physical_witness_missing")
                    witnesses.extend(receipts)
                    final = () if result.batch is None else tuple(p.CandidateRef.from_candidate(row.candidate)
                                                                 for row in result.batch.candidates)
                    traces[arm] = replace(p.captured_trace(arm, case, capture.paths, tuple(ports.reranks), final),
                                          latency_seconds=elapsed)
                    captures[arm] = capture
                p._validate_pair(case, p.CaseReplay(case.case_id, captures["old"], captures["current"], vector))
                completed.append(p.CaseTrace(case.case_id, traces["old"], traces["current"]))
            return StageComparisonResult(tuple(completed), tuple(self.ledger.counts.items()), tuple(witnesses))
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            failed = True
        # Stop after technical/protocol failure; keep attempts in the outer
        # journal, but never retain raw response/exception/provider messages.
        self.ledger.abort()
        if cancelled:
            raise asyncio.CancelledError from None
        if failed:
            raise p.ProtocolError("stage_comparison_failed") from None
        raise p.ProtocolError("stage_comparison_incomplete")
