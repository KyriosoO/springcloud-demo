from __future__ import annotations

import hashlib
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
from tests.evaluation.knowledge.live_bootstrap import (
    LiveEvaluationBootstrapError,
    build_live_from_environment,
    manifest_path,
)
from tests.evaluation.knowledge.live_contracts import (
    BudgetedLiveModelTransport,
    load_authorization_template,
    load_manifest,
)
from tests.evaluation.knowledge.live_diagnostics import LiveDiagnosticPhase, LivePhaseCheckpointJournal
from tests.evaluation.knowledge.test_live_p5_candidate_03_preparation import SAFE_PHASE_KEYS


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v4-20260828-candidate-07"
MANIFEST_SHA256 = "af545166b37a33899d6f1d7830c09472df8cc2fe45047fea242ecc524bfc2211"
AUTHORIZATION_REFERENCE = "P3_00:GATE-079"
AUTHORIZATION_TEMPLATE = REPOSITORY_ROOT / (
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v4-20260828-candidate-07.authorization-template.json"
)
AUTHORIZATION_PATH = REPOSITORY_ROOT / (
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v4-20260828-candidate-07.authorization.json"
)
RESULT_ROOT = REPOSITORY_ROOT / "agent-runtime/tests/evaluation/knowledge/results" / RUN_ID


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(task_id: ModelTaskId) -> StructuredModelRequest:
    task_version = "1" if task_id is ModelTaskId.KNOWLEDGE_REWRITE else "4"
    payload = '{"question":"synthetic"}' if task_id is ModelTaskId.KNOWLEDGE_REWRITE else '{"evidence":[]}'
    return StructuredModelRequest(
        task_id=task_id,
        task_version=task_version,
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
        await diagnostics.run_async(phase=LiveDiagnosticPhase.VARIANT_EXECUTION, operation=variant_execution())
    finally:
        transport.end()
        diagnostics.end_variant()


class FakeTransport:
    def __init__(self, *, output_dir: Path, fail: bool = False) -> None:
        self.output_dir = output_dir
        self.fail = fail
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
            self.first_call_saw_consumed = (self.output_dir / "authorization.consumed.json").is_file()
        if self.fail:
            raise RuntimeError("synthetic.transport_failure")
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"insufficient_evidence","points":[]}',
            tool_calls=(),
            usage_total_tokens=1,
        )


def test_candidate_07_manifest_template_assets_and_history_are_frozen() -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-07"))
    template = load_authorization_template(AUTHORIZATION_TEMPLATE)

    assert digest == MANIFEST_SHA256
    assert manifest.schema_version == 5
    assert manifest.work_package_id == "WP-K-EFFECT-LIVE-07"
    assert manifest.run_id == template.run_id == RUN_ID
    assert manifest.authorization_reference == template.authorization_reference == AUTHORIZATION_REFERENCE
    assert manifest.task_versions == {"knowledge_rewrite": "1", "knowledge_summary": "4"}
    assert manifest.paid_request_budget.maximum_paid_requests == template.maximum_paid_requests == 78
    assert manifest.paid_request_budget.retry == 0
    assert manifest.configuration_binding is not None
    assert manifest.configuration_binding.effect_metric_version == "knowledge-effect-metrics-v2"
    assert manifest.configuration_binding.quality_population_minimum_rate == 0.9
    assert template.live_p5_authorized is False

    asset_paths = {asset.path for asset in manifest.asset_hashes}
    for candidate in range(1, 7):
        assert any(f"candidate-0{candidate}" in path for path in asset_paths)
    assert "agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v4.py" in asset_paths
    assert "agent-runtime/tests/evaluation/knowledge/test_effect_metrics_v2.py" in asset_paths
    assert "agent-runtime/scripts/run-knowledge-p5-live-candidate-07.ps1" in asset_paths
    assert str(AUTHORIZATION_TEMPLATE.relative_to(REPOSITORY_ROOT)).replace("\\", "/") in asset_paths
    assert tuple(asset.path for asset in manifest.asset_hashes) == tuple(sorted(asset_paths))
    assert all(_sha256(REPOSITORY_ROOT / asset.path) == asset.sha256 for asset in manifest.asset_hashes)


def test_candidate_07_prepared_state_has_no_authorization_or_result() -> None:
    assert not AUTHORIZATION_PATH.exists()
    assert not RESULT_ROOT.exists()


@pytest.mark.asyncio
async def test_candidate_07_requires_separate_authorization_before_key_or_outbound(tmp_path: Path) -> None:
    with pytest.raises(LiveEvaluationBootstrapError, match="evaluation.live_authorization_missing"):
        await build_live_from_environment(
            environ={
                "P5_KNOWLEDGE_MODE": "live",
                "P5_KNOWLEDGE_LIVE_OPT_IN": "I_UNDERSTAND_LIVE_EXTERNAL_CALLS",
                "P5_KNOWLEDGE_USER_JWT": "synthetic-not-persisted",
                "P5_KNOWLEDGE_AUTH_EVIDENCE_REF": "WP-KRET-REAL-01:authorizationMatrix.admin",
                "P5_KNOWLEDGE_CANDIDATE": "candidate-07",
            },
            repository_root=REPOSITORY_ROOT,
            output_dir=tmp_path / RUN_ID,
        )


@pytest.mark.asyncio
async def test_candidate_07_fake_budget_pairs_52_executions_and_consumes_once(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-07"))
    output_dir = tmp_path / RUN_ID
    delegate = FakeTransport(output_dir=output_dir)
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=output_dir,
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="a" * 40,
    )
    diagnostics = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)

    for ordinal in range(26):
        case_id = f"case-{ordinal:02d}"
        await _run_fake_variant(case_id=case_id, variant="primary", transport=transport, diagnostics=diagnostics)
        await _run_fake_variant(
            case_id=case_id,
            variant="rewrite_ablation",
            transport=transport,
            diagnostics=diagnostics,
        )

    paid_events = [json.loads(line) for line in (output_dir / "paid-attempts.jsonl").read_text().splitlines()]
    phase_events = [json.loads(line) for line in diagnostics.path.read_text(encoding="ascii").splitlines()]
    assert delegate.first_call_saw_consumed is True
    assert delegate.calls == transport.total_calls == 78
    assert transport.rewrite_calls == 26
    assert transport.summary_calls == 52
    assert len(paid_events) == 156
    assert len(phase_events) == 572
    assert [item["sequence"] for item in phase_events] == list(range(1, 573))
    assert all(set(item) <= SAFE_PHASE_KEYS for item in phase_events)
    assert all(item.get("status") in {None, "completed"} for item in phase_events)


@pytest.mark.asyncio
async def test_candidate_07_failure_is_terminal_without_retry_or_resume(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-07"))
    output_dir = tmp_path / RUN_ID
    delegate = FakeTransport(output_dir=output_dir, fail=True)
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=output_dir,
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="b" * 40,
    )
    diagnostics = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)

    with pytest.raises(RuntimeError, match="synthetic.transport_failure"):
        await _run_fake_variant(
            case_id="case-failure",
            variant="primary",
            transport=transport,
            diagnostics=diagnostics,
        )

    paid_events = [json.loads(line) for line in (output_dir / "paid-attempts.jsonl").read_text().splitlines()]
    assert delegate.first_call_saw_consumed is True
    assert transport.total_calls == delegate.calls == 1
    assert [item["event"] for item in paid_events] == ["started", "terminal"]
    assert paid_events[-1]["status"] == "failed"


def test_candidate_07_prepared_assets_contain_no_secret_or_live_result() -> None:
    raw = manifest_path(REPOSITORY_ROOT, "candidate-07").read_text(encoding="utf-8") + AUTHORIZATION_TEMPLATE.read_text(
        encoding="utf-8"
    )
    assert "LLM_API_KEY" not in raw
    assert "Bearer " not in raw
    assert not AUTHORIZATION_PATH.exists()
    assert not RESULT_ROOT.exists()
