from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol, cast


WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-TEST-DATA-PREP-01"
SCHEMA_VERSION: Final = 1
CONTRACT_VERSION: Final = "employee-synthetic-fixture-v1"
METADATA_RESULT_SHA256: Final = (
    "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51"
)
FIELD_NAMES: Final = ("idCardNo", "chineseName", "position", "workBaseSi")
_RUN_ID_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,95}\Z")
_SEED_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_ID_CARD_PATTERN: Final = re.compile(r"\d{17}[0-9Xx]\Z")
_STATUSES: Final = {"passed", "failed", "failed_cleanup_required"}
_REASONS: Final = {
    "none",
    "identifier_conflict",
    "repository_failure",
    "insert_count_invalid",
    "fingerprint_mismatch",
    "consumer_failure",
    "cleanup_count_invalid",
    "cleanup_verification_failed",
    "journal_failure",
}
_PHASES: Final = {
    "run",
    "precheck",
    "insert",
    "verify",
    "consumer",
    "cleanup_delete",
    "cleanup_verify",
}
_PHASE_ORDER: Final = (
    "precheck",
    "insert",
    "verify",
    "consumer",
    "cleanup_delete",
    "cleanup_verify",
)
_FIXED_TEMPLATE: Final = {
    "chineseName": "Synthetic Employee",
    "identifierAlgorithm": "synthetic-employee-sha256-v1-prefix24",
    "position": "Synthetic Position",
    "workBaseSi": "Synthetic Work Base",
}


class EmployeeFixtureContractError(ValueError):
    pass


class EmployeeFixtureRepository(Protocol):
    def count_by_identifier(self, identifier: str) -> int: ...

    def insert(self, fixture: EmployeeFixtureSpec) -> int: ...

    def count_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int: ...

    def delete_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int: ...


@dataclass(frozen=True, slots=True)
class EmployeeFixtureSpec:
    identifier: str
    chinese_name: str
    position: str
    work_base_si: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class EmployeeFixtureExecution:
    status: Literal["passed", "failed", "failed_cleanup_required"]
    reason: str
    fixture: EmployeeFixtureSpec
    evidence: Mapping[str, object]


class InMemoryEmployeeFixtureRepository:
    def __init__(self, records: tuple[EmployeeFixtureSpec, ...] = ()) -> None:
        self._records = list(records)
        self.calls: list[str] = []

    def count_by_identifier(self, identifier: str) -> int:
        self.calls.append("count_by_identifier")
        return sum(record.identifier == identifier for record in self._records)

    def insert(self, fixture: EmployeeFixtureSpec) -> int:
        self.calls.append("insert")
        self._records.append(fixture)
        return 1

    def count_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        self.calls.append("count_by_fingerprint")
        return sum(record == fixture for record in self._records)

    def delete_by_fingerprint(self, fixture: EmployeeFixtureSpec) -> int:
        self.calls.append("delete_by_fingerprint")
        matching = [record for record in self._records if record == fixture]
        if len(matching) == 1:
            self._records.remove(fixture)
        return len(matching)


class EmployeeFixtureLifecycleJournal:
    def __init__(self, path: Path, *, run_id: str) -> None:
        _validate_run_id(run_id)
        self._path = path
        self._run_id = run_id
        self._sequence = 0
        self._terminal = False
        self._append(phase="run", state="started", reason="none")

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
        if self._terminal:
            raise EmployeeFixtureContractError("employee.fixture_journal_terminal")
        if phase not in _PHASES or reason not in _REASONS:
            raise EmployeeFixtureContractError("employee.fixture_journal_invalid")
        if phase == "run" and state in {"succeeded", "failed"}:
            self._terminal = True
        self._append(phase=phase, state=state, reason=reason)

    def _append(self, *, phase: str, state: str, reason: str) -> None:
        self._sequence += 1
        record = {
            "contractVersion": CONTRACT_VERSION,
            "phase": phase,
            "reason": reason,
            "runId": self._run_id,
            "sequence": self._sequence,
            "state": state,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        mode = "x" if self._sequence == 1 else "a"
        with self._path.open(mode, encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical_json(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def build_fixture_spec(seed: str) -> EmployeeFixtureSpec:
    if not _SEED_PATTERN.fullmatch(seed):
        raise EmployeeFixtureContractError("employee.fixture_seed_invalid")
    digest = hashlib.sha256(f"{CONTRACT_VERSION}:{seed}".encode()).hexdigest()
    identifier = f"synthetic-employee-{digest[:24]}"
    if _ID_CARD_PATTERN.fullmatch(identifier):
        raise EmployeeFixtureContractError("employee.fixture_identifier_invalid")
    values = {
        "chineseName": _FIXED_TEMPLATE["chineseName"],
        "idCardNo": identifier,
        "position": _FIXED_TEMPLATE["position"],
        "workBaseSi": _FIXED_TEMPLATE["workBaseSi"],
    }
    fingerprint = hashlib.sha256(_canonical_json(values).encode()).hexdigest()
    return EmployeeFixtureSpec(
        identifier=identifier,
        chinese_name=values["chineseName"],
        position=values["position"],
        work_base_si=values["workBaseSi"],
        fingerprint=fingerprint,
    )


def validate_metadata_result(path: Path) -> None:
    if _sha256_file(path) != METADATA_RESULT_SHA256:
        raise EmployeeFixtureContractError("employee.fixture_metadata_hash_invalid")
    value = _load_strict_json(path)
    if value.get("status") != "passed":
        raise EmployeeFixtureContractError("employee.fixture_metadata_invalid")
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        raise EmployeeFixtureContractError("employee.fixture_metadata_invalid")
    table = metadata.get("table")
    if not isinstance(table, dict):
        raise EmployeeFixtureContractError("employee.fixture_metadata_invalid")
    columns = table.get("columns")
    if (
        table.get("name") != "employee"
        or table.get("engine") != "InnoDB"
        or not isinstance(columns, list)
        or len(columns) != 58
        or metadata.get("constraints") != []
        or metadata.get("checks") != []
        or metadata.get("triggers") != []
    ):
        raise EmployeeFixtureContractError("employee.fixture_metadata_invalid")
    by_name = {
        column.get("name"): column
        for column in columns
        if isinstance(column, dict) and isinstance(column.get("name"), str)
    }
    for name in ("ID_CARD_NO", "CHINESE_NAME", "POSITION", "WORK_BASE_SI"):
        column = by_name.get(name)
        if (
            not isinstance(column, dict)
            or column.get("dataType") != "longtext"
            or column.get("nullable") != "YES"
            or column.get("default") is not None
            or column.get("extra") != ""
            or column.get("generationExpression") != ""
        ):
            raise EmployeeFixtureContractError("employee.fixture_metadata_invalid")


def execute_fixture_lifecycle(
    *,
    repository: EmployeeFixtureRepository,
    metadata_result_path: Path,
    lifecycle_path: Path,
    evidence_path: Path,
    run_id: str,
    seed: str,
    consumer: Callable[[EmployeeFixtureSpec], None],
) -> EmployeeFixtureExecution:
    validate_metadata_result(metadata_result_path)
    if lifecycle_path.exists() or evidence_path.exists():
        raise EmployeeFixtureContractError("employee.fixture_output_exists")
    fixture = build_fixture_spec(seed)
    journal = EmployeeFixtureLifecycleJournal(lifecycle_path, run_id=run_id)
    counts = {
        "preexisting": 0,
        "inserted": 0,
        "verified": 0,
        "deleted": 0,
        "remaining": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    status: Literal["passed", "failed", "failed_cleanup_required"] = "failed"
    reason = "none"
    insert_started = False

    try:
        journal.record(phase="precheck", state="started")
        try:
            counts["preexisting"] = _bounded_count(
                repository.count_by_identifier(fixture.identifier)
            )
        except Exception:
            reason = "repository_failure"
            journal.record(phase="precheck", state="failed", reason=reason)
            return _finish(
                journal=journal,
                evidence_path=evidence_path,
                run_id=run_id,
                fixture=fixture,
                counts=counts,
                status="failed",
                reason=reason,
            )
        if counts["preexisting"] != 0:
            reason = "identifier_conflict"
            journal.record(phase="precheck", state="failed", reason=reason)
            return _finish(
                journal=journal,
                evidence_path=evidence_path,
                run_id=run_id,
                fixture=fixture,
                counts=counts,
                status="failed",
                reason=reason,
            )
        journal.record(phase="precheck", state="succeeded")

        insert_started = True
        journal.record(phase="insert", state="started")
        try:
            inserted = repository.insert(fixture)
        except Exception:
            reason = "repository_failure"
            journal.record(phase="insert", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason) from None
        try:
            counts["inserted"] = _bounded_count(inserted)
        except EmployeeFixtureContractError:
            reason = "insert_count_invalid"
            journal.record(phase="insert", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason) from None
        if counts["inserted"] != 1:
            reason = "insert_count_invalid"
            journal.record(phase="insert", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason)
        journal.record(phase="insert", state="succeeded")

        journal.record(phase="verify", state="started")
        try:
            verified = repository.count_by_fingerprint(fixture)
        except Exception:
            reason = "repository_failure"
            journal.record(phase="verify", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason) from None
        try:
            counts["verified"] = _bounded_count(verified)
        except EmployeeFixtureContractError:
            reason = "fingerprint_mismatch"
            journal.record(phase="verify", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason) from None
        if counts["verified"] != 1:
            reason = "fingerprint_mismatch"
            journal.record(phase="verify", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason)
        journal.record(phase="verify", state="succeeded")

        journal.record(phase="consumer", state="started")
        try:
            consumer(fixture)
        except Exception:
            reason = "consumer_failure"
            journal.record(phase="consumer", state="failed", reason=reason)
            raise EmployeeFixtureContractError(reason) from None
        journal.record(phase="consumer", state="succeeded")
        status = "passed"
    except EmployeeFixtureContractError as exc:
        if reason == "none":
            reason = _bounded_reason(str(exc))
        status = "failed"
    except Exception:
        reason = "repository_failure"
        status = "failed"
    finally:
        if insert_started:
            cleanup_status, cleanup_reason = _cleanup_fixture(
                repository=repository,
                fixture=fixture,
                journal=journal,
                counts=counts,
            )
            if cleanup_status == "failed_cleanup_required":
                status = cleanup_status
                reason = cleanup_reason

    return _finish(
        journal=journal,
        evidence_path=evidence_path,
        run_id=run_id,
        fixture=fixture,
        counts=counts,
        status=status,
        reason=reason,
    )


def validate_evidence(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    expected = {
        "contractHash",
        "contractVersion",
        "counts",
        "fieldNames",
        "fixtureFingerprintPersisted",
        "identifierPersisted",
        "metadataResultSha256",
        "nonRealIdentifier",
        "reason",
        "runId",
        "schemaVersion",
        "status",
        "synthetic",
        "valuesPersisted",
        "workPackageId",
    }
    if set(value) != expected:
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    status = value.get("status")
    reason = value.get("reason")
    counts = value.get("counts")
    if (
        value.get("schemaVersion") != SCHEMA_VERSION
        or value.get("contractVersion") != CONTRACT_VERSION
        or value.get("contractHash") != _contract_hash()
        or value.get("workPackageId") != WORK_PACKAGE_ID
        or value.get("metadataResultSha256") != METADATA_RESULT_SHA256
        or value.get("fieldNames") != list(FIELD_NAMES)
        or value.get("synthetic") is not True
        or value.get("nonRealIdentifier") is not True
        or value.get("identifierPersisted") is not False
        or value.get("valuesPersisted") is not False
        or value.get("fixtureFingerprintPersisted") is not False
        or status not in _STATUSES
        or reason not in _REASONS
        or not isinstance(value.get("runId"), str)
        or not isinstance(counts, dict)
    ):
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    _validate_run_id(cast(str, value["runId"]))
    expected_counts = {
        "deleted",
        "existingRowsModified",
        "inserted",
        "preexisting",
        "remaining",
        "resumeCount",
        "retryCount",
        "verified",
    }
    if set(counts) != expected_counts or any(
        type(counts[key]) is not int or cast(int, counts[key]) < 0 for key in expected_counts
    ):
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    if counts["existingRowsModified"] != 0 or counts["retryCount"] != 0 or counts["resumeCount"] != 0:
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    if status == "passed" and (
        reason != "none"
        or counts["preexisting"] != 0
        or counts["inserted"] != 1
        or counts["verified"] != 1
        or counts["deleted"] != 1
        or counts["remaining"] != 0
    ):
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    if status != "passed" and reason == "none":
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    if status == "failed_cleanup_required" and reason not in {
        "cleanup_count_invalid",
        "cleanup_verification_failed",
        "repository_failure",
    }:
        raise EmployeeFixtureContractError("employee.fixture_evidence_invalid")
    return cast(Mapping[str, object], value)


def validate_lifecycle(path: Path) -> tuple[Mapping[str, object], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid") from exc
    if len(lines) < 3 or len(lines) > 15:
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    records: list[Mapping[str, object]] = []
    for sequence, line in enumerate(lines, start=1):
        value = _loads_strict_json(line)
        if set(value) != {
            "contractVersion",
            "phase",
            "reason",
            "runId",
            "sequence",
            "state",
        }:
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        phase = value.get("phase")
        state = value.get("state")
        reason = value.get("reason")
        run_id = value.get("runId")
        if (
            value.get("contractVersion") != CONTRACT_VERSION
            or phase not in _PHASES
            or state not in {"started", "succeeded", "failed"}
            or reason not in _REASONS
            or value.get("sequence") != sequence
            or not isinstance(run_id, str)
        ):
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        _validate_run_id(run_id)
        if state == "started" and reason != "none":
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        if state == "succeeded" and reason != "none":
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        if state == "failed" and reason == "none":
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        records.append(cast(Mapping[str, object], value))
    run_ids = {cast(str, record["runId"]) for record in records}
    if len(run_ids) != 1:
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    if records[0]["phase"] != "run" or records[0]["state"] != "started":
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    if records[-1]["phase"] != "run" or records[-1]["state"] not in {
        "succeeded",
        "failed",
    }:
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    cursor = 1
    seen_phases: list[str] = []
    terminal_states: list[str] = []
    while cursor < len(records) - 1:
        started = records[cursor]
        if started["phase"] == "run" or started["state"] != "started":
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        if cursor + 1 >= len(records) - 1:
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        terminal = records[cursor + 1]
        if terminal["phase"] != started["phase"] or terminal["state"] not in {
            "succeeded",
            "failed",
        }:
            raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
        seen_phases.append(cast(str, started["phase"]))
        terminal_states.append(cast(str, terminal["state"]))
        cursor += 2
    phase_indexes = [_PHASE_ORDER.index(phase) for phase in seen_phases]
    if len(set(seen_phases)) != len(seen_phases) or phase_indexes != sorted(phase_indexes):
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    if records[-1]["state"] == "succeeded" and (
        tuple(seen_phases) != _PHASE_ORDER or any(state != "succeeded" for state in terminal_states)
    ):
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    if records[-1]["state"] == "failed" and not any(
        state == "failed" for state in terminal_states
    ):
        raise EmployeeFixtureContractError("employee.fixture_lifecycle_invalid")
    return tuple(records)


def _cleanup_fixture(
    *,
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    journal: EmployeeFixtureLifecycleJournal,
    counts: dict[str, int],
) -> tuple[Literal["clean", "failed_cleanup_required"], str]:
    try:
        journal.record(phase="cleanup_delete", state="started")
        present_value = repository.count_by_fingerprint(fixture)
    except Exception:
        _record_failure_best_effort(journal, "cleanup_delete", "repository_failure")
        return "failed_cleanup_required", "repository_failure"
    try:
        present = _bounded_count(present_value)
    except EmployeeFixtureContractError:
        journal.record(
            phase="cleanup_delete", state="failed", reason="cleanup_count_invalid"
        )
        return "failed_cleanup_required", "cleanup_count_invalid"
    try:
        if present == 0:
            counts["deleted"] = 0
        elif present == 1:
            deleted = repository.delete_by_fingerprint(fixture)
            try:
                counts["deleted"] = _bounded_count(deleted)
            except EmployeeFixtureContractError:
                journal.record(
                    phase="cleanup_delete",
                    state="failed",
                    reason="cleanup_count_invalid",
                )
                return "failed_cleanup_required", "cleanup_count_invalid"
            if counts["deleted"] != 1:
                journal.record(
                    phase="cleanup_delete",
                    state="failed",
                    reason="cleanup_count_invalid",
                )
                return "failed_cleanup_required", "cleanup_count_invalid"
        else:
            journal.record(
                phase="cleanup_delete", state="failed", reason="cleanup_count_invalid"
            )
            return "failed_cleanup_required", "cleanup_count_invalid"
        journal.record(phase="cleanup_delete", state="succeeded")
    except Exception:
        _record_failure_best_effort(journal, "cleanup_delete", "repository_failure")
        return "failed_cleanup_required", "repository_failure"
    try:
        journal.record(phase="cleanup_verify", state="started")
        counts["remaining"] = _bounded_count(
            repository.count_by_identifier(fixture.identifier)
        )
        if counts["remaining"] != 0:
            journal.record(
                phase="cleanup_verify",
                state="failed",
                reason="cleanup_verification_failed",
            )
            return "failed_cleanup_required", "cleanup_verification_failed"
        journal.record(phase="cleanup_verify", state="succeeded")
        return "clean", "none"
    except Exception:
        _record_failure_best_effort(journal, "cleanup_verify", "repository_failure")
        return "failed_cleanup_required", "repository_failure"


def _finish(
    *,
    journal: EmployeeFixtureLifecycleJournal,
    evidence_path: Path,
    run_id: str,
    fixture: EmployeeFixtureSpec,
    counts: Mapping[str, int],
    status: Literal["passed", "failed", "failed_cleanup_required"],
    reason: str,
) -> EmployeeFixtureExecution:
    terminal_state: Literal["succeeded", "failed"] = (
        "succeeded" if status == "passed" else "failed"
    )
    journal.record(phase="run", state=terminal_state, reason=reason)
    validate_lifecycle(journal.path)
    evidence = {
        "contractHash": _contract_hash(),
        "contractVersion": CONTRACT_VERSION,
        "counts": {
            **counts,
            "existingRowsModified": 0,
        },
        "fieldNames": list(FIELD_NAMES),
        "fixtureFingerprintPersisted": False,
        "identifierPersisted": False,
        "metadataResultSha256": METADATA_RESULT_SHA256,
        "nonRealIdentifier": True,
        "reason": reason,
        "runId": run_id,
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "synthetic": True,
        "valuesPersisted": False,
        "workPackageId": WORK_PACKAGE_ID,
    }
    validate_evidence(evidence)
    _write_exclusive_json(evidence_path, evidence)
    return EmployeeFixtureExecution(
        status=status,
        reason=reason,
        fixture=fixture,
        evidence=cast(Mapping[str, object], evidence),
    )


def _contract_hash() -> str:
    contract = {
        "contractVersion": CONTRACT_VERSION,
        "fieldNames": list(FIELD_NAMES),
        "fixtureTemplateSha256": hashlib.sha256(
            _canonical_json(_FIXED_TEMPLATE).encode()
        ).hexdigest(),
        "metadataResultSha256": METADATA_RESULT_SHA256,
        "retryAllowed": False,
        "resumeAllowed": False,
    }
    return hashlib.sha256(_canonical_json(contract).encode()).hexdigest()


def _load_strict_json(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise EmployeeFixtureContractError("employee.fixture_json_invalid") from exc
    return _loads_strict_json(raw)


def _loads_strict_json(raw: str) -> dict[str, object]:
    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise EmployeeFixtureContractError("employee.fixture_json_invalid")
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate)
    except json.JSONDecodeError as exc:
        raise EmployeeFixtureContractError("employee.fixture_json_invalid") from exc
    if not isinstance(value, dict):
        raise EmployeeFixtureContractError("employee.fixture_json_invalid")
    return value


def _write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_canonical_json(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _bounded_count(value: object) -> int:
    if type(value) is not int or value < 0 or value > 1:
        raise EmployeeFixtureContractError("employee.fixture_repository_count_invalid")
    return value


def _bounded_reason(value: str) -> str:
    return value if value in _REASONS else "repository_failure"


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise EmployeeFixtureContractError("employee.fixture_run_id_invalid")


def _record_failure_best_effort(
    journal: EmployeeFixtureLifecycleJournal, phase: str, reason: str
) -> None:
    try:
        journal.record(phase=phase, state="failed", reason=reason)
    except Exception:
        return
