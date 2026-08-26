from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from tests.evaluation.knowledge.live_bootstrap import authorization_path, manifest_path
from tests.evaluation.knowledge.live_contracts import load_authorization, load_manifest
from tests.evaluation.knowledge.run_evaluation import validate_result_bytes


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v2-20260826-candidate-05"
FROZEN_HEAD = "63bc30baa68948a35840b650c0deb39d1e312efa"
MANIFEST_SHA256 = "41997c6d41f3109b178844c9b74799bb59c869ae06ec23aca66bea1a6f1e278c"
AUTHORIZATION_REFERENCE = "P3_00:GATE-072"
RESULT_ROOT = Path("agent-runtime/tests/evaluation/knowledge/results") / RUN_ID
EXPECTED_HASHES = {
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v2-20260826-candidate-05.authorization.json": "186815c07475ab35489f40e32ac4c9714574354bb2c7bda8a4f080065b91c1d5",
    (RESULT_ROOT / "authorization.consumed.json").as_posix(): "29181761560afd6ecece5740fc774205a42e3e557e183a1e86fed9cc0417a821",
    (RESULT_ROOT / "paid-attempts.jsonl").as_posix(): "f37e7926cf1c0e068251d8819d4cfcd3d195b739ec23c3d1658e5be626e6042b",
    (RESULT_ROOT / "phase-checkpoints.jsonl").as_posix(): "c6e95ed58c9f974f0a83287ab80b4ba57133d58dd6078d79e18c3a1f6bc7e062",
    (RESULT_ROOT / "result.json").as_posix(): "a6de81fe960c80aecae6d198d1de8b99eb13b14d69128541418dab2849af36eb",
    (RESULT_ROOT / "evidence.json").as_posix(): "75391778b123ac96f5f4889d9fffec6306d118e6d4347121995227d84f6d42df",
    (RESULT_ROOT / "launcher-evidence.json").as_posix(): "8defbd1f85374d3afe5a08de0158662fa79e02a133f497583dd88eca69899888",
}
EXPECTED_RESULT_FILES = {
    "authorization.consumed.json",
    "paid-attempts.jsonl",
    "phase-checkpoints.jsonl",
    "result.json",
    "evidence.json",
    "launcher-evidence.json",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _json_lines(path: Path) -> list[dict[str, object]]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert all(isinstance(value, dict) for value in values)
    return values


def test_candidate_05_completed_assets_are_append_only_and_bound() -> None:
    for relative, expected in EXPECTED_HASHES.items():
        assert _sha256(REPOSITORY_ROOT / relative) == expected

    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-05"))
    authorization = load_authorization(authorization_path(REPOSITORY_ROOT, "candidate-05"))
    result_root = REPOSITORY_ROOT / RESULT_ROOT
    consumed = _json(result_root / "authorization.consumed.json")
    evidence = _json(result_root / "evidence.json")
    launcher = _json(result_root / "launcher-evidence.json")
    result = validate_result_bytes((result_root / "result.json").read_bytes())

    assert {item.name for item in result_root.iterdir()} == EXPECTED_RESULT_FILES
    assert digest == MANIFEST_SHA256
    assert manifest.status == "prepared_unconsumed"
    assert authorization.status == "authorized_unconsumed"
    assert manifest.run_id == authorization.run_id == result.run_id == RUN_ID
    assert manifest.authorization_reference == authorization.authorization_reference == AUTHORIZATION_REFERENCE
    assert consumed == {
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "frozenGitCommit": FROZEN_HEAD,
        "manifestSha256": MANIFEST_SHA256,
        "maximumPaidRequests": 78,
        "retryAllowed": False,
        "runId": RUN_ID,
        "schemaVersion": 1,
        "status": "consumed",
        "workPackageId": "WP-K-EFFECT-LIVE-05",
    }
    assert result.git_commit == FROZEN_HEAD
    assert result.worktree_dirty is False
    assert result.provider_mode == "live"
    assert len(result.case_results) == 26
    assert all(item.primary.variant == "primary" for item in result.case_results)
    assert all(item.rewrite_ablation.variant == "rewrite_ablation" for item in result.case_results)
    assert all(item.primary.model_call_counts.core_answer == 0 for item in result.case_results)
    assert all(item.rewrite_ablation.model_call_counts.core_answer == 0 for item in result.case_results)
    assert result.safety_gate.denied_summary_call_count == 0
    assert result.safety_gate.unauthorized_content_count == 0
    assert result.safety_gate.citation_validity_rate == 1.0
    assert result.safety_gate.constraint_preservation_rate == 1.0
    assert result.safety_gate.passed is True
    assert result.reviewer == "codex-assisted-manual-v2"
    assert result.aggregate_metrics.q1 is True
    assert result.aggregate_metrics.q2 is True
    assert result.aggregate_metrics.q3 is False
    assert result.aggregate_metrics.q4 is False
    assert result.conclusion == "partially_effective"

    assert evidence["workPackageId"] == "WP-KP5-LIVE-01"
    assert evidence["conclusion"] == "partially_effective"
    assert evidence["capabilityExecutions"] == 52
    assert evidence["paidRequests"] == {
        "coreAnswer": 0,
        "knowledgeRewrite": 22,
        "knowledgeSummary": 22,
        "maximum": 78,
        "retry": 0,
        "total": 44,
    }
    assert evidence["journalStarted"] == evidence["journalTerminal"] == 44
    assert evidence["resultSha256"] == EXPECTED_HASHES[(RESULT_ROOT / "result.json").as_posix()]
    assert evidence["schemaValidated"] is True
    assert evidence["humanRubricCompleted"] is True
    assert evidence["jwtPersisted"] is False
    assert evidence["apiKeyPersisted"] is False

    assert launcher["status"] == "completed"
    assert launcher["workPackageId"] == "WP-K-EFFECT-LIVE-05"
    assert launcher["frozenGitCommit"] == FROZEN_HEAD
    assert launcher["runnerExitCode"] == 0
    assert launcher["logLeakCount"] == 0
    assert launcher["rawLogsRetained"] is False
    assert launcher["resultSha256"] == EXPECTED_HASHES[(RESULT_ROOT / "result.json").as_posix()]
    assert launcher["evidenceSha256"] == EXPECTED_HASHES[(RESULT_ROOT / "evidence.json").as_posix()]
    assert launcher["failureSha256"] is None


def test_candidate_05_paid_and_phase_journals_are_complete_without_retry() -> None:
    result_root = REPOSITORY_ROOT / RESULT_ROOT
    paid = _json_lines(result_root / "paid-attempts.jsonl")
    phases = _json_lines(result_root / "phase-checkpoints.jsonl")
    started = [item for item in paid if item["event"] == "started"]
    terminal = [item for item in paid if item["event"] == "terminal"]

    assert len(paid) == 88
    assert len(started) == len(terminal) == 44
    assert [item["callOrdinal"] for item in started] == list(range(1, 45))
    assert [item["callOrdinal"] for item in terminal] == list(range(1, 45))
    assert all(item["runId"] == RUN_ID for item in paid)
    assert all(item.get("status") == "completed" for item in terminal)
    assert all("retry" not in item for item in paid)
    assert sum(item["taskId"] == "knowledge_rewrite" for item in started) == 22
    assert sum(item["taskId"] == "knowledge_summary" for item in started) == 22
    assert len({(item["caseId"], item["variant"], item["taskId"]) for item in started}) == 44

    assert len(phases) == 592
    assert [item["sequence"] for item in phases] == list(range(1, 593))
    assert all(item["runId"] == RUN_ID for item in phases)
    assert all("reason" not in item for item in phases)
    operations: dict[tuple[object, object, object], list[dict[str, object]]] = defaultdict(list)
    for item in phases:
        operations[(item["caseId"], item["variant"], item["phase"])].append(item)
    assert len(operations) == 296
    assert all([item["event"] for item in events] == ["started", "terminal"] for events in operations.values())
    assert all(events[-1].get("status") == "completed" for events in operations.values())


def test_candidate_05_history_and_future_evidence_binding_are_explicit() -> None:
    historical_result = (
        REPOSITORY_ROOT
        / "agent-runtime/tests/evaluation/knowledge/results/knowledge-p5-live-v1-20260813-candidate-04/result.json"
    )
    assert _sha256(historical_result) == "8be86ed49d8560265ab87fbf7441d45d382b2dc40c3e099eb105f55c1507e1c3"

    runner_source = (
        REPOSITORY_ROOT / "agent-runtime/tests/evaluation/knowledge/live_runner.py"
    ).read_text(encoding="utf-8")
    assert '"workPackageId": bootstrap.manifest.work_package_id' in runner_source

    forbidden = (
        "LLM_API_KEY",
        "Bearer ",
        "SYNTHETIC_INVALID_SECRET_001",
        "SYNTHETIC_INVALID_ID_002",
        "SYNTHETIC_INVALID_JWT_003",
        "SYNTHETIC_INVALID_PHONE_004",
    )
    for relative in EXPECTED_HASHES:
        if relative.endswith(".json") or relative.endswith(".jsonl"):
            raw = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
            assert not any(value in raw for value in forbidden)
