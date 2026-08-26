from __future__ import annotations

import hashlib
import json
import subprocess
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
    authorization_path,
    build_live_from_environment,
    manifest_path,
)
from tests.evaluation.knowledge.live_contracts import (
    BudgetedLiveModelTransport,
    load_authorization,
    load_authorization_template,
    load_manifest,
)
from tests.evaluation.knowledge.live_diagnostics import LiveDiagnosticPhase, LivePhaseCheckpointJournal
from tests.evaluation.knowledge.run_evaluation import load_dataset
from tests.evaluation.knowledge.test_live_p5_candidate_03_preparation import SAFE_PHASE_KEYS


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v2-20260826-candidate-05"
FROZEN_HEAD = "63bc30baa68948a35840b650c0deb39d1e312efa"
AUTHORIZATION_REFERENCE = "P3_00:GATE-072"
DATASET = Path(__file__).with_name("representative_questions.v2.jsonl")
DATASET_SHA256 = "1ea7417d80686545bd96d0f88f27b5b57de3de2ae6d6cb60c272190193645408"
AUTHORIZATION_TEMPLATE = REPOSITORY_ROOT / (
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v2-20260826-candidate-05.authorization-template.json"
)
RESULT_ROOT = REPOSITORY_ROOT / "agent-runtime/tests/evaluation/knowledge/results" / RUN_ID
HISTORY_HASHES = {
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-01.authorization.json": "c599996d71bc62c756a51e711b7509882643723798c33ff9d851c8b1ee1dfc3c",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-01.manifest.json": "b57af536909af4b6ec9a3c02b4332b91db4f48f4b23e2c33e4a1570100de7084",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-02.authorization.json": "d1faad700c6933c19fff6162768e890834da6caf29f9f4fceed054b8090f6988",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-02.manifest.json": "9fba41444d6bf55d8d54900d188317de796688849ce256b95756df688b245471",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-03.authorization.json": "cc0d2efb360b30148fe81fdcc3be58918f5f67ee890696a63342ebab73d4bca3",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-03.manifest.json": "5c83082828596f567c46a2047ac57b35f3aac44f5389d9846f2d63109d551988",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-04.authorization.json": "2e19e1cbca2e1c8530d3530ae9c2e02d7bc3f27c65e03b617614cb520fafea70",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-04.manifest.json": "8d1976508830024cbdec1a98adb0b5254afe51a33f933ceccf45a2d192a0b4b2",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-01/authorization.consumed.json": "1f767a5887854b32255134d0f0166aa106c2be4f576b59fac396cdf74eb0349e",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-01/failure.json": "1162eeddee526006168653c90c7fcd59eda69d6163952a6d289b2433fe4fb3b7",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-01/paid-attempts.jsonl": "94846c956d867feb42c098f6881db28dd1966643ec9335d22ee300ea21433a15",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-02/authorization.consumed.json": "dc729185ebc77eed16c7b0ca493d5d4dd7017a12d4e82998a909b9dae9c39e3d",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-02/failure.json": "08f4de1203a5fb419eb8e4b032669125da4afdb26aa693c264d87e045e8750fd",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-02/paid-attempts.jsonl": "081d881a57ae38e07a7d61f78e80aa515362745b1f845fcf0b5719791eb0b2f6",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-03/authorization.consumed.json": "c1fe1dcc0abce62620e1eca27103654fa5ffd1605632c57d8de8f15626e92cfe",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-03/failure.json": "6881cf6194dac87df5b6f9cf5d9c31ffb434f02b8d734506adcbdf5901e27188",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-03/paid-attempts.jsonl": "779e6b318e46a84fdf1ca0b93933190bac1e4e6e542c75f6b3f78bb28dccad75",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-03/phase-checkpoints.jsonl": "917a8ed73ba43c3d7bef50c8ff88a803c7b6b077af9da98a1e6d9977aae4393f",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/authorization.consumed.json": "96685b9eb8cd554d45ee8f0511f3ec582192063d816aa6ce64d9ecb9bfbc6651",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/evidence.json": "03932c85d6a9da835aaf6e699af27a1006f025a14c4abec18df48b5bda446cf7",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/launcher-evidence.json": "afe1a86b7a88649628b0aa43b81cff1006841e5353cf0fe9be70b2ded5c0b837",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/paid-attempts.jsonl": "9d83b2970903d97a085ecee9ba8fd6eb2f50987528d8d1a25fbdcd05b3f8d855",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/phase-checkpoints.jsonl": "bd8e9babb8fe44bfd4d1aacef3aab745a1dcccd82f469824908f9b17adac71c2",
    "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/result.json": "8be86ed49d8560265ab87fbf7441d45d382b2dc40c3e099eb105f55c1507e1c3",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(task_id: ModelTaskId, *, task_version: str | None = None) -> StructuredModelRequest:
    version = task_version or ("1" if task_id is ModelTaskId.KNOWLEDGE_REWRITE else "3")
    payload = '{"question":"synthetic"}' if task_id is ModelTaskId.KNOWLEDGE_REWRITE else '{"evidence":[]}'
    return StructuredModelRequest(
        task_id=task_id,
        task_version=version,
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


def test_candidate_05_manifest_template_history_and_frozen_assets_are_exact() -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-05"))
    authorization = load_authorization(authorization_path(REPOSITORY_ROOT, "candidate-05"))
    template = load_authorization_template(AUTHORIZATION_TEMPLATE)
    _, _, cases = load_dataset(DATASET)

    assert manifest.schema_version == 3
    assert manifest.work_package_id == "WP-K-EFFECT-LIVE-05"
    assert manifest.run_id == template.run_id == RUN_ID
    assert manifest.authorization_reference == template.authorization_reference == AUTHORIZATION_REFERENCE
    assert manifest.dataset_sha256 == template.dataset_sha256 == DATASET_SHA256 == _sha256(DATASET)
    assert manifest.dataset_case_count == len(cases) == 26
    assert manifest.configuration_binding is not None
    assert manifest.configuration_binding.domain_catalog_version == "tax-domain-catalog-v2"
    assert manifest.configuration_binding.flow_config_version == "knowledge-flow-config-v1"
    assert manifest.configuration_binding.retrieval_profile_version == "tax-knowledge-search-v1"
    assert manifest.configuration_binding.embedding_model == "BGE-M3"
    assert manifest.configuration_binding.rerank_model == "BAAI/bge-reranker-v2-m3"
    assert manifest.configuration_binding.policy_catalog_sha256 == (
        "442761355510165265cb2eee3be8ee8a310c38ab7796a998ff1863073dbbd698"
    )
    assert manifest.configuration_binding.evidence_rules_version == "knowledge-evidence-v1"
    assert manifest.configuration_binding.summary_prompt_sha256 == (
        "cf6318629fcc7e6156efa89e566e2083b84da94c2c783a041cf9f1338476ca22"
    )
    assert manifest.task_versions == {"knowledge_rewrite": "1", "knowledge_summary": "3"}
    assert manifest.paid_request_budget.maximum_paid_requests == template.maximum_paid_requests == 78
    assert manifest.paid_request_budget.retry == 0
    assert template.live_p5_authorized is False
    assert authorization.status == "authorized_unconsumed"
    assert authorization.live_p5_authorized is True
    assert authorization.run_id == manifest.run_id
    assert authorization.authorization_reference == manifest.authorization_reference
    assert authorization.maximum_paid_requests == manifest.paid_request_budget.maximum_paid_requests
    assert len(digest) == 64
    assert RESULT_ROOT.is_dir()

    manifest_hashes = {item.path: item.sha256 for item in manifest.asset_hashes}
    assert set(HISTORY_HASHES) <= set(manifest_hashes)
    assert {path: manifest_hashes[path] for path in HISTORY_HASHES} == HISTORY_HASHES
    assert all(_sha256(REPOSITORY_ROOT / path) == expected for path, expected in HISTORY_HASHES.items())
    for asset in manifest.asset_hashes:
        frozen = subprocess.run(
            ["git", "show", f"{FROZEN_HEAD}:{asset.path}"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset.sha256
    assert str(AUTHORIZATION_TEMPLATE.relative_to(REPOSITORY_ROOT)).replace("\\", "/") in manifest_hashes
    assert "agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v3.py" in manifest_hashes
    assert "agent-runtime/src/agent_runtime/knowledge/catalog.py" in manifest_hashes
    assert "agent-runtime/tests/evaluation/knowledge/representative_questions.v2.provenance.json" in manifest_hashes


@pytest.mark.asyncio
async def test_candidate_05_cannot_restart_after_authorization_was_consumed() -> None:
    with pytest.raises(LiveEvaluationBootstrapError, match="evaluation.output_exists"):
        await build_live_from_environment(
            environ={
                "P5_KNOWLEDGE_MODE": "live",
                "P5_KNOWLEDGE_LIVE_OPT_IN": "I_UNDERSTAND_LIVE_EXTERNAL_CALLS",
                "P5_KNOWLEDGE_USER_JWT": "synthetic-not-persisted",
                "P5_KNOWLEDGE_AUTH_EVIDENCE_REF": "WP-KRET-REAL-01:authorizationMatrix.admin",
                "P5_KNOWLEDGE_CANDIDATE": "candidate-05",
            },
            repository_root=REPOSITORY_ROOT,
            output_dir=RESULT_ROOT,
        )


@pytest.mark.asyncio
async def test_candidate_05_fake_budget_consumes_once_and_records_all_phases(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-05"))
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

    assert delegate.first_call_saw_consumed is True
    assert delegate.calls == transport.total_calls == 78
    assert transport.rewrite_calls == 26
    assert transport.summary_calls == 52
    paid_events = [json.loads(line) for line in (output_dir / "paid-attempts.jsonl").read_text().splitlines()]
    phase_events = [json.loads(line) for line in diagnostics.path.read_text(encoding="ascii").splitlines()]
    assert len(paid_events) == 156
    assert len(phase_events) == 572
    assert [item["sequence"] for item in phase_events] == list(range(1, 573))
    assert all(set(item) <= SAFE_PHASE_KEYS for item in phase_events)
    assert all(item.get("status") in {None, "completed"} for item in phase_events)


@pytest.mark.asyncio
async def test_candidate_05_failure_is_terminal_and_cannot_retry(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-05"))
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

    assert delegate.first_call_saw_consumed is True
    assert transport.total_calls == delegate.calls == 1
    assert json.loads((output_dir / "paid-attempts.jsonl").read_text().splitlines()[-1])["status"] == "failed"


@pytest.mark.asyncio
async def test_candidate_05_task_version_drift_fails_before_consumption(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-05"))
    output_dir = tmp_path / RUN_ID
    delegate = FakeTransport(output_dir=output_dir)
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=output_dir,
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="c" * 40,
    )
    transport.begin(case_id="version-drift", variant="primary")
    try:
        with pytest.raises(RuntimeError, match="evaluation.live_task_version_drift"):
            await transport.complete(
                _request(ModelTaskId.KNOWLEDGE_SUMMARY, task_version="2"),
                call_deadline=1.0,
            )
    finally:
        transport.end()

    assert delegate.calls == transport.total_calls == 0
    assert not output_dir.exists()
