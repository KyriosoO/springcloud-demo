from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from typing import Any, cast

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageCode, EvidenceStageKind
from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeCitedSummaryOutput, KnowledgeCitedSummaryPoint, KnowledgeEgressDisposition,
    KnowledgeModeSummaryInput, SummaryOutcome,
)
from agent_runtime.knowledge.evidence.minimal_stage import MinimalKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task_v9 import KnowledgeSummaryTaskV9, OUTPUT_NAME
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    ModelTaskDefinition, ModelTaskResult, StructuredFinishKind, StructuredModelResponse, StructuredToolCall,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.evidence_helpers import synthetic_catalog
from tests.integration.knowledge.test_evidence_stage import _context
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context
from tests.unit.knowledge.evidence.test_minimal_selection import minimal_input


def _stage(gateway: Any, *, denied: bool = False,
           definition: ModelTaskDefinition[KnowledgeModeSummaryInput, KnowledgeCitedSummaryOutput] | None = None,
           ) -> MinimalKnowledgeEvidenceStage:
    return MinimalKnowledgeEvidenceStage(
        catalog=synthetic_catalog(disposition=(KnowledgeEgressDisposition.DENY if denied
                                               else KnowledgeEgressDisposition.ALLOW_MINIMAL)),
        guard=QuestionEgressGuard(), context=ModelCallContextAccessor(), gateway=gateway,
        definition=definition or KnowledgeSummaryTaskV9.definition(),
    )


@pytest.mark.parametrize("fault", ["task_id", "version", "input_type"])
def test_current_stage_rejects_wrong_binding_at_construction(fault: str) -> None:
    from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput
    from agent_runtime.model.contracts import ModelTaskId

    definition = KnowledgeSummaryTaskV9.definition()
    if fault == "task_id":
        definition = replace(definition, task_id=ModelTaskId.KNOWLEDGE_REWRITE)
    elif fault == "version":
        definition = replace(definition, task_version="8")
    else:
        definition = replace(definition, input_type=KnowledgeSummaryInput)
    gateway = FakeGateway()
    with pytest.raises(ValueError, match="knowledge.production_task_version_invalid"):
        _stage(gateway, definition=definition)
    assert gateway.inputs == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["input", "hash", "mode", "question", "context", "policy_version",
                                  "question_denied", "policy_missing"])
async def test_current_stage_invalid_input_is_closed_before_summary(fault: str) -> None:
    gateway = FakeGateway()
    source = minimal_input()
    context = _context()
    if fault == "input":
        source = object()
    elif fault == "hash":
        ranked = source.batch.candidates[0]
        source = replace(source, batch=replace(source.batch, candidates=(replace(ranked,
            candidate=replace(ranked.candidate, content_sha256="b" * 64)),)))
    elif fault == "mode":
        source = replace(source, intent=replace(source.intent, query_mode=KnowledgeQueryMode.EXPLANATION))
    elif fault == "question":
        source = replace(source, question=replace(source.question, minimized_question="其他税务政策"))
    elif fault == "context":
        context = replace(context, request_id="different-request")
    elif fault == "policy_version":
        source = replace(source, question_policy_version="different-policy")
    elif fault == "question_denied":
        source = replace(source, question_egress_denied=True)
    else:
        ranked = source.batch.candidates[0]
        source = replace(source, batch=replace(source.batch, candidates=(replace(ranked,
            candidate=replace(ranked.candidate, document_id="unknown")),)))
    result = await call_with_model_context(lambda: _stage(gateway).build_result(
        input=source, context=context, timeout_s=2,
    ))
    assert result.kind is (EvidenceStageKind.MODEL_EGRESS_DENIED
                           if fault in {"policy_version", "question_denied", "policy_missing"}
                           else EvidenceStageKind.DOWNSTREAM_FAILURE)
    assert result.domain_result is None and gateway.inputs == []


@pytest.mark.asyncio
async def test_current_stage_selected_policy_denial_never_reselects_allowed_candidate() -> None:
    from tests.integration.knowledge.test_minimal_evidence_stage import _catalog_with_second_document

    gateway = FakeGateway()
    source = minimal_input((("d1", "tax.policy", "税务政策正文"), ("d2", "tax.policy", "其他政策正文")))
    second = source.batch.candidates[1]
    source = replace(source, batch=replace(source.batch, candidates=(source.batch.candidates[0],
        replace(second, candidate=replace(second.candidate, policy_ref="policy-doc-v2")))))
    stage = MinimalKnowledgeEvidenceStage(
        catalog=_catalog_with_second_document(deny_first=True), guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(), gateway=gateway, definition=KnowledgeSummaryTaskV9.definition(),
    )
    result = await call_with_model_context(lambda: stage.build_result(input=source, context=_context(), timeout_s=2))
    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
    assert result.domain_result is None and gateway.inputs == []


class FakeGateway:
    def __init__(self, *, claim: str = "相关政策见引文。", quote: str = "税务政策正文",
                 insufficient: bool = False) -> None:
        self.inputs: list[KnowledgeModeSummaryInput] = []
        self.claim = claim
        self.quote = quote
        self.insufficient = insufficient

    async def generate(self, *, definition: object, input: KnowledgeModeSummaryInput,
                       context: object) -> ModelTaskResult[KnowledgeCitedSummaryOutput]:
        del definition, context
        self.inputs.append(input)
        if self.insufficient:
            return ModelTaskResult(output=KnowledgeCitedSummaryOutput(
                outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE, points=(),
            ))
        return ModelTaskResult(output=KnowledgeCitedSummaryOutput(
            outcome=SummaryOutcome.ANSWER,
            points=(KnowledgeCitedSummaryPoint(evidence_ref="e1", quote=self.quote, claim=self.claim),),
        ))


class RaisingGateway:
    def __init__(self, failure: BaseException) -> None:
        self.failure = failure
        self.calls = 0

    async def generate(self, *, definition: object, input: KnowledgeModeSummaryInput,
                       context: object) -> ModelTaskResult[KnowledgeCitedSummaryOutput]:
        del definition, input, context
        self.calls += 1
        raise self.failure


@pytest.mark.asyncio
async def test_v9_stage_returns_limited_answer_and_keeps_quote_local() -> None:
    gateway = FakeGateway()
    result = await call_with_model_context(lambda: _stage(gateway).build_result(
        input=minimal_input(mode=KnowledgeQueryMode.EXPLANATION), context=_context(), timeout_s=2,
    ))
    assert result.kind is EvidenceStageKind.SUCCESS and len(gateway.inputs) == 1
    assert result.domain_result is not None
    plain = cast(dict[str, Any], json.loads(canonical_json_bytes(result.domain_result)))
    assert result.domain_result["summaryType"] == "cited_limited_answer"
    assert result.domain_result["answerSummary"] == "1. 相关政策见引文。"
    assert plain["points"][0]["quote"] == "税务政策正文"
    assert "claim" not in plain["points"][0]


@pytest.mark.asyncio
async def test_v9_stage_policy_denial_has_no_summary_call() -> None:
    gateway = FakeGateway()
    result = await call_with_model_context(lambda: _stage(gateway, denied=True).build_result(
        input=minimal_input(), context=_context(), timeout_s=2,
    ))
    assert result.kind is EvidenceStageKind.MODEL_EGRESS_DENIED and gateway.inputs == []


@pytest.mark.asyncio
async def test_v9_stage_timeout_fails_closed_after_one_call() -> None:
    gateway = RaisingGateway(TimeoutError("synthetic timeout"))
    result = await call_with_model_context(lambda: _stage(gateway).build_result(
        input=minimal_input(mode=KnowledgeQueryMode.EXPLANATION), context=_context(), timeout_s=2,
    ))
    assert gateway.calls == 1 and result.kind is EvidenceStageKind.TIMEOUT
    assert result.stage_code is EvidenceStageCode.SUMMARY_TIMEOUT and result.domain_result is None


@pytest.mark.asyncio
async def test_v9_stage_cancellation_propagates_without_result() -> None:
    gateway = RaisingGateway(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await call_with_model_context(lambda: _stage(gateway).build_result(
            input=minimal_input(mode=KnowledgeQueryMode.EXPLANATION), context=_context(), timeout_s=2,
        ))
    assert gateway.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("gateway,kind,code", [
    (FakeGateway(insufficient=True), EvidenceStageKind.NO_RESULT, None),
    (FakeGateway(claim="https://example.test"), EvidenceStageKind.DOWNSTREAM_FAILURE,
     EvidenceStageCode.INVALID_SUMMARY),
    (FakeGateway(quote="编造原文"), EvidenceStageKind.DOWNSTREAM_FAILURE, EvidenceStageCode.INVALID_SUMMARY),
])
async def test_v9_stage_terminal_results_have_one_call_and_no_model_output(
    gateway: FakeGateway, kind: EvidenceStageKind, code: EvidenceStageCode | None,
) -> None:
    result = await call_with_model_context(lambda: _stage(gateway).build_result(
        input=minimal_input(mode=KnowledgeQueryMode.EXPLANATION), context=_context(), timeout_s=2,
    ))
    assert result.kind is kind and result.stage_code is code and len(gateway.inputs) == 1
    assert result.domain_result is None


@pytest.mark.asyncio
async def test_v9_real_gateway_decoder_rejects_forged_citation_with_one_transport_call() -> None:
    definition = KnowledgeSummaryTaskV9.definition()
    response = StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
        tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps({
            "outcome": "answer", "points": [{"evidence_ref": "e1", "quote": "税务政策正文",
                                           "claim": "相关政策见引文。", "citation": "fake"}],
        }, ensure_ascii=False)),), usage_total_tokens=None)
    transport = FakeStructuredModelTransport(response)
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    result = await call_with_model_context(lambda: _stage(gateway, definition=definition).build_result(
        input=minimal_input(mode=KnowledgeQueryMode.EXPLANATION), context=_context(), timeout_s=2,
    ))
    assert result.kind is EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.stage_code is EvidenceStageCode.SUMMARY_FAILURE and result.domain_result is None
    assert transport.calls == 1 and len(transport.requests) == 1
