from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.adapters.employee.employee_test_data_fixture import (
    EmployeeFixtureSpec,
    InMemoryEmployeeFixtureRepository,
)
from tests.integration.adapters.employee.employee_test_data_fixture_candidate import (
    AUTHORIZATION_REFERENCE,
    GATE_ID,
    MAX_DATABASE_DELETES,
    MAX_DATABASE_INSERTS,
    MAX_DATABASE_SELECTS,
    RUN_ID,
    FixtureCandidateError,
    FixtureCandidateExecution,
    execute_fake_candidate,
    finalize_staging_result,
    load_strict_json,
    sha256_file,
    validate_lifecycle,
    validate_manifest,
    validate_result,
    verify_source_history,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
METADATA_RESULT = EVIDENCE / (
    "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.result.json"
)
JAVA_CANDIDATE = REPOSITORY / (
    "employee-service/src/test/java/com/dylan/employee/live/"
    "EmployeeSyntheticFixtureCandidateLiveIntegrationTest.java"
)
LAUNCHER = Path(__file__).with_name("run_employee_test_data_fixture_candidate_01.ps1")


class FaultRepository(InMemoryEmployeeFixtureRepository):
    def __init__(self, *, fail_at: str) -> None:
        super().__init__()
        self._fail_at = fail_at
        self._verify_calls = 0

    def count_by_identifier(self, identifier: str) -> int:
        if self._fail_at == "precheck" and not self.calls:
            raise RuntimeError("sensitive failure")
        if self._fail_at == "cleanup_verify" and "delete_by_fingerprint" in self.calls:
            self.calls.append("count_by_identifier")
            return 1
        return super().count_by_identifier(identifier)

    def insert(self, fixture: EmployeeFixtureSpec) -> int:
        if self._fail_at == "insert":
            raise RuntimeError("sensitive failure")
        return super().insert(fixture)

    def count_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        self._verify_calls += 1
        if self._fail_at == "verify" and self._verify_calls == 1:
            self.calls.append("count_by_fingerprint")
            return 0
        return super().count_by_fingerprint(fixture)

    def delete_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        if self._fail_at == "delete":
            self.calls.append("delete_by_fingerprint")
            return 0
        return super().delete_by_fingerprint(fixture)


def _execute(
    tmp_path: Path,
    repository: InMemoryEmployeeFixtureRepository,
    **kwargs: bool,
) -> FixtureCandidateExecution:
    return execute_fake_candidate(
        repository=repository,
        metadata_result_path=METADATA_RESULT,
        lifecycle_path=tmp_path / "lifecycle.jsonl",
        result_path=tmp_path / "result.json",
        manifest_sha256="a" * 64,
        **kwargs,
    )


def test_source_history_is_exact() -> None:
    verify_source_history(REPOSITORY)


def test_fake_candidate_passes_with_exact_budget_and_cleanup(tmp_path: Path) -> None:
    execution = _execute(tmp_path, InMemoryEmployeeFixtureRepository())
    assert execution.status == "passed"
    result = validate_result(load_strict_json(tmp_path / "result.json"))
    assert result["counts"] == {
        "databaseSelectStarted": 3,
        "databaseSelectTerminal": 3,
        "databaseInsertStarted": 1,
        "databaseInsertTerminal": 1,
        "databaseDeleteStarted": 1,
        "databaseDeleteTerminal": 1,
        "preexisting": 0,
        "inserted": 1,
        "verified": 1,
        "deleted": 1,
        "remaining": 0,
        "consumerCalls": 1,
        "employeeEndpointCalls": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    records = validate_lifecycle(tmp_path / "lifecycle.jsonl", manifest_sha256="a" * 64)
    assert len(records) == 16
    assert records[-1]["state"] == "succeeded"
    persisted = (tmp_path / "lifecycle.jsonl").read_text() + (tmp_path / "result.json").read_text()
    for forbidden in (
        "synthetic-employee-",
        "Synthetic Employee",
        "Synthetic Position",
        "Synthetic Work Base",
    ):
        assert forbidden not in persisted


@pytest.mark.parametrize(
    ("fail_at", "expected_status", "expected_reason"),
    [
        ("precheck", "failed", "database_operation_failed"),
        ("insert", "failed_cleanup_required", "cleanup_count_invalid"),
        ("verify", "failed", "fingerprint_mismatch"),
        ("delete", "failed_cleanup_required", "cleanup_count_invalid"),
        (
            "cleanup_verify",
            "failed_cleanup_required",
            "cleanup_verification_failed",
        ),
    ],
)
def test_each_repository_failure_is_finite_and_never_retried(
    tmp_path: Path,
    fail_at: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    execution = _execute(tmp_path, FaultRepository(fail_at=fail_at))
    assert execution.status == expected_status
    assert execution.reason == expected_reason
    result = validate_result(load_strict_json(tmp_path / "result.json"))
    counts = result["counts"]
    assert counts["databaseSelectStarted"] <= MAX_DATABASE_SELECTS
    assert counts["databaseInsertStarted"] <= MAX_DATABASE_INSERTS
    assert counts["databaseDeleteStarted"] <= MAX_DATABASE_DELETES
    assert counts["retryCount"] == 0
    assert counts["resumeCount"] == 0


def test_consumer_failure_still_cleans_and_remains_finite(tmp_path: Path) -> None:
    execution = _execute(
        tmp_path,
        InMemoryEmployeeFixtureRepository(),
        fail_consumer=True,
    )
    assert execution.status == "failed"
    assert execution.reason == "consumer_failure"
    validate_result(load_strict_json(tmp_path / "result.json"))


def test_host_failure_is_appended_before_final_run_terminal(tmp_path: Path) -> None:
    _execute(tmp_path, InMemoryEmployeeFixtureRepository())
    lifecycle = tmp_path / "lifecycle.jsonl"
    records = lifecycle.read_text(encoding="utf-8").splitlines()
    lifecycle.write_text("\n".join(records[:-3]) + "\n", encoding="utf-8")
    staging = tmp_path / "staging.json"
    value = load_strict_json(tmp_path / "result.json")
    value["safety"]["rawLogsDeleted"] = False
    value["lifecycleSha256"] = sha256_file(lifecycle)
    staging.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")
    (tmp_path / "result.json").unlink()

    finalize_staging_result(
        staging,
        lifecycle,
        tmp_path / "result.json",
        log_leak_count=2,
        host_exit_code=0,
    )

    finalized = validate_result(load_strict_json(tmp_path / "result.json"))
    assert finalized["status"] == "failed"
    assert finalized["reason"] == "log_leak_detected"
    assert finalized["safety"]["logLeakCount"] == 2
    terminal = validate_lifecycle(lifecycle, manifest_sha256="a" * 64)
    assert [record["phase"] for record in terminal[-3:]] == [
        "host_validation",
        "host_validation",
        "run",
    ]


def test_lifecycle_and_result_are_exclusive(tmp_path: Path) -> None:
    repository = InMemoryEmployeeFixtureRepository()
    _execute(tmp_path, repository)
    with pytest.raises(FixtureCandidateError, match="employee.fixture_candidate_output_exists"):
        _execute(tmp_path, repository)


def test_result_validator_rejects_extra_fields_and_relaxed_safety(tmp_path: Path) -> None:
    _execute(tmp_path, InMemoryEmployeeFixtureRepository())
    value = load_strict_json(tmp_path / "result.json")
    value["employeeIdentifier"] = "forbidden"
    with pytest.raises(FixtureCandidateError):
        validate_result(value)
    value.pop("employeeIdentifier")
    value["safety"]["identifierPersisted"] = True
    with pytest.raises(FixtureCandidateError):
        validate_result(value)


def test_schemas_are_strict_and_zero_external() -> None:
    lifecycle = json.loads(
        (EVIDENCE / "employee-test-data-fixture-candidate-v1-lifecycle.schema.json").read_text()
    )
    result = json.loads(
        (EVIDENCE / "employee-test-data-fixture-candidate-v1-result.schema.json").read_text()
    )
    assert lifecycle["additionalProperties"] is False
    assert result["additionalProperties"] is False
    assert result["properties"]["counts"]["properties"]["employeeEndpointCalls"] == {
        "const": 0
    }
    assert result["properties"]["counts"]["properties"]["modelCalls"] == {"const": 0}


def test_java_candidate_uses_only_parameterized_exact_fixture_sql() -> None:
    source = JAVA_CANDIDATE.read_text(encoding="utf-8")
    assert source.count("jdbcTemplate.queryForObject(") == 3
    assert source.count("jdbcTemplate.update(") == 2
    for token in (
        "BINARY ID_CARD_NO = BINARY ?",
        "BINARY CHINESE_NAME = BINARY ?",
        "BINARY POSITION = BINARY ?",
        "BINARY WORK_BASE_SI = BINARY ?",
        "INSERT INTO employee (ID_CARD_NO, CHINESE_NAME, POSITION, WORK_BASE_SI)",
        "DELETE FROM employee",
        "StandardOpenOption.CREATE_NEW",
        "channel.force(true)",
        "failed_cleanup_required",
        "TransactionTemplate",
    ):
        assert token in source
    for forbidden in (
        "EmployeeService",
        "EmployeeMapper",
        "EmployeeChangeEvent",
        "UPDATE employee",
        "LLM_API_KEY",
        "Authorization",
        "@Transactional",
    ):
        assert forbidden not in source


def test_manifest_authorization_and_launcher_are_prepared_only() -> None:
    manifest_path = EVIDENCE / f"{RUN_ID}.manifest.json"
    authorization_path = EVIDENCE / f"{RUN_ID}.authorization.json"
    manifest = validate_manifest(manifest_path, authorization_path, REPOSITORY)
    authorization = load_strict_json(authorization_path)
    assert manifest["status"] == "prepared_unconsumed"
    assert authorization["liveExecutionAuthorized"] is False
    assert not (EVIDENCE / f"{RUN_ID}.lifecycle.jsonl").exists()
    assert not (EVIDENCE / f"{RUN_ID}.result.json").exists()

    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert RUN_ID in launcher
    assert AUTHORIZATION_REFERENCE in launcher
    assert GATE_ID in launcher
    assert launcher.index("employee.fixture_candidate_live_not_authorized") < launcher.index(
        "mvn -f"
    )
    assert "Remove-Item Env:\\LLM_API_KEY" in launcher
    assert "COMMON_SECURITY_JWT_HMAC_KEY" in launcher
    assert "employee-service" in launcher
    assert "DeepSeek" not in launcher


def test_manifest_hash_is_stable_and_authorization_bound() -> None:
    manifest_path = EVIDENCE / f"{RUN_ID}.manifest.json"
    authorization = load_strict_json(EVIDENCE / f"{RUN_ID}.authorization.json")
    assert authorization["manifestSha256"] == sha256_file(manifest_path)
