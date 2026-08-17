from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.adapters.employee.egress_candidate_v4 import (
    AUTHORIZATION_REFERENCE,
    EXPECTED_PASSED_RECORDS,
    MAXIMUM_PAID_ANSWER_CALLS,
    RUN_ID,
    EmployeeEgressCandidateV4Error,
    execute_fake_candidate,
    load_strict_json,
    validate_consumed_marker,
    validate_lifecycle,
    validate_pending,
    validate_result,
    write_fallback_pending,
)


MANIFEST_SHA256 = "a" * 64


def _path(directory: Path, suffix: str) -> Path:
    return directory / f"{RUN_ID}.{suffix}"


def test_fake_candidate_passes_with_exact_cross_language_budgets(tmp_path: Path) -> None:
    result = execute_fake_candidate(tmp_path, manifest_sha256=MANIFEST_SHA256)

    assert result["status"] == "passed"
    assert result["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert result["counts"] == {
        "databaseSelectStarted": 3,
        "databaseSelectTerminal": 3,
        "databaseInsertStarted": 1,
        "databaseInsertTerminal": 1,
        "databaseDeleteStarted": 1,
        "databaseDeleteTerminal": 1,
        "employeeDetailStarted": 1,
        "employeeDetailTerminal": 1,
        "modelAnswerStarted": 30,
        "modelAnswerTerminal": 30,
        "validAnswers": 30,
        "retryCount": 0,
        "resumeCount": 0,
        "otherEndpointCalls": 0,
        "preexisting": 0,
        "inserted": 1,
        "verified": 1,
    }
    assert result["cleanup"] == {"deleted": 1, "remaining": 0}
    assert result["lifecycle"]["recordCount"] == EXPECTED_PASSED_RECORDS
    snapshot = validate_lifecycle(
        _path(tmp_path, "lifecycle.jsonl"),
        consumed_path=_path(tmp_path, "authorization.consumed.json"),
        manifest_sha256=MANIFEST_SHA256,
    )
    assert snapshot.record_count == EXPECTED_PASSED_RECORDS
    assert snapshot.valid_answers == MAXIMUM_PAID_ANSWER_CALLS
    validate_pending(
        load_strict_json(_path(tmp_path, "pending.json")),
        manifest_sha256=MANIFEST_SHA256,
    )
    validate_consumed_marker(
        load_strict_json(_path(tmp_path, "authorization.consumed.json")),
        manifest_sha256=MANIFEST_SHA256,
    )
    validate_result(load_strict_json(_path(tmp_path, "result.json")))


@pytest.mark.parametrize(
    ("fault", "status", "consumed"),
    [
        ("fixture_precheck", "failed_unconsumed", False),
        ("fixture_insert", "failed_unconsumed", False),
        ("fixture_verify", "failed_unconsumed", False),
        ("employee_detail", "failed_unconsumed", False),
        ("model_setup", "failed_unconsumed", False),
        ("forbidden_payload", "failed_unconsumed", False),
        ("model_answer", "failed_consumed", True),
        ("threshold", "failed_consumed", True),
        ("cleanup_delete", "failed_cleanup_required", True),
        ("cleanup_verify", "failed_cleanup_required", True),
        ("host_validation", "failed_consumed", True),
    ],
)
def test_faults_fail_closed_and_never_retry_or_resume(
    tmp_path: Path, fault: str, status: str, consumed: bool
) -> None:
    result = execute_fake_candidate(
        tmp_path,
        manifest_sha256=MANIFEST_SHA256,
        fault=fault,  # type: ignore[arg-type]
    )

    assert result["status"] == status
    assert result["authorizationConsumed"] is consumed
    assert result["counts"]["retryCount"] == 0
    assert result["counts"]["resumeCount"] == 0
    assert result["counts"]["databaseInsertStarted"] <= 1
    assert result["counts"]["databaseDeleteStarted"] <= 1
    assert result["counts"]["employeeDetailStarted"] <= 1
    assert result["counts"]["modelAnswerStarted"] <= 30
    if fault == "forbidden_payload":
        assert result["safety"]["forbiddenPayloadFieldCount"] == 1


def test_result_cannot_infer_cleanup_success_from_lifecycle_only(tmp_path: Path) -> None:
    execute_fake_candidate(tmp_path, manifest_sha256=MANIFEST_SHA256)
    result_path = _path(tmp_path, "result.json")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["cleanup"]["remaining"] = 1

    with pytest.raises(EmployeeEgressCandidateV4Error, match="invalid"):
        validate_result(result)


def test_outputs_are_exclusive_and_a_run_cannot_resume(tmp_path: Path) -> None:
    execute_fake_candidate(tmp_path, manifest_sha256=MANIFEST_SHA256)
    with pytest.raises(EmployeeEgressCandidateV4Error, match="invalid"):
        execute_fake_candidate(tmp_path, manifest_sha256=MANIFEST_SHA256)


def test_pre_context_failure_gets_finite_unconsumed_evidence(tmp_path: Path) -> None:
    from tests.integration.adapters.employee.egress_candidate_v4 import (
        LifecycleJournal,
        finalize_candidate,
    )

    lifecycle = _path(tmp_path, "lifecycle.jsonl")
    pending = _path(tmp_path, "pending.json")
    result = _path(tmp_path, "result.json")
    LifecycleJournal(lifecycle, manifest_sha256=MANIFEST_SHA256)
    write_fallback_pending(
        lifecycle_path=lifecycle,
        pending_path=pending,
        manifest_sha256=MANIFEST_SHA256,
    )
    value = finalize_candidate(
        lifecycle_path=lifecycle,
        consumed_path=_path(tmp_path, "authorization.consumed.json"),
        pending_path=pending,
        result_path=result,
        manifest_sha256=MANIFEST_SHA256,
        failure_phase="host_validation",
        failure_reason="host_failed",
        host_exit_code=1,
    )
    assert value["status"] == "failed_unconsumed"
    assert value["counts"]["databaseSelectStarted"] == 0
    assert value["counts"]["modelAnswerStarted"] == 0

