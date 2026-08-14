from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_input_qualification_v2 import (
    RUN_ID,
    QualificationReason,
    QualificationRunStatus,
    load_strict_json,
    sha256_file,
    validate_lifecycle,
    validate_result,
)


_LIFECYCLE_SHA256 = (
    "570295951f8bf1a109156c017c30609ca548bfba3f021bff4cd2825f978ac231"
)
_RESULT_SHA256 = (
    "7534b1d04a1512720dcbee1fe630114fb1f08bf9c3615dec1d2cb18bec4d5054"
)


def test_candidate_02_consumed_history_is_exact_and_not_qualified() -> None:
    evidence = Path(__file__).parent / "evidence"
    manifest_path = evidence / f"{RUN_ID}.manifest.json"
    lifecycle_path = evidence / f"{RUN_ID}.lifecycle.jsonl"
    result_path = evidence / f"{RUN_ID}.result.json"
    manifest_sha256 = sha256_file(manifest_path)

    assert sha256_file(lifecycle_path) == _LIFECYCLE_SHA256
    assert sha256_file(result_path) == _RESULT_SHA256
    lifecycle = validate_lifecycle(lifecycle_path, manifest_sha256=manifest_sha256)
    assert lifecycle.run_status is QualificationRunStatus.NOT_QUALIFIED
    assert lifecycle.failure_reason is QualificationReason.NO_QUALIFIED_INPUT
    assert (
        lifecycle.database_selection_started,
        lifecycle.database_selection_terminal,
        lifecycle.database_selection_rows,
        lifecycle.employee_detail_started,
        lifecycle.employee_detail_terminal,
    ) == (1, 1, 0, 0, 0)

    result = load_strict_json(result_path)
    validate_result(result)
    assert result["status"] == QualificationRunStatus.NOT_QUALIFIED.value
    assert result["egressReason"] == QualificationReason.NO_QUALIFIED_INPUT.value
    assert result["counts"] == {
        "databaseSelectionStarted": 1,
        "databaseSelectionTerminal": 1,
        "databaseSelectionRows": 0,
        "employeeDetailStarted": 0,
        "employeeDetailTerminal": 0,
        "otherEmployeeEndpoints": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
