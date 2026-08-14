from __future__ import annotations

import json
import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Final, NoReturn

from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
)


WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-01"
RUN_ID: Final = "employee-egress-input-qualification-v1-20260814-candidate-01"


class QualificationSelectionMode(StrEnum):
    MAINTAINER_CONFIRMED = "maintainer_confirmed"
    READ_ONLY_DATABASE = "read_only_database"


class QualificationStatus(StrEnum):
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    FAILED = "failed"


class QualificationReason(StrEnum):
    QUALIFIED = "qualified"
    NO_QUALIFIED_INPUT = "employee.no_qualified_input"
    NO_MODEL_FIELDS = "business.no_model_fields"
    EGRESS_DISABLED = "business.egress_disabled"
    POLICY_CONFLICT = "business.policy_conflict"
    RESULT_INVALID = "employee.result_invalid"
    REQUEST_FAILED = "employee.request_failed"


class InputQualificationError(ValueError):
    pass


def _invalid() -> NoReturn:
    raise InputQualificationError("employee.egress_input_qualification_invalid")


def _nonblank_field_presence(result: CapabilityResult) -> tuple[bool, bool]:
    domain_result = result.domain_result
    if not isinstance(domain_result, Mapping):
        return False, False
    records = domain_result.get("records")
    if not isinstance(records, tuple) or len(records) != 1:
        return False, False
    record = records[0]
    if not isinstance(record, Mapping):
        return False, False
    fields = record.get("fields")
    if not isinstance(fields, Mapping):
        return False, False
    position = fields.get("position")
    work_base_si = fields.get("work_base_si")
    return (
        isinstance(position, str) and bool(position.strip()),
        isinstance(work_base_si, str) and bool(work_base_si.strip()),
    )


def build_qualification_probe(
    *,
    selection_mode: QualificationSelectionMode,
    result: CapabilityResult | None,
    database_selection_rows: int,
    employee_detail_requests: int,
) -> dict[str, object]:
    if type(database_selection_rows) is not int or database_selection_rows not in (0, 1):
        _invalid()
    if type(employee_detail_requests) is not int or employee_detail_requests not in (0, 1):
        _invalid()
    if selection_mode is QualificationSelectionMode.MAINTAINER_CONFIRMED and database_selection_rows != 0:
        _invalid()

    position_present = False
    work_base_si_present = False
    status = QualificationStatus.FAILED
    reason = QualificationReason.NO_QUALIFIED_INPUT
    if result is not None:
        position_present, work_base_si_present = _nonblank_field_presence(result)
        if result.status is not CapabilityStatus.SUCCESS:
            reason = (
                QualificationReason.REQUEST_FAILED
                if result.status
                in {
                    CapabilityStatus.UNAUTHENTICATED,
                    CapabilityStatus.FORBIDDEN,
                    CapabilityStatus.TIMEOUT,
                    CapabilityStatus.DOWNSTREAM_FAILURE,
                }
                else QualificationReason.RESULT_INVALID
            )
        elif (
            position_present
            and work_base_si_present
            and result.egress.disposition is EgressDisposition.ALLOWED
            and result.egress.safe_payload is not None
        ):
            status = QualificationStatus.QUALIFIED
            reason = QualificationReason.QUALIFIED
        else:
            status = QualificationStatus.NOT_QUALIFIED
            reason_code = result.egress.reason_code
            try:
                reason = (
                    QualificationReason(reason_code)
                    if isinstance(reason_code, str)
                    else QualificationReason.NO_MODEL_FIELDS
                )
            except ValueError:
                reason = QualificationReason.NO_MODEL_FIELDS

    probe: dict[str, object] = {
        "selectionMode": selection_mode.value,
        "status": status.value,
        "fieldPresence": {
            "position": position_present,
            "workBaseSi": work_base_si_present,
        },
        "egressReason": reason.value,
        "requestCounts": {
            "databaseSelectionRows": database_selection_rows,
            "employeeDetail": employee_detail_requests,
            "otherEmployeeEndpoints": 0,
            "model": 0,
        },
    }
    validate_qualification_probe(probe)
    return probe


def validate_qualification_probe(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "selectionMode",
        "status",
        "fieldPresence",
        "egressReason",
        "requestCounts",
    }:
        _invalid()
    try:
        selection_mode = QualificationSelectionMode(value["selectionMode"])
        status = QualificationStatus(value["status"])
        reason = QualificationReason(value["egressReason"])
    except (TypeError, ValueError):
        _invalid()
    fields = value["fieldPresence"]
    counts = value["requestCounts"]
    if (
        type(fields) is not dict
        or set(fields) != {"position", "workBaseSi"}
        or any(type(item) is not bool for item in fields.values())
        or type(counts) is not dict
        or set(counts)
        != {"databaseSelectionRows", "employeeDetail", "otherEmployeeEndpoints", "model"}
        or type(counts["databaseSelectionRows"]) is not int
        or counts["databaseSelectionRows"] not in (0, 1)
        or type(counts["employeeDetail"]) is not int
        or counts["employeeDetail"] not in (0, 1)
        or counts["otherEmployeeEndpoints"] != 0
        or counts["model"] != 0
    ):
        _invalid()
    if selection_mode is QualificationSelectionMode.MAINTAINER_CONFIRMED and counts["databaseSelectionRows"] != 0:
        _invalid()
    if status is QualificationStatus.QUALIFIED:
        if (
            fields != {"position": True, "workBaseSi": True}
            or reason is not QualificationReason.QUALIFIED
            or counts["employeeDetail"] != 1
        ):
            _invalid()
    elif reason is QualificationReason.QUALIFIED:
        _invalid()
    if counts["employeeDetail"] == 0 and reason is not QualificationReason.NO_QUALIFIED_INPUT:
        _invalid()
    return value


def build_input_qualification_evidence(
    probe: Mapping[str, object],
    *,
    raw_logs_deleted: bool,
    log_leak_count: int,
) -> dict[str, object]:
    validated = validate_qualification_probe(dict(probe))
    if type(raw_logs_deleted) is not bool or type(log_leak_count) is not int or log_leak_count < 0:
        _invalid()
    evidence: dict[str, object] = {
        "schemaVersion": 1,
        "workPackageId": WORK_PACKAGE_ID,
        "runId": RUN_ID,
        **validated,
        "safety": {
            "identifierPersisted": False,
            "jwtPersisted": False,
            "fieldValuesPersisted": False,
            "rawResponsePersisted": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "logLeakCount": log_leak_count,
            "rawLogsDeleted": raw_logs_deleted,
        },
    }
    validate_input_qualification_evidence(evidence)
    return evidence


def validate_input_qualification_evidence(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "workPackageId",
        "runId",
        "selectionMode",
        "status",
        "fieldPresence",
        "egressReason",
        "requestCounts",
        "safety",
    }:
        _invalid()
    if (
        value["schemaVersion"] != 1
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["runId"] != RUN_ID
    ):
        _invalid()
    validate_qualification_probe(
        {
            key: value[key]
            for key in (
                "selectionMode",
                "status",
                "fieldPresence",
                "egressReason",
                "requestCounts",
            )
        }
    )
    safety = value["safety"]
    if (
        type(safety) is not dict
        or set(safety)
        != {
            "identifierPersisted",
            "jwtPersisted",
            "fieldValuesPersisted",
            "rawResponsePersisted",
            "llmApiKeyRead",
            "modelOutbound",
            "logLeakCount",
            "rawLogsDeleted",
        }
        or safety["identifierPersisted"] is not False
        or safety["jwtPersisted"] is not False
        or safety["fieldValuesPersisted"] is not False
        or safety["rawResponsePersisted"] is not False
        or safety["llmApiKeyRead"] is not False
        or safety["modelOutbound"] is not False
        or safety["logLeakCount"] != 0
        or safety["rawLogsDeleted"] is not True
    ):
        _invalid()
    return value


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
