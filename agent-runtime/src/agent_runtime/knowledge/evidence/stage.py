from __future__ import annotations

import asyncio

from agent_runtime.capability_api.contracts import EgressDisposition, ModelEgressResult
from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V3,
    EvidenceEgressDenialReason,
    EvidenceNoResultReason,
    EvidenceStageCode,
    EvidenceStageKind,
    EvidenceStageResult,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
)
from agent_runtime.knowledge.evidence.builder import (
    DeterministicEvidenceSelector,
    EvidenceIntegrityVerifier,
)
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.evidence.contracts import (
    EvidencePolicyDenial,
    KnowledgeEvidenceLimits,
    KnowledgeModeSummaryInput,
    KnowledgeRequirementSummaryInput,
    MinimalKnowledgeEvidenceInput,
)
from agent_runtime.knowledge.evidence.minimal_selection import (
    MinimalEvidenceIntegrityVerifier, MinimalEvidenceSelector,
)
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator, InvalidSummary, SummaryValidationFailureReason,
)
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_task_v6 import requirement_summary_input_json
from agent_runtime.knowledge.evidence.summary_task_v8 import mode_summary_input_json
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    ModelProviderFailureKind,
    ModelTaskDefinition,
    ModelTaskId,
    QuestionEgressDisposition,
    StructuredModelGateway,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, KnowledgeSummaryOutput


class DefaultKnowledgeEvidenceStage:
    __slots__ = ("_catalog", "_context", "_decider", "_definition", "_gateway", "_guard", "_limits", "_minimal_verifier", "_selector", "_validator", "_verifier")

    def __init__(
        self,
        *,
        catalog: KnowledgeEgressPolicyCatalog,
        guard: QuestionEgressGuard,
        context: ModelCallContextAccessor,
        gateway: StructuredModelGateway,
        definition: ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput],
        verifier: EvidenceIntegrityVerifier | None = None,
        selector: DeterministicEvidenceSelector | MinimalEvidenceSelector | None = None,
        decider: KnowledgeEvidenceEgressDecider | None = None,
        validator: ExtractiveSummaryValidator | None = None,
        limits: KnowledgeEvidenceLimits | None = None,
    ) -> None:
        self._catalog = catalog
        self._guard = guard
        self._context = context
        self._gateway = gateway
        self._definition = definition
        self._verifier = verifier or EvidenceIntegrityVerifier()
        self._minimal_verifier = MinimalEvidenceIntegrityVerifier()
        self._selector = selector or DeterministicEvidenceSelector()
        self._decider = decider or KnowledgeEvidenceEgressDecider()
        self._validator = validator or ExtractiveSummaryValidator()
        self._limits = limits or KnowledgeEvidenceLimits.v1()

    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch] | MinimalKnowledgeEvidenceInput,
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult:
        if input.question_egress_denied:
            return self._denied(EvidenceEgressDenialReason.QUESTION_DENIED)
        decision = self._guard.evaluate(input.original_question)
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return self._denied(EvidenceEgressDenialReason.QUESTION_DENIED)
        if decision.policy_version != input.question_policy_version:
            return self._denied(EvidenceEgressDenialReason.POLICY_CONFLICT)
        assert decision.minimized_question is not None
        minimal = isinstance(input, MinimalKnowledgeEvidenceInput)
        v3 = isinstance(input, KnowledgeEvidenceInput) and input.quality_version == KNOWLEDGE_QUALITY_VERSION_V3
        if (
            (minimal and (
                self._definition.task_id is not ModelTaskId.KNOWLEDGE_SUMMARY
                or self._definition.task_version != "8"
                or self._definition.input_type is not KnowledgeModeSummaryInput
                or self._limits != KnowledgeEvidenceLimits.minimal_v1()
                or type(self._selector) is not MinimalEvidenceSelector
            ))
            or (not minimal and type(self._selector) is MinimalEvidenceSelector)
            or (not minimal and self._definition.task_version == "8")
            or (v3 and (self._definition.task_id is not ModelTaskId.KNOWLEDGE_SUMMARY
                     or self._definition.task_version not in {"6", "7"}
                     or self._definition.input_type is not KnowledgeRequirementSummaryInput
                     or self._limits != KnowledgeEvidenceLimits.quality_v3()))
            or (not minimal and not v3 and (self._definition.task_version in {"6", "7"} or self._definition.input_type is KnowledgeRequirementSummaryInput))
        ):
            return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.EVIDENCE_FAILURE)
        try:
            if isinstance(input, MinimalKnowledgeEvidenceInput):
                if decision.minimized_question != input.plan.original_question:
                    raise ValueError("knowledge.question_mismatch")
                assert isinstance(self._selector, MinimalEvidenceSelector)
                verified = self._minimal_verifier.verify(input=input)
                selection = self._selector.select(
                    candidates=verified, input=input, minimized_question=decision.minimized_question,
                    limits=self._limits,
                )
            else:
                assert isinstance(self._selector, DeterministicEvidenceSelector)
                verified_legacy = self._verifier.verify(input=input)
                selection = self._selector.select(
                    candidates=verified_legacy, input=input, minimized_question=decision.minimized_question,
                    limits=self._limits,
                )
        except Exception:
            return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.EVIDENCE_FAILURE)
        if not selection.sufficient or selection.bundle is None:
            return EvidenceStageResult(kind=EvidenceStageKind.NO_RESULT, no_result_reason=EvidenceNoResultReason.INSUFFICIENT_EVIDENCE)
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
        summary_input = policy.summary_input
        if isinstance(input, MinimalKnowledgeEvidenceInput):
            summary_input = KnowledgeModeSummaryInput(
                schema_version=3, question=summary_input.question, coverage=summary_input.coverage,
                evidence=summary_input.evidence, query_mode=input.plan.query_mode,
            )
            try:
                if summary_input.question != decision.minimized_question:
                    raise ValueError("knowledge.summary_input_invalid")
                mode_summary_input_json(summary_input)
            except (ValueError, TypeError, AttributeError):
                return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.EVIDENCE_FAILURE)
        elif v3:
            summary_input = KnowledgeRequirementSummaryInput(
                schema_version=2, question=summary_input.question, coverage=summary_input.coverage,
                evidence=summary_input.evidence, requirements=input.evidence_requirements,
            )
            try:
                if len(requirement_summary_input_json(summary_input).encode("utf-8")) > self._limits.max_summary_input_bytes:
                    raise ValueError("knowledge.summary_input_invalid")
            except (ValueError, TypeError, AttributeError):
                return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.EVIDENCE_FAILURE)
        try:
            call_context = self._context.require_current()
        except Exception:
            return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.EVIDENCE_FAILURE)
        if (call_context.request_id, call_context.correlation_id) != (context.request_id, context.correlation_id):
            return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.EVIDENCE_FAILURE)
        loop = asyncio.get_running_loop()
        deadline = min(context.deadline_monotonic - 0.1, loop.time() + timeout_s)
        if deadline <= loop.time():
            return EvidenceStageResult(kind=EvidenceStageKind.TIMEOUT, stage_code=EvidenceStageCode.SUMMARY_TIMEOUT)
        try:
            async with asyncio.timeout_at(deadline):
                model_result = await self._gateway.generate(
                    definition=self._definition,
                    input=summary_input,
                    context=call_context,
                )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return EvidenceStageResult(kind=EvidenceStageKind.TIMEOUT, stage_code=EvidenceStageCode.SUMMARY_TIMEOUT)
        except Exception:
            return EvidenceStageResult(
                kind=EvidenceStageKind.DOWNSTREAM_FAILURE,
                stage_code=EvidenceStageCode.SUMMARY_FAILURE,
            )
        if model_result.failure_kind is not None:
            if model_result.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT:
                return EvidenceStageResult(kind=EvidenceStageKind.TIMEOUT, stage_code=EvidenceStageCode.SUMMARY_TIMEOUT)
            return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.SUMMARY_FAILURE)
        assert model_result.output is not None
        try:
            output = model_result.output
            if minimal and type(output) is not KnowledgeSummaryOutput:
                raise InvalidSummary(SummaryValidationFailureReason.OUTCOME_POINTS_MISMATCH)
            if v3 and isinstance(input, KnowledgeEvidenceInput):
                if not isinstance(summary_input, KnowledgeRequirementSummaryInput):
                    raise ValueError("knowledge.summary_input_invalid")
                output = RequirementCoverageValidator().validate(
                    output=output, requirements=input.evidence_requirements,
                    summary_input=summary_input, bundle=selection.bundle,
                )
            validated = self._validator.validate(output=output, bundle=selection.bundle, limits=self._limits)
        except InvalidSummary:
            return EvidenceStageResult(kind=EvidenceStageKind.DOWNSTREAM_FAILURE, stage_code=EvidenceStageCode.INVALID_SUMMARY)
        if validated.insufficient:
            return EvidenceStageResult(kind=EvidenceStageKind.NO_RESULT, no_result_reason=EvidenceNoResultReason.INSUFFICIENT_EVIDENCE)
        assert validated.domain_result is not None
        return EvidenceStageResult(
            kind=EvidenceStageKind.SUCCESS,
            domain_result=validated.domain_result,
            egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        )

    @staticmethod
    def _denied(reason: EvidenceEgressDenialReason) -> EvidenceStageResult:
        return EvidenceStageResult(
            kind=EvidenceStageKind.MODEL_EGRESS_DENIED,
            policy_version="knowledge-evidence-egress-v1",
            denial_reason=reason,
        )
