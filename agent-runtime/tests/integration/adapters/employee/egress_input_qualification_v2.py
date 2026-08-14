from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, NoReturn

from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
)


PREPARATION_WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-02-PREP"
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-02"
GATE_ID: Final = "GATE-049"
RUN_ID: Final = "employee-egress-input-qualification-v2-20260814-candidate-02"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-049"
RETIRED_RUN_ID: Final = "employee-egress-input-qualification-v1-20260814-candidate-01"

EMPLOYEE_EGRESS_HISTORY: Final = (
    (
        "candidate01_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.manifest.json",
        "c3cdfacd32797474f68e11758ec094df97a95d56fb0efed9355ccfaa6a145c57",
    ),
    (
        "candidate01_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.authorization.json",
        "52b9075117f3e5f3ea84f1ea3c5da846c7b168f013fc4d8523d7ed52979f416c",
    ),
    (
        "candidate01_environment_diagnostic",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-egress-env-diag-01-20260814T004517Z.json",
        "2bc16cf63f3775d778925a5a5a66cfbae5138401e2f209e8288f4db076598a2c",
    ),
    (
        "candidate01_pre_model_failure",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.pre-model-failure-20260814T005222Z.json",
        "1a55b324fc912ee4e9133c2946183473347eb8e7f3337f8e33286bdf96f0b76f",
    ),
    (
        "candidate02_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.manifest.json",
        "28cd7b04b0700b43e5feed7bdef22e9da0494cd941e2e9f96b698a75b21b03b1",
    ),
    (
        "candidate02_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.authorization.json",
        "6fe6489fb5d32481909b88b860325dbbc35dec0c242d86f106327222e790c971",
    ),
    (
        "candidate02_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.lifecycle.jsonl",
        "15982e15d454795d7052215ad46221b6f85cc26726ca0267a597f6d6002ec679",
    ),
    (
        "candidate02_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.result.json",
        "dd8a5bac1586da4e44cc6a583c07289a91012bc34892f848ffb4a0241ae7561d",
    ),
)

RETIRED_RUN_ASSET_PATHS: Final = (
    "agent-runtime/scripts/run-employee-egress-input-qualification.ps1",
    "agent-runtime/tests/integration/adapters/employee/egress_input_qualification.py",
    "agent-runtime/tests/integration/adapters/employee/"
    "test_employee_egress_input_qualification.py",
    "agent-runtime/tests/integration/adapters/employee/"
    "test_real_employee_egress_input_qualification.py",
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-egress-input-qualification-v1.schema.json",
    "employee-service/src/test/java/com/dylan/employee/live/"
    "EmployeeEgressInputQualificationLiveIntegrationTest.java",
)

REQUIRED_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-employee-egress-input-qualification-candidate-02.ps1",
        "agent-runtime/src/agent_runtime/adapters/employee/codec.py",
        "agent-runtime/src/agent_runtime/adapters/employee/definition.py",
        "agent-runtime/src/agent_runtime/adapters/employee/normalizer.py",
        "agent-runtime/src/agent_runtime/business/user_projection.py",
        "agent-runtime/tests/integration/adapters/employee/egress_input_qualification_v2.py",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_employee_egress_input_qualification_v2.py",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_real_employee_egress_input_qualification_v2.py",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v2-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v2-result.schema.json",
        "employee-service/src/test/java/com/dylan/employee/live/"
        "EmployeeEgressInputQualificationV2LiveIntegrationTest.java",
    }
)


class QualificationV2Error(ValueError):
    pass


class QualificationRunStatus(StrEnum):
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    FAILED = "failed"


class QualificationFailurePhase(StrEnum):
    DATABASE_SELECTION = "database_selection"
    EMPLOYEE_DETAIL = "employee_detail"
    EMPLOYEE_RESULT = "employee_result"
    EGRESS_PROJECTION = "egress_projection"
    CLEANUP = "cleanup"
    INTERNAL = "internal"


class QualificationReason(StrEnum):
    QUALIFIED = "qualified"
    NO_QUALIFIED_INPUT = "employee.no_qualified_input"
    DATABASE_SELECTION_FAILED = "employee.database_selection_failed"
    EMPLOYEE_REQUEST_FAILED = "employee.request_failed"
    EMPLOYEE_RESULT_INVALID = "employee.result_invalid"
    EGRESS_PROJECTION_INVALID = "business.egress_projection_invalid"
    CLEANUP_FAILED = "employee.cleanup_failed"
    LOG_LEAK_DETECTED = "employee.log_leak_detected"
    EVIDENCE_WRITE_FAILED = "employee.evidence_write_failed"
    INTERNAL_FAILURE = "employee.internal_failure"


_FAILURE_REASONS: Final = {
    QualificationFailurePhase.DATABASE_SELECTION: frozenset(
        {
            QualificationReason.NO_QUALIFIED_INPUT,
            QualificationReason.DATABASE_SELECTION_FAILED,
        }
    ),
    QualificationFailurePhase.EMPLOYEE_DETAIL: frozenset(
        {QualificationReason.EMPLOYEE_REQUEST_FAILED}
    ),
    QualificationFailurePhase.EMPLOYEE_RESULT: frozenset(
        {QualificationReason.EMPLOYEE_RESULT_INVALID}
    ),
    QualificationFailurePhase.EGRESS_PROJECTION: frozenset(
        {QualificationReason.EGRESS_PROJECTION_INVALID}
    ),
    QualificationFailurePhase.CLEANUP: frozenset(
        {QualificationReason.CLEANUP_FAILED, QualificationReason.LOG_LEAK_DETECTED}
    ),
    QualificationFailurePhase.INTERNAL: frozenset(
        {QualificationReason.EVIDENCE_WRITE_FAILED, QualificationReason.INTERNAL_FAILURE}
    ),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class QualificationLifecycleSnapshotV2:
    record_count: int
    database_selection_started: int
    database_selection_terminal: int
    database_selection_rows: int
    employee_detail_started: int
    employee_detail_terminal: int
    employee_detail_terminal_status: str | None
    run_status: QualificationRunStatus | None
    failure_phase: QualificationFailurePhase | None
    failure_reason: QualificationReason | None


def _invalid() -> NoReturn:
    raise QualificationV2Error("employee.egress_input_qualification_v2_invalid")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def load_strict_json(path: Path, *, max_bytes: int = 262_144) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError):
        _invalid()
    if type(value) is not dict:
        _invalid()
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _common_record(*, manifest_sha256: str) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }


class QualificationLifecycleJournalV2:
    def __init__(self, path: Path, *, manifest_sha256: str) -> None:
        if not _is_sha256(manifest_sha256):
            _invalid()
        self._path = path
        self._manifest_sha256 = manifest_sha256
        self._database_started = False
        self._database_terminal = False
        self._database_rows = 0
        self._detail_started = False
        self._detail_terminal: str | None = None
        self._run_terminal = False
        self._write_first(
            {
                **_common_record(manifest_sha256=manifest_sha256),
                "event": "run_started",
                "selectionMode": "read_only_database",
                "databaseSelectionMaximumRows": 1,
                "employeeDetailMaximumRequests": 1,
                "modelMaximumCalls": 0,
                "retryAllowed": False,
                "resumeAllowed": False,
            }
        )

    @classmethod
    def open_existing(
        cls,
        path: Path,
        *,
        manifest_sha256: str,
    ) -> QualificationLifecycleJournalV2:
        snapshot = validate_lifecycle(path, manifest_sha256=manifest_sha256)
        if snapshot.run_status is not None:
            _invalid()
        instance = cls.__new__(cls)
        instance._path = path
        instance._manifest_sha256 = manifest_sha256
        instance._database_started = snapshot.database_selection_started == 1
        instance._database_terminal = snapshot.database_selection_terminal == 1
        instance._database_rows = snapshot.database_selection_rows
        instance._detail_started = snapshot.employee_detail_started == 1
        instance._detail_terminal = snapshot.employee_detail_terminal_status
        instance._run_terminal = False
        return instance

    @property
    def path(self) -> Path:
        return self._path

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    def record_database_selection_started(self) -> None:
        if self._database_started or self._run_terminal:
            _invalid()
        self._append({"event": "database_selection_started", "queryOrdinal": 1})
        self._database_started = True

    def record_database_selection_terminal(self, *, status: str, selected_rows: int) -> None:
        if (
            not self._database_started
            or self._database_terminal
            or self._run_terminal
            or status not in {"completed", "failed"}
            or type(selected_rows) is not int
            or selected_rows not in (0, 1)
            or (status == "failed" and selected_rows != 0)
        ):
            _invalid()
        self._append(
            {
                "event": "database_selection_terminal",
                "queryOrdinal": 1,
                "status": status,
                "selectedRows": selected_rows,
            }
        )
        self._database_terminal = True
        self._database_rows = selected_rows

    def record_employee_detail_started(self) -> None:
        if (
            not self._database_terminal
            or self._database_rows != 1
            or self._detail_started
            or self._run_terminal
        ):
            _invalid()
        self._append({"event": "employee_detail_started", "requestOrdinal": 1})
        self._detail_started = True

    def record_employee_detail_terminal(self, *, status: str) -> None:
        if (
            not self._detail_started
            or self._detail_terminal is not None
            or self._run_terminal
            or status not in {"completed", "failed"}
        ):
            _invalid()
        self._append(
            {
                "event": "employee_detail_terminal",
                "requestOrdinal": 1,
                "status": status,
            }
        )
        self._detail_terminal = status

    def record_run_terminal(
        self,
        *,
        status: QualificationRunStatus,
        failure_phase: QualificationFailurePhase | None,
        failure_reason: QualificationReason | None,
    ) -> None:
        if self._run_terminal:
            _invalid()
        if status is QualificationRunStatus.QUALIFIED:
            if (
                failure_phase is not None
                or failure_reason is not None
                or self._database_rows != 1
                or self._detail_terminal != "completed"
            ):
                _invalid()
        elif status is QualificationRunStatus.NOT_QUALIFIED:
            if (
                failure_phase is None
                or failure_reason is None
                or failure_reason not in _FAILURE_REASONS[failure_phase]
                or failure_reason
                not in {
                    QualificationReason.NO_QUALIFIED_INPUT,
                    QualificationReason.EMPLOYEE_RESULT_INVALID,
                    QualificationReason.EGRESS_PROJECTION_INVALID,
                }
            ):
                _invalid()
        elif (
            status is not QualificationRunStatus.FAILED
            or failure_phase is None
            or failure_reason is None
            or failure_reason not in _FAILURE_REASONS[failure_phase]
            or failure_reason is QualificationReason.NO_QUALIFIED_INPUT
        ):
            _invalid()
        self._append(
            {
                "event": "run_terminal",
                "status": status.value,
                "failurePhase": None if failure_phase is None else failure_phase.value,
                "failureReason": None if failure_reason is None else failure_reason.value,
            }
        )
        self._run_terminal = True

    def _write_first(self, value: Mapping[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _append(self, value: Mapping[str, object]) -> None:
        record = {**_common_record(manifest_sha256=self._manifest_sha256), **value}
        with self._path.open("a", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if not raw or len(raw) > 262_144 or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line:
            _invalid()
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeError, json.JSONDecodeError):
            _invalid()
        if type(value) is not dict:
            _invalid()
        records.append(value)
    return records


def validate_lifecycle(
    path: Path,
    *,
    manifest_sha256: str,
) -> QualificationLifecycleSnapshotV2:
    if not _is_sha256(manifest_sha256):
        _invalid()
    records = _load_jsonl(path)
    expected_common = _common_record(manifest_sha256=manifest_sha256)
    first = records[0]
    if (
        set(first)
        != set(expected_common)
        | {
            "event",
            "selectionMode",
            "databaseSelectionMaximumRows",
            "employeeDetailMaximumRequests",
            "modelMaximumCalls",
            "retryAllowed",
            "resumeAllowed",
        }
        or any(first.get(key) != value for key, value in expected_common.items())
        or first["event"] != "run_started"
        or first["selectionMode"] != "read_only_database"
        or first["databaseSelectionMaximumRows"] != 1
        or first["employeeDetailMaximumRequests"] != 1
        or first["modelMaximumCalls"] != 0
        or first["retryAllowed"] is not False
        or first["resumeAllowed"] is not False
    ):
        _invalid()

    database_started = 0
    database_terminal = 0
    database_rows = 0
    detail_started = 0
    detail_terminal = 0
    detail_terminal_status: str | None = None
    run_status: QualificationRunStatus | None = None
    failure_phase: QualificationFailurePhase | None = None
    failure_reason: QualificationReason | None = None
    for record in records[1:]:
        if any(record.get(key) != value for key, value in expected_common.items()):
            _invalid()
        event = record.get("event")
        if event == "database_selection_started":
            if set(record) != set(expected_common) | {"event", "queryOrdinal"}:
                _invalid()
            if record["queryOrdinal"] != 1 or database_started or run_status is not None:
                _invalid()
            database_started = 1
        elif event == "database_selection_terminal":
            if set(record) != set(expected_common) | {
                "event",
                "queryOrdinal",
                "status",
                "selectedRows",
            }:
                _invalid()
            if (
                not database_started
                or database_terminal
                or record["queryOrdinal"] != 1
                or record["status"] not in {"completed", "failed"}
                or type(record["selectedRows"]) is not int
                or record["selectedRows"] not in (0, 1)
                or (record["status"] == "failed" and record["selectedRows"] != 0)
                or run_status is not None
            ):
                _invalid()
            database_terminal = 1
            database_rows = record["selectedRows"]
        elif event == "employee_detail_started":
            if set(record) != set(expected_common) | {"event", "requestOrdinal"}:
                _invalid()
            if (
                database_terminal != 1
                or database_rows != 1
                or detail_started
                or record["requestOrdinal"] != 1
                or run_status is not None
            ):
                _invalid()
            detail_started = 1
        elif event == "employee_detail_terminal":
            if set(record) != set(expected_common) | {
                "event",
                "requestOrdinal",
                "status",
            }:
                _invalid()
            if (
                detail_started != 1
                or detail_terminal
                or record["requestOrdinal"] != 1
                or record["status"] not in {"completed", "failed"}
                or run_status is not None
            ):
                _invalid()
            detail_terminal = 1
            detail_terminal_status = record["status"]
        elif event == "run_terminal":
            if set(record) != set(expected_common) | {
                "event",
                "status",
                "failurePhase",
                "failureReason",
            } or run_status is not None:
                _invalid()
            try:
                run_status = QualificationRunStatus(record["status"])
                failure_phase = (
                    None
                    if record["failurePhase"] is None
                    else QualificationFailurePhase(record["failurePhase"])
                )
                failure_reason = (
                    None
                    if record["failureReason"] is None
                    else QualificationReason(record["failureReason"])
                )
            except (TypeError, ValueError):
                _invalid()
            if run_status is QualificationRunStatus.QUALIFIED:
                if (
                    failure_phase is not None
                    or failure_reason is not None
                    or database_rows != 1
                    or detail_terminal_status != "completed"
                ):
                    _invalid()
            else:
                if (
                    failure_phase is None
                    or failure_reason is None
                    or failure_reason not in _FAILURE_REASONS[failure_phase]
                ):
                    _invalid()
                if run_status is QualificationRunStatus.NOT_QUALIFIED:
                    if failure_reason not in {
                        QualificationReason.NO_QUALIFIED_INPUT,
                        QualificationReason.EMPLOYEE_RESULT_INVALID,
                        QualificationReason.EGRESS_PROJECTION_INVALID,
                    }:
                        _invalid()
                elif failure_reason is QualificationReason.NO_QUALIFIED_INPUT:
                    _invalid()
        else:
            _invalid()
    return QualificationLifecycleSnapshotV2(
        record_count=len(records),
        database_selection_started=database_started,
        database_selection_terminal=database_terminal,
        database_selection_rows=database_rows,
        employee_detail_started=detail_started,
        employee_detail_terminal=detail_terminal,
        employee_detail_terminal_status=detail_terminal_status,
        run_status=run_status,
        failure_phase=failure_phase,
        failure_reason=failure_reason,
    )


def _field_presence(result: CapabilityResult | None) -> tuple[dict[str, bool], dict[str, bool]]:
    codec = {
        "idCardNo": False,
        "chineseName": False,
        "position": False,
        "workBaseSi": False,
    }
    required_user = {"employeeIdMasked": False, "chineseName": False}
    if result is None or not isinstance(result.domain_result, Mapping):
        return codec, required_user
    records = result.domain_result.get("records")
    if not isinstance(records, tuple) or len(records) != 1 or not isinstance(records[0], Mapping):
        return codec, required_user
    fields = records[0].get("fields")
    if not isinstance(fields, Mapping):
        return codec, required_user
    masked = fields.get("employee_id_masked")
    name = fields.get("chinese_name")
    position = fields.get("position")
    work_base = fields.get("work_base_si")
    codec.update(
        {
            "idCardNo": isinstance(masked, str) and bool(masked.strip()),
            "chineseName": isinstance(name, str) and bool(name.strip()),
            "position": isinstance(position, str) and bool(position.strip()),
            "workBaseSi": isinstance(work_base, str) and bool(work_base.strip()),
        }
    )
    required_user.update(
        {
            "employeeIdMasked": codec["idCardNo"],
            "chineseName": codec["chineseName"],
        }
    )
    return codec, required_user


def build_result(
    *,
    lifecycle_path: Path,
    manifest_sha256: str,
    result: CapabilityResult | None,
    raw_logs_deleted: bool,
    log_leak_count: int,
) -> dict[str, Any]:
    snapshot = validate_lifecycle(lifecycle_path, manifest_sha256=manifest_sha256)
    if snapshot.run_status is None or type(raw_logs_deleted) is not bool:
        _invalid()
    if type(log_leak_count) is not int or log_leak_count < 0:
        _invalid()
    codec, required_user = _field_presence(result)
    egress_reason: str = (
        QualificationReason.QUALIFIED.value
        if result is not None
        and result.status is CapabilityStatus.SUCCESS
        and result.egress.disposition is EgressDisposition.ALLOWED
        and result.egress.safe_payload is not None
        else (
            QualificationReason.EMPLOYEE_REQUEST_FAILED.value
            if result is not None
            and result.status
            in {
                CapabilityStatus.UNAUTHENTICATED,
                CapabilityStatus.FORBIDDEN,
                CapabilityStatus.TIMEOUT,
                CapabilityStatus.DOWNSTREAM_FAILURE,
            }
            else (
                snapshot.failure_reason.value
                if snapshot.failure_reason is not None
                else QualificationReason.EMPLOYEE_RESULT_INVALID.value
            )
        )
    )
    value: dict[str, Any] = {
        "schemaVersion": 2,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "recordedAt": _timestamp(),
        "status": snapshot.run_status.value,
        "selectionMode": "read_only_database",
        "codecMinimumFieldPresence": codec,
        "requiredUserResultFieldPresence": required_user,
        "egressReason": egress_reason,
        "counts": {
            "databaseSelectionStarted": snapshot.database_selection_started,
            "databaseSelectionTerminal": snapshot.database_selection_terminal,
            "databaseSelectionRows": snapshot.database_selection_rows,
            "employeeDetailStarted": snapshot.employee_detail_started,
            "employeeDetailTerminal": snapshot.employee_detail_terminal,
            "otherEmployeeEndpoints": 0,
            "modelCalls": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "failure": {
            "phase": None if snapshot.failure_phase is None else snapshot.failure_phase.value,
            "reason": None if snapshot.failure_reason is None else snapshot.failure_reason.value,
        },
        "lifecycle": {
            "recordCount": snapshot.record_count,
            "sha256": sha256_file(lifecycle_path),
        },
        "safety": {
            "identifierPersisted": False,
            "jwtPersisted": False,
            "fieldValuesPersisted": False,
            "rawResponsePersisted": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "logLeakCount": log_leak_count,
            "logScanCompleted": raw_logs_deleted,
            "rawLogsDeleted": raw_logs_deleted,
        },
    }
    return validate_result(value)


def validate_result(
    value: object,
    *,
    require_cleanup: bool = False,
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "workPackageId",
        "gateId",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "recordedAt",
        "status",
        "selectionMode",
        "codecMinimumFieldPresence",
        "requiredUserResultFieldPresence",
        "egressReason",
        "counts",
        "failure",
        "lifecycle",
        "safety",
    }:
        _invalid()
    try:
        status = QualificationRunStatus(value["status"])
        reason = QualificationReason(value["egressReason"])
    except (TypeError, ValueError):
        _invalid()
    if (
        value["schemaVersion"] != 2
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or not _is_sha256(value["manifestSha256"])
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_utc_timestamp(value["recordedAt"])
        or value["selectionMode"] != "read_only_database"
    ):
        _invalid()
    codec = value["codecMinimumFieldPresence"]
    required_user = value["requiredUserResultFieldPresence"]
    if (
        type(codec) is not dict
        or set(codec) != {"idCardNo", "chineseName", "position", "workBaseSi"}
        or any(type(item) is not bool for item in codec.values())
        or type(required_user) is not dict
        or set(required_user) != {"employeeIdMasked", "chineseName"}
        or any(type(item) is not bool for item in required_user.values())
    ):
        _invalid()
    counts = value["counts"]
    if type(counts) is not dict or set(counts) != {
        "databaseSelectionStarted",
        "databaseSelectionTerminal",
        "databaseSelectionRows",
        "employeeDetailStarted",
        "employeeDetailTerminal",
        "otherEmployeeEndpoints",
        "modelCalls",
        "retryCount",
        "resumeCount",
    }:
        _invalid()
    if any(
        type(counts[key]) is not int or counts[key] not in (0, 1)
        for key in (
            "databaseSelectionStarted",
            "databaseSelectionTerminal",
            "databaseSelectionRows",
            "employeeDetailStarted",
            "employeeDetailTerminal",
        )
    ) or any(
        counts[key] != 0
        for key in (
            "otherEmployeeEndpoints",
            "modelCalls",
            "retryCount",
            "resumeCount",
        )
    ):
        _invalid()
    failure = value["failure"]
    if type(failure) is not dict or set(failure) != {"phase", "reason"}:
        _invalid()
    if status is QualificationRunStatus.QUALIFIED:
        if (
            not all(codec.values())
            or not all(required_user.values())
            or reason is not QualificationReason.QUALIFIED
            or counts
            != {
                "databaseSelectionStarted": 1,
                "databaseSelectionTerminal": 1,
                "databaseSelectionRows": 1,
                "employeeDetailStarted": 1,
                "employeeDetailTerminal": 1,
                "otherEmployeeEndpoints": 0,
                "modelCalls": 0,
                "retryCount": 0,
                "resumeCount": 0,
            }
            or failure != {"phase": None, "reason": None}
        ):
            _invalid()
    else:
        try:
            phase = QualificationFailurePhase(failure["phase"])
            failure_reason = QualificationReason(failure["reason"])
        except (TypeError, ValueError):
            _invalid()
        if (
            failure_reason not in _FAILURE_REASONS[phase]
            or reason is not failure_reason
        ):
            _invalid()
    lifecycle = value["lifecycle"]
    if (
        type(lifecycle) is not dict
        or set(lifecycle) != {"recordCount", "sha256"}
        or type(lifecycle["recordCount"]) is not int
        or not 2 <= lifecycle["recordCount"] <= 6
        or not _is_sha256(lifecycle["sha256"])
    ):
        _invalid()
    safety = value["safety"]
    if type(safety) is not dict or set(safety) != {
        "identifierPersisted",
        "jwtPersisted",
        "fieldValuesPersisted",
        "rawResponsePersisted",
        "llmApiKeyRead",
        "modelOutbound",
        "logLeakCount",
        "logScanCompleted",
        "rawLogsDeleted",
    }:
        _invalid()
    if (
        any(
            safety[key] is not False
            for key in (
                "identifierPersisted",
                "jwtPersisted",
                "fieldValuesPersisted",
                "rawResponsePersisted",
                "llmApiKeyRead",
                "modelOutbound",
            )
        )
        or type(safety["logLeakCount"]) is not int
        or safety["logLeakCount"] < 0
        or type(safety["logScanCompleted"]) is not bool
        or type(safety["rawLogsDeleted"]) is not bool
        or safety["logScanCompleted"] is not safety["rawLogsDeleted"]
        or (not safety["logScanCompleted"] and safety["logLeakCount"] != 0)
        or (
            require_cleanup
            and (
                safety["logScanCompleted"] is not True
                or safety["rawLogsDeleted"] is not True
                or safety["logLeakCount"] != 0
            )
        )
    ):
        _invalid()
    return value


def validate_manifest(value: object, *, repository_root: Path) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "preparedAt",
        "executionBoundary",
        "qualificationContract",
        "retiredQualificationRun",
        "employeeEgressHistory",
        "assetHashes",
    }:
        _invalid()
    if (
        value["schemaVersion"] != 2
        or value["status"] != "prepared_unconsumed"
        or value["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_utc_timestamp(value["preparedAt"])
        or value["executionBoundary"]
        != {
            "databaseSelectionMaximumRows": 1,
            "employeeDetailMaximumRequests": 1,
            "modelMaximumCalls": 0,
            "retryAllowed": False,
            "resumeAllowed": False,
            "liveExecutionAuthorized": False,
            "lifecycleOutputPath": (
                "agent-runtime/tests/integration/adapters/employee/evidence/"
                f"{RUN_ID}.lifecycle.jsonl"
            ),
            "resultOutputPath": (
                "agent-runtime/tests/integration/adapters/employee/evidence/"
                f"{RUN_ID}.result.json"
            ),
        }
        or value["qualificationContract"]
        != {
            "selectionMode": "read_only_database",
            "codecMinimumFields": ["idCardNo", "chineseName", "position", "workBaseSi"],
            "requiredUserResultFieldIds": ["employee_id_masked", "chinese_name"],
            "requiredEgressFieldIds": ["position", "work_base_si"],
            "identifierPersistenceAllowed": False,
            "fieldValuePersistenceAllowed": False,
        }
    ):
        _invalid()
    root = repository_root.resolve()
    retired = value["retiredQualificationRun"]
    if (
        type(retired) is not dict
        or set(retired) != {"runId", "status", "assetHashes"}
        or retired["runId"] != RETIRED_RUN_ID
        or retired["status"] != "retired_failed_inconclusive"
    ):
        _invalid()
    _validate_assets(
        retired["assetHashes"],
        expected_paths=frozenset(RETIRED_RUN_ASSET_PATHS),
        repository_root=root,
    )
    history = value["employeeEgressHistory"]
    if type(history) is not list or len(history) != len(EMPLOYEE_EGRESS_HISTORY):
        _invalid()
    for item, expected in zip(history, EMPLOYEE_EGRESS_HISTORY, strict=True):
        if (
            type(item) is not dict
            or set(item) != {"kind", "path", "sha256"}
            or (item["kind"], item["path"], item["sha256"]) != expected
            or sha256_file((root / item["path"]).resolve()) != item["sha256"]
        ):
            _invalid()
    _validate_assets(
        value["assetHashes"],
        expected_paths=REQUIRED_ASSET_PATHS,
        repository_root=root,
    )
    return value


def _validate_assets(
    value: object,
    *,
    expected_paths: frozenset[str],
    repository_root: Path,
) -> None:
    if type(value) is not list or len(value) != len(expected_paths):
        _invalid()
    actual_paths: list[str] = []
    for item in value:
        if (
            type(item) is not dict
            or set(item) != {"path", "sha256"}
            or type(item["path"]) is not str
            or not _is_sha256(item["sha256"])
        ):
            _invalid()
        path = (repository_root / item["path"]).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError:
            _invalid()
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            _invalid()
        actual_paths.append(item["path"])
    if frozenset(actual_paths) != expected_paths or len(actual_paths) != len(set(actual_paths)):
        _invalid()


def validate_authorization(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "workPackageId",
        "gateId",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "databaseSelectionMaximumRows",
        "employeeDetailMaximumRequests",
        "modelMaximumCalls",
        "retryAllowed",
        "resumeAllowed",
        "liveExecutionAuthorized",
        "confirmedBy",
        "preparedAt",
    }:
        _invalid()
    if (
        value["schemaVersion"] != 2
        or value["status"] != "prepared_unconsumed"
        or value["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["manifestSha256"] != manifest_sha256
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["databaseSelectionMaximumRows"] != 1
        or value["employeeDetailMaximumRequests"] != 1
        or value["modelMaximumCalls"] != 0
        or value["retryAllowed"] is not False
        or value["resumeAllowed"] is not False
        or value["liveExecutionAuthorized"] is not False
        or value["confirmedBy"] != "project-maintainer-pending-gate-049-live-authorization"
        or not _is_utc_timestamp(value["preparedAt"])
    ):
        _invalid()
    return value


def build_asset_hashes(repository_root: Path, paths: Sequence[str]) -> list[dict[str, str]]:
    root = repository_root.resolve()
    return [
        {"path": path, "sha256": sha256_file((root / path).resolve())}
        for path in sorted(paths)
    ]
