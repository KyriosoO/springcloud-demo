from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from tests.evaluation.knowledge.live_bootstrap import authorization_path, manifest_path
from tests.evaluation.knowledge.live_contracts import (
    BudgetedLiveModelTransport,
    load_authorization,
    load_manifest,
)
from tests.evaluation.knowledge.live_diagnostics import LiveDiagnosticPhase, LivePhaseCheckpointJournal


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v1-20260813-candidate-03"
AUTHORIZATION_REFERENCE = "P3_00:GATE-045"
LAUNCHER = "agent-runtime/scripts/run-knowledge-p5-live-candidate-03.ps1"
MANDATORY_ASSETS = {
    LAUNCHER,
    "agent-runtime/tests/evaluation/knowledge/live_bootstrap.py",
    "agent-runtime/tests/evaluation/knowledge/live_contracts.py",
    "agent-runtime/tests/evaluation/knowledge/live_diagnostics.py",
    "agent-runtime/tests/evaluation/knowledge/live_executor.py",
    "agent-runtime/tests/evaluation/knowledge/live_runner.py",
    "agent-runtime/tests/evaluation/knowledge/test_live_p5_diagnostics.py",
    "agent-runtime/tests/evaluation/knowledge/test_live_p5_preparation.py",
    "agent-runtime/tests/evaluation/knowledge/test_live_p5_candidate_03_preparation.py",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.jsonl",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.authorization.json",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.provenance.json",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.sha256",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-01.manifest.json",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-02.manifest.json",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-01/authorization.consumed.json",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-02/authorization.consumed.json",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-01/paid-attempts.jsonl",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-02/paid-attempts.jsonl",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-01/failure.json",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-02/failure.json",
}
SAFE_PHASE_KEYS = {
    "schemaVersion",
    "runId",
    "sequence",
    "caseId",
    "variant",
    "phase",
    "event",
    "status",
    "reasonCode",
}


class FakeTransport:
    def __init__(self, *, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.calls = 0
        self.first_call_saw_consumed = False

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del request, call_deadline
        self.calls += 1
        if self.calls == 1:
            self.first_call_saw_consumed = (
                self.output_dir.is_dir() and (self.output_dir / "authorization.consumed.json").is_file()
            )
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"insufficient_evidence","points":[]}',
            tool_calls=(),
            usage_total_tokens=1,
        )


def _request(task_id: ModelTaskId) -> StructuredModelRequest:
    payload = '{"question":"synthetic"}' if task_id is ModelTaskId.KNOWLEDGE_REWRITE else '{"evidence":[]}'
    return StructuredModelRequest(
        task_id=task_id,
        task_version="1" if task_id is ModelTaskId.KNOWLEDGE_REWRITE else "2",
        system_instruction="synthetic fixed instruction",
        user_payload_json=payload,
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=16,
    )


async def _completed() -> None:
    return None


async def _run_fake_variant(
    *,
    case_id: str,
    variant: Literal["primary", "rewrite_ablation"],
    transport: BudgetedLiveModelTransport,
    diagnostics: LivePhaseCheckpointJournal,
) -> None:
    diagnostics.begin_variant(case_id=case_id, variant=variant)
    transport.begin(case_id=case_id, variant=variant)

    async def capability() -> None:
        if variant == "primary":
            await diagnostics.run_async(
                phase=LiveDiagnosticPhase.REWRITE,
                operation=transport.complete(_request(ModelTaskId.KNOWLEDGE_REWRITE), call_deadline=1.0),
            )
        await diagnostics.run_async(phase=LiveDiagnosticPhase.RETRIEVAL, operation=_completed())
        await diagnostics.run_async(
            phase=LiveDiagnosticPhase.EVIDENCE,
            operation=transport.complete(_request(ModelTaskId.KNOWLEDGE_SUMMARY), call_deadline=1.0),
        )

    async def variant_execution() -> None:
        await diagnostics.run_async(phase=LiveDiagnosticPhase.CAPABILITY, operation=capability())
        diagnostics.run_sync(phase=LiveDiagnosticPhase.VARIANT_PACK, operation=lambda: None)

    try:
        await diagnostics.run_async(
            phase=LiveDiagnosticPhase.VARIANT_EXECUTION,
            operation=variant_execution(),
        )
    finally:
        transport.end()
        diagnostics.end_variant()


def test_candidate_03_manifest_authorization_and_frozen_asset_scope_are_exact() -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT))
    authorization = load_authorization(authorization_path(REPOSITORY_ROOT))

    assert manifest.run_id == RUN_ID == authorization.run_id
    assert manifest.authorization_reference == AUTHORIZATION_REFERENCE == authorization.authorization_reference
    assert len(digest) == 64
    assert manifest.schema_version == 2
    assert manifest.paid_request_budget.capability_executions == 52
    assert manifest.paid_request_budget.knowledge_rewrite == 26
    assert manifest.paid_request_budget.knowledge_summary == 52
    assert manifest.paid_request_budget.maximum_paid_requests == 78
    assert manifest.paid_request_budget.retry == 0
    assert manifest.paid_request_budget.core_answer == 0
    assert manifest.retrieval_binding is not None
    assert (
        manifest.retrieval_binding.read_alias,
        manifest.retrieval_binding.expected_index_name,
        manifest.retrieval_binding.expected_index_uuid,
        manifest.retrieval_binding.mapping_version,
        manifest.retrieval_binding.policy_snapshot_id,
        manifest.retrieval_binding.law_snapshot_id,
    ) == (
        "agent-doc-tax-policy-v2-read",
        "agent-doc-tax-policy-v3-20260803-agent-read-v1",
        "k97bn1gxROSfVm7zGfzbOg",
        "agent-knowledge-tax-v1",
        "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed",
        "99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2",
    )
    paths = {item.path for item in manifest.asset_hashes}
    assert MANDATORY_ASSETS <= paths
    assert "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-03.manifest.json" not in paths

    launcher = (REPOSITORY_ROOT / LAUNCHER).read_text(encoding="utf-8")
    assert "candidate-03.manifest.json" in launcher
    assert "candidate-02.manifest.json" not in launcher
    assert "[Parameter(Mandatory = $true)][string]$AuthorizedRunId" in launcher
    assert "[Parameter(Mandatory = $true)][string]$AuthorizedManifestSha256" in launcher
    assert "[Parameter(Mandatory = $true)][string]$AuthorizationReference" in launcher
    assert "[Parameter(Mandatory = $true)][int]$MaximumPaidRequests" in launcher


@pytest.mark.asyncio
async def test_candidate_03_fake_run_consumes_once_and_records_all_finite_phases(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT))
    output_dir = tmp_path / RUN_ID
    delegate = FakeTransport(output_dir=output_dir)
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=output_dir,
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="c" * 40,
    )
    diagnostics = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)

    assert not output_dir.exists()
    for ordinal in range(26):
        case_id = f"case-{ordinal:02d}"
        await _run_fake_variant(
            case_id=case_id,
            variant="primary",
            transport=transport,
            diagnostics=diagnostics,
        )
        await _run_fake_variant(
            case_id=case_id,
            variant="rewrite_ablation",
            transport=transport,
            diagnostics=diagnostics,
        )

    assert delegate.first_call_saw_consumed is True
    assert delegate.calls == transport.total_calls == 78
    assert transport.rewrite_calls == 26
    assert transport.summary_calls == 52
    assert transport.unauthorized_content_count == 0

    paid_events = [
        json.loads(line)
        for line in (output_dir / "paid-attempts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    phase_events = [
        json.loads(line)
        for line in diagnostics.path.read_text(encoding="ascii").splitlines()
    ]
    assert len(paid_events) == 156
    assert len(phase_events) == 572
    assert [item["sequence"] for item in phase_events] == list(range(1, 573))
    assert {item["phase"] for item in phase_events} == {item.value for item in LiveDiagnosticPhase}
    assert all(set(item) <= SAFE_PHASE_KEYS for item in phase_events)
    assert all("reasonCode" not in item for item in phase_events)
    assert sum(item["event"] == "started" for item in phase_events) == 286
    assert sum(item["event"] == "terminal" for item in phase_events) == 286
    assert all(item.get("status") in {None, "completed"} for item in phase_events)
