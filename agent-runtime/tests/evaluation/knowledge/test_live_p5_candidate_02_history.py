from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.evaluation.knowledge.contracts import EvaluationFailureRecord


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v1-20260813-candidate-02"
FROZEN_COMMIT = "adab16fcd39932c060bb8a33488741da18f81783"
MANIFEST_RELATIVE = Path(
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-02.manifest.json"
)
RESULT_ROOT = Path("agent-runtime/tests/evaluation/knowledge/results") / RUN_ID
EXPECTED_HASHES = {
    MANIFEST_RELATIVE.as_posix(): "9fba41444d6bf55d8d54900d188317de796688849ce256b95756df688b245471",
    (RESULT_ROOT / "authorization.consumed.json").as_posix(): "dc729185ebc77eed16c7b0ca493d5d4dd7017a12d4e82998a909b9dae9c39e3d",
    (RESULT_ROOT / "paid-attempts.jsonl").as_posix(): "081d881a57ae38e07a7d61f78e80aa515362745b1f845fcf0b5719791eb0b2f6",
    (RESULT_ROOT / "failure.json").as_posix(): "08f4de1203a5fb419eb8e4b032669125da4afdb26aa693c264d87e045e8750fd",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_02_consumed_failure_assets_are_append_only_and_bound() -> None:
    for relative, expected in EXPECTED_HASHES.items():
        assert _sha256(REPOSITORY_ROOT / relative) == expected

    manifest = json.loads((REPOSITORY_ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    result_root = REPOSITORY_ROOT / RESULT_ROOT
    consumed = json.loads((result_root / "authorization.consumed.json").read_text(encoding="utf-8"))
    failure = EvaluationFailureRecord.model_validate_json((result_root / "failure.json").read_bytes())

    assert manifest["status"] == "prepared_unconsumed"
    assert consumed == {
        "authorizationReference": "P3_00:GATE-044",
        "frozenGitCommit": FROZEN_COMMIT,
        "manifestSha256": EXPECTED_HASHES[MANIFEST_RELATIVE.as_posix()],
        "maximumPaidRequests": 78,
        "retryAllowed": False,
        "runId": RUN_ID,
        "schemaVersion": 1,
        "status": "consumed",
        "workPackageId": "WP-KP5-LIVE-01",
    }
    assert failure.run_id == RUN_ID
    assert failure.git_commit == FROZEN_COMMIT
    assert failure.failure_code == "execution_failed"
    assert not (result_root / "result.json").exists()
    assert not (result_root / "evidence.json").exists()


def test_candidate_02_journal_has_58_unique_completed_attempts_and_zero_retry() -> None:
    journal = [
        json.loads(line)
        for line in (REPOSITORY_ROOT / RESULT_ROOT / "paid-attempts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    started = [item for item in journal if item["event"] == "started"]
    terminal = [item for item in journal if item["event"] == "terminal"]
    attempt_keys = {(item["caseId"], item["variant"], item["taskId"]) for item in started}

    assert len(started) == len(terminal) == len(attempt_keys) == 58
    assert [item["callOrdinal"] for item in started] == list(range(1, 59))
    assert [item["callOrdinal"] for item in terminal] == list(range(1, 59))
    assert all(item["status"] == "completed" for item in terminal)
    assert sum(item["taskId"] == "knowledge_rewrite" for item in started) == 22
    assert sum(item["taskId"] == "knowledge_summary" for item in started) == 36
    assert sum(item["variant"] == "primary" for item in started) == 40
    assert sum(item["variant"] == "rewrite_ablation" for item in started) == 18
    assert started[-1]["caseId"] == "draft-insufficient-missing-transaction-type"
    assert started[-1]["variant"] == "primary"
    assert started[-1]["taskId"] == "knowledge_rewrite"
