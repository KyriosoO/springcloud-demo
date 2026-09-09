"""Candidate selection through the unchanged verifier/policy/Summary V7 stage."""
import asyncio
from dataclasses import asdict, replace

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageCode, EvidenceStageKind, EvidenceNoResultReason
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.evidence.contracts import KnowledgeEgressDisposition
from agent_runtime.knowledge.evidence.summary_task_v7 import KnowledgeSummaryTaskV7
from agent_runtime.observation import observation_scope
from tests.evidence_helpers import synthetic_catalog
from tests.integration.knowledge.test_evidence_stage import _context
from tests.integration.knowledge.test_requirement_evidence_stage import Gateway, stage
from tests.model_helpers import call_with_model_context
from tests.unit.knowledge.test_evidence_admission import scored_input


def candidate_stage(gateway, **kwargs):
    return stage(gateway, definition=KnowledgeSummaryTaskV7.definition(),
        selector=ScoreAwareEvidenceSelector(), **kwargs)


@pytest.mark.asyncio
async def test_full_stage_filters_only_optional_tail_and_keeps_safe_projection(caplog):
    source, gateway = scored_input(), Gateway()
    with observation_scope() as collector:
        result = await call_with_model_context(lambda: candidate_stage(gateway).build_result(
            input=source, context=_context(), timeout_s=2))
        observation = collector.snapshot()
    assert result.kind is EvidenceStageKind.SUCCESS and len(gateway.inputs) == 1
    assert [e.content for e in gateway.inputs[0].evidence] == [
        source.batch.candidates[i].candidate.content for i in (0, 1, 2, 4, 5)]
    assert gateway.inputs[0].requirements == source.evidence_requirements
    visible = repr(asdict(observation)) + caplog.text
    assert all(item.candidate.content not in visible for item in source.batch.candidates)
    assert all(item.focus not in visible for item in source.evidence_requirements)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,kind,code", [
    ("low_hash", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.EVIDENCE_FAILURE),
    ("anchor_score", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.EVIDENCE_FAILURE),
    ("optional_score", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.EVIDENCE_FAILURE),
    ("missing_anchor", EvidenceStageKind.NO_RESULT, None),
    ("sensitive", EvidenceStageKind.MODEL_EGRESS_DENIED, None),
    ("document_denied", EvidenceStageKind.MODEL_EGRESS_DENIED, None),
    ("policy_missing", EvidenceStageKind.MODEL_EGRESS_DENIED, None),
])
async def test_pre_summary_failures_remain_zero_call(fault, kind, code):
    source, gateway, catalog = scored_input(), Gateway(), synthetic_catalog()
    if fault == "low_hash":
        items = source.batch.candidates
        bad = replace(items[3], candidate=replace(items[3].candidate, content_sha256="0" * 64))
        source = replace(source, batch=replace(source.batch, candidates=items[:3] + (bad,) + items[4:]))
    elif fault in {"anchor_score", "optional_score"}:
        index = 0 if fault == "anchor_score" else 3
        source = replace(source, batch=replace(source.batch, candidates=tuple(
            replace(item, rerank_score=-0.01) if i == index else item
            for i, item in enumerate(source.batch.candidates))))
    elif fault == "missing_anchor": source = scored_input((1, 1))
    elif fault == "sensitive": source = replace(source, original_question="税务问题，邮箱someone@example.com")
    elif fault == "document_denied": catalog = synthetic_catalog(disposition=KnowledgeEgressDisposition.DENY)
    else:
        source = replace(source, batch=replace(source.batch, candidates=tuple(
            replace(item, candidate=replace(item.candidate, policy_ref="unclassified"))
            for item in source.batch.candidates)))
    result = await call_with_model_context(lambda: candidate_stage(gateway, catalog=catalog).build_result(
        input=source, context=_context(), timeout_s=2))
    assert result.kind is kind and gateway.inputs == []
    if code is not None: assert result.stage_code is code
    if fault == "missing_anchor": assert result.no_result_reason is EvidenceNoResultReason.INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,kind,code", [
    ("quote", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("missing", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
    ("failure", EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.SUMMARY_FAILURE),
    ("timeout", EvidenceStageKind.TIMEOUT, EvidenceStageCode.SUMMARY_TIMEOUT),
    ("insufficient", EvidenceStageKind.NO_RESULT, None),
])
async def test_summary_validation_not_weakened_and_no_retry(fault, kind, code):
    gateway = Gateway(fault)
    result = await call_with_model_context(lambda: candidate_stage(gateway).build_result(
        input=scored_input(), context=_context(), timeout_s=2))
    assert result.kind is kind and result.stage_code is code and len(gateway.inputs) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancellation_release_without_retry(cancel):
    gateway = Gateway("wait")
    operation = call_with_model_context(lambda: candidate_stage(gateway).build_result(
        input=scored_input(), context=_context(), timeout_s=1 if cancel else 0.02))
    if cancel:
        task = asyncio.create_task(operation)
        await asyncio.wait_for(gateway.entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    else:
        assert (await operation).kind is EvidenceStageKind.TIMEOUT
    assert len(gateway.inputs) == 1 and gateway.released.is_set()
