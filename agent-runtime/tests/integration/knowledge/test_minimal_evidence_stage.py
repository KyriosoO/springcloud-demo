from __future__ import annotations

import asyncio
from dataclasses import replace
import json

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageCode, EvidenceStageKind
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, canonical_policy_fingerprint
from agent_runtime.knowledge.evidence.contracts import (
    DocumentPolicyBinding, KnowledgeEgressDisposition, KnowledgeEgressField,
    KnowledgeEvidenceLimits, KnowledgeModeSummaryInput, KnowledgeSummaryOutput,
    KnowledgeSummaryPoint, SummaryOutcome,
)
from agent_runtime.knowledge.evidence.minimal_selection import MinimalEvidenceSelector
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task_v7 import KnowledgeSummaryTaskV7
from agent_runtime.knowledge.evidence.summary_task_v8 import KnowledgeSummaryTaskV8, OUTPUT_NAME
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    ModelTaskResult, StructuredFinishKind, StructuredModelResponse, StructuredToolCall,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.observation import observation_scope
from tests.evidence_helpers import synthetic_catalog
from tests.integration.knowledge.test_evidence_stage import _context
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context
from tests.unit.knowledge.evidence.test_minimal_selection import minimal_input


class FakeGateway:
    def __init__(self, fault: str | None = None) -> None:
        self.fault = fault
        self.inputs: list[KnowledgeModeSummaryInput] = []
        self.entered = asyncio.Event()
        self.released = asyncio.Event()

    async def generate(self, *, definition, input, context):
        del definition, context
        self.inputs.append(input)
        self.entered.set()
        if self.fault == "wait":
            try:
                await asyncio.Event().wait()
            finally:
                self.released.set()
        if self.fault == "failure":
            raise RuntimeError("synthetic provider detail")
        if self.fault == "insufficient":
            return ModelTaskResult(output=KnowledgeSummaryOutput(
                outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE, points=()))
        if self.fault in {"duplicate_ref", "unknown_ref", "stitched_quote"}:
            invalid_point = KnowledgeSummaryPoint(
                evidence_ref="e8" if self.fault == "unknown_ref" else "e1",
                quote="税务政策正文税务政策正文" if self.fault == "stitched_quote" else input.evidence[0].content,
            )
            points = (KnowledgeSummaryPoint(evidence_ref="e1", quote=input.evidence[0].content), invalid_point)
            return ModelTaskResult(output=KnowledgeSummaryOutput(outcome=SummaryOutcome.ANSWER, points=points))
        quote = "可信标题" if self.fault == "title_quote" else input.evidence[0].content
        if self.fault == "old_coverage":
            from agent_runtime.knowledge.evidence.contracts import KnowledgeRequirementSummaryOutput
            return ModelTaskResult(output=KnowledgeRequirementSummaryOutput(outcome=SummaryOutcome.ANSWER,
                points=(KnowledgeSummaryPoint(evidence_ref="e1", quote=quote),), coverage=()))
        return ModelTaskResult(output=KnowledgeSummaryOutput(outcome=SummaryOutcome.ANSWER,
            points=(KnowledgeSummaryPoint(evidence_ref="e1", quote=quote),)))


def stage(gateway, *, catalog=None, definition=None, limits=None, selector=None):
    return DefaultKnowledgeEvidenceStage(
        catalog=catalog or synthetic_catalog(), guard=QuestionEgressGuard(), context=ModelCallContextAccessor(),
        gateway=gateway, definition=definition or KnowledgeSummaryTaskV8.definition(),
        limits=limits or KnowledgeEvidenceLimits.minimal_v1(), selector=selector or MinimalEvidenceSelector(),
    )


def _catalog_with_second_document(*, deny_first: bool = False, content_only: bool = False):
    base = synthetic_catalog()
    policies = base.snapshot.policies
    if deny_first:
        policies = tuple(replace(item, disposition=KnowledgeEgressDisposition.DENY,
            allowed_fields=frozenset(), max_content_code_points=0) for item in policies)
    elif content_only:
        policies = tuple(replace(item, allowed_fields=frozenset({KnowledgeEgressField.CONTENT})) for item in policies)
    if deny_first:
        from agent_runtime.knowledge.evidence.contracts import KnowledgeEgressPolicy
        policies += (KnowledgeEgressPolicy(policy_ref="policy-doc-v2", policy_version="1",
            disposition=KnowledgeEgressDisposition.ALLOW_MINIMAL,
            allowed_fields=frozenset(KnowledgeEgressField), max_content_code_points=4096),)
    bindings = base.snapshot.bindings + (DocumentPolicyBinding(
        document_id="d2", policy_ref="policy-doc-v2" if deny_first else "policy-doc-v1",
        policy_version="1", allowed_index_snapshot_ids=frozenset({"a" * 64}),
    ),)
    snapshot = replace(base.snapshot, policies=policies, bindings=bindings)
    return KnowledgeEgressPolicyCatalog(replace(snapshot, canonical_fingerprint=canonical_policy_fingerprint(snapshot)))


@pytest.mark.asyncio
async def test_minimal_stage_uses_mode_projection_and_local_citation_without_extra_fields(caplog):
    gateway = FakeGateway()
    source = minimal_input()
    with observation_scope() as collector:
        result = await call_with_model_context(lambda: stage(gateway, catalog=_catalog_with_second_document(
            content_only=True)).build_result(input=source, context=_context(), timeout_s=2))
        observation = collector.snapshot()
    assert result.kind is EvidenceStageKind.SUCCESS and len(gateway.inputs) == 1
    payload = gateway.inputs[0]
    assert type(payload) is KnowledgeModeSummaryInput and payload.schema_version == 3
    assert payload.query_mode is source.intent.query_mode and payload.question == source.plan.original_question
    assert payload.evidence[0].title is None and payload.evidence[0].content == "税务政策正文"
    assert result.domain_result["points"][0]["quote"] == "税务政策正文"
    assert result.domain_result["points"][0]["citation"]["evidenceId"].startswith("ev-")
    assert result.domain_result["coverage"]["domainCoverageComplete"] is True
    assert "税务政策正文" not in repr(observation) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [
    ("question_denied", EvidenceStageKind.MODEL_EGRESS_DENIED),
    ("bad_hash", EvidenceStageKind.DOWNSTREAM_FAILURE),
    ("mode_mismatch", EvidenceStageKind.DOWNSTREAM_FAILURE),
    ("old_task", EvidenceStageKind.DOWNSTREAM_FAILURE),
    ("wrong_selector", EvidenceStageKind.DOWNSTREAM_FAILURE),
    ("policy_deny", EvidenceStageKind.MODEL_EGRESS_DENIED),
    ("policy_missing", EvidenceStageKind.MODEL_EGRESS_DENIED),
    ("context", EvidenceStageKind.DOWNSTREAM_FAILURE),
])
async def test_minimal_pre_summary_failures_are_closed_with_zero_model_calls(fault, expected):
    gateway = FakeGateway()
    source = minimal_input()
    catalog, definition, selector, context = synthetic_catalog(), None, None, _context()
    if fault == "question_denied":
        source = replace(source, question_egress_denied=True)
    elif fault == "bad_hash":
        ranked = source.batch.candidates[0]
        source = replace(source, batch=replace(source.batch,
            candidates=(replace(ranked, candidate=replace(ranked.candidate, content_sha256="f" * 64)),)))
    elif fault == "mode_mismatch":
        from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
        source = replace(source, intent=replace(source.intent, query_mode=KnowledgeQueryMode.EXPLANATION))
    elif fault == "old_task":
        definition = KnowledgeSummaryTaskV7.definition()
    elif fault == "wrong_selector":
        from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector
        selector = DeterministicEvidenceSelector()
    elif fault == "policy_deny":
        catalog = synthetic_catalog(disposition=KnowledgeEgressDisposition.DENY)
    elif fault == "policy_missing":
        ranked = source.batch.candidates[0]
        source = replace(source, batch=replace(source.batch,
            candidates=(replace(ranked, candidate=replace(ranked.candidate, document_id="unknown")),)))
    elif fault == "context":
        context = replace(context, request_id="another")
    result = await call_with_model_context(lambda: stage(gateway, catalog=catalog,
        definition=definition, selector=selector).build_result(input=source, context=context, timeout_s=2))
    assert result.kind is expected and gateway.inputs == []
    assert result.domain_result is None


@pytest.mark.asyncio
async def test_selected_policy_deny_does_not_fallback_to_allowed_later_candidate():
    gateway = FakeGateway()
    source = minimal_input((("d1", "tax.policy", "税务政策正文"), ("d2", "tax.policy", "其他政策正文")))
    second = source.batch.candidates[1]
    source = replace(source, batch=replace(source.batch, candidates=(source.batch.candidates[0],
        replace(second, candidate=replace(second.candidate, policy_ref="policy-doc-v2")))))
    result = await call_with_model_context(lambda: stage(gateway,
        catalog=_catalog_with_second_document(deny_first=True)).build_result(
            input=source, context=_context(), timeout_s=2))
    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED and gateway.inputs == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,kind,code", [
    ("insufficient", EvidenceStageKind.NO_RESULT, None),
    ("title_quote", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("duplicate_ref", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("unknown_ref", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("stitched_quote", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("old_coverage", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("failure", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.SUMMARY_FAILURE),
])
async def test_minimal_summary_failure_matrix_has_one_call_and_no_model_text(fault, kind, code):
    gateway = FakeGateway(fault)
    result = await call_with_model_context(lambda: stage(gateway).build_result(
        input=minimal_input(), context=_context(), timeout_s=2))
    assert result.kind is kind and result.stage_code is code and len(gateway.inputs) == 1
    if kind is not EvidenceStageKind.SUCCESS:
        assert result.domain_result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_minimal_summary_timeout_or_cancel_releases_single_call(cancel):
    gateway = FakeGateway("wait")
    operation = call_with_model_context(lambda: stage(gateway).build_result(
        input=minimal_input(), context=_context(), timeout_s=1 if cancel else 0.02))
    if cancel:
        task = asyncio.create_task(operation)
        await asyncio.wait_for(gateway.entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        assert (await operation).kind is EvidenceStageKind.TIMEOUT
    assert len(gateway.inputs) == 1 and gateway.released.is_set()


@pytest.mark.asyncio
async def test_real_gateway_v8_decoder_and_extractive_validator_reject_non_body_quote():
    definition = KnowledgeSummaryTaskV8.definition()
    response = StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
        tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps({
            "outcome": "answer", "points": [{"evidence_ref": "e1", "quote": "可信标题"}],
        }, ensure_ascii=False)),), usage_total_tokens=None)
    transport = FakeStructuredModelTransport(response)
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    result = await call_with_model_context(lambda: stage(gateway, definition=definition).build_result(
        input=minimal_input(), context=_context(), timeout_s=2))
    assert result.kind is EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.stage_code is EvidenceStageCode.INVALID_SUMMARY and result.domain_result is None
    assert transport.calls == 1 and len(transport.requests) == 1
    assert json.loads(transport.requests[0].user_payload_json)["query_mode"] == "lookup"


@pytest.mark.asyncio
async def test_real_gateway_rejects_forged_coverage_before_local_validator():
    definition = KnowledgeSummaryTaskV8.definition()
    response = StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
        tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps({
            "outcome": "answer", "points": [{"evidence_ref": "e1", "quote": "税务政策正文"}],
            "coverage": [],
        }, ensure_ascii=False)),), usage_total_tokens=None)
    transport = FakeStructuredModelTransport(response)
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    result = await call_with_model_context(lambda: stage(gateway, definition=definition).build_result(
        input=minimal_input(), context=_context(), timeout_s=2))
    assert result.kind is EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.stage_code is EvidenceStageCode.SUMMARY_FAILURE and result.domain_result is None
    assert transport.calls == 1
