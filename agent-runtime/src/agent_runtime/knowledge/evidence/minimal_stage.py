"""Current intent12/minimal-v1 Evidence stage, statically bound to Summary9."""
from __future__ import annotations

import asyncio

from agent_runtime.capability_api.contracts import EgressDisposition, ModelEgressResult
from agent_runtime.knowledge.contracts import (
    EvidenceEgressDenialReason, EvidenceNoResultReason, EvidenceStageCode,
    EvidenceStageKind, EvidenceStageResult, KnowledgeEvidenceContext,
)
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.evidence.cited_summary_validation import CitedSummaryValidator, InvalidCitedSummary
from agent_runtime.knowledge.evidence.contracts import (
    EvidencePolicyDenial, KnowledgeCitedSummaryOutput, KnowledgeEvidenceLimits,
    KnowledgeModeSummaryInput, MinimalKnowledgeEvidenceInput,
)
from agent_runtime.knowledge.evidence.minimal_selection import MinimalEvidenceIntegrityVerifier, MinimalEvidenceSelector
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.knowledge.evidence.summary_task_v8 import mode_summary_input_json
from agent_runtime.knowledge.evidence.summary_validation import InvalidSummary
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    ModelProviderFailureKind, ModelTaskDefinition, ModelTaskId,
    QuestionEgressDisposition, StructuredModelGateway,
)
from agent_runtime.model.input_guard import QuestionEgressGuard


class MinimalKnowledgeEvidenceStage:
    def __init__(
        self, *, catalog: KnowledgeEgressPolicyCatalog, guard: QuestionEgressGuard,
        context: ModelCallContextAccessor, gateway: StructuredModelGateway,
        definition: ModelTaskDefinition[KnowledgeModeSummaryInput, KnowledgeCitedSummaryOutput],
    ) -> None:
        if (definition.task_id is not ModelTaskId.KNOWLEDGE_SUMMARY
                or definition.task_version != "9"
                or definition.input_type is not KnowledgeModeSummaryInput):
            raise ValueError("knowledge.production_task_version_invalid")
        self._catalog = catalog
        self._guard = guard
        self._context = context
        self._gateway = gateway
        self._definition = definition
        self._verifier = MinimalEvidenceIntegrityVerifier()
        self._selector = MinimalEvidenceSelector()
        self._decider = KnowledgeEvidenceEgressDecider()
        self._validator = CitedSummaryValidator()
        self._limits = KnowledgeEvidenceLimits.minimal_v1()

    async def build_result(
        self, *, input: MinimalKnowledgeEvidenceInput,
        context: KnowledgeEvidenceContext, timeout_s: float,
    ) -> EvidenceStageResult:
        if type(input) is not MinimalKnowledgeEvidenceInput:
            return self._failure(EvidenceStageCode.EVIDENCE_FAILURE)
        if input.question_egress_denied:
            return self._denied(EvidenceEgressDenialReason.QUESTION_DENIED)
        decision = self._guard.evaluate(input.original_question)
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return self._denied(EvidenceEgressDenialReason.QUESTION_DENIED)
        if decision.policy_version != input.question_policy_version:
            return self._denied(EvidenceEgressDenialReason.POLICY_CONFLICT)
        assert decision.minimized_question is not None
        try:
            if decision.minimized_question != input.plan.original_question:
                raise ValueError("knowledge.question_mismatch")
            verified = self._verifier.verify(input=input)
            selection = self._selector.select(
                candidates=verified, input=input, minimized_question=decision.minimized_question,
                limits=self._limits,
            )
        except Exception:
            return self._failure(EvidenceStageCode.EVIDENCE_FAILURE)
        if not selection.sufficient or selection.bundle is None:
            return EvidenceStageResult(kind=EvidenceStageKind.NO_RESULT,
                no_result_reason=EvidenceNoResultReason.INSUFFICIENT_EVIDENCE)
        policy = self._decider.decide(bundle=selection.bundle, catalog=self._catalog)
        if not policy.allowed or policy.summary_input is None:
            denial_mapping = {
                EvidencePolicyDenial.GLOBAL_DENIED: EvidenceEgressDenialReason.GLOBAL_DENIED,
                EvidencePolicyDenial.DOMAIN_DENIED: EvidenceEgressDenialReason.DOMAIN_DENIED,
                EvidencePolicyDenial.DOCUMENT_DENIED: EvidenceEgressDenialReason.DOCUMENT_DENIED,
                EvidencePolicyDenial.POLICY_MISSING: EvidenceEgressDenialReason.POLICY_MISSING,
                EvidencePolicyDenial.POLICY_CONFLICT: EvidenceEgressDenialReason.POLICY_CONFLICT,
            }
            return self._denied(denial_mapping[policy.denial_reason or EvidencePolicyDenial.POLICY_CONFLICT])
        projection = policy.summary_input
        summary_input = KnowledgeModeSummaryInput(
            schema_version=3, question=projection.question, coverage=projection.coverage,
            evidence=projection.evidence, query_mode=input.plan.query_mode,
        )
        try:
            if summary_input.question != decision.minimized_question:
                raise ValueError("knowledge.summary_input_invalid")
            mode_summary_input_json(summary_input)
        except (ValueError, TypeError, AttributeError):
            return self._failure(EvidenceStageCode.EVIDENCE_FAILURE)
        try:
            call_context = self._context.require_current()
        except Exception:
            return self._failure(EvidenceStageCode.EVIDENCE_FAILURE)
        if (call_context.request_id, call_context.correlation_id) != (context.request_id, context.correlation_id):
            return self._failure(EvidenceStageCode.EVIDENCE_FAILURE)
        loop = asyncio.get_running_loop()
        deadline = min(context.deadline_monotonic - 0.1, loop.time() + timeout_s)
        if deadline <= loop.time():
            return EvidenceStageResult(kind=EvidenceStageKind.TIMEOUT, stage_code=EvidenceStageCode.SUMMARY_TIMEOUT)
        try:
            async with asyncio.timeout_at(deadline):
                model_result = await self._gateway.generate(
                    definition=self._definition, input=summary_input, context=call_context,
                )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return EvidenceStageResult(kind=EvidenceStageKind.TIMEOUT, stage_code=EvidenceStageCode.SUMMARY_TIMEOUT)
        except Exception:
            return self._failure(EvidenceStageCode.SUMMARY_FAILURE)
        if model_result.failure_kind is not None:
            if model_result.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT:
                return EvidenceStageResult(kind=EvidenceStageKind.TIMEOUT, stage_code=EvidenceStageCode.SUMMARY_TIMEOUT)
            return self._failure(EvidenceStageCode.SUMMARY_FAILURE)
        assert model_result.output is not None
        try:
            validated = self._validator.validate(
                output=model_result.output, query_mode=summary_input.query_mode,
                bundle=selection.bundle, limits=self._limits,
            )
        except (InvalidSummary, InvalidCitedSummary):
            return self._failure(EvidenceStageCode.INVALID_SUMMARY)
        if validated.insufficient:
            return EvidenceStageResult(kind=EvidenceStageKind.NO_RESULT,
                no_result_reason=EvidenceNoResultReason.INSUFFICIENT_EVIDENCE)
        assert validated.domain_result is not None
        return EvidenceStageResult(
            kind=EvidenceStageKind.SUCCESS, domain_result=validated.domain_result,
            egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        )

    @staticmethod
    def _failure(code: EvidenceStageCode) -> EvidenceStageResult:
        return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=code)

    @staticmethod
    def _denied(reason: EvidenceEgressDenialReason) -> EvidenceStageResult:
        return EvidenceStageResult(kind=EvidenceStageKind.MODEL_EGRESS_DENIED,
            policy_version="knowledge-evidence-egress-v1", denial_reason=reason)
