from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageCode, EvidenceStageKind, KnowledgeEvidenceContext
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    KnowledgeSummaryOutput,
    KnowledgeSummaryPoint,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.evidence.summary_validation import (
    InvalidSummary,
    SummaryValidationFailureReason,
)
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    ModelTaskId,
    ModelTaskResult,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.evidence_helpers import evidence_input, synthetic_catalog
from tests.helpers import ManualCancellationSignal
from tests.integration.knowledge.egress_diagnostic_journal import (
    KnowledgeEgressDiagnosticJournal,
    validate_diagnostic_journal,
)
from tests.integration.knowledge.knowledge_egress_diagnostic_support import (
    DiagnosticBudgetedSummaryTransport,
    RecordingExtractiveSummaryValidator,
)
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


def _request() -> StructuredModelRequest:
    return StructuredModelRequest(
        task_id=ModelTaskId.KNOWLEDGE_SUMMARY,
        task_version="1",
        system_instruction="diagnostic test",
        user_payload_json='{"evidence":[{"evidence_ref":"e1","content":"public"}]}',
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=16,
    )


def _bundle() -> KnowledgeEvidenceBundle:
    source = evidence_input()
    selection = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source),
        input=source,
        minimized_question="现行增值税政策是什么",
        limits=KnowledgeEvidenceLimits.v1(),
    )
    assert selection.bundle is not None
    return selection.bundle


@pytest.mark.asyncio
async def test_budgeted_transport_records_reason_without_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal_path = tmp_path / "attempt.jsonl"
    consumed_path = tmp_path / "consumed.json"
    monkeypatch.setenv("AGENT_KNOWLEDGE_DIAGNOSTIC_CONSUMED_OUTPUT", str(consumed_path))
    monkeypatch.setenv("AGENT_KNOWLEDGE_DIAGNOSTIC_RUN_ID", "knowledge-egress-diagnostic-v1-20260812-candidate-01")
    monkeypatch.setenv("AGENT_KNOWLEDGE_DIAGNOSTIC_AUTHORIZATION_REFERENCE", "P3_00:GATE-041")
    monkeypatch.setenv("AGENT_KNOWLEDGE_DIAGNOSTIC_MANIFEST_SHA256", "a" * 64)
    journal = KnowledgeEgressDiagnosticJournal(
        journal_path,
        run_id="knowledge-egress-diagnostic-v1-20260812-candidate-01",
        authorization_reference="P3_00:GATE-041",
        manifest_sha256="a" * 64,
    )
    validator = RecordingExtractiveSummaryValidator()
    delegate = FakeStructuredModelTransport(
        StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"answer","points":[]}',
            tool_calls=(),
            usage_total_tokens=1,
        )
    )
    transport = DiagnosticBudgetedSummaryTransport(delegate, journal, validator)
    transport.begin_case("tax-policy")
    await transport.complete(_request(), call_deadline=asyncio.get_running_loop().time() + 1)
    with pytest.raises(InvalidSummary):
        validator.validate(
            output=KnowledgeSummaryOutput(
                outcome=SummaryOutcome.ANSWER,
                points=(KnowledgeSummaryPoint(evidence_ref="e1", quote="not present"),),
            ),
            bundle=_bundle(),
            limits=KnowledgeEvidenceLimits.v1(),
        )
    transport.record_result(
        case_id="tax-policy",
        kind=EvidenceStageKind.DOWNSTREAM_FAILURE,
        stage_code=EvidenceStageCode.INVALID_SUMMARY,
    )
    transport.end_case("tax-policy")

    records = validate_diagnostic_journal(journal_path)
    assert records[-1]["validationReason"] == "quote_not_substring"
    serialized = journal_path.read_text(encoding="utf-8")
    assert "not present" not in serialized
    assert "税务政策正文" not in serialized
    consumed = json.loads(consumed_path.read_text(encoding="utf-8"))
    assert consumed["authorizedSummaryCalls"] == 9
    assert consumed["diagnosticOnly"] is True
    assert consumed["manifestSha256"] == "a" * 64


class InvalidGateway:
    async def generate(self, *, definition: object, input: object, context: object) -> ModelTaskResult[KnowledgeSummaryOutput]:
        del definition, input, context
        return ModelTaskResult(
            output=KnowledgeSummaryOutput(
                outcome=SummaryOutcome.ANSWER,
                points=(KnowledgeSummaryPoint(evidence_ref="e1", quote="not present"),),
            )
        )


@pytest.mark.asyncio
async def test_public_stage_contract_remains_invalid_summary_only() -> None:
    validator = RecordingExtractiveSummaryValidator()
    stage = DefaultKnowledgeEvidenceStage(
        catalog=synthetic_catalog(),
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=InvalidGateway(),  # type: ignore[arg-type]
        definition=KnowledgeSummaryTaskV1.definition(),
        validator=validator,
    )
    stage_context = KnowledgeEvidenceContext(
        request_id="req-1",
        correlation_id="corr-1",
        subject="user-1",
        deadline_monotonic=asyncio.get_running_loop().time() + 5,
        cancellation=ManualCancellationSignal(),
    )

    result = await call_with_model_context(
        lambda: stage.build_result(input=evidence_input(), context=stage_context, timeout_s=4)
    )

    assert result.kind is EvidenceStageKind.DOWNSTREAM_FAILURE
    assert result.stage_code is EvidenceStageCode.INVALID_SUMMARY
    assert not hasattr(result, "validation_reason")
    assert validator.take_reason() is SummaryValidationFailureReason.QUOTE_NOT_SUBSTRING
