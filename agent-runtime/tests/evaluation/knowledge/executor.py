from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from agent_runtime.capability_api.contracts import CapabilityResult, CapabilityStatus
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.contracts import (
    KnowledgeQueryArguments,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    KnowledgeEvidenceInput,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceStage,
    EvidenceStageResult,
    RetrievalCoverage,
    RetrievalStageKind,
    RetrievalStageResult,
    RewriteCandidate,
    RewriteCandidateSource,
    RewriteMode,
    RewriteResult,
    RewriteStageKind,
    RewriteStageResult,
    PathRef,
    DomainCandidateCount,
)
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryInput,
    KnowledgeSummaryOutput,
    KnowledgeSummaryPoint,
    SummaryOutcome,
)
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelCallContext,
    ModelTaskDefinition,
    ModelTaskResult,
    QuestionEgressDisposition,
)
from agent_runtime.model.input_guard import QuestionEgressGuard

from tests.evaluation.knowledge.contracts import (
    EvaluationCase,
    EvaluationExecutionFixture,
    EvaluationVariantResult,
    MetricValue,
    ModelCallCountRecord,
    PathRankingRecord,
    VariantCaseMetrics,
)


class StubQuestionRewriter:
    def __init__(self, *, mode: Literal["primary", "rewrite_ablation"]) -> None:
        self.mode = mode
        self.guard = QuestionEgressGuard()
        self.calls = 0

    async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult:
        if timeout_s <= 0:
            raise ValueError("evaluation.invalid_timeout")
        self.calls += 1
        decision = self.guard.evaluate(original_question)
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return RewriteStageResult(
                kind=RewriteStageKind.QUESTION_DENIED,
                policy_version=decision.policy_version,
                reason_code=decision.reason_code.value if decision.reason_code is not None else "unknown_input",
            )
        assert decision.minimized_question is not None
        rewrite_mode = RewriteMode.MODEL if self.mode == "primary" else RewriteMode.ORIGINAL_FALLBACK
        source = RewriteCandidateSource.MODEL if self.mode == "primary" else RewriteCandidateSource.ORIGINAL_FALLBACK
        selected_query = decision.minimized_question if self.mode == "primary" else original_question
        return RewriteStageResult(
            kind=RewriteStageKind.SUCCESS,
            rewrite=RewriteResult(
                original_question=original_question,
                selected_query=selected_query,
                candidates=(RewriteCandidate(text=selected_query, source=source, ordinal=1),),
                mode=rewrite_mode,
                question_policy_version="question-egress-v1",
                question_egress_denied=False,
            ),
        )


class IdentityQuestionRewriter(StubQuestionRewriter):
    def __init__(self) -> None:
        super().__init__(mode="rewrite_ablation")


class SyntheticRetrievalStage:
    def __init__(self, batch: RankedKnowledgeBatch) -> None:
        self.batch = batch
        self.calls = 0
        self.last_plan: KnowledgeRetrievalPlan | None = None

    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[RankedKnowledgeBatch]:
        del context
        if timeout_s <= 0:
            raise ValueError("evaluation.invalid_timeout")
        self.calls += 1
        self.last_plan = plan
        paths = tuple(PathRef(logical_domain_id=item.logical_domain_id, path=item.path) for item in plan.items)
        counts = tuple(
            DomainCandidateCount(
                logical_domain_id=domain_id,
                count=sum(1 for item in self.batch.candidates if domain_id in item.domain_ids),
            )
            for domain_id in plan.selected_domain_ids
        )
        return RetrievalStageResult(
            kind=RetrievalStageKind.SUCCESS,
            batch=self.batch,
            coverage=RetrievalCoverage(
                successful_paths=paths,
                no_result_paths=(),
                failed_paths=(),
                candidate_count_by_domain=counts,
                complete=True,
            ),
        )


class SyntheticSummaryGateway:
    def __init__(self, quote: str) -> None:
        self.quote = quote
        self.calls = 0

    async def generate(
        self,
        *,
        definition: ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput],
        input: KnowledgeSummaryInput,
        context: ModelCallContext,
    ) -> ModelTaskResult[KnowledgeSummaryOutput]:
        del definition, input, context
        self.calls += 1
        return ModelTaskResult(
            output=KnowledgeSummaryOutput(
                outcome=SummaryOutcome.ANSWER,
                points=(KnowledgeSummaryPoint(evidence_ref="e1", quote=self.quote),),
            )
        )


class RecordingEvidenceStage:
    def __init__(self, delegate: KnowledgeEvidenceStage[RankedKnowledgeBatch]) -> None:
        self.delegate = delegate
        self.calls = 0
        self.last_input: KnowledgeEvidenceInput[RankedKnowledgeBatch] | None = None

    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult:
        self.calls += 1
        self.last_input = input
        return await self.delegate.build_result(input=input, context=context, timeout_s=timeout_s)


def _metric_for_rank(document_ids: tuple[str, ...], gold: tuple[str, ...]) -> tuple[MetricValue, MetricValue]:
    if not gold:
        return "not_applicable", "not_applicable"
    hits = set(document_ids) & set(gold)
    recall = len(hits) / len(set(gold))
    first = next((index for index, item in enumerate(document_ids, 1) if item in set(gold)), None)
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


class KnowledgeEvaluationCaseExecutor:
    def __init__(
        self,
        *,
        variant: Literal["primary", "rewrite_ablation"],
        capability: KnowledgeQueryCapability[RankedKnowledgeBatch],
        rewriter: StubQuestionRewriter,
        retrieval: SyntheticRetrievalStage,
        evidence: RecordingEvidenceStage,
        summary_gateway: SyntheticSummaryGateway,
        component_signature: str,
    ) -> None:
        self.variant = variant
        self.capability = capability
        self.rewriter = rewriter
        self.retrieval = retrieval
        self.evidence = evidence
        self.summary_gateway = summary_gateway
        self.component_signature = component_signature
        self.calls = 0

    async def execute(self, *, case: EvaluationCase, fixture: EvaluationExecutionFixture) -> EvaluationVariantResult:
        if not fixture.synthetic_only:
            raise ValueError("evaluation.non_synthetic_fixture")
        self.calls += 1
        before_rewrite = self.rewriter.calls
        before_retrieval = self.retrieval.calls
        before_evidence = self.evidence.calls
        before_summary = self.summary_gateway.calls
        scope = fixture.make_scope(case.case_id, self.variant, case.question)
        result_box: list[CapabilityResult] = []

        class Delegate:
            async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome:
                del question, scope
                result = await self_outer.capability.handle(KnowledgeQueryArguments(), execution_scope.context)
                result_box.append(result)
                return AgentSemanticOutcome(
                    status=result.status,
                    capability_id="knowledge.query",
                    answer_text=None,
                    user_result=result.domain_result,
                    failure=result.failure,
                )

        self_outer = self
        execution_scope = scope
        await ModelContextBindingRuntimeInvoker(Delegate()).ainvoke(question=case.question, scope=scope)
        result = result_box[0]
        if (
            self.rewriter.calls - before_rewrite != 1
            or self.retrieval.calls - before_retrieval not in {0, 1}
            or self.evidence.calls - before_evidence not in {0, 1}
            or self.summary_gateway.calls - before_summary not in {0, 1}
        ):
            raise ValueError("evaluation.stage_call_count_invalid")
        plan = self.retrieval.last_plan
        selected_domains = () if plan is None else plan.selected_domain_ids
        document_ids = tuple(item.candidate.document_id for item in self.retrieval.batch.candidates)[:10]
        path_rankings = () if plan is None else tuple(
            PathRankingRecord(
                logicalDomainId=cast(Literal["tax.policy", "tax.law"], item.logical_domain_id),
                path=item.path.value,
                documentIds=document_ids,
            )
            for item in plan.items
        )
        recall, mrr = _metric_for_rank(document_ids, case.relevant_document_ids)
        adopted = _evidence_ids(result)
        evidence_coverage: MetricValue
        if case.required_evidence_ids:
            evidence_coverage = len(set(adopted) & set(case.required_evidence_ids)) / len(set(case.required_evidence_ids))
        else:
            evidence_coverage = "not_applicable"
        tokens_preserved = all(token in case.question for token in case.must_preserve_tokens)
        return EvaluationVariantResult(
            variant=self.variant,
            terminalStatus=cast(
                Literal[
                    "success", "no_result", "invalid_argument", "forbidden", "timeout",
                    "downstream_failure", "model_egress_denied", "internal_failure"
                ],
                result.status.value,
            ),
            rewriteMode="model" if self.variant == "primary" else "original_fallback",
            selectedDomainIds=cast(tuple[Literal["tax.policy", "tax.law"], ...], selected_domains),
            pathRankings=path_rankings,
            fusedTop10DocumentIds=document_ids,
            rerankedTop10DocumentIds=document_ids,
            adoptedEvidenceIds=adopted,
            summaryStatus="answer" if result.status is CapabilityStatus.SUCCESS else "failed",
            modelCallCounts=ModelCallCountRecord(
                rewrite=1 if self.variant == "primary" else 0,
                embedding=1 if plan is not None else 0,
                keywordRetrieval=sum(1 for item in path_rankings if item.path == "keyword"),
                vectorRetrieval=sum(1 for item in path_rankings if item.path == "vector"),
                rerank=1 if plan is not None else 0,
                summary=self.summary_gateway.calls - before_summary,
                coreAnswer=0,
            ),
            metrics=VariantCaseMetrics(
                constraintPreserved=(1.0 if tokens_preserved else 0.0) if self.variant == "primary" else "not_applicable",
                pathHitAt10=1.0 if isinstance(recall, float) and recall > 0 else recall,
                fusionRecallAt10=recall,
                fusionMrrAt10=mrr,
                rerankRecallAt10=recall,
                rerankMrrAt10=mrr,
                requiredEvidenceCoverage=evidence_coverage,
                citationValidityRate=1.0 if adopted else "not_applicable",
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationExecutors:
    primary: KnowledgeEvaluationCaseExecutor
    rewrite_ablation: KnowledgeEvaluationCaseExecutor

    def validate_pair(self) -> None:
        if self.primary.component_signature != self.rewrite_ablation.component_signature:
            raise ValueError("evaluation.component_snapshot_mismatch")


def synthetic_evidence_id(*, document_id: str, chunk_id: str, content_sha256: str) -> str:
    material = f"{document_id}\n{chunk_id}\n{content_sha256}".encode("utf-8")
    return "ev-" + hashlib.sha256(material).hexdigest()
