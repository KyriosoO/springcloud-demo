from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Final, Mapping, NoReturn, cast


WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-04"
GATE_ID: Final = "GATE-049"
RUN_ID: Final = "employee-egress-input-qualification-v4-20260816-candidate-04"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-049"
_SHA: Final = re.compile(r"[0-9a-f]{64}\Z")
_HOST_KEYS: Final = {
    "schemaVersion",
    "workPackageId",
    "gateId",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "sequence",
    "phase",
    "state",
    "reason",
}
_FAILURE_KEYS: Final = {
    "schemaVersion",
    "workPackageId",
    "gateId",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "status",
    "reason",
    "hostExitCode",
    "counts",
    "safety",
    "hostLifecycleSha256",
}


class QualificationV4HostError(ValueError):
    pass


def _invalid() -> NoReturn:
    raise QualificationV4HostError("employee.qualification_v4_host_contract_invalid")


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _record(
    *,
    manifest_sha256: str,
    sequence: int,
    phase: str,
    state: str,
    reason: str,
) -> dict[str, object]:
    return {
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


def create_host_lifecycle(path: Path, *, manifest_sha256: str) -> None:
    if _SHA.fullmatch(manifest_sha256) is None:
        _invalid()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = (
        _record(
            manifest_sha256=manifest_sha256,
            sequence=1,
            phase="host_bootstrap",
            state="started",
            reason="none",
        ),
        _record(
            manifest_sha256=manifest_sha256,
            sequence=2,
            phase="spring_context",
            state="started",
            reason="none",
        ),
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(_canonical(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def complete_host_lifecycle(
    path: Path,
    *,
    manifest_sha256: str,
    spring_context_succeeded: bool,
) -> None:
    records = _load_records(path)
    _validate_prefix(records, manifest_sha256=manifest_sha256)
    if len(records) != 2:
        _invalid()
    reason = "none" if spring_context_succeeded else "spring_context_start_failed"
    state = "succeeded" if spring_context_succeeded else "failed"
    terminal = (
        _record(
            manifest_sha256=manifest_sha256,
            sequence=3,
            phase="spring_context",
            state=state,
            reason=reason,
        ),
        _record(
            manifest_sha256=manifest_sha256,
            sequence=4,
            phase="host_bootstrap",
            state=state,
            reason=reason,
        ),
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for record in terminal:
            handle.write(_canonical(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    validate_host_lifecycle(path, manifest_sha256=manifest_sha256)


def validate_host_lifecycle(path: Path, *, manifest_sha256: str) -> list[dict[str, Any]]:
    records = _load_records(path)
    _validate_prefix(records, manifest_sha256=manifest_sha256)
    if len(records) != 4:
        _invalid()
    succeeded = records[2]["state"] == "succeeded"
    expected_reason = "none" if succeeded else "spring_context_start_failed"
    expected_state = "succeeded" if succeeded else "failed"
    expected = (
        (1, "host_bootstrap", "started", "none"),
        (2, "spring_context", "started", "none"),
        (3, "spring_context", expected_state, expected_reason),
        (4, "host_bootstrap", expected_state, expected_reason),
    )
    for record, item in zip(records, expected, strict=True):
        if (
            record["sequence"],
            record["phase"],
            record["state"],
            record["reason"],
        ) != item:
            _invalid()
    return records


def write_pre_sql_failure(
    path: Path,
    *,
    host_lifecycle_path: Path,
    manifest_sha256: str,
    host_exit_code: int,
    log_leak_count: int,
    raw_logs_deleted: bool,
) -> dict[str, Any]:
    records = validate_host_lifecycle(host_lifecycle_path, manifest_sha256=manifest_sha256)
    if records[-1]["state"] != "failed" or not isinstance(host_exit_code, int):
        _invalid()
    if not isinstance(log_leak_count, int) or log_leak_count < 0 or raw_logs_deleted is not True:
        _invalid()
    value: dict[str, Any] = {
        "schemaVersion": 1,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "status": "failed_unconsumed",
        "reason": "spring_context_start_failed",
        "hostExitCode": host_exit_code,
        "counts": {
            "firstSqlStarted": 0,
            "databaseSelectStarted": 0,
            "databaseInsertStarted": 0,
            "databaseDeleteStarted": 0,
            "employeeDetailStarted": 0,
            "modelCalls": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "safety": {
            "logLeakCount": log_leak_count,
            "rawLogsDeleted": True,
            "jwtPersisted": False,
            "hmacPersisted": False,
            "employeeIdentifierPersisted": False,
            "employeeFieldValuePersisted": False,
            "rawResponsePersisted": False,
        },
        "hostLifecycleSha256": sha256_file(host_lifecycle_path),
    }
    validate_pre_sql_failure(value)
    write_exclusive_json(path, value)
    return value


def validate_pre_sql_failure(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _FAILURE_KEYS:
        _invalid()
    counts = value.get("counts")
    safety = value.get("safety")
    if not isinstance(safety, dict):
        _invalid()
    leak_count = safety.get("logLeakCount")
    if (
        value.get("schemaVersion") != 1
        or value.get("workPackageId") != WORK_PACKAGE_ID
        or value.get("gateId") != GATE_ID
        or value.get("runId") != RUN_ID
        or not isinstance(value.get("manifestSha256"), str)
        or _SHA.fullmatch(cast(str, value.get("manifestSha256"))) is None
        or value.get("authorizationReference") != AUTHORIZATION_REFERENCE
        or value.get("status") != "failed_unconsumed"
        or value.get("reason") != "spring_context_start_failed"
        or not isinstance(value.get("hostExitCode"), int)
        or not isinstance(value.get("hostLifecycleSha256"), str)
        or _SHA.fullmatch(cast(str, value.get("hostLifecycleSha256"))) is None
        or counts
        != {
            "firstSqlStarted": 0,
            "databaseSelectStarted": 0,
            "databaseInsertStarted": 0,
            "databaseDeleteStarted": 0,
            "employeeDetailStarted": 0,
            "modelCalls": 0,
            "retryCount": 0,
            "resumeCount": 0,
        }
        or set(safety)
        != {
            "logLeakCount",
            "rawLogsDeleted",
            "jwtPersisted",
            "hmacPersisted",
            "employeeIdentifierPersisted",
            "employeeFieldValuePersisted",
            "rawResponsePersisted",
        }
        or not isinstance(leak_count, int)
        or leak_count < 0
        or safety.get("rawLogsDeleted") is not True
        or any(
            safety.get(key) is not False
            for key in (
                "jwtPersisted",
                "hmacPersisted",
                "employeeIdentifierPersisted",
                "employeeFieldValuePersisted",
                "rawResponsePersisted",
            )
        )
    ):
        _invalid()
    return cast(dict[str, Any], value)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)


def load_strict_json(path: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object),
    )


def _load_records(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [
            cast(dict[str, Any], json.loads(line, object_pairs_hook=_unique_object))
            for line in lines
        ]
    except (OSError, json.JSONDecodeError, QualificationV4HostError):
        _invalid()


def _validate_prefix(records: list[dict[str, Any]], *, manifest_sha256: str) -> None:
    if _SHA.fullmatch(manifest_sha256) is None or len(records) not in {2, 4}:
        _invalid()
    for record in records:
        if (
            set(record) != _HOST_KEYS
            or record.get("schemaVersion") != 1
            or record.get("workPackageId") != WORK_PACKAGE_ID
            or record.get("gateId") != GATE_ID
            or record.get("runId") != RUN_ID
            or record.get("manifestSha256") != manifest_sha256
            or record.get("authorizationReference") != AUTHORIZATION_REFERENCE
            or record.get("reason") not in {"none", "spring_context_start_failed"}
        ):
            _invalid()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value
