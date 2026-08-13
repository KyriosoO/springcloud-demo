from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from agent_runtime.capability_api.contracts import CapabilityResult, CapabilityStatus
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.contracts import (
    EvidenceStageResult,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
    KnowledgeEvidenceStage,
    KnowledgeQueryArguments,
    KnowledgeQuestionRewriteStage,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    KnowledgeRetrievalStage,
    RetrievalPath,
    RetrievalStageResult,
    RewriteStageResult,
)
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceBundle
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate,
    EmbeddingPort,
    FusedCandidate,
    KnowledgePathRequest,
    KnowledgeSearchPort,
    PathCandidateSet,
    PathRetrievalResult,
    RankedKnowledgeBatch,
    RerankPort,
    RerankScore,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker

from tests.evaluation.knowledge.contracts import (
    EvaluationCase,
    EvaluationExecutionFixture,
    EvaluationVariantResult,
    MetricValue,
    ModelCallCountRecord,
    PathRankingRecord,
    VariantCaseMetrics,
)
from tests.evaluation.knowledge.live_contracts import BudgetedLiveModelTransport


class ResettableRecorder(Protocol):
    def reset(self) -> None: ...


class RecordingQuestionRewriter:
    def __init__(self, delegate: KnowledgeQuestionRewriteStage) -> None:
        self._delegate = delegate
        self.calls = 0
        self.last_result: RewriteStageResult | None = None

    def reset(self) -> None:
        self.last_result = None

    async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult:
        self.calls += 1
        self.last_result = await self._delegate.rewrite(original_question=original_question, timeout_s=timeout_s)
        return self.last_result


class RecordingKnowledgeSearch:
    def __init__(self, delegate: KnowledgeSearchPort) -> None:
        self._delegate = delegate
        self.calls = 0
        self.requests: list[tuple[str, RetrievalPath]] = []
        self.results: dict[tuple[str, RetrievalPath], PathRetrievalResult] = {}

    def reset(self) -> None:
        self.requests.clear()
        self.results.clear()

    async def search(
        self,
        *,
        request: KnowledgePathRequest,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> PathRetrievalResult:
        self.calls += 1
        self.requests.append((request.logical_domain_id, request.path))
        result = await self._delegate.search(request=request, context=context, timeout_s=timeout_s)
        self.results[(request.logical_domain_id, request.path)] = result
        return result


class RecordingEmbedding:
    def __init__(self, delegate: EmbeddingPort) -> None:
        self._delegate = delegate
        self.calls = 0

    def reset(self) -> None:
        return

    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]:
        self.calls += 1
        return await self._delegate.embed(text=text, timeout_s=timeout_s)


class RecordingFusion:
    def __init__(self, delegate: ReciprocalRankFusion | None = None) -> None:
        self._delegate = delegate or ReciprocalRankFusion()
        self.last_fused: tuple[FusedCandidate, ...] = ()

    def reset(self) -> None:
        self.last_fused = ()

    def fuse(self, results: tuple[PathCandidateSet, ...]) -> tuple[FusedCandidate, ...]:
        self.last_fused = self._delegate.fuse(results)
        return self.last_fused


class RecordingRerank:
    def __init__(self, delegate: RerankPort) -> None:
        self._delegate = delegate
        self.calls = 0

    def reset(self) -> None:
        return

    async def rerank(
        self,
        *,
        query: str,
        candidates: tuple[AuthorizedKnowledgeCandidate, ...],
        timeout_s: float,
    ) -> tuple[RerankScore, ...]:
        self.calls += 1
        return await self._delegate.rerank(query=query, candidates=candidates, timeout_s=timeout_s)


class RecordingRetrievalStage:
    def __init__(self, delegate: KnowledgeRetrievalStage[RankedKnowledgeBatch]) -> None:
        self._delegate = delegate
        self.calls = 0
        self.last_plan: KnowledgeRetrievalPlan | None = None
        self.last_result: RetrievalStageResult[RankedKnowledgeBatch] | None = None

    def reset(self) -> None:
        self.last_plan = None
        self.last_result = None

    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[RankedKnowledgeBatch]:
        self.calls += 1
        self.last_plan = plan
        self.last_result = await self._delegate.execute(plan=plan, context=context, timeout_s=timeout_s)
        return self.last_result


class RecordingEvidenceStage:
    def __init__(self, delegate: KnowledgeEvidenceStage[RankedKnowledgeBatch]) -> None:
        self._delegate = delegate
        self.calls = 0
        self.last_input: KnowledgeEvidenceInput[RankedKnowledgeBatch] | None = None
        self.last_result: EvidenceStageResult | None = None

    def reset(self) -> None:
        self.last_input = None
        self.last_result = None

    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult:
        self.calls += 1
        self.last_input = input
        self.last_result = await self._delegate.build_result(input=input, context=context, timeout_s=timeout_s)
        return self.last_result


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewMaterial:
    case_id: str
    expected_answerability: str
    question: str
    terminal_status: str
    answer_summary: str | None
    points: tuple[dict[str, object], ...]
    coverage: Mapping[str, object] | None

    def as_dict(self) -> dict[str, object]:
        return {
            "caseId": self.case_id,
            "expectedAnswerability": self.expected_answerability,
            "question": self.question,
            "terminalStatus": self.terminal_status,
            "answerSummary": self.answer_summary,
            "points": _thaw(self.points),
            "coverage": _thaw(self.coverage),
        }


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveEvaluatedVariant:
    result: EvaluationVariantResult
    review_material: ReviewMaterial | None


def _metric_for_rank(document_ids: tuple[str, ...], gold: tuple[str, ...]) -> tuple[MetricValue, MetricValue]:
    if not gold:
        return "not_applicable", "not_applicable"
    gold_set = set(gold)
    recall = len(set(document_ids) & gold_set) / len(gold_set)
    first = next((index for index, item in enumerate(document_ids, 1) if item in gold_set), None)
    return recall, 0.0 if first is None else 1.0 / first


def _evidence_ids(result: CapabilityResult) -> tuple[str, ...]:
    if result.domain_result is None:
        return ()
    points = result.domain_result.get("points")
    if not isinstance(points, tuple):
        return ()
    output: list[str] = []
    for point in points:
        if not isinstance(point, Mapping):
            continue
        citation = point.get("citation")
        if isinstance(citation, Mapping) and isinstance(citation.get("evidenceId"), str):
            output.append(cast(str, citation["evidenceId"]))
    return tuple(output)


def _review_material(case: EvaluationCase, result: CapabilityResult) -> ReviewMaterial:
    domain = result.domain_result
    answer_summary: str | None = None
    points: tuple[dict[str, object], ...] = ()
    coverage: Mapping[str, object] | None = None
    if domain is not None:
        raw_answer = domain.get("answerSummary")
        answer_summary = raw_answer if isinstance(raw_answer, str) else None
        raw_points = domain.get("points")
        if isinstance(raw_points, tuple):
            thawed_points = tuple(_thaw(item) for item in raw_points if isinstance(item, Mapping))
            points = tuple(cast(dict[str, object], item) for item in thawed_points if isinstance(item, dict))
        raw_coverage = domain.get("coverage")
        coverage = raw_coverage if isinstance(raw_coverage, Mapping) else None
    return ReviewMaterial(
        case_id=case.case_id,
        expected_answerability=case.expected_answerability,
        question=case.question,
        terminal_status=result.status.value,
        answer_summary=answer_summary,
        points=points,
        coverage=coverage,
    )


class LiveKnowledgeEvaluationCaseExecutor:
    def __init__(
        self,
        *,
        variant: Literal["primary", "rewrite_ablation"],
        capability: KnowledgeQueryCapability[RankedKnowledgeBatch],
        rewriter: RecordingQuestionRewriter,
        search: RecordingKnowledgeSearch,
        embedding: RecordingEmbedding,
        fusion: RecordingFusion,
        rerank: RecordingRerank,
        retrieval: RecordingRetrievalStage,
        evidence: RecordingEvidenceStage,
        model_transport: BudgetedLiveModelTransport,
        component_signature: str,
    ) -> None:
        self.variant = variant
        self.capability = capability
        self.rewriter = rewriter
        self.search = search
        self.embedding = embedding
        self.fusion = fusion
        self.rerank = rerank
        self.retrieval = retrieval
        self.evidence = evidence
        self.model_transport = model_transport
        self.component_signature = component_signature
        self.calls = 0

    def _reset_recorders(self) -> None:
        for recorder in (
            self.rewriter,
            self.search,
            self.embedding,
            self.fusion,
            self.rerank,
            self.retrieval,
            self.evidence,
        ):
            cast(ResettableRecorder, recorder).reset()

    async def execute(self, *, case: EvaluationCase, fixture: EvaluationExecutionFixture) -> LiveEvaluatedVariant:
        if fixture.synthetic_only:
            raise ValueError("evaluation.live_fixture_required")
        self.calls += 1
        self._reset_recorders()
        before = {
            "rewrite": self.model_transport.rewrite_calls,
            "summary": self.model_transport.summary_calls,
            "embedding": self.embedding.calls,
            "rerank": self.rerank.calls,
        }
        scope = fixture.make_scope(case.case_id, self.variant, case.question)
        result_box: list[CapabilityResult] = []
        outer = self

        class Delegate:
            async def ainvoke(self, *, question: str, scope: Any) -> AgentSemanticOutcome:
                del question, scope
                result = await outer.capability.handle(KnowledgeQueryArguments(), execution_scope.context)
                result_box.append(result)
                return AgentSemanticOutcome(
                    status=result.status,
                    capability_id="knowledge.query",
                    answer_text=None,
                    user_result=result.domain_result,
                    failure=result.failure,
                )

        execution_scope = scope
        self.model_transport.begin(case_id=case.case_id, variant=self.variant)
        try:
            await ModelContextBindingRuntimeInvoker(Delegate()).ainvoke(question=case.question, scope=scope)
        finally:
            self.model_transport.end()
        if len(result_box) != 1:
            raise ValueError("evaluation.live_capability_result_missing")
        result = result_box[0]
        rewrite_calls = self.model_transport.rewrite_calls - before["rewrite"]
        summary_calls = self.model_transport.summary_calls - before["summary"]
        if rewrite_calls != (1 if self.variant == "primary" else 0) and not (
            self.variant == "primary" and rewrite_calls == 0 and result.status is CapabilityStatus.MODEL_EGRESS_DENIED
        ):
            raise ValueError("evaluation.live_rewrite_call_count_invalid")
        if summary_calls not in {0, 1}:
            raise ValueError("evaluation.live_summary_call_count_invalid")

        plan = self.retrieval.last_plan
        selected_domains = () if plan is None else plan.selected_domain_ids
        path_rankings: list[PathRankingRecord] = []
        if plan is not None:
            for item in plan.items:
                path_result = self.search.results.get((item.logical_domain_id, item.path))
                ids = () if path_result is None else tuple(candidate.document_id for candidate in path_result.candidates[:10])
                path_rankings.append(
                    PathRankingRecord(
                        logicalDomainId=cast(Literal["tax.policy", "tax.law"], item.logical_domain_id),
                        path=item.path.value,
                        documentIds=ids,
                    )
                )
        fused_ids = tuple(item.candidate.document_id for item in self.fusion.last_fused[:10])
        batch = self.retrieval.last_result.batch if self.retrieval.last_result is not None else None
        reranked_ids = () if batch is None else tuple(item.candidate.document_id for item in batch.candidates[:10])
        fusion_recall, fusion_mrr = _metric_for_rank(fused_ids, case.relevant_document_ids)
        rerank_recall, rerank_mrr = _metric_for_rank(reranked_ids, case.relevant_document_ids)
        path_hit: MetricValue
        if not case.relevant_document_ids:
            path_hit = "not_applicable"
        else:
            path_hit = 1.0 if any(set(item.document_ids) & set(case.relevant_document_ids) for item in path_rankings) else 0.0
        adopted = _evidence_ids(result)
        evidence_coverage: MetricValue = "not_applicable"
        if case.required_evidence_ids:
            evidence_coverage = len(set(adopted) & set(case.required_evidence_ids)) / len(set(case.required_evidence_ids))
        rewritten = self.rewriter.last_result.rewrite if self.rewriter.last_result is not None else None
        constraint_preserved: MetricValue = "not_applicable"
        if self.variant == "primary" and rewritten is not None:
            constraint_preserved = 1.0 if all(
                token in rewritten.selected_query for token in case.must_preserve_tokens
            ) else 0.0
        summary_status: Literal["answer", "insufficient_evidence", "not_called", "failed"]
        if summary_calls == 0:
            summary_status = "not_called"
        elif result.status is CapabilityStatus.SUCCESS:
            summary_status = "answer"
        elif result.status is CapabilityStatus.NO_RESULT:
            summary_status = "insufficient_evidence"
        else:
            summary_status = "failed"
        variant_result = EvaluationVariantResult(
            variant=self.variant,
            terminalStatus=cast(Any, result.status.value),
            rewriteMode="model" if self.variant == "primary" else "original_fallback",
            selectedDomainIds=cast(tuple[Literal["tax.policy", "tax.law"], ...], selected_domains),
            pathRankings=tuple(path_rankings),
            fusedTop10DocumentIds=fused_ids,
            rerankedTop10DocumentIds=reranked_ids,
            adoptedEvidenceIds=adopted,
            summaryStatus=summary_status,
            modelCallCounts=ModelCallCountRecord(
                rewrite=rewrite_calls,
                embedding=self.embedding.calls - before["embedding"],
                keywordRetrieval=sum(path is RetrievalPath.KEYWORD for _, path in self.search.requests),
                vectorRetrieval=sum(path is RetrievalPath.VECTOR for _, path in self.search.requests),
                rerank=self.rerank.calls - before["rerank"],
                summary=summary_calls,
                coreAnswer=0,
            ),
            metrics=VariantCaseMetrics(
                constraintPreserved=constraint_preserved,
                pathHitAt10=path_hit,
                fusionRecallAt10=fusion_recall,
                fusionMrrAt10=fusion_mrr,
                rerankRecallAt10=rerank_recall,
                rerankMrrAt10=rerank_mrr,
                requiredEvidenceCoverage=evidence_coverage,
                citationValidityRate=1.0 if adopted else "not_applicable",
            ),
        )
        return LiveEvaluatedVariant(
            result=variant_result,
            review_material=_review_material(case, result) if self.variant == "primary" else None,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveEvaluationExecutors:
    primary: LiveKnowledgeEvaluationCaseExecutor
    rewrite_ablation: LiveKnowledgeEvaluationCaseExecutor

    def validate_pair(self) -> None:
        if self.primary.component_signature != self.rewrite_ablation.component_signature:
            raise ValueError("evaluation.component_snapshot_mismatch")
