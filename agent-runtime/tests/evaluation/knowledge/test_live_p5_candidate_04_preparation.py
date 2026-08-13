from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from agent_runtime.model.contracts import StructuredModelRequest, StructuredModelResponse
from tests.evaluation.knowledge.live_bootstrap import (
    _CANDIDATE_BINDINGS,
    LiveEvaluationBootstrapError,
    _candidate_id,
    authorization_path,
    manifest_path,
)
from tests.evaluation.knowledge.live_contracts import (
    BudgetedLiveModelTransport,
    load_authorization,
    load_manifest,
)
from tests.evaluation.knowledge.live_diagnostics import LivePhaseCheckpointJournal
from tests.evaluation.knowledge.run_evaluation import load_dataset
from tests.evaluation.knowledge.test_live_p5_candidate_03_preparation import (
    SAFE_PHASE_KEYS,
    FakeTransport,
    _run_fake_variant,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v1-20260813-candidate-04"
FROZEN_HEAD = "6108b2ac6718f0b8161f77ced1ef06bf0c994b18"
AUTHORIZATION_REFERENCE = "P3_00:GATE-047"
DATASET = Path(__file__).with_name("representative_questions.v2.jsonl")
DATASET_SHA256 = "1ea7417d80686545bd96d0f88f27b5b57de3de2ae6d6cb60c272190193645408"
LAUNCHER = "agent-runtime/scripts/run-knowledge-p5-live-candidate-04.ps1"
HISTORY_HASHES = {
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-01.authorization.json": "c599996d71bc62c756a51e711b7509882643723798c33ff9d851c8b1ee1dfc3c",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-01.manifest.json": "b57af536909af4b6ec9a3c02b4332b91db4f48f4b23e2c33e4a1570100de7084",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-02.authorization.json": "d1faad700c6933c19fff6162768e890834da6caf29f9f4fceed054b8090f6988",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-02.manifest.json": "9fba41444d6bf55d8d54900d188317de796688849ce256b95756df688b245471",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-03.authorization.json": "cc0d2efb360b30148fe81fdcc3be58918f5f67ee890696a63342ebab73d4bca3",
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-03.manifest.json": "5c83082828596f567c46a2047ac57b35f3aac44f5389d9846f2d63109d551988",
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
}
MANDATORY_ASSETS = {
    LAUNCHER,
    "agent-runtime/src/agent_runtime/knowledge/capability.py",
    "agent-runtime/src/agent_runtime/knowledge/domain_selection.py",
    "agent-runtime/src/agent_runtime/model/input_guard.py",
    "agent-runtime/src/agent_runtime/model/question_policy.py",
    "agent-runtime/tests/evaluation/knowledge/live_bootstrap.py",
    "agent-runtime/tests/evaluation/knowledge/live_contracts.py",
    "agent-runtime/tests/evaluation/knowledge/live_diagnostics.py",
    "agent-runtime/tests/evaluation/knowledge/live_executor.py",
    "agent-runtime/tests/evaluation/knowledge/live_runner.py",
    "agent-runtime/tests/evaluation/knowledge/test_live_p5_candidate_04_preparation.py",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v2.authorization.json",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v2.provenance.json",
    "agent-runtime/tests/evaluation/knowledge/representative_questions.v2.sha256",
    *HISTORY_HASHES,
}


class FailingTransport:
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
        self.first_call_saw_consumed = (self.output_dir / "authorization.consumed.json").is_file()
        raise RuntimeError("synthetic.transport_failure")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_04_manifest_authorization_v2_and_history_scope_are_exact() -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-04"))
    authorization = load_authorization(authorization_path(REPOSITORY_ROOT, "candidate-04"))
    _, _, cases = load_dataset(DATASET)

    assert manifest.run_id == RUN_ID == authorization.run_id
    assert manifest.authorization_reference == AUTHORIZATION_REFERENCE == authorization.authorization_reference
    assert manifest.dataset_path.endswith("representative_questions.v2.jsonl")
    assert manifest.dataset_sha256 == DATASET_SHA256 == authorization.dataset_sha256 == _sha256(DATASET)
    assert len(cases) == manifest.dataset_case_count == 26
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
    manifest_hashes = {item.path: item.sha256 for item in manifest.asset_hashes}
    assert len(manifest.asset_hashes) == 73
    assert MANDATORY_ASSETS <= paths
    assert "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-04.manifest.json" not in paths
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

    assert manifest_path(REPOSITORY_ROOT).name.endswith("candidate-03.manifest.json")
    assert manifest_path(REPOSITORY_ROOT, "candidate-04").name.endswith("candidate-04.manifest.json")
    assert authorization_path(REPOSITORY_ROOT).name.endswith("candidate-03.authorization.json")
    assert _CANDIDATE_BINDINGS["candidate-03"].dataset_path.endswith("representative_questions.v1.jsonl")
    assert _CANDIDATE_BINDINGS["candidate-04"].run_id == RUN_ID
    assert _CANDIDATE_BINDINGS["candidate-04"].dataset_path.endswith("representative_questions.v2.jsonl")
    with pytest.raises(LiveEvaluationBootstrapError, match="live_candidate_invalid"):
        _candidate_id("../../candidate-04.manifest.json")

    launcher = (REPOSITORY_ROOT / LAUNCHER).read_text(encoding="utf-8")
    assert "candidate-04.manifest.json" in launcher
    assert "representative_questions.v2.jsonl" in launcher
    assert "$env:P5_KNOWLEDGE_CANDIDATE = 'candidate-04'" in launcher
    assert "test_live_p5_candidate_04_preparation.py" in launcher
    assert "candidate-03.manifest.json" not in launcher


@pytest.mark.asyncio
async def test_candidate_04_fake_run_consumes_once_and_records_all_finite_phases(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-04"))
    output_dir = tmp_path / RUN_ID
    delegate = FakeTransport(output_dir=output_dir)
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=output_dir,
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="d" * 40,
    )
    diagnostics = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)

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
    paid_events = [json.loads(line) for line in (output_dir / "paid-attempts.jsonl").read_text().splitlines()]
    phase_events = [json.loads(line) for line in diagnostics.path.read_text(encoding="ascii").splitlines()]
    assert len(paid_events) == 156
    assert len(phase_events) == 572
    assert [item["sequence"] for item in phase_events] == list(range(1, 573))
    assert all(set(item) <= SAFE_PHASE_KEYS for item in phase_events)
    assert all(item.get("status") in {None, "completed"} for item in phase_events)


@pytest.mark.asyncio
async def test_candidate_04_fake_failure_consumes_once_and_cannot_retry(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-04"))
    output_dir = tmp_path / RUN_ID
    delegate = FailingTransport(output_dir=output_dir)
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=output_dir,
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="e" * 40,
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
    assert delegate.calls == transport.total_calls == 1
    paid_events = [json.loads(line) for line in (output_dir / "paid-attempts.jsonl").read_text().splitlines()]
    phase_events = [json.loads(line) for line in diagnostics.path.read_text(encoding="ascii").splitlines()]
    assert len(paid_events) == 2
    assert paid_events[-1]["status"] == "failed"
    assert sum(item.get("status") == "failed" for item in phase_events) >= 1
    assert all(set(item) <= SAFE_PHASE_KEYS for item in phase_events)
