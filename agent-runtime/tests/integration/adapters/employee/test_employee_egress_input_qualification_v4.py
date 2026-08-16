from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.adapters.employee.employee_test_data_fixture import (
    EmployeeFixtureSpec,
    InMemoryEmployeeFixtureRepository,
)
from tests.integration.adapters.employee.egress_input_qualification_v4 import (
    ASSET_PATHS,
    CandidateExecution,
    MAX_DATABASE_DELETES,
    MAX_DATABASE_INSERTS,
    MAX_DATABASE_SELECTS,
    MAX_EMPLOYEE_DETAILS,
    QualificationOutcome,
    QualificationV4Error,
    execute_fake_candidate,
    finalize_live_candidate,
    validate_lifecycle,
    validate_result,
    verify_history,
    write_exclusive_json,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
METADATA = EVIDENCE / "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.result.json"
JAVA = REPOSITORY / "employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationV4LiveIntegrationTest.java"
LAUNCHER = REPOSITORY / "agent-runtime/scripts/run-employee-egress-input-qualification-candidate-04.ps1"


class FaultRepository(InMemoryEmployeeFixtureRepository):
    def __init__(self, fail_at: str) -> None:
        super().__init__()
        self.fail_at = fail_at
        self.fingerprint_calls = 0

    def count_by_identifier(self, identifier: str) -> int:
        if self.fail_at == "precheck" and not self.calls:
            raise RuntimeError("private database exception")
        if self.fail_at == "cleanup_verify" and "delete_by_fingerprint" in self.calls:
            self.calls.append("count_by_identifier")
            return 1
        return super().count_by_identifier(identifier)

    def insert(self, fixture: EmployeeFixtureSpec) -> int:
        if self.fail_at == "insert":
            raise RuntimeError("private database exception")
        return super().insert(fixture)

    def count_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        self.fingerprint_calls += 1
        if self.fail_at == "verify" and self.fingerprint_calls == 1:
            self.calls.append("count_by_fingerprint")
            return 0
        return super().count_by_fingerprint(fixture)

    def delete_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        if self.fail_at == "delete":
            self.calls.append("delete_by_fingerprint")
            return 0
        return super().delete_by_fingerprint(fixture)


def _execute(
    tmp_path: Path,
    repository: InMemoryEmployeeFixtureRepository,
    detail: object = None,
) -> CandidateExecution:
    callback = detail if callable(detail) else lambda _: QualificationOutcome.qualified()
    return execute_fake_candidate(
        repository=repository,
        metadata_result_path=METADATA,
        lifecycle_path=tmp_path / "lifecycle.jsonl",
        result_path=tmp_path / "result.json",
        manifest_sha256="a" * 64,
        detail=callback,
    )


def test_candidate_passes_with_one_lifecycle_exact_budget_and_cleanup(tmp_path: Path) -> None:
    execution = _execute(tmp_path, InMemoryEmployeeFixtureRepository())
    assert execution.status == "qualified"
    result = validate_result(execution.result)
    counts = result["counts"]
    assert counts["databaseSelectStarted"] == MAX_DATABASE_SELECTS
    assert counts["databaseInsertStarted"] == MAX_DATABASE_INSERTS
    assert counts["databaseDeleteStarted"] == MAX_DATABASE_DELETES
    assert counts["employeeDetailStarted"] == MAX_EMPLOYEE_DETAILS
    assert counts["inserted"] == counts["verified"] == counts["deleted"] == 1
    assert counts["remaining"] == 0
    assert len(validate_lifecycle(tmp_path / "lifecycle.jsonl", manifest_sha256="a" * 64)) == 16
    persisted = (tmp_path / "lifecycle.jsonl").read_text() + (tmp_path / "result.json").read_text()
    for forbidden in ("synthetic-employee-", "Synthetic Employee", "Synthetic Position", "Synthetic Work Base"):
        assert forbidden not in persisted


@pytest.mark.parametrize(
    ("fail_at", "status", "reason"),
    [
        ("precheck", "failed", "database_operation_failed"),
        ("insert", "failed_cleanup_required", "cleanup_count_invalid"),
        ("verify", "failed", "fingerprint_mismatch"),
        ("delete", "failed_cleanup_required", "cleanup_count_invalid"),
        ("cleanup_verify", "failed_cleanup_required", "cleanup_verification_failed"),
    ],
)
def test_repository_failures_are_finite_and_never_retried(
    tmp_path: Path, fail_at: str, status: str, reason: str
) -> None:
    execution = _execute(tmp_path, FaultRepository(fail_at))
    assert (execution.status, execution.reason) == (status, reason)
    assert execution.result["counts"]["retryCount"] == 0
    assert execution.result["counts"]["resumeCount"] == 0


def test_detail_failure_still_exactly_cleans(tmp_path: Path) -> None:
    def fail(_: EmployeeFixtureSpec) -> QualificationOutcome:
        raise RuntimeError("private downstream exception")

    result = _execute(tmp_path, InMemoryEmployeeFixtureRepository(), fail)
    assert (result.status, result.reason) == ("failed", "employee_request_failed")
    assert result.result["counts"]["deleted"] == 1
    assert result.result["counts"]["remaining"] == 0


def test_incomplete_result_is_not_qualified_and_model_is_zero(tmp_path: Path) -> None:
    outcome = QualificationOutcome(
        codec_fields={"idCardNo": True, "chineseName": True, "position": True, "workBaseSi": False},
        required_user_fields={"employeeIdMasked": True, "chineseName": True},
        egress_allowed=False,
    )
    result = _execute(tmp_path, InMemoryEmployeeFixtureRepository(), lambda _: outcome)
    assert (result.status, result.reason) == ("not_qualified", "employee_result_invalid")
    assert result.result["counts"]["modelCalls"] == 0


def test_result_rejects_success_count_and_reason_presence_drift(tmp_path: Path) -> None:
    qualified = _execute(tmp_path / "qualified", InMemoryEmployeeFixtureRepository())
    bad_counts = dict(qualified.result)
    bad_counts["counts"] = {**qualified.result["counts"], "databaseSelectStarted": 2}
    with pytest.raises(QualificationV4Error, match="invalid"):
        validate_result(bad_counts)

    outcome = QualificationOutcome(
        codec_fields={"idCardNo": True, "chineseName": True, "position": True, "workBaseSi": False},
        required_user_fields={"employeeIdMasked": True, "chineseName": True},
        egress_allowed=False,
    )
    not_qualified = _execute(
        tmp_path / "not-qualified",
        InMemoryEmployeeFixtureRepository(),
        lambda _: outcome,
    )
    bad_presence = dict(not_qualified.result)
    bad_presence["fieldPresence"] = {
        "codec": {"idCardNo": True, "chineseName": True, "position": True, "workBaseSi": True},
        "requiredUser": {"employeeIdMasked": True, "chineseName": True},
        "egressAllowed": True,
    }
    with pytest.raises(QualificationV4Error, match="invalid"):
        validate_result(bad_presence)


def test_outputs_are_exclusive(tmp_path: Path) -> None:
    repository = InMemoryEmployeeFixtureRepository()
    _execute(tmp_path, repository)
    with pytest.raises(QualificationV4Error, match="output_exists"):
        _execute(tmp_path, repository)


def test_host_finalizer_preserves_cleanup_and_fails_closed_on_log_leak(tmp_path: Path) -> None:
    execution = _execute(tmp_path, InMemoryEmployeeFixtureRepository())
    lifecycle = tmp_path / "lifecycle.jsonl"
    lines = lifecycle.read_text(encoding="utf-8").splitlines()
    lifecycle.write_text("\n".join(lines[:-3]) + "\n", encoding="utf-8")
    (tmp_path / "result.json").unlink()
    pending = tmp_path / "pending.json"
    write_exclusive_json(
        pending,
        {
            "schemaVersion": 4,
            "status": execution.status,
            "reason": execution.reason,
            "fieldPresence": execution.result["fieldPresence"],
            "counts": execution.result["counts"],
        },
    )
    result = finalize_live_candidate(
        lifecycle_path=lifecycle,
        pending_path=pending,
        result_path=tmp_path / "result.json",
        manifest_sha256="a" * 64,
        host_exit_code=0,
        log_leak_count=1,
    )
    assert (result["status"], result["reason"]) == ("failed", "log_leak_detected")
    assert result["counts"]["deleted"] == 1
    assert result["counts"]["remaining"] == 0


def test_history_schemas_and_static_live_seams_are_strict() -> None:
    verify_history(REPOSITORY)
    lifecycle_schema = json.loads(
        (EVIDENCE / "employee-egress-input-qualification-v4-lifecycle.schema.json").read_text()
    )
    result_schema = json.loads(
        (EVIDENCE / "employee-egress-input-qualification-v4-result.schema.json").read_text()
    )
    assert lifecycle_schema["additionalProperties"] is False
    assert result_schema["additionalProperties"] is False
    assert result_schema["properties"]["counts"]["properties"]["modelCalls"] == {"const": 0}
    source = JAVA.read_text(encoding="utf-8")
    for token in (
        "import com.dylan.employee.EmployeeServiceApplication;",
        "@SpringBootTest(classes = EmployeeServiceApplication.class",
        "BINARY ID_CARD_NO = BINARY ?",
        "BINARY CHINESE_NAME = BINARY ?",
        "BINARY POSITION = BINARY ?",
        "BINARY WORK_BASE_SI = BINARY ?",
        "TransactionTemplate",
        "finally",
        "Files.readAllLines(path, StandardCharsets.UTF_8).size() + 1",
        'counts.employeeDetailStarted == 1 && counts.employeeDetailTerminal == 0',
        'journal.record("employee_detail", "failed", "employee_request_failed")',
        "value.size() != 5",
        "EmployeeEgressInputQualificationV4LiveIntegrationTest",
    ):
        assert token in source
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V4" in launcher
    assert "Remove-Item Env:\\LLM_API_KEY" in launcher
    assert launcher.index("Remove-Item Env:\\LLM_API_KEY") < launcher.index("& $python -c")
    assert "GetEnvironmentVariable('LLM_API_KEY'" not in launcher
    assert "SetEnvironmentVariable('LLM_API_KEY'" not in launcher
    assert "-Dsurefire.failIfNoSpecifiedTests=false" in launcher
    assert "GATE-049" in launcher
    assert "create_host_lifecycle" in launcher
    assert launcher.index("create_host_lifecycle") < launcher.index("& mvn")
    assert "write_pre_sql_failure" in launcher
    assert len(ASSET_PATHS) == 11
