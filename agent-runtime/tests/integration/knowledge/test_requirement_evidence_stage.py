from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
import json

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageCode, EvidenceStageKind, EvidenceNoResultReason
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, canonical_policy_fingerprint
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceLimits, KnowledgeRequirementSummaryInput, KnowledgeSummaryOutput,
    KnowledgeEgressDisposition, KnowledgeEgressField, SummaryOutcome,
)
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.requirement_validation import (
    CoverageValidationFailureReason, InvalidRequirementCoverage, RequirementCoverageValidator,
)
from agent_runtime.knowledge.evidence.summary_task_v5 import KnowledgeSummaryTaskV5
from agent_runtime.knowledge.evidence.summary_task_v6 import KnowledgeSummaryTaskV6
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import ModelProviderFailureKind, ModelTaskResult
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.observation import observation_scope
from tests.contract.knowledge.test_summary_task_v5 import _response
from tests.evidence_helpers import evidence_input, synthetic_catalog
from tests.integration.knowledge.test_evidence_stage import _context
from tests.model_helpers import call_with_model_context
from tests.requirement_evidence_helpers import requirement_input, output_for


class Gateway:
    def __init__(self, fault=None):
        self.fault, self.inputs, self.entered, self.released = fault, [], asyncio.Event(), asyncio.Event()

    async def generate(self, *, definition, input, context):
        self.inputs.append(input)
        self.entered.set()
        if self.fault == "wait":
            try:
                await asyncio.Event().wait()
            finally:
                self.released.set()
        if self.fault == "failure": raise RuntimeError("synthetic provider detail")
        if self.fault == "timeout": return ModelTaskResult(failure_kind=ModelProviderFailureKind.PROVIDER_TIMEOUT)
        output = output_for(input)
        if self.fault == "old_output": output = KnowledgeSummaryOutput(outcome=output.outcome, points=output.points)
        elif self.fault == "missing": output = replace(output, coverage=output.coverage[:-1])
        elif self.fault == "quote": output = replace(output, points=(replace(output.points[0], quote="不存在的语句"),) + output.points[1:])
        elif self.fault == "insufficient": output = replace(output, outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE, points=(), coverage=())
        return ModelTaskResult(output=output)


def stage(gateway, *, definition=None, limits=None, catalog=None, **kwargs):
    return DefaultKnowledgeEvidenceStage(catalog=catalog or synthetic_catalog(), guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(), gateway=gateway, definition=definition or KnowledgeSummaryTaskV6.definition(),
        limits=limits or KnowledgeEvidenceLimits.quality_v3(), **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,kind,code", [(None, EvidenceStageKind.SUCCESS, None),
    ("insufficient", EvidenceStageKind.NO_RESULT, None), ("missing", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("quote", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("old_output", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("failure", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.SUMMARY_FAILURE),
    ("timeout", EvidenceStageKind.TIMEOUT, EvidenceStageCode.SUMMARY_TIMEOUT)])
async def test_stage_single_model_call_and_finite_output(fault, kind, code):
    gateway = Gateway(fault)
    result = await call_with_model_context(lambda: stage(gateway).build_result(input=requirement_input(), context=_context(), timeout_s=2))
    assert result.kind is kind and result.stage_code is code and len(gateway.inputs) == 1
    assert type(gateway.inputs[0]) is KnowledgeRequirementSummaryInput
    if fault == "insufficient": assert result.no_result_reason is EvidenceNoResultReason.INSUFFICIENT_EVIDENCE
    if kind is EvidenceStageKind.SUCCESS:
        assert len(result.domain_result["points"]) == 3 and result.domain_result["schemaVersion"] == 1
        assert "coverage" not in result.domain_result["points"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", tuple(CoverageValidationFailureReason))
async def test_internal_coverage_reasons_keep_same_public_failure_and_one_call(reason, monkeypatch, caplog):
    def reject(self, **kwargs):
        raise InvalidRequirementCoverage(reason)
    monkeypatch.setattr(RequirementCoverageValidator, "validate", reject)
    gateway = Gateway()
    with observation_scope() as collector:
        result = await call_with_model_context(lambda: stage(gateway).build_result(input=requirement_input(), context=_context(), timeout_s=2))
        observation = collector.snapshot()
    assert type(reason) is CoverageValidationFailureReason
    assert result.kind is EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.stage_code is EvidenceStageCode.INVALID_SUMMARY
    assert result.domain_result is None and len(gateway.inputs) == 1
    assert reason.value not in repr(result) + repr(observation) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["old_task", "wrong_limits", "old_input", "missing_requirements", "wrong_labels", "context", "expired", "missing_anchor", "sensitive", "question_policy", "document_denied", "policy_missing", "policy_conflict"])
async def test_pre_model_failures_have_zero_summary_calls(fault):
    gateway = Gateway()
    source, definition, limits, catalog = requirement_input(), None, None, synthetic_catalog()
    context = _context()
    if fault == "old_task": definition = KnowledgeSummaryTaskV5.definition()
    elif fault == "wrong_limits": limits = KnowledgeEvidenceLimits.v1()
    elif fault == "old_input": source = evidence_input()
    elif fault == "missing_requirements": source = replace(source, evidence_requirements=())
    elif fault == "wrong_labels": source = replace(source, batch=replace(source.batch, candidates=(replace(source.batch.candidates[0], requirement_ids=("r4",)),) + source.batch.candidates[1:]))
    elif fault == "context": context = replace(context, request_id="another-request")
    elif fault == "expired": context = replace(context, deadline_monotonic=0)
    elif fault == "missing_anchor": source = requirement_input(count=2)
    elif fault == "sensitive": source = replace(source, original_question="税务问题，邮箱someone@example.com")
    elif fault == "question_policy": source = replace(source, question_policy_version="unknown")
    elif fault == "document_denied": catalog = synthetic_catalog(disposition=KnowledgeEgressDisposition.DENY)
    elif fault in {"policy_missing", "policy_conflict"}:
        changes = {"document_id": "missing"} if fault == "policy_missing" else {"policy_ref": "conflict"}
        source = replace(source, batch=replace(source.batch, candidates=tuple(replace(item, candidate=replace(item.candidate, **changes)) for item in source.batch.candidates)))
    result = await call_with_model_context(lambda: stage(gateway, definition=definition, limits=limits, catalog=catalog).build_result(input=source, context=context, timeout_s=2))
    expected = EvidenceStageKind.MODEL_EGRESS_DENIED if fault in {"sensitive", "question_policy", "document_denied", "policy_missing", "policy_conflict"} else EvidenceStageKind.TIMEOUT if fault == "expired" else EvidenceStageKind.NO_RESULT if fault == "missing_anchor" else EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.kind is expected and gateway.inputs == []


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancel_release_active_summary_without_retry(cancel):
    gateway = Gateway("wait")
    operation = call_with_model_context(lambda: stage(gateway).build_result(input=requirement_input(), context=_context(), timeout_s=1 if cancel else 0.02))
    if cancel:
        task = asyncio.create_task(operation)
        await asyncio.wait_for(gateway.entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    else:
        assert (await operation).kind is EvidenceStageKind.TIMEOUT
    assert len(gateway.inputs) == 1 and gateway.released.is_set()


@pytest.mark.asyncio
async def test_real_gateway_receives_only_actual_policy_projection_and_observations_hide_body_and_focus(caplog):
    catalog = synthetic_catalog()
    snapshot = replace(catalog.snapshot, policies=tuple(replace(item, allowed_fields=frozenset({KnowledgeEgressField.CONTENT})) for item in catalog.snapshot.policies))
    catalog = KnowledgeEgressPolicyCatalog(replace(snapshot, canonical_fingerprint=canonical_policy_fingerprint(snapshot)))

    class Transport:
        def __init__(self): self.requests = []
        async def complete(self, request, **kwargs):
            self.requests.append(request)
            payload = json.loads(request.user_payload_json)
            return _response(json.dumps({"outcome": "answer",
                "points": [{"evidence_ref": item["evidence_ref"], "quote": item["content"]} for item in payload["evidence"]],
                "coverage": [{"requirement_id": item["requirement_id"], "evidence_refs": [f"e{i}"]} for i, item in enumerate(payload["requirements"], 1)]}))

    definition, transport = KnowledgeSummaryTaskV6.definition(), Transport()
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    source = requirement_input()
    with observation_scope() as collector:
        result = await call_with_model_context(lambda: stage(gateway, definition=definition, catalog=catalog).build_result(input=source, context=_context(), timeout_s=2))
        observation = collector.snapshot()
    assert result.kind is EvidenceStageKind.SUCCESS and len(transport.requests) == 1
    payload = json.loads(transport.requests[0].user_payload_json)
    assert all(set(item) == {"evidence_ref", "content"} for item in payload["evidence"])
    assert payload["schema_version"] == 2 and len(payload["requirements"]) == 3
    for text in [item.focus for item in source.evidence_requirements] + [item.candidate.content for item in source.batch.candidates]:
        assert text not in repr(observation) + caplog.text
