"""Current Knowledge flow; historical version dispatch stays outside this class."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext, CapabilityResult, CapabilityStatus,
    EgressDisposition, FailureSource, ModelEgressResult,
)
from agent_runtime.knowledge.capability import MinimalFlowBindings, _result, compute_phase_deadline
from agent_runtime.knowledge.context import to_evidence_context, to_retrieval_context
from agent_runtime.knowledge.contracts import (
    EvidenceStageCode, EvidenceStageKind, EvidenceStageResult, KnowledgeQueryArguments,
    PathRef, RetrievalCoverage, RetrievalStageCode, RetrievalStageKind, RetrievalStageResult,
)
from agent_runtime.knowledge.evidence.contracts import MinimalKnowledgeEvidenceInput
from agent_runtime.knowledge.intent_contracts import KnowledgeIntentOutcome
from agent_runtime.knowledge.intent_stage_v12 import MinimalIntentStageKind
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgeRetrievalPlan
from agent_runtime.knowledge.retrieval.minimal_ranking import MinimalRankedBatch
from agent_runtime.knowledge.settings import KnowledgeSettings

TPhase = TypeVar("TPhase")


class MinimalKnowledgeQueryCapability:
    def __init__(self, *, settings: KnowledgeSettings, flow: MinimalFlowBindings) -> None:
        if flow.settings.enabled_domain_ids != settings.enabled_domain_ids:
            raise ValueError("knowledge.minimal_binding_invalid")
        self._settings = settings
        self._flow = flow

    async def handle(self, input: KnowledgeQueryArguments, context: CapabilityExecutionContext) -> CapabilityResult:
        del input
        if context.cancellation.is_cancelled():
            return _result(CapabilityStatus.TIMEOUT, code="knowledge.request_cancelled")
        question = context.original_question
        if not question or not question.strip():
            return _result(CapabilityStatus.INVALID_ARGUMENT, code="knowledge.invalid_question")
        flow = self._flow
        try:
            planned = await self._run_phase(
                lambda: flow.intent.rewrite(original_question=question,
                                            timeout_s=self._settings.rewrite_timeout_ms / 1000),
                context=context, phase_timeout_s=self._settings.rewrite_timeout_ms / 1000,
            )
        except TimeoutError:
            return _result(CapabilityStatus.TIMEOUT, code="knowledge.rewrite_timeout", source=FailureSource.DOWNSTREAM)
        if planned.kind is MinimalIntentStageKind.INPUT_INVALID:
            return _result(CapabilityStatus.INVALID_ARGUMENT, code="knowledge.invalid_question")
        if planned.kind is MinimalIntentStageKind.QUESTION_DENIED:
            return _result(CapabilityStatus.MODEL_EGRESS_DENIED, code="knowledge.rewrite_input_denied",
                source=FailureSource.POLICY,
                egress=ModelEgressResult(disposition=EgressDisposition.DENIED,
                    policy_version=planned.policy_version or "question-egress-v1",
                    reason_code="knowledge.rewrite_input_denied"))
        if planned.kind is MinimalIntentStageKind.TIMEOUT:
            return _result(CapabilityStatus.TIMEOUT, code="knowledge.rewrite_timeout", source=FailureSource.DOWNSTREAM)
        if (planned.kind is not MinimalIntentStageKind.SUCCESS or planned.question is None
                or planned.intent is None or planned.policy_version is None):
            return _result(CapabilityStatus.DOWNSTREAM_FAILURE, code="knowledge.rewrite_failure",
                           source=FailureSource.DOWNSTREAM)
        intent = planned.intent
        if intent.outcome is KnowledgeIntentOutcome.UNSUPPORTED:
            return _result(CapabilityStatus.NO_RESULT,
                domain_result={"reason": "no_matching_domain", "selected_domain_ids": (), "coverage_complete": True})
        if intent.outcome is KnowledgeIntentOutcome.CLARIFICATION_REQUIRED:
            return _result(CapabilityStatus.NO_RESULT,
                domain_result={"reason": "clarification_required", "selected_domain_ids": (), "coverage_complete": False})
        try:
            plan = flow.planner.build(question=planned.question, intent=intent, settings=flow.settings)
        except ValueError:
            return _result(CapabilityStatus.DOWNSTREAM_FAILURE, code="knowledge.rewrite_failure",
                           source=FailureSource.DOWNSTREAM)
        try:
            retrieval = await self._run_phase(
                lambda: flow.retrieval.execute(plan=plan, context=to_retrieval_context(context),
                    timeout_s=self._settings.retrieval_timeout_ms / 1000),
                context=context, phase_timeout_s=self._settings.retrieval_timeout_ms / 1000,
            )
        except TimeoutError:
            return _result(CapabilityStatus.TIMEOUT, code="knowledge.retrieval_timeout", source=FailureSource.DOWNSTREAM)
        decision = self.map_retrieval_result(result=retrieval, plan=plan)
        if isinstance(decision, CapabilityResult):
            return decision
        batch, coverage = decision
        raw_batch: object = batch
        if not isinstance(raw_batch, MinimalRankedBatch):
            return _result(CapabilityStatus.DOWNSTREAM_FAILURE, code="knowledge.retrieval_failure",
                           source=FailureSource.DOWNSTREAM)
        evidence_input = MinimalKnowledgeEvidenceInput(
            question=planned.question, intent=intent, plan=plan, coverage=coverage,
            question_policy_version=planned.policy_version, question_egress_denied=False, batch=batch,
        )
        try:
            evidence = await self._run_phase(
                lambda: flow.evidence.build_result(input=evidence_input, context=to_evidence_context(context),
                    timeout_s=self._settings.evidence_timeout_ms / 1000),
                context=context, phase_timeout_s=self._settings.evidence_timeout_ms / 1000,
            )
        except TimeoutError:
            return _result(CapabilityStatus.TIMEOUT, code="knowledge.evidence_timeout", source=FailureSource.DOWNSTREAM)
        return self.map_evidence_result(result=evidence)

    async def _run_phase(
        self, operation_factory: Callable[[], Awaitable[TPhase]], *,
        context: CapabilityExecutionContext, phase_timeout_s: float,
    ) -> TPhase:
        if context.cancellation.is_cancelled():
            raise TimeoutError("knowledge.request_cancelled")
        loop = asyncio.get_running_loop()
        deadline = compute_phase_deadline(
            now_monotonic=loop.time(), request_deadline=context.deadline_monotonic, phase_timeout_s=phase_timeout_s,
        )
        async with asyncio.timeout_at(deadline):
            result = await operation_factory()
        if context.cancellation.is_cancelled() or loop.time() >= context.deadline_monotonic:
            raise TimeoutError("knowledge.deadline_exhausted")
        return result

    def map_retrieval_result(
        self, *, result: RetrievalStageResult[MinimalRankedBatch], plan: MinimalKnowledgeRetrievalPlan,
    ) -> tuple[MinimalRankedBatch, RetrievalCoverage] | CapabilityResult:
        if result.kind is RetrievalStageKind.FORBIDDEN and result.stage_code is RetrievalStageCode.DOMAIN_FORBIDDEN:
            return _result(CapabilityStatus.FORBIDDEN, code="knowledge.domain_forbidden", source=FailureSource.DOWNSTREAM)
        timeout_codes = {
            RetrievalStageCode.READ_AUTHORITY_TIMEOUT, RetrievalStageCode.RETRIEVAL_TIMEOUT,
            RetrievalStageCode.RERANK_TIMEOUT,
        }
        if result.kind is RetrievalStageKind.TIMEOUT and result.stage_code in timeout_codes:
            code = "knowledge.read_authority_timeout" if result.stage_code is RetrievalStageCode.READ_AUTHORITY_TIMEOUT else "knowledge.retrieval_timeout"
            return _result(CapabilityStatus.TIMEOUT, code=code, source=FailureSource.DOWNSTREAM)
        if result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and result.stage_code is not None:
            mapping = {
                RetrievalStageCode.READ_DECISION_UNVERIFIABLE: "knowledge.read_decision_unverifiable",
                RetrievalStageCode.READ_AUTHORITY_FAILURE: "knowledge.read_authority_failure",
                RetrievalStageCode.RETRIEVAL_FAILURE: "knowledge.retrieval_failure",
                RetrievalStageCode.RERANK_FAILURE: "knowledge.retrieval_failure",
                RetrievalStageCode.INVALID_PROVIDER_RESULT: "knowledge.retrieval_failure",
            }
            if result.stage_code in mapping:
                return _result(CapabilityStatus.DOWNSTREAM_FAILURE, code=mapping[result.stage_code], source=FailureSource.DOWNSTREAM)
        if result.kind in (RetrievalStageKind.SUCCESS, RetrievalStageKind.NO_RESULT) and result.coverage is not None:
            if not self._valid_coverage(result.coverage, plan,
                                        require_candidates=result.kind is RetrievalStageKind.SUCCESS):
                return _result(CapabilityStatus.DOWNSTREAM_FAILURE, code="knowledge.retrieval_failure", source=FailureSource.DOWNSTREAM)
            if result.kind is RetrievalStageKind.NO_RESULT and result.batch is None:
                return _result(CapabilityStatus.NO_RESULT,
                    domain_result={"reason": "no_candidate", "selected_domain_ids": plan.selected_domain_ids, "coverage_complete": True})
            if result.kind is RetrievalStageKind.SUCCESS and result.batch is not None:
                return result.batch, result.coverage
        return _result(CapabilityStatus.INTERNAL_FAILURE, code="knowledge.invalid_stage_result")

    def _valid_coverage(
        self, coverage: RetrievalCoverage, plan: MinimalKnowledgeRetrievalPlan, *, require_candidates: bool,
    ) -> bool:
        raw_complete: object = coverage.complete
        if type(raw_complete) is not bool:
            return False
        expected = tuple(PathRef(logical_domain_id=item.logical_domain_id, path=item.path) for item in plan.items)
        observed = tuple(coverage.successful_paths) + tuple(coverage.no_result_paths) + tuple(
            PathRef(logical_domain_id=item.logical_domain_id, path=item.path) for item in coverage.failed_paths
        )
        if len(set(observed)) != len(observed) or set(observed) != set(expected):
            return False
        counts = {item.logical_domain_id: item.count for item in coverage.candidate_count_by_domain}
        if (len(counts) != len(coverage.candidate_count_by_domain)
                or set(counts) != set(plan.selected_domain_ids)
                or any(type(value) is not int or not 0 <= value <= 2 * self._settings.per_path_candidate_limit for value in counts.values())):
            return False
        if coverage.complete != (not coverage.failed_paths):
            return False
        if not require_candidates:
            return not coverage.failed_paths and not any(counts.values())
        if not any(counts.values()):
            return False
        if coverage.failed_paths:
            return (
                {item.logical_domain_id for item in coverage.successful_paths} == set(plan.selected_domain_ids)
                and all(counts.values())
                and sum(counts.values()) >= self._settings.min_partial_candidates
            )
        return True

    def map_evidence_result(self, *, result: EvidenceStageResult) -> CapabilityResult:
        if result.kind is EvidenceStageKind.SUCCESS and result.domain_result is not None and result.egress is not None:
            if result.egress.disposition is EgressDisposition.NOT_APPLICABLE:
                return _result(CapabilityStatus.SUCCESS, domain_result=result.domain_result, egress=result.egress)
        if result.kind is EvidenceStageKind.NO_RESULT and result.no_result_reason is not None:
            return _result(CapabilityStatus.NO_RESULT, domain_result={"reason": result.no_result_reason.value})
        if result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED and result.policy_version and result.denial_reason is not None:
            return _result(CapabilityStatus.MODEL_EGRESS_DENIED,
                code="knowledge.evidence_egress_denied", source=FailureSource.POLICY,
                domain_result=result.domain_result,
                egress=ModelEgressResult(disposition=EgressDisposition.DENIED,
                    policy_version=result.policy_version, reason_code=f"knowledge.{result.denial_reason.value}"))
        mapping = {
            EvidenceStageCode.EVIDENCE_READ_FORBIDDEN: (CapabilityStatus.FORBIDDEN, "knowledge.evidence_read_forbidden"),
            EvidenceStageCode.EVIDENCE_TIMEOUT: (CapabilityStatus.TIMEOUT, "knowledge.evidence_timeout"),
            EvidenceStageCode.SUMMARY_TIMEOUT: (CapabilityStatus.TIMEOUT, "knowledge.summary_timeout"),
            EvidenceStageCode.EVIDENCE_FAILURE: (CapabilityStatus.DOWNSTREAM_FAILURE, "knowledge.evidence_failure"),
            EvidenceStageCode.SUMMARY_FAILURE: (CapabilityStatus.DOWNSTREAM_FAILURE, "knowledge.summary_failure"),
            EvidenceStageCode.INVALID_SUMMARY: (CapabilityStatus.DOWNSTREAM_FAILURE, "knowledge.summary_failure"),
        }
        if result.stage_code in mapping:
            status, code = mapping[result.stage_code]
            return _result(status, code=code, source=FailureSource.DOWNSTREAM)
        return _result(CapabilityStatus.INTERNAL_FAILURE, code="knowledge.invalid_stage_result")
