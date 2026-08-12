from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageKind
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryInput,
    SummaryCoverageInput,
    SummaryEvidenceInput,
)
from agent_runtime.knowledge.evidence.summary_task_v2 import KnowledgeSummaryTaskV2
from agent_runtime.model.contracts import StructuredFinishKind, StructuredModelRequest, StructuredModelResponse
from tests.integration.knowledge.egress_attempt_journal import (
    KnowledgeEgressAttemptJournal,
    validate_attempt_journal,
)
from tests.integration.knowledge.egress_v2_stability import (
    AUTHORIZATION_REFERENCE,
    AUTHORIZED_SUMMARY_CALLS,
    Gate043BudgetedSummaryTransport,
    KnowledgeEgressV2EvidenceError,
    RUN_ID,
    TASK_BINDING,
    validate_v2_live_evidence,
)
from tests.integration.knowledge.test_knowledge_egress_live_harness import fixture as v1_evidence_fixture


class FakeTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del request, call_deadline
        self.calls += 1
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"insufficient_evidence","points":[]}',
            tool_calls=(),
            usage_total_tokens=1,
        )


def summary_input() -> KnowledgeSummaryInput:
    return KnowledgeSummaryInput(
        schema_version=1,
        question="税务政策",
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(
            SummaryEvidenceInput(
                evidence_ref="e1",
                content="税务政策正文",
                domain_ids=("tax.policy",),
            ),
        ),
    )


def v2_evidence_fixture() -> dict[str, Any]:
    value = v1_evidence_fixture()
    value["runId"] = RUN_ID
    value["authorizationReference"] = AUTHORIZATION_REFERENCE
    value["authorizationGateId"] = "GATE-043"
    value["taskBinding"] = dict(TASK_BINDING)
    return value


@pytest.mark.asyncio
async def test_fake_transport_consumes_once_runs_exact_thirty_and_rejects_call_thirty_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumed = tmp_path / "consumed.json"
    journal_path = tmp_path / "attempt.jsonl"
    monkeypatch.setenv("AGENT_KNOWLEDGE_EGRESS_CONSUMED_OUTPUT", str(consumed))
    monkeypatch.setenv("AGENT_KNOWLEDGE_EGRESS_RUN_ID", RUN_ID)
    monkeypatch.setenv("AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE", AUTHORIZATION_REFERENCE)
    journal = KnowledgeEgressAttemptJournal(
        journal_path,
        run_id=RUN_ID,
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    delegate = FakeTransport()
    transport = Gate043BudgetedSummaryTransport(delegate, journal)
    structured_request = KnowledgeSummaryTaskV2.definition().build_request(summary_input())
    case_ids = ("tax-policy", "tax-law", "tax-mixed")
    for _ in range(10):
        for case_id in case_ids:
            transport.begin_case(case_id)
            await transport.complete(structured_request, call_deadline=100.0)
            transport.record_result(case_id=case_id, kind=EvidenceStageKind.SUCCESS, stage_code=None)
            transport.end_case(case_id)

    assert transport.calls == AUTHORIZED_SUMMARY_CALLS
    assert delegate.calls == AUTHORIZED_SUMMARY_CALLS
    assert transport.retry_count == 0
    assert transport.forbidden_field_count == 0
    records = validate_attempt_journal(journal_path)
    assert sum(record["event"] == "outbound_started" for record in records) == 30
    assert sum(record["event"] == "call_terminal" for record in records) == 30
    marker = json.loads(consumed.read_text(encoding="utf-8"))
    assert marker["gateId"] == "GATE-043"
    assert marker["runId"] == RUN_ID
    assert marker["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert marker["authorizedSummaryCalls"] == 30

    transport.begin_case("tax-policy")
    with pytest.raises(RuntimeError, match="knowledge.egress_v2_budget_exhausted"):
        await transport.complete(structured_request, call_deadline=100.0)
    transport.end_case("tax-policy")
    assert delegate.calls == 30


@pytest.mark.asyncio
async def test_fake_transport_fails_before_consumption_for_non_v2_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumed = tmp_path / "consumed.json"
    monkeypatch.setenv("AGENT_KNOWLEDGE_EGRESS_CONSUMED_OUTPUT", str(consumed))
    monkeypatch.setenv("AGENT_KNOWLEDGE_EGRESS_RUN_ID", RUN_ID)
    monkeypatch.setenv("AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE", AUTHORIZATION_REFERENCE)
    journal = KnowledgeEgressAttemptJournal(
        tmp_path / "attempt.jsonl",
        run_id=RUN_ID,
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    delegate = FakeTransport()
    transport = Gate043BudgetedSummaryTransport(delegate, journal)
    request = KnowledgeSummaryTaskV2.definition().build_request(summary_input())
    invalid = StructuredModelRequest(
        task_id=request.task_id,
        task_version="1",
        system_instruction=request.system_instruction,
        user_payload_json=request.user_payload_json,
        tools=request.tools,
        tool_mode=request.tool_mode,
        output_mode=request.output_mode,
        max_output_tokens=request.max_output_tokens,
    )
    transport.begin_case("tax-policy")
    with pytest.raises(RuntimeError, match="knowledge.egress_v2_request_invalid"):
        await transport.complete(invalid, call_deadline=100.0)
    transport.end_case("tax-policy")
    assert delegate.calls == 0
    assert not consumed.exists()


def test_v2_evidence_contract_accepts_exact_binding_and_rejects_drift() -> None:
    value = v2_evidence_fixture()
    assert validate_v2_live_evidence(value) == value

    mutations: tuple[Callable[[dict[str, Any]], object], ...] = (
        lambda item: item["taskBinding"].update(taskVersion="1"),
        lambda item: item.update(authorizationGateId="GATE-040"),
        lambda item: item["budget"].update(actualSummaryCalls=29),
        lambda item: item["validation"].update(invalidQuoteAcceptedCount=1),
    )
    for mutation in mutations:
        invalid = deepcopy(value)
        mutation(invalid)
        with pytest.raises(KnowledgeEgressV2EvidenceError):
            validate_v2_live_evidence(invalid)


def test_v2_runner_fails_binding_before_key_or_service_and_targets_only_v2_assets() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts/run-knowledge-egress-v2-stability.ps1").read_text(encoding="utf-8")

    binding_guard = script.index("knowledge.egress_v2_authorization_binding_invalid")
    assert binding_guard < script.index("GetEnvironmentVariable('LLM_API_KEY'")
    assert binding_guard < script.index("Start-Process -FilePath 'java'")
    assert "$expectedRunId = 'knowledge-egress-v2-20260812-candidate-01'" in script
    assert "$expectedAuthorizationReference = 'P3_00:GATE-043'" in script
    assert "knowledge-egress-v2-20260812-candidate-01.manifest.json" in script
    assert "gate043-knowledge-egress-v2-20260812-candidate-01.consumed.json" in script
    assert "test_real_knowledge_egress_v2_stability.py" in script
    assert "RUN_KNOWLEDGE_EGRESS_V2_STABILITY" in script
    assert "RUN_KNOWLEDGE_EGRESS_LIVE" not in script
    assert script.count("Move-Item -LiteralPath $stagedJournal") == 2
