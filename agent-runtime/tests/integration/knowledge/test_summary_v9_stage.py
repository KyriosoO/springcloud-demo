from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageCode, EvidenceStageKind
from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeCitedSummaryOutput, KnowledgeCitedSummaryPoint, KnowledgeEgressDisposition,
    KnowledgeEvidenceLimits, KnowledgeModeSummaryInput, KnowledgeSummaryInput,
    KnowledgeSummaryOutput, SummaryOutcome,
)
from agent_runtime.knowledge.evidence.minimal_selection import MinimalEvidenceSelector
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
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
           definition: ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeCitedSummaryOutput] | None = None,
           ) -> DefaultKnowledgeEvidenceStage:
    return DefaultKnowledgeEvidenceStage(
        catalog=synthetic_catalog(disposition=(KnowledgeEgressDisposition.DENY if denied
                                               else KnowledgeEgressDisposition.ALLOW_MINIMAL)),
        guard=QuestionEgressGuard(), context=ModelCallContextAccessor(), gateway=gateway,
        definition=cast(ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput],
                        definition or KnowledgeSummaryTaskV9.definition()),
        limits=KnowledgeEvidenceLimits.minimal_v1(), selector=MinimalEvidenceSelector(),
    )


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
