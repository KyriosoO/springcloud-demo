from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from tests.evaluation.knowledge.live_bootstrap import authorization_path, manifest_path
from tests.evaluation.knowledge.live_contracts import load_authorization, load_manifest
from tests.evaluation.knowledge.run_evaluation import validate_result_bytes


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v1-20260813-candidate-04"
FROZEN_HEAD = "6108b2ac6718f0b8161f77ced1ef06bf0c994b18"
MANIFEST_SHA256 = "8d1976508830024cbdec1a98adb0b5254afe51a33f933ceccf45a2d192a0b4b2"
AUTHORIZATION_REFERENCE = "P3_00:GATE-047"
RESULT_ROOT = Path("agent-runtime/tests/evaluation/knowledge/results") / RUN_ID
MANIFEST_RELATIVE = Path(
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v1-20260813-candidate-04.manifest.json"
)
AUTHORIZATION_RELATIVE = Path(
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v1-20260813-candidate-04.authorization.json"
)
EXPECTED_HASHES = {
    MANIFEST_RELATIVE.as_posix(): MANIFEST_SHA256,
    AUTHORIZATION_RELATIVE.as_posix(): "2e19e1cbca2e1c8530d3530ae9c2e02d7bc3f27c65e03b617614cb520fafea70",
    (RESULT_ROOT / "authorization.consumed.json").as_posix(): (
        "96685b9eb8cd554d45ee8f0511f3ec582192063d816aa6ce64d9ecb9bfbc6651"
    ),
    (RESULT_ROOT / "paid-attempts.jsonl").as_posix(): (
        "9d83b2970903d97a085ecee9ba8fd6eb2f50987528d8d1a25fbdcd05b3f8d855"
    ),
    (RESULT_ROOT / "phase-checkpoints.jsonl").as_posix(): (
        "bd8e9babb8fe44bfd4d1aacef3aab745a1dcccd82f469824908f9b17adac71c2"
    ),
    (RESULT_ROOT / "result.json").as_posix(): "8be86ed49d8560265ab87fbf7441d45d382b2dc40c3e099eb105f55c1507e1c3",
    (RESULT_ROOT / "evidence.json").as_posix(): "03932c85d6a9da835aaf6e699af27a1006f025a14c4abec18df48b5bda446cf7",
    (RESULT_ROOT / "launcher-evidence.json").as_posix(): (
        "afe1a86b7a88649628b0aa43b81cff1006841e5353cf0fe9be70b2ded5c0b837"
    ),
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


def test_candidate_04_completed_assets_are_append_only_and_bound() -> None:
    for relative, expected in EXPECTED_HASHES.items():
        assert _sha256(REPOSITORY_ROOT / relative) == expected

    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT, "candidate-04"))
    authorization = load_authorization(authorization_path(REPOSITORY_ROOT, "candidate-04"))
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
        "workPackageId": "WP-KP5-LIVE-01",
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
    assert result.reviewer == "codex-assisted-manual-v1"
    assert len([item.primary_judgment for item in result.case_results]) == 26
    assert result.aggregate_metrics.q1 is False
    assert result.aggregate_metrics.q2 is True
    assert result.aggregate_metrics.q3 is False
    assert result.aggregate_metrics.q4 is False
    assert result.conclusion == "ineffective"

    assert evidence == {
        "apiKeyPersisted": False,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "capabilityExecutions": 52,
        "conclusion": "ineffective",
        "frozenGitCommit": FROZEN_HEAD,
        "humanRubricCompleted": True,
        "journalStarted": 58,
        "journalTerminal": 58,
        "jwtPersisted": False,
        "manifestSha256": MANIFEST_SHA256,
        "paidRequests": {
            "coreAnswer": 0,
            "knowledgeRewrite": 22,
            "knowledgeSummary": 36,
            "maximum": 78,
            "retry": 0,
            "total": 58,
        },
        "questionOrEvidencePersistedOutsideDatasetAndResult": False,
        "resultSha256": EXPECTED_HASHES[(RESULT_ROOT / "result.json").as_posix()],
        "runId": RUN_ID,
        "schemaValidated": True,
        "schemaVersion": 1,
        "status": "completed",
        "workPackageId": "WP-KP5-LIVE-01",
    }
    assert launcher == {
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "authService": "isolated-local",
        "embedding": "BGE-M3",
        "evidenceSha256": EXPECTED_HASHES[(RESULT_ROOT / "evidence.json").as_posix()],
        "knowledgeProvider": "isolated-local",
        "logLeakCount": 0,
        "manifestSha256": MANIFEST_SHA256,
        "maximumPaidRequests": 78,
        "rawLogsRetained": False,
        "rerank": "BAAI/bge-reranker-v2-m3",
        "resultSha256": EXPECTED_HASHES[(RESULT_ROOT / "result.json").as_posix()],
        "runId": RUN_ID,
        "schemaVersion": 1,
        "status": "passed",
        "workPackageId": "WP-KP5-LIVE-01",
    }


def test_candidate_04_paid_and_phase_journals_are_complete_without_retry() -> None:
    result_root = REPOSITORY_ROOT / RESULT_ROOT
    paid = _json_lines(result_root / "paid-attempts.jsonl")
    phases = _json_lines(result_root / "phase-checkpoints.jsonl")
    started = [item for item in paid if item["event"] == "started"]
    terminal = [item for item in paid if item["event"] == "terminal"]

    assert len(paid) == 116
    assert len(started) == len(terminal) == 58
    assert [item["callOrdinal"] for item in started] == list(range(1, 59))
    assert [item["callOrdinal"] for item in terminal] == list(range(1, 59))
    assert all(item["runId"] == RUN_ID for item in paid)
    assert all(item.get("status") == "completed" for item in terminal)
    assert all("retry" not in item for item in paid)
    assert sum(item["taskId"] == "knowledge_rewrite" for item in started) == 22
    assert sum(item["taskId"] == "knowledge_summary" for item in started) == 36
    assert len({(item["caseId"], item["variant"], item["taskId"]) for item in started}) == 58

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
