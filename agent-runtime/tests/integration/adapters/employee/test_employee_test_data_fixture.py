from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.integration.adapters.employee.employee_test_data_fixture import (
    FIELD_NAMES,
    METADATA_RESULT_SHA256,
    EmployeeFixtureContractError,
    EmployeeFixtureExecution,
    EmployeeFixtureSpec,
    InMemoryEmployeeFixtureRepository,
    build_fixture_spec,
    execute_fixture_lifecycle,
    validate_evidence,
    validate_lifecycle,
    validate_metadata_result,
)


REPOSITORY = Path(__file__).parents[5]
METADATA_RESULT = (
    Path(__file__).parent
    / "evidence"
    / "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.result.json"
)
SCHEMA = Path(__file__).parent / "evidence" / "employee-test-data-fixture-v1.schema.json"


class FaultRepository(InMemoryEmployeeFixtureRepository):
    def __init__(self, *, fail_at: str | None = None, mutate_before_insert_failure: bool = False) -> None:
        super().__init__()
        self._fail_at = fail_at
        self._mutate_before_insert_failure = mutate_before_insert_failure
        self._verify_failed_once = False

    def count_by_identifier(self, identifier: str) -> int:
        if self._fail_at == "precheck":
            raise RuntimeError("sensitive repository detail")
        if self._fail_at == "cleanup_verify" and "delete_by_fingerprint" in self.calls:
            self.calls.append("count_by_identifier")
            return 1
        return super().count_by_identifier(identifier)

    def insert(self, fixture: EmployeeFixtureSpec) -> int:
        if self._fail_at == "insert":
            if self._mutate_before_insert_failure:
                super().insert(fixture)
            raise RuntimeError("sensitive repository detail")
        return super().insert(fixture)

    def count_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        if self._fail_at == "verify" and "insert" in self.calls and not self._verify_failed_once:
            self._verify_failed_once = True
            self.calls.append("count_by_fingerprint")
            return 0
        return super().count_by_fingerprint(fixture)

    def delete_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        if self._fail_at == "delete":
            self.calls.append("delete_by_fingerprint")
            return 0
        return super().delete_by_fingerprint(fixture)


class InvalidInsertCountRepository(InMemoryEmployeeFixtureRepository):
    def insert(self, fixture: EmployeeFixtureSpec) -> int:
        super().insert(fixture)
        return 2


def _run(
    tmp_path: Path,
    repository: InMemoryEmployeeFixtureRepository,
    *,
    consumer: Callable[[EmployeeFixtureSpec], None] | None = None,
) -> EmployeeFixtureExecution:
    callback = consumer if consumer is not None else (lambda _: None)
    return execute_fixture_lifecycle(
        repository=repository,
        metadata_result_path=METADATA_RESULT,
        lifecycle_path=tmp_path / "lifecycle.jsonl",
        evidence_path=tmp_path / "evidence.json",
        run_id="employee-fixture-nonlive-test",
        seed="candidate-01",
        consumer=callback,
    )


def test_fixture_spec_is_deterministic_and_not_an_id_card_number() -> None:
    first = build_fixture_spec("candidate-01")
    second = build_fixture_spec("candidate-01")
    assert first == second
    assert first.identifier.startswith("synthetic-employee-")
    assert not first.identifier.isdigit()
    assert len(first.fingerprint) == 64
    assert set(FIELD_NAMES) == {"idCardNo", "chineseName", "position", "workBaseSi"}


def test_metadata_snapshot_and_schema_are_frozen() -> None:
    validate_metadata_result(METADATA_RESULT)
    assert METADATA_RESULT_SHA256 == "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51"
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["metadataResultSha256"]["const"] == METADATA_RESULT_SHA256
    assert schema["properties"]["fieldNames"]["const"] == list(FIELD_NAMES)


def test_passed_lifecycle_creates_verifies_consumes_and_cleans_once(tmp_path: Path) -> None:
    repository = InMemoryEmployeeFixtureRepository()
    seen: list[str] = []
    result = _run(tmp_path, repository, consumer=lambda fixture: seen.append(fixture.identifier))

    assert result.status == "passed"
    assert result.reason == "none"
    assert len(seen) == 1
    assert repository.calls == [
        "count_by_identifier",
        "insert",
        "count_by_fingerprint",
        "count_by_fingerprint",
        "delete_by_fingerprint",
        "count_by_identifier",
    ]
    assert result.evidence["counts"] == {
        "preexisting": 0,
        "inserted": 1,
        "verified": 1,
        "deleted": 1,
        "remaining": 0,
        "retryCount": 0,
        "resumeCount": 0,
        "existingRowsModified": 0,
    }
    records = validate_lifecycle(tmp_path / "lifecycle.jsonl")
    assert records[0]["phase"] == "run"
    assert records[-1]["state"] == "succeeded"
    persisted = json.loads((tmp_path / "evidence.json").read_text())
    validate_evidence(persisted)
    serialized = (tmp_path / "lifecycle.jsonl").read_text() + (tmp_path / "evidence.json").read_text()
    assert result.fixture.identifier not in serialized
    assert result.fixture.chinese_name not in serialized
    assert result.fixture.position not in serialized
    assert result.fixture.work_base_si not in serialized
    assert result.fixture.fingerprint not in serialized


def test_lifecycle_rejects_missing_stage_terminal_and_extra_keys(tmp_path: Path) -> None:
    path = tmp_path / "invalid.jsonl"
    records = [
        {
            "contractVersion": "employee-synthetic-fixture-v1",
            "phase": "run",
            "reason": "none",
            "runId": "employee-fixture-nonlive-test",
            "sequence": 1,
            "state": "started",
        },
        {
            "contractVersion": "employee-synthetic-fixture-v1",
            "phase": "insert",
            "reason": "none",
            "runId": "employee-fixture-nonlive-test",
            "sequence": 2,
            "state": "started",
        },
        {
            "contractVersion": "employee-synthetic-fixture-v1",
            "phase": "run",
            "reason": "repository_failure",
            "runId": "employee-fixture-nonlive-test",
            "sequence": 3,
            "state": "failed",
        },
    ]
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    with pytest.raises(EmployeeFixtureContractError, match="employee.fixture_lifecycle_invalid"):
        validate_lifecycle(path)


def test_lifecycle_rejects_reordered_stages(tmp_path: Path) -> None:
    result = _run(tmp_path, InMemoryEmployeeFixtureRepository())
    assert result.status == "passed"
    path = tmp_path / "lifecycle.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[1:5] = records[3:5] + records[1:3]
    for sequence, record in enumerate(records, start=1):
        record["sequence"] = sequence
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    with pytest.raises(EmployeeFixtureContractError, match="employee.fixture_lifecycle_invalid"):
        validate_lifecycle(path)


def test_identifier_conflict_stops_before_insert(tmp_path: Path) -> None:
    fixture = build_fixture_spec("candidate-01")
    repository = InMemoryEmployeeFixtureRepository((fixture,))
    result = _run(tmp_path, repository)
    assert result.status == "failed"
    assert result.reason == "identifier_conflict"
    assert repository.calls == ["count_by_identifier"]


@pytest.mark.parametrize(
    ("fail_at", "mutate", "expected_status", "expected_reason"),
    [
        ("precheck", False, "failed", "repository_failure"),
        ("insert", False, "failed", "repository_failure"),
        ("insert", True, "failed", "repository_failure"),
        ("verify", False, "failed", "fingerprint_mismatch"),
        ("delete", False, "failed_cleanup_required", "cleanup_count_invalid"),
        (
            "cleanup_verify",
            False,
            "failed_cleanup_required",
            "cleanup_verification_failed",
        ),
    ],
)
def test_repository_failures_are_bounded_and_never_retried(
    tmp_path: Path,
    fail_at: str,
    mutate: bool,
    expected_status: str,
    expected_reason: str,
) -> None:
    repository = FaultRepository(fail_at=fail_at, mutate_before_insert_failure=mutate)
    result = _run(tmp_path, repository)
    assert result.status == expected_status
    assert result.reason == expected_reason
    counts = result.evidence["counts"]
    assert isinstance(counts, dict)
    assert counts["retryCount"] == 0
    assert counts["resumeCount"] == 0
    assert repository.calls.count("insert") <= 1
    assert repository.calls.count("delete_by_fingerprint") <= 1


def test_consumer_failure_is_cleaned_without_persisting_exception(tmp_path: Path) -> None:
    repository = InMemoryEmployeeFixtureRepository()

    def fail(_: EmployeeFixtureSpec) -> None:
        raise RuntimeError("sensitive consumer detail")

    result = _run(tmp_path, repository, consumer=fail)
    assert result.status == "failed"
    assert result.reason == "consumer_failure"
    combined = (tmp_path / "lifecycle.jsonl").read_text() + (tmp_path / "evidence.json").read_text()
    assert "sensitive consumer detail" not in combined
    assert repository.count_by_identifier(result.fixture.identifier) == 0


def test_invalid_insert_count_is_classified_and_cleaned(tmp_path: Path) -> None:
    repository = InvalidInsertCountRepository()
    result = _run(tmp_path, repository)
    assert result.status == "failed"
    assert result.reason == "insert_count_invalid"
    assert repository.count_by_identifier(result.fixture.identifier) == 0


def test_existing_output_fails_before_repository_access(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.jsonl"
    lifecycle.write_text("existing", encoding="utf-8")
    repository = InMemoryEmployeeFixtureRepository()
    with pytest.raises(EmployeeFixtureContractError, match="employee.fixture_output_exists"):
        execute_fixture_lifecycle(
            repository=repository,
            metadata_result_path=METADATA_RESULT,
            lifecycle_path=lifecycle,
            evidence_path=tmp_path / "evidence.json",
            run_id="employee-fixture-nonlive-test",
            seed="candidate-01",
            consumer=lambda _: None,
        )
    assert repository.calls == []


def test_evidence_rejects_extra_keys_and_sensitive_flags(tmp_path: Path) -> None:
    result = _run(tmp_path, InMemoryEmployeeFixtureRepository())
    invalid = dict(result.evidence)
    invalid["identifier"] = "forbidden"
    with pytest.raises(EmployeeFixtureContractError, match="employee.fixture_evidence_invalid"):
        validate_evidence(invalid)
    invalid = dict(result.evidence)
    invalid["valuesPersisted"] = True
    with pytest.raises(EmployeeFixtureContractError, match="employee.fixture_evidence_invalid"):
        validate_evidence(invalid)
