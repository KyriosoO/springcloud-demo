from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, cast

from tests.integration.adapters.employee.employee_test_data_fixture import (
    EmployeeFixtureRepository,
    EmployeeFixtureSpec,
    build_fixture_spec,
    validate_metadata_result,
)


PREPARATION_WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-06-PREP"
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-06"
GATE_ID: Final = "GATE-049"
RUN_ID: Final = "employee-egress-input-qualification-v6-20260816-candidate-06"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-049"
SEED: Final = "employee-qualification-candidate-06"
PREPARED_AT: Final = "2026-08-16T10:00:00Z"
MAX_DATABASE_SELECTS: Final = 3
MAX_DATABASE_INSERTS: Final = 1
MAX_DATABASE_DELETES: Final = 1
MAX_EMPLOYEE_DETAILS: Final = 1
PHASES: Final = (
    "fixture_precheck",
    "fixture_insert",
    "fixture_verify",
    "employee_detail",
    "cleanup_delete",
    "cleanup_verify",
    "host_validation",
)
HISTORY: Final = (
    (
        "qualification_v5_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v5-20260816-candidate-05.manifest.json",
        "8b44a38ad6a02edd6db64b7c8e5fd02adee67a19ff1e9ef08e2ed3eb82f5ff74",
    ),
    (
        "qualification_v5_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v5-20260816-candidate-05.authorization.json",
        "c8e3a3c5b85994a446fd93e9b7d291a189d36a1016856e4acb8f3969cd2e1d72",
    ),
    (
        "qualification_v5_host_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v5-20260816-candidate-05.host-lifecycle.jsonl",
        "c0e8ef84d1deedb3adaaeca7866e87d278d4112248c775e45739e6dbb72eb51e",
    ),
    (
        "qualification_v5_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v5-20260816-candidate-05.lifecycle.jsonl",
        "442dfc7e88aa6a02689e0431805311e71e384ea19c53761da609b72b88ea318f",
    ),
    (
        "qualification_v5_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v5-20260816-candidate-05.result.json",
        "f51915e067433dace3c0019dd85e99e7dde443204089fea6d078401df24a6690",
    ),
    (
        "qualification_v5_consumed_history_test",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_employee_egress_input_qualification_v5_consumed_history.py",
        "518b6eda0961924075449fed161054d0e6f8dea5c87e02d738c76aa2e2c681ea",
    ),
    (
        "qualification_v4_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v4-20260816-candidate-04.manifest.json",
        "7dcae58a2a503a97fe89de0d01e63cb0450ccb0dd5945e4da5947d2df0875bb9",
    ),
    (
        "qualification_v4_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v4-20260816-candidate-04.authorization.json",
        "e49c063ef6d93ab1395179fb5ae4026fc10da577108b676db0b5762f68274d98",
    ),
    (
        "qualification_v4_host_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v4-20260816-candidate-04.host-lifecycle.jsonl",
        "73bd37aaec1c3c57d7debea5f1120cd3cff828057bcaee84afbdb4495658472a",
    ),
    (
        "qualification_v4_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v4-20260816-candidate-04.lifecycle.jsonl",
        "aa2479fc8051cb4741f9826b81521583285ede692d31b9c6bed01bf1b2a922c3",
    ),
    (
        "qualification_v4_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v4-20260816-candidate-04.result.json",
        "757bd4840143bbe5158facec89f7035cf72f99eac88b4c345d70cbc8ea0b5975",
    ),
    (
        "qualification_v4_history_test",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_employee_egress_input_qualification_v4_history.py",
        "e43e9c9a9353cd77ea7fa907ddd98ad8b0971a4c4c4853acde3683b32d570eda",
    ),
    (
        "qualification_v3_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v3-20260814-candidate-03.manifest.json",
        "495063a328af6a233f5600bd4efff31fdae5ab4e28aad8287bfce194051680dd",
    ),
    (
        "qualification_v3_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v3-20260814-candidate-03.authorization.json",
        "b772119e66b98ceec73738653a0033f6e2c1752e8fae8944f8eabea8d7ad74ad",
    ),
    (
        "qualification_v3_pre_sql_failure",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v3-20260814-candidate-03.pre-sql-failure.json",
        "bfe4976f9a962bd1f7b9ed870176faefc4fbb742bf9b991cb07bba866a218d77",
    ),
    (
        "qualification_v2_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v2-20260814-candidate-02.manifest.json",
        "6d853ecee412a734f111d1d30740a703fe0343593560b7b01ed4c5194dfdb66f",
    ),
    (
        "qualification_v2_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v2-20260814-candidate-02.authorization.json",
        "c49f3bc23b6131506431b98697bb9dd35bc2d33200b29a1e507d845c95b587e1",
    ),
    (
        "qualification_v2_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v2-20260814-candidate-02.lifecycle.jsonl",
        "570295951f8bf1a109156c017c30609ca548bfba3f021bff4cd2825f978ac231",
    ),
    (
        "qualification_v2_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v2-20260814-candidate-02.result.json",
        "7534b1d04a1512720dcbee1fe630114fb1f08bf9c3615dec1d2cb18bec4d5054",
    ),
    (
        "fixture_v1_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-synthetic-fixture-v1-20260814-candidate-01.manifest.json",
        "e0c74e5a21d4b80c292cf20266227f7c8f1a11037d1816a6513f6de604e98b11",
    ),
    (
        "fixture_v1_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-synthetic-fixture-v1-20260814-candidate-01.authorization.json",
        "00e44c6df2d04edbc03ee9eaa51541041b6263a73bc91c3fdf9ed57bf11c3a2f",
    ),
    (
        "fixture_v1_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-synthetic-fixture-v1-20260814-candidate-01.lifecycle.jsonl",
        "4d5ab81e68d24ac76a7c1d6f7b1a57204b7cb81c99f40f93afe444f4077f5b6c",
    ),
    (
        "fixture_v1_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-synthetic-fixture-v1-20260814-candidate-01.result.json",
        "f0003ec559fa4606edda2982f0ae6878bfa066262168236128705d0c40aa0e4a",
    ),
)
ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v6.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_egress_input_qualification_v6.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_egress_input_qualification_v6_host.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_egress_input_qualification_v6_history.py",
        "agent-runtime/tests/integration/adapters/employee/test_real_employee_egress_input_qualification_v6.py",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-input-qualification-v6-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-input-qualification-v6-result.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-input-qualification-v6-host-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-input-qualification-v6-pre-sql-failure.schema.json",
        "agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v6_host.py",
        "agent-runtime/scripts/run-employee-egress-input-qualification-candidate-06.ps1",
        "employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressInputQualificationV6LiveIntegrationTest.java",
    }
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STATUSES = {"qualified", "not_qualified", "failed", "failed_cleanup_required"}
_REASONS = {
    "none",
    "identifier_conflict",
    "database_operation_failed",
    "insert_count_invalid",
    "fingerprint_mismatch",
    "employee_request_failed",
    "employee_result_invalid",
    "egress_projection_invalid",
    "cleanup_count_invalid",
    "cleanup_verification_failed",
    "host_execution_failed",
    "log_leak_detected",
}
_RESULT_KEYS = {
    "schemaVersion",
    "preparationWorkPackageId",
    "workPackageId",
    "gateId",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "status",
    "reason",
    "fieldPresence",
    "counts",
    "safety",
    "history",
    "lifecycleSha256",
}


class QualificationV6Error(ValueError):
    pass


def _invalid() -> NoReturn:
    raise QualificationV6Error("employee.qualification_v6_invalid")


@dataclass(frozen=True, slots=True)
class QualificationOutcome:
    codec_fields: Mapping[str, bool]
    required_user_fields: Mapping[str, bool]
    egress_allowed: bool

    @classmethod
    def qualified(cls) -> QualificationOutcome:
        return cls(
            codec_fields={
                "idCardNo": True,
                "chineseName": True,
                "position": True,
                "workBaseSi": True,
            },
            required_user_fields={"employeeIdMasked": True, "chineseName": True},
            egress_allowed=True,
        )


@dataclass(frozen=True, slots=True)
class CandidateExecution:
    status: str
    reason: str
    result: Mapping[str, Any]


class LifecycleJournal:
    def __init__(self, path: Path, *, manifest_sha256: str) -> None:
        if not _SHA.fullmatch(manifest_sha256) or path.exists():
            _invalid()
        self.path = path
        self.manifest_sha256 = manifest_sha256
        self.sequence = 0
        self.terminal = False
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        self.record(phase="run", state="started")

    @classmethod
    def open_existing(cls, path: Path, *, manifest_sha256: str) -> LifecycleJournal:
        records = validate_lifecycle(
            path, manifest_sha256=manifest_sha256, allow_pending=True
        )
        instance = cls.__new__(cls)
        instance.path = path
        instance.manifest_sha256 = manifest_sha256
        instance.sequence = len(records)
        instance.terminal = False
        return instance

    def record(
        self,
        *,
        phase: str,
        state: Literal["started", "succeeded", "failed"],
        reason: str = "none",
    ) -> None:
        if (
            self.terminal
            or phase not in {"run", *PHASES}
            or reason not in _REASONS
            or (state == "started" and reason != "none")
            or (state == "succeeded" and reason != "none" and phase != "run")
            or (state == "failed" and reason == "none")
        ):
            _invalid()
        if phase == "run" and state != "started":
            self.terminal = True
        self.sequence += 1
        record = {
            "schemaVersion": 6,
            "workPackageId": WORK_PACKAGE_ID,
            "gateId": GATE_ID,
            "runId": RUN_ID,
            "manifestSha256": self.manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "sequence": self.sequence,
            "phase": phase,
            "state": state,
            "reason": reason,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_canonical(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_history(repository_root: Path) -> None:
    for _, relative, expected in HISTORY:
        path = repository_root / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise QualificationV6Error("employee.qualification_v6_history_mismatch")


def execute_fake_candidate(
    *,
    repository: EmployeeFixtureRepository,
    metadata_result_path: Path,
    lifecycle_path: Path,
    result_path: Path,
    manifest_sha256: str,
    detail: Callable[[EmployeeFixtureSpec], QualificationOutcome],
) -> CandidateExecution:
    validate_metadata_result(metadata_result_path)
    if lifecycle_path.exists() or result_path.exists():
        raise QualificationV6Error("employee.qualification_v6_output_exists")
    fixture = build_fixture_spec(SEED)
    journal = LifecycleJournal(lifecycle_path, manifest_sha256=manifest_sha256)
    counts = _empty_counts()
    presence = _empty_presence()
    status = "failed"
    reason = "none"
    insert_started = False
    try:
        _pair(journal, "fixture_precheck", lambda: _precheck(repository, fixture, counts))
        insert_started = True
        _pair(journal, "fixture_insert", lambda: _insert(repository, fixture, counts))
        _pair(journal, "fixture_verify", lambda: _verify(repository, fixture, counts))

        def call_detail() -> None:
            counts["employeeDetailStarted"] += 1
            try:
                outcome = detail(fixture)
            finally:
                counts["employeeDetailTerminal"] += 1
            _apply_outcome(outcome, presence)

        _pair(journal, "employee_detail", call_detail)
        if not all(presence["codec"].values()) or not all(
            presence["requiredUser"].values()
        ):
            status, reason = "not_qualified", "employee_result_invalid"
        elif not presence["egressAllowed"]:
            status, reason = "not_qualified", "egress_projection_invalid"
        else:
            status, reason = "qualified", "none"
    except QualificationV6Error as failure:
        reason = _bounded_reason(str(failure))
    except Exception:
        reason = "employee_request_failed" if counts["employeeDetailStarted"] else "database_operation_failed"
    finally:
        if insert_started:
            cleanup_reason = _cleanup(repository, fixture, journal, counts)
            if cleanup_reason != "none":
                status, reason = "failed_cleanup_required", cleanup_reason
    pending_path = result_path.with_suffix(".pending.json")
    write_exclusive_json(
        pending_path,
        {
            "schemaVersion": 6,
            "status": status,
            "reason": reason,
            "fieldPresence": presence,
            "counts": counts,
        },
    )
    result = finalize_live_candidate(
        lifecycle_path=lifecycle_path,
        pending_path=pending_path,
        result_path=result_path,
        manifest_sha256=manifest_sha256,
        host_exit_code=0,
        log_leak_count=0,
    )
    return CandidateExecution(
        status=cast(str, result["status"]),
        reason=cast(str, result["reason"]),
        result=result,
    )


def _pair(journal: LifecycleJournal, phase: str, operation: Callable[[], None]) -> None:
    journal.record(phase=phase, state="started")
    try:
        operation()
    except QualificationV6Error as failure:
        journal.record(phase=phase, state="failed", reason=_bounded_reason(str(failure)))
        raise
    except Exception as failure:
        reason = "employee_request_failed" if phase == "employee_detail" else "database_operation_failed"
        journal.record(phase=phase, state="failed", reason=reason)
        raise QualificationV6Error(reason) from failure
    journal.record(phase=phase, state="succeeded")


def _precheck(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseSelectStarted"] += 1
    try:
        counts["preexisting"] = _count(
            repository.count_by_identifier(fixture.identifier),
            reason="database_operation_failed",
        )
    finally:
        counts["databaseSelectTerminal"] += 1
    if counts["preexisting"] != 0:
        raise QualificationV6Error("identifier_conflict")


def _insert(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseInsertStarted"] += 1
    try:
        counts["inserted"] = _count(
            repository.insert(fixture), reason="insert_count_invalid"
        )
    finally:
        counts["databaseInsertTerminal"] += 1
    if counts["inserted"] != 1:
        raise QualificationV6Error("insert_count_invalid")


def _verify(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseSelectStarted"] += 1
    try:
        counts["verified"] = _count(
            repository.count_by_fingerprint(fixture), reason="fingerprint_mismatch"
        )
    finally:
        counts["databaseSelectTerminal"] += 1
    if counts["verified"] != 1:
        raise QualificationV6Error("fingerprint_mismatch")


def _cleanup(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    journal: LifecycleJournal,
    counts: dict[str, int],
) -> str:
    try:
        _pair(journal, "cleanup_delete", lambda: _delete(repository, fixture, counts))
        _pair(journal, "cleanup_verify", lambda: _verify_deleted(repository, fixture, counts))
    except QualificationV6Error as failure:
        return _bounded_reason(str(failure))
    return "none"


def _delete(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseDeleteStarted"] += 1
    try:
        counts["deleted"] = _count(
            repository.delete_by_fingerprint(fixture), reason="cleanup_count_invalid"
        )
    finally:
        counts["databaseDeleteTerminal"] += 1
    if counts["deleted"] != 1:
        raise QualificationV6Error("cleanup_count_invalid")


def _verify_deleted(
    repository: EmployeeFixtureRepository,
    fixture: EmployeeFixtureSpec,
    counts: dict[str, int],
) -> None:
    counts["databaseSelectStarted"] += 1
    try:
        counts["remaining"] = _count(
            repository.count_by_identifier(fixture.identifier),
            reason="cleanup_verification_failed",
        )
    finally:
        counts["databaseSelectTerminal"] += 1
    if counts["remaining"] != 0:
        raise QualificationV6Error("cleanup_verification_failed")


def _apply_outcome(
    outcome: QualificationOutcome, presence: dict[str, Any]
) -> None:
    if set(outcome.codec_fields) != {"idCardNo", "chineseName", "position", "workBaseSi"}:
        _invalid()
    if set(outcome.required_user_fields) != {"employeeIdMasked", "chineseName"}:
        _invalid()
    if any(type(value) is not bool for value in outcome.codec_fields.values()) or any(
        type(value) is not bool for value in outcome.required_user_fields.values()
    ) or type(outcome.egress_allowed) is not bool:
        _invalid()
    presence["codec"] = dict(outcome.codec_fields)
    presence["requiredUser"] = dict(outcome.required_user_fields)
    presence["egressAllowed"] = outcome.egress_allowed


def _empty_counts() -> dict[str, int]:
    return {
        "databaseSelectStarted": 0,
        "databaseSelectTerminal": 0,
        "databaseInsertStarted": 0,
        "databaseInsertTerminal": 0,
        "databaseDeleteStarted": 0,
        "databaseDeleteTerminal": 0,
        "preexisting": 0,
        "inserted": 0,
        "verified": 0,
        "deleted": 0,
        "remaining": 0,
        "employeeDetailStarted": 0,
        "employeeDetailTerminal": 0,
        "otherEmployeeEndpoints": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }


def _empty_presence() -> dict[str, Any]:
    return {
        "codec": {key: False for key in ("idCardNo", "chineseName", "position", "workBaseSi")},
        "requiredUser": {key: False for key in ("employeeIdMasked", "chineseName")},
        "egressAllowed": False,
    }


def _build_result(
    *,
    status: str,
    reason: str,
    presence: Mapping[str, object],
    counts: Mapping[str, int],
    lifecycle_path: Path,
    manifest_sha256: str,
    log_leak_count: int = 0,
    raw_logs_deleted: bool = True,
) -> dict[str, object]:
    return {
        "schemaVersion": 6,
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "status": status,
        "reason": reason,
        "fieldPresence": dict(presence),
        "counts": dict(counts),
        "safety": {
            "synthetic": True,
            "nonRealIdentifier": True,
            "identifierPersisted": False,
            "jwtPersisted": False,
            "fieldValuesPersisted": False,
            "rawResponsePersisted": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "existingRowsModified": 0,
            "logLeakCount": log_leak_count,
            "rawLogsDeleted": raw_logs_deleted,
        },
        "history": [
            {"kind": kind, "path": path, "sha256": digest}
            for kind, path, digest in HISTORY
        ],
        "lifecycleSha256": sha256_file(lifecycle_path),
    }


def validate_lifecycle(
    path: Path,
    *,
    manifest_sha256: str,
    allow_pending: bool = False,
) -> list[dict[str, Any]]:
    if not path.is_file() or not _SHA.fullmatch(manifest_sha256):
        _invalid()
    records = [_loads_strict(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if not records:
        _invalid()
    common = {
        "schemaVersion": 6,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }
    for sequence, record in enumerate(records, 1):
        if set(record) != {*common, "sequence", "phase", "state", "reason"}:
            _invalid()
        if any(record[key] != value for key, value in common.items()):
            _invalid()
        if record["sequence"] != sequence or record["phase"] not in {"run", *PHASES}:
            _invalid()
        state = record["state"]
        reason = record["reason"]
        if (
            state not in {"started", "succeeded", "failed"}
            or reason not in _REASONS
            or (state == "started" and reason != "none")
            or (state == "succeeded" and reason != "none" and record["phase"] != "run")
            or (state == "failed" and reason == "none")
        ):
            _invalid()
    if records[0]["phase"] != "run" or records[0]["state"] != "started":
        _invalid()
    terminal = records[-1]["phase"] == "run" and records[-1]["state"] != "started"
    if terminal == allow_pending:
        _invalid()
    middle = records[1:-1] if terminal else records[1:]
    if len(middle) % 2:
        _invalid()
    observed: list[str] = []
    for index in range(0, len(middle), 2):
        started, ended = middle[index : index + 2]
        if started["phase"] != ended["phase"] or started["state"] != "started" or ended["state"] == "started":
            _invalid()
        observed.append(cast(str, started["phase"]))
    if len(observed) != len(set(observed)) or [PHASES.index(item) for item in observed] != sorted(PHASES.index(item) for item in observed):
        _invalid()
    if terminal and (not observed or observed[-1] != "host_validation"):
        _invalid()
    return records


def validate_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _RESULT_KEYS:
        _invalid()
    counts = value.get("counts")
    presence = value.get("fieldPresence")
    safety = value.get("safety")
    if (
        value.get("schemaVersion") != 6
        or value.get("preparationWorkPackageId") != PREPARATION_WORK_PACKAGE_ID
        or value.get("workPackageId") != WORK_PACKAGE_ID
        or value.get("gateId") != GATE_ID
        or value.get("runId") != RUN_ID
        or not isinstance(value.get("manifestSha256"), str)
        or not _SHA.fullmatch(cast(str, value["manifestSha256"]))
        or value.get("authorizationReference") != AUTHORIZATION_REFERENCE
        or value.get("status") not in _STATUSES
        or value.get("reason") not in _REASONS
        or not isinstance(counts, dict)
        or set(counts) != set(_empty_counts())
        or not isinstance(presence, dict)
        or set(presence) != {"codec", "requiredUser", "egressAllowed"}
        or not isinstance(safety, dict)
        or not isinstance(value.get("history"), list)
        or value.get("history") != [
            {"kind": kind, "path": path, "sha256": digest}
            for kind, path, digest in HISTORY
        ]
        or not isinstance(value.get("lifecycleSha256"), str)
        or not _SHA.fullmatch(cast(str, value["lifecycleSha256"]))
    ):
        _invalid()
    if any(type(counts[key]) is not int or counts[key] < 0 for key in counts):
        _invalid()
    if (
        counts["databaseSelectStarted"] > MAX_DATABASE_SELECTS
        or counts["databaseSelectStarted"] != counts["databaseSelectTerminal"]
        or counts["databaseInsertStarted"] > MAX_DATABASE_INSERTS
        or counts["databaseInsertStarted"] != counts["databaseInsertTerminal"]
        or counts["databaseDeleteStarted"] > MAX_DATABASE_DELETES
        or counts["databaseDeleteStarted"] != counts["databaseDeleteTerminal"]
        or counts["employeeDetailStarted"] > MAX_EMPLOYEE_DETAILS
        or counts["employeeDetailStarted"] != counts["employeeDetailTerminal"]
        or any(counts[key] != 0 for key in ("otherEmployeeEndpoints", "modelCalls", "retryCount", "resumeCount"))
        or any(
            counts[key] > 1
            for key in ("preexisting", "inserted", "verified", "deleted", "remaining")
        )
    ):
        _invalid()
    _validate_presence(presence)
    if set(safety) != {
        "synthetic",
        "nonRealIdentifier",
        "identifierPersisted",
        "jwtPersisted",
        "fieldValuesPersisted",
        "rawResponsePersisted",
        "llmApiKeyRead",
        "modelOutbound",
        "existingRowsModified",
        "logLeakCount",
        "rawLogsDeleted",
    } or any(
        safety[key] is not False
        for key in (
            "identifierPersisted",
            "jwtPersisted",
            "fieldValuesPersisted",
            "rawResponsePersisted",
            "llmApiKeyRead",
            "modelOutbound",
        )
    ) or safety["synthetic"] is not True or safety["nonRealIdentifier"] is not True or safety["existingRowsModified"] != 0 or type(safety["logLeakCount"]) is not int or safety["logLeakCount"] < 0 or safety["rawLogsDeleted"] is not True:
        _invalid()
    status = value["status"]
    reason = value["reason"]
    cleaned = counts["deleted"] == 1 and counts["remaining"] == 0
    fixture_completed = (
        counts["databaseSelectStarted"] == MAX_DATABASE_SELECTS
        and counts["databaseInsertStarted"] == MAX_DATABASE_INSERTS
        and counts["databaseDeleteStarted"] == MAX_DATABASE_DELETES
        and counts["preexisting"] == 0
        and counts["inserted"] == 1
        and counts["verified"] == 1
        and cleaned
    )
    if status == "qualified" and (
        reason != "none"
        or not fixture_completed
        or counts["employeeDetailStarted"] != 1
        or not all(presence["codec"].values())
        or not all(presence["requiredUser"].values())
        or presence["egressAllowed"] is not True
    ):
        _invalid()
    if status == "not_qualified" and (
        reason not in {"employee_result_invalid", "egress_projection_invalid"}
        or not fixture_completed
        or counts["employeeDetailStarted"] != 1
        or counts["employeeDetailTerminal"] != 1
        or (
            reason == "employee_result_invalid"
            and all(presence["codec"].values())
            and all(presence["requiredUser"].values())
        )
        or (
            reason == "egress_projection_invalid"
            and (
                not all(presence["codec"].values())
                or not all(presence["requiredUser"].values())
                or presence["egressAllowed"] is not False
            )
        )
    ):
        _invalid()
    if status == "failed_cleanup_required" and (
        reason
        not in {
            "cleanup_count_invalid",
            "cleanup_verification_failed",
            "database_operation_failed",
        }
        or counts["databaseInsertStarted"] != 1
    ):
        _invalid()
    if status == "failed" and (reason == "none" or (counts["databaseInsertStarted"] and not cleaned)):
        _invalid()
    return cast(dict[str, Any], value)


def _validate_presence(value: Mapping[str, Any]) -> None:
    codec = value.get("codec")
    required = value.get("requiredUser")
    if (
        not isinstance(codec, dict)
        or set(codec) != {"idCardNo", "chineseName", "position", "workBaseSi"}
        or not isinstance(required, dict)
        or set(required) != {"employeeIdMasked", "chineseName"}
        or any(type(item) is not bool for item in codec.values())
        or any(type(item) is not bool for item in required.values())
        or type(value.get("egressAllowed")) is not bool
    ):
        _invalid()


def validate_manifest(value: object, *, repository_root: Path) -> dict[str, Any]:
    expected = {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "preparedAt",
        "budgets",
        "outputPaths",
        "history",
        "assetHashes",
    }
    if not isinstance(value, dict) or set(value) != expected:
        _invalid()
    if (
        value["schemaVersion"] != 6
        or value["status"] != "prepared_unconsumed"
        or value["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["preparedAt"] != PREPARED_AT
        or value["budgets"] != {"databaseSelect": 3, "databaseInsert": 1, "databaseDelete": 1, "employeeDetail": 1, "model": 0, "retry": 0, "resume": 0}
        or value["outputPaths"] != {
            "hostLifecycle": f"agent-runtime/tests/integration/adapters/employee/evidence/{RUN_ID}.host-lifecycle.jsonl",
            "lifecycle": f"agent-runtime/tests/integration/adapters/employee/evidence/{RUN_ID}.lifecycle.jsonl",
            "result": f"agent-runtime/tests/integration/adapters/employee/evidence/{RUN_ID}.result.json",
            "preSqlFailure": f"agent-runtime/tests/integration/adapters/employee/evidence/{RUN_ID}.pre-sql-failure.json",
        }
        or value["history"] != [{"kind": kind, "path": path, "sha256": digest} for kind, path, digest in HISTORY]
    ):
        _invalid()
    root = repository_root.resolve()
    assets = value["assetHashes"]
    if not isinstance(assets, list) or len(assets) != len(ASSET_PATHS):
        _invalid()
    seen: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {"path", "sha256"} or asset["path"] not in ASSET_PATHS:
            _invalid()
        path = (root / asset["path"]).resolve()
        if asset["path"] in seen or not path.is_file() or sha256_file(path) != asset["sha256"]:
            _invalid()
        seen.add(asset["path"])
    return cast(dict[str, Any], value)


def validate_authorization(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    expected = {
        "schemaVersion",
        "status",
        "workPackageId",
        "gateId",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "budgets",
        "liveExecutionAuthorized",
        "confirmedBy",
        "preparedAt",
    }
    if not isinstance(value, dict) or set(value) != expected:
        _invalid()
    if (
        value["schemaVersion"] != 6
        or value["status"] != "prepared_unconsumed"
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["manifestSha256"] != manifest_sha256
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["budgets"] != {"databaseSelect": 3, "databaseInsert": 1, "databaseDelete": 1, "employeeDetail": 1, "model": 0, "retry": 0, "resume": 0}
        or value["liveExecutionAuthorized"] is not False
        or value["confirmedBy"] != "project-maintainer-pending-gate-049-live-authorization"
        or value["preparedAt"] != PREPARED_AT
    ):
        _invalid()
    return cast(dict[str, Any], value)


def build_asset_hashes(repository_root: Path, paths: Sequence[str]) -> list[dict[str, str]]:
    return [
        {"path": path, "sha256": sha256_file(repository_root / path)}
        for path in sorted(paths)
    ]


def load_strict_json(path: Path) -> dict[str, Any]:
    return _loads_strict(path.read_text(encoding="utf-8"))


def _loads_strict(raw: str) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                _invalid()
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError):
        _invalid()
    if not isinstance(value, dict):
        _invalid()
    return value


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write((_canonical(value) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _count(value: object, *, reason: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise QualificationV6Error(reason)
    return value


def _bounded_reason(value: str) -> str:
    return value if value in _REASONS else "database_operation_failed"


def finalize_live_candidate(
    *,
    lifecycle_path: Path,
    pending_path: Path,
    result_path: Path,
    manifest_sha256: str,
    host_exit_code: int,
    log_leak_count: int,
) -> dict[str, Any]:
    if result_path.exists() or type(host_exit_code) is not int or type(log_leak_count) is not int or log_leak_count < 0:
        _invalid()
    pending = load_strict_json(pending_path)
    if set(pending) != {"schemaVersion", "status", "reason", "fieldPresence", "counts"} or pending["schemaVersion"] != 6:
        _invalid()
    journal = LifecycleJournal.open_existing(
        lifecycle_path, manifest_sha256=manifest_sha256
    )
    status = cast(str, pending["status"])
    reason = cast(str, pending["reason"])
    if status not in _STATUSES or reason not in _REASONS:
        _invalid()
    if status != "failed_cleanup_required":
        if log_leak_count:
            status, reason = "failed", "log_leak_detected"
        elif host_exit_code != 0:
            status, reason = "failed", "host_execution_failed"
    journal.record(phase="host_validation", state="started")
    journal.record(
        phase="host_validation",
        state="succeeded" if host_exit_code == 0 and log_leak_count == 0 else "failed",
        reason=(
            "none"
            if host_exit_code == 0 and log_leak_count == 0
            else ("log_leak_detected" if log_leak_count else "host_execution_failed")
        ),
    )
    journal.record(
        phase="run",
        state="succeeded" if status in {"qualified", "not_qualified"} else "failed",
        reason=reason,
    )
    validate_lifecycle(lifecycle_path, manifest_sha256=manifest_sha256)
    counts = pending["counts"]
    presence = pending["fieldPresence"]
    if not isinstance(counts, dict) or not isinstance(presence, dict):
        _invalid()
    result = _build_result(
        status=status,
        reason=reason,
        presence=presence,
        counts=cast(Mapping[str, int], counts),
        lifecycle_path=lifecycle_path,
        manifest_sha256=manifest_sha256,
        log_leak_count=log_leak_count,
        raw_logs_deleted=True,
    )
    validate_result(result)
    write_exclusive_json(result_path, result)
    return cast(dict[str, Any], result)
