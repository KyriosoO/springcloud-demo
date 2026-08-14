from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, cast

from tests.integration.adapters.employee.employee_test_data_fixture import (
    EmployeeFixtureRepository,
    EmployeeFixtureSpec,
    build_fixture_spec,
    validate_metadata_result,
)


PREPARATION_WORK_PACKAGE_ID: Final = (
    "WP-EMP-EGRESS-TEST-DATA-CANDIDATE-01-PREP"
)
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-TEST-DATA-CANDIDATE-01"
GATE_ID: Final = "GATE-051"
RUN_ID: Final = "employee-synthetic-fixture-v1-20260814-candidate-01"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-051"
PREPARED_AT: Final = "2026-08-14T10:00:00Z"
MANIFEST_SHA_PLACEHOLDER: Final = "0" * 64
SEED: Final = "employee-fixture-candidate-01"
MAX_DATABASE_SELECTS: Final = 3
MAX_DATABASE_INSERTS: Final = 1
MAX_DATABASE_DELETES: Final = 1
PHASES: Final = (
    "precheck",
    "insert",
    "verify",
    "consumer",
    "cleanup_delete",
    "cleanup_verify",
    "host_validation",
)
SOURCE_HISTORY: Final = (
    (
        "fixture_contract",
        "agent-runtime/tests/integration/adapters/employee/employee_test_data_fixture.py",
        "d0b23b75edb600d6aba2e143305a3492c5f263e9d5ce58de55c138c082aa1148",
    ),
    (
        "fixture_schema",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-test-data-fixture-v1.schema.json",
        "93db9b28e38dc77b6568e28e3e3878a021164c6e187ed5e7a7244336005f5f31",
    ),
    (
        "metadata_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.manifest.json",
        "ce3dcd481352bbb59be01a2d3b975dfd1b9f35ae1479dd24d7408f11be7af6b7",
    ),
    (
        "metadata_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.authorization.json",
        "532353a032835c7f9eb4e5d8548061f22f45b16f42525d79e635131f5e0a2fb4",
    ),
    (
        "metadata_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.lifecycle.jsonl",
        "affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105",
    ),
    (
        "metadata_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.result.json",
        "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51",
    ),
)
ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/tests/integration/adapters/employee/"
        "employee_test_data_fixture_candidate.py",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_employee_test_data_fixture_candidate.py",
        "agent-runtime/tests/integration/adapters/employee/"
        "run_employee_test_data_fixture_candidate_01.ps1",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-test-data-fixture-candidate-v1-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-test-data-fixture-candidate-v1-result.schema.json",
        "employee-service/src/test/java/com/dylan/employee/live/"
        "EmployeeSyntheticFixtureCandidateLiveIntegrationTest.java",
    }
)

_RUN_ID_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,95}\Z")
_SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}\Z")
_STATUSES: Final = {"passed", "failed", "failed_cleanup_required"}
_REASONS: Final = {
    "none",
    "identifier_conflict",
    "database_operation_failed",
    "insert_count_invalid",
    "fingerprint_mismatch",
    "consumer_failure",
    "cleanup_count_invalid",
    "cleanup_verification_failed",
    "host_execution_failed",
    "log_leak_detected",
}
_RESULT_KEYS: Final = {
    "schemaVersion",
    "preparationWorkPackageId",
    "workPackageId",
    "gateId",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "status",
    "reason",
    "fieldNames",
    "sourceHistory",
    "counts",
    "safety",
    "lifecycleSha256",
}
_COUNT_KEYS: Final = {
    "databaseSelectStarted",
    "databaseSelectTerminal",
    "databaseInsertStarted",
    "databaseInsertTerminal",
    "databaseDeleteStarted",
    "databaseDeleteTerminal",
    "preexisting",
    "inserted",
    "verified",
    "deleted",
    "remaining",
    "consumerCalls",
    "employeeEndpointCalls",
    "modelCalls",
    "retryCount",
    "resumeCount",
}
_SAFETY_KEYS: Final = {
    "synthetic",
    "nonRealIdentifier",
    "identifierPersisted",
    "fixtureFingerprintPersisted",
    "fieldValuesPersisted",
    "existingRowsModified",
    "publicApiCalls",
    "jwtRead",
    "llmApiKeyRead",
    "modelOutbound",
    "logLeakCount",
    "rawLogsDeleted",
}


class FixtureCandidateError(ValueError):
    """Finite failure for the test-only real-fixture candidate."""


def _invalid() -> NoReturn:
    raise FixtureCandidateError("employee.fixture_candidate_invalid")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_strict_json(path: Path, *, max_bytes: int = 1_048_576) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0 or path.stat().st_size > max_bytes:
        _invalid()

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                _invalid()
            value[key] = item
        return value

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _invalid()
    if not isinstance(value, dict):
        _invalid()
    return value


def verify_source_history(repository_root: Path) -> None:
    for _, relative, expected in SOURCE_HISTORY:
        path = repository_root / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise FixtureCandidateError("employee.fixture_candidate_history_mismatch")


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    _write_exclusive(path, (_canonical_json(value) + "\n").encode("utf-8"))


class CandidateLifecycleJournal:
    def __init__(self, path: Path, *, manifest_sha256: str) -> None:
        if not _SHA256_PATTERN.fullmatch(manifest_sha256):
            _invalid()
        self._path = path
        self._manifest_sha256 = manifest_sha256
        self._sequence = 0
        self._terminal = False
        _write_exclusive(path, b"")
        self.record(phase="run", state="started")

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        *,
        phase: str,
        state: Literal["started", "succeeded", "failed"],
        reason: str = "none",
    ) -> None:
        if self._terminal or phase not in {"run", *PHASES} or reason not in _REASONS:
            _invalid()
        if phase == "run" and state != "started":
            self._terminal = True
        self._sequence += 1
        record = {
            "schemaVersion": 1,
            "workPackageId": WORK_PACKAGE_ID,
            "gateId": GATE_ID,
            "runId": RUN_ID,
            "manifestSha256": self._manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "sequence": self._sequence,
            "phase": phase,
            "state": state,
            "reason": reason,
        }
        with self._path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical_json(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


@dataclass(frozen=True, slots=True)
class FixtureCandidateExecution:
    status: Literal["passed", "failed", "failed_cleanup_required"]
    reason: str
    result: Mapping[str, object]


def execute_fake_candidate(
    *,
    repository: EmployeeFixtureRepository,
    metadata_result_path: Path,
    lifecycle_path: Path,
    result_path: Path,
    manifest_sha256: str,
    fail_consumer: bool = False,
) -> FixtureCandidateExecution:
    validate_metadata_result(metadata_result_path)
    if lifecycle_path.exists() or result_path.exists():
        raise FixtureCandidateError("employee.fixture_candidate_output_exists")
    fixture = build_fixture_spec(SEED)
    journal = CandidateLifecycleJournal(lifecycle_path, manifest_sha256=manifest_sha256)
    counts = _empty_counts()
    status: Literal["passed", "failed", "failed_cleanup_required"] = "failed"
    reason = "none"
    insert_started = False
    try:
        _record_pair(journal, "precheck", lambda: _precheck(repository, fixture, counts))
        insert_started = True
        _record_pair(journal, "insert", lambda: _insert(repository, fixture, counts))
        _record_pair(journal, "verify", lambda: _verify(repository, fixture, counts))

        def consume() -> None:
            counts["consumerCalls"] += 1
            if fail_consumer:
                raise FixtureCandidateError("consumer_failure")

        _record_pair(journal, "consumer", consume)
        status = "passed"
    except FixtureCandidateError as failure:
        reason = _bounded_reason(str(failure))
    except Exception:
        reason = "database_operation_failed"
    finally:
        if insert_started:
            cleanup_reason = _cleanup(repository, fixture, journal, counts)
            if cleanup_reason != "none":
                status = "failed_cleanup_required"
                reason = cleanup_reason
    _record_pair(journal, "host_validation", lambda: None)
    journal.record(
        phase="run",
        state="succeeded" if status == "passed" else "failed",
        reason=reason,
    )
    result = _build_result(
        status=status,
        reason=reason,
        counts=counts,
        lifecycle_path=lifecycle_path,
        manifest_sha256=manifest_sha256,
        raw_logs_deleted=True,
    )
    validate_result(result)
    _write_exclusive_json(result_path, result)
    return FixtureCandidateExecution(status=status, reason=reason, result=result)


def _record_pair(
    journal: CandidateLifecycleJournal, phase: str, operation: Callable[[], None]
) -> None:
    journal.record(phase=phase, state="started")
    try:
        operation()
    except FixtureCandidateError as failure:
        journal.record(phase=phase, state="failed", reason=_bounded_reason(str(failure)))
        raise
    except Exception as failure:
        journal.record(
            phase=phase, state="failed", reason="database_operation_failed"
        )
        raise FixtureCandidateError("database_operation_failed") from failure
    journal.record(phase=phase, state="succeeded")


def _precheck(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseSelectStarted"] += 1
    try:
        counts["preexisting"] = _bounded_count(
            repository.count_by_identifier(fixture.identifier)
        )
    finally:
        counts["databaseSelectTerminal"] += 1
    if counts["preexisting"] != 0:
        raise FixtureCandidateError("identifier_conflict")


def _insert(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseInsertStarted"] += 1
    try:
        counts["inserted"] = _bounded_count(repository.insert(fixture))
    finally:
        counts["databaseInsertTerminal"] += 1
    if counts["inserted"] != 1:
        raise FixtureCandidateError("insert_count_invalid")


def _verify(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseSelectStarted"] += 1
    try:
        counts["verified"] = _bounded_count(repository.count_by_fingerprint(fixture))
    finally:
        counts["databaseSelectTerminal"] += 1
    if counts["verified"] != 1:
        raise FixtureCandidateError("fingerprint_mismatch")


def _cleanup(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    journal: CandidateLifecycleJournal,
    counts: dict[str, int],
) -> str:
    try:
        _record_pair(journal, "cleanup_delete", lambda: _delete(repository, fixture, counts))
        _record_pair(
            journal, "cleanup_verify", lambda: _verify_deleted(repository, fixture, counts)
        )
    except FixtureCandidateError as failure:
        return _bounded_reason(str(failure))
    return "none"


def _delete(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseDeleteStarted"] += 1
    try:
        counts["deleted"] = _bounded_count(repository.delete_by_fingerprint(fixture))
    finally:
        counts["databaseDeleteTerminal"] += 1
    if counts["deleted"] != 1:
        raise FixtureCandidateError("cleanup_count_invalid")


def _verify_deleted(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseSelectStarted"] += 1
    try:
        counts["remaining"] = _bounded_count(
            repository.count_by_identifier(fixture.identifier)
        )
    finally:
        counts["databaseSelectTerminal"] += 1
    if counts["remaining"] != 0:
        raise FixtureCandidateError("cleanup_verification_failed")


def _empty_counts() -> dict[str, int]:
    return {key: 0 for key in _COUNT_KEYS}


def _build_result(
    *,
    status: str,
    reason: str,
    counts: Mapping[str, int],
    lifecycle_path: Path,
    manifest_sha256: str,
    raw_logs_deleted: bool,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "status": status,
        "reason": reason,
        "fieldNames": ["idCardNo", "chineseName", "position", "workBaseSi"],
        "sourceHistory": [
            {"kind": kind, "path": path, "sha256": digest}
            for kind, path, digest in SOURCE_HISTORY
        ],
        "counts": dict(counts),
        "safety": {
            "synthetic": True,
            "nonRealIdentifier": True,
            "identifierPersisted": False,
            "fixtureFingerprintPersisted": False,
            "fieldValuesPersisted": False,
            "existingRowsModified": 0,
            "publicApiCalls": 0,
            "jwtRead": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "logLeakCount": 0,
            "rawLogsDeleted": raw_logs_deleted,
        },
        "lifecycleSha256": sha256_file(lifecycle_path),
    }


def validate_lifecycle(
    path: Path,
    *,
    manifest_sha256: str,
    allow_pending_terminal: bool = False,
) -> list[dict[str, Any]]:
    if not path.is_file() or not _SHA256_PATTERN.fullmatch(manifest_sha256):
        _invalid()
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            _invalid()
        if not isinstance(value, dict):
            _invalid()
        records.append(value)
    if len(records) < 2:
        _invalid()
    common = {
        "schemaVersion": 1,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }
    for sequence, record in enumerate(records, start=1):
        if set(record) != {*common, "sequence", "phase", "state", "reason"}:
            _invalid()
        if any(record[key] != expected for key, expected in common.items()):
            _invalid()
        if (
            record["sequence"] != sequence
            or record["phase"] not in {"run", *PHASES}
            or record["state"] not in {"started", "succeeded", "failed"}
            or record["reason"] not in _REASONS
        ):
            _invalid()
    if records[0]["phase"] != "run" or records[0]["state"] != "started":
        _invalid()
    has_run_terminal = records[-1]["phase"] == "run" and records[-1]["state"] != "started"
    if not has_run_terminal and not allow_pending_terminal:
        _invalid()
    middle = records[1:-1] if has_run_terminal else records[1:]
    if len(middle) % 2 != 0:
        _invalid()
    observed: list[str] = []
    for index in range(0, len(middle), 2):
        started, terminal = middle[index : index + 2]
        if (
            started["phase"] != terminal["phase"]
            or started["state"] != "started"
            or terminal["state"] == "started"
            or started["reason"] != "none"
        ):
            _invalid()
        observed.append(cast(str, started["phase"]))
    if len(observed) != len(set(observed)):
        _invalid()
    phase_positions = [PHASES.index(phase) for phase in observed]
    if phase_positions != sorted(phase_positions):
        _invalid()
    if allow_pending_terminal and has_run_terminal:
        _invalid()
    if has_run_terminal and (not observed or observed[-1] != "host_validation"):
        _invalid()
    if not has_run_terminal and "host_validation" in observed:
        _invalid()
    return records


def validate_result(value: object, *, allow_logs_pending: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _RESULT_KEYS:
        _invalid()
    counts = value.get("counts")
    safety = value.get("safety")
    if (
        value.get("schemaVersion") != 1
        or value.get("preparationWorkPackageId") != PREPARATION_WORK_PACKAGE_ID
        or value.get("workPackageId") != WORK_PACKAGE_ID
        or value.get("gateId") != GATE_ID
        or value.get("runId") != RUN_ID
        or not isinstance(value.get("manifestSha256"), str)
        or not _SHA256_PATTERN.fullmatch(cast(str, value["manifestSha256"]))
        or value.get("authorizationReference") != AUTHORIZATION_REFERENCE
        or value.get("status") not in _STATUSES
        or value.get("reason") not in _REASONS
        or value.get("fieldNames")
        != ["idCardNo", "chineseName", "position", "workBaseSi"]
        or value.get("sourceHistory")
        != [
            {"kind": kind, "path": path, "sha256": digest}
            for kind, path, digest in SOURCE_HISTORY
        ]
        or not isinstance(counts, dict)
        or set(counts) != _COUNT_KEYS
        or not isinstance(safety, dict)
        or set(safety) != _SAFETY_KEYS
        or not isinstance(value.get("lifecycleSha256"), str)
        or not _SHA256_PATTERN.fullmatch(cast(str, value["lifecycleSha256"]))
    ):
        _invalid()
    if any(type(counts[key]) is not int or counts[key] < 0 for key in _COUNT_KEYS):
        _invalid()
    if (
        counts["databaseSelectStarted"] > MAX_DATABASE_SELECTS
        or counts["databaseSelectStarted"] != counts["databaseSelectTerminal"]
        or counts["databaseInsertStarted"] > MAX_DATABASE_INSERTS
        or counts["databaseInsertStarted"] != counts["databaseInsertTerminal"]
        or counts["databaseDeleteStarted"] > MAX_DATABASE_DELETES
        or counts["databaseDeleteStarted"] != counts["databaseDeleteTerminal"]
        or counts["consumerCalls"] > 1
        or counts["employeeEndpointCalls"] != 0
        or counts["modelCalls"] != 0
        or counts["retryCount"] != 0
        or counts["resumeCount"] != 0
    ):
        _invalid()
    expected_safety: dict[str, object] = {
        "synthetic": True,
        "nonRealIdentifier": True,
        "identifierPersisted": False,
        "fixtureFingerprintPersisted": False,
        "fieldValuesPersisted": False,
        "existingRowsModified": 0,
        "publicApiCalls": 0,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "modelOutbound": False,
        "rawLogsDeleted": safety.get("rawLogsDeleted"),
    }
    if (
        any(safety.get(key) != expected for key, expected in expected_safety.items())
        or type(safety.get("logLeakCount")) is not int
        or cast(int, safety["logLeakCount"]) < 0
        or cast(int, safety["logLeakCount"]) > 1000
    ):
        _invalid()
    if safety["rawLogsDeleted"] is not True and not (
        allow_logs_pending and safety["rawLogsDeleted"] is False
    ):
        _invalid()
    if value["status"] == "passed" and (
        value["reason"] != "none"
        or safety["logLeakCount"] != 0
        or any(
            counts[key] != expected
            for key, expected in {
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
            }.items()
        )
    ):
        _invalid()
    insert_started = cast(int, counts["databaseInsertStarted"])
    delete_started = cast(int, counts["databaseDeleteStarted"])
    if insert_started == 0 and delete_started != 0:
        _invalid()
    if insert_started == 1 and delete_started != 1:
        _invalid()
    if value["status"] != "failed_cleanup_required" and insert_started == 1 and (
        counts["deleted"] != 1 or counts["remaining"] != 0
    ):
        _invalid()
    if value["status"] == "failed_cleanup_required" and value["reason"] not in {
        "database_operation_failed",
        "cleanup_count_invalid",
        "cleanup_verification_failed",
    }:
        _invalid()
    return value


def finalize_staging_result(
    staging_path: Path,
    lifecycle_path: Path,
    result_path: Path,
    *,
    log_leak_count: int,
    host_exit_code: int,
) -> None:
    if type(log_leak_count) is not int or log_leak_count < 0 or type(host_exit_code) is not int:
        _invalid()
    value = validate_result(load_strict_json(staging_path), allow_logs_pending=True)
    manifest_sha256 = cast(str, value["manifestSha256"])
    records = validate_lifecycle(
        lifecycle_path,
        manifest_sha256=manifest_sha256,
        allow_pending_terminal=True,
    )
    status = cast(str, value["status"])
    reason = cast(str, value["reason"])
    host_reason = "none"
    if log_leak_count > 0:
        status = "failed"
        reason = host_reason = "log_leak_detected"
    elif host_exit_code != 0 and status == "passed":
        status = "failed"
        reason = host_reason = "host_execution_failed"
    _append_lifecycle_record(
        lifecycle_path,
        sequence=len(records) + 1,
        manifest_sha256=manifest_sha256,
        phase="host_validation",
        state="started",
        reason="none",
    )
    _append_lifecycle_record(
        lifecycle_path,
        sequence=len(records) + 2,
        manifest_sha256=manifest_sha256,
        phase="host_validation",
        state="failed" if host_reason != "none" else "succeeded",
        reason=host_reason,
    )
    _append_lifecycle_record(
        lifecycle_path,
        sequence=len(records) + 3,
        manifest_sha256=manifest_sha256,
        phase="run",
        state="succeeded" if status == "passed" else "failed",
        reason=reason,
    )
    value["status"] = status
    value["reason"] = reason
    safety = cast(dict[str, Any], value["safety"])
    safety["logLeakCount"] = log_leak_count
    safety["rawLogsDeleted"] = True
    value["lifecycleSha256"] = sha256_file(lifecycle_path)
    validate_lifecycle(lifecycle_path, manifest_sha256=manifest_sha256)
    validate_result(value)
    _write_exclusive_json(result_path, value)


def _append_lifecycle_record(
    path: Path,
    *,
    sequence: int,
    manifest_sha256: str,
    phase: str,
    state: str,
    reason: str,
) -> None:
    record = {
        "schemaVersion": 1,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "sequence": sequence,
        "phase": phase,
        "state": state,
        "reason": reason,
    }
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_canonical_json(record) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_manifest(
    manifest_path: Path, authorization_path: Path, repository_root: Path
) -> dict[str, Any]:
    verify_source_history(repository_root)
    validate_metadata_result(repository_root / SOURCE_HISTORY[-1][1])
    manifest = load_strict_json(manifest_path)
    if set(manifest) != {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "preparedAt",
        "executionBoundary",
        "sourceHistory",
        "assetHashes",
    }:
        _invalid()
    expected_history = [
        {"kind": kind, "path": path, "sha256": digest}
        for kind, path, digest in SOURCE_HISTORY
    ]
    if (
        manifest["schemaVersion"] != 1
        or manifest["status"] != "prepared_unconsumed"
        or manifest["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or manifest["workPackageId"] != WORK_PACKAGE_ID
        or manifest["gateId"] != GATE_ID
        or manifest["runId"] != RUN_ID
        or manifest["authorizationReference"] != AUTHORIZATION_REFERENCE
        or manifest["preparedAt"] != PREPARED_AT
        or manifest["sourceHistory"] != expected_history
        or manifest["executionBoundary"]
        != {
            "databaseSelectMaximum": 3,
            "databaseInsertMaximum": 1,
            "databaseDeleteMaximum": 1,
            "employeeEndpointMaximum": 0,
            "modelMaximumCalls": 0,
            "retryAllowed": False,
            "resumeAllowed": False,
            "liveExecutionAuthorized": False,
        }
    ):
        _invalid()
    assets = manifest["assetHashes"]
    if not isinstance(assets, list) or len(assets) != len(ASSET_PATHS):
        _invalid()
    observed: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {"path", "sha256"}:
            _invalid()
        relative = asset.get("path")
        digest = asset.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(digest, str)
            or relative in observed
            or relative not in ASSET_PATHS
            or not (repository_root / relative).is_file()
            or sha256_file(repository_root / relative) != digest
        ):
            _invalid()
        observed.add(relative)
    if observed != set(ASSET_PATHS):
        _invalid()
    manifest_sha256 = sha256_file(manifest_path)
    authorization = load_strict_json(authorization_path)
    if authorization != {
        "schemaVersion": 1,
        "status": "prepared_unconsumed",
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "databaseSelectMaximum": 3,
        "databaseInsertMaximum": 1,
        "databaseDeleteMaximum": 1,
        "employeeEndpointMaximum": 0,
        "modelMaximumCalls": 0,
        "retryAllowed": False,
        "resumeAllowed": False,
        "liveExecutionAuthorized": False,
        "confirmedBy": "project-maintainer-pending-gate-051-live-authorization",
        "preparedAt": PREPARED_AT,
    }:
        _invalid()
    return manifest


def _bounded_count(value: object) -> int:
    if type(value) is not int or value < 0 or value > 1:
        raise FixtureCandidateError("database_operation_failed")
    return value


def _bounded_reason(value: str) -> str:
    return value if value in _REASONS else "database_operation_failed"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
