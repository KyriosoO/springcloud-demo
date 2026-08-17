from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_candidate_v3 import (
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_consumed_marker,
    validate_lifecycle,
    validate_result,
)


EVIDENCE = Path(__file__).parent / "evidence"
MANIFEST_SHA256 = "901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e"
EXPECTED_HASHES = {
    "manifest.json": MANIFEST_SHA256,
    "authorization.json": "a4dff9272a539f162fa0bd36fe88d3a1a3592c16294622cb6e9925f59896c4f8",
    "lifecycle.jsonl": "da23d55c4aada51fe47bdd68ec2ec40a2895997e3050b04b21dba27f70ab8ce8",
    "authorization.consumed.json": "e7def6942e153cea5787f503250c514e738f81cdea0a015ad47a948f782341a5",
    "result.json": "2ab7a22476ba4e0b5ddd54ef4749b04ca2653c0bb7f4a811f1e78af20bb256a2",
}


def test_candidate03_consumed_failure_evidence_is_byte_exact() -> None:
    for suffix, expected_hash in EXPECTED_HASHES.items():
        assert sha256_file(EVIDENCE / f"{RUN_ID}.{suffix}") == expected_hash


def test_candidate03_failed_consumed_with_complete_cleanup_and_no_retry() -> None:
    lifecycle_path = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
    consumed_path = EVIDENCE / f"{RUN_ID}.authorization.consumed.json"
    result = validate_result(load_strict_json(EVIDENCE / f"{RUN_ID}.result.json"))
    snapshot = validate_lifecycle(
        lifecycle_path,
        consumed_path=consumed_path,
        manifest_sha256=MANIFEST_SHA256,
    )
    consumed = validate_consumed_marker(
        load_strict_json(consumed_path), manifest_sha256=MANIFEST_SHA256
    )

    assert consumed["runId"] == RUN_ID
    assert snapshot.record_count == 76
    assert snapshot.status == "failed_consumed"
    assert snapshot.failure_phase == "threshold"
    assert snapshot.failure_reason == "threshold_not_met"
    assert snapshot.authorization_consumed is True
    assert snapshot.counts["modelAnswerStarted"] == 30
    assert snapshot.counts["modelAnswerTerminal"] == 30
    assert snapshot.valid_answers == 0

    assert result["status"] == "failed_consumed"
    assert result["failure"] == {"phase": "threshold", "reason": "threshold_not_met"}
    assert result["authorizationConsumed"] is True
    assert result["counts"]["databaseSelectStarted"] == 3
    assert result["counts"]["databaseInsertStarted"] == 1
    assert result["counts"]["databaseDeleteStarted"] == 1
    assert result["counts"]["employeeDetailStarted"] == 1
    assert result["counts"]["modelAnswerStarted"] == 30
    assert result["counts"]["modelAnswerTerminal"] == 30
    assert result["counts"]["validAnswers"] == 0
    assert result["counts"]["retryCount"] == 0
    assert result["counts"]["resumeCount"] == 0
    assert result["counts"]["otherEndpointCalls"] == 0
    assert result["cleanup"] == {"deleted": 1, "remaining": 0}
    assert result["safety"] == {
        "forbiddenPayloadFieldCount": 0,
        "forbiddenLiteralCount": 0,
        "logLeakCount": 0,
        "rawLogsDeleted": True,
    }
