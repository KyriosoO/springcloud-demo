from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, NoReturn


SCHEMA_VERSION: Final = 1
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-WORK-BASE-DATA-DIAG-01"
RUN_ID: Final = "employee-work-base-data-diagnostic-v1-20260814-run-01"
SOURCE_EVIDENCE_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-work-base-static-diagnostic-v1-20260814-run-01.json"
)
SOURCE_EVIDENCE_SHA256: Final = (
    "7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8"
)
EXPECTED_TOTAL_ROWS: Final = 990
EXPECTED_VALID_ROWS: Final = 0

_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "workPackageId",
        "runId",
        "recordedAt",
        "status",
        "sourceEvidence",
        "columnDefinition",
        "counts",
        "diagnosis",
        "safety",
    }
)
_SOURCE_KEYS: Final = frozenset(
    {"path", "sha256", "expectedTotalRows", "expectedValidRows"}
)
_COLUMN_KEYS: Final = frozenset(
    {
        "dataType",
        "columnType",
        "isNullable",
        "characterMaximumLength",
        "columnDefault",
        "collationName",
    }
)
_COUNT_KEYS: Final = frozenset(
    {
        "totalRows",
        "nullRows",
        "lengthInvalidRows",
        "controlCharacterRows",
        "bidiControlRows",
        "validRows",
        "metadataQueries",
        "metadataResultRows",
        "aggregateQueries",
        "aggregateResultRows",
        "employeeEndpointCalls",
        "modelCalls",
        "retryCount",
        "resumeCount",
    }
)
_DIAGNOSIS_KEYS: Final = frozenset(
    {"reason", "distributionProven", "sourceSnapshotMatches", "nextStep"}
)
_SAFETY_KEYS: Final = frozenset(
    {
        "identifiersPersisted",
        "fieldValuesPersisted",
        "rawRowsPersisted",
        "jwtRead",
        "llmApiKeyRead",
        "modelOutbound",
        "logLeakCount",
        "rawLogsDeleted",
    }
)


class WorkBaseDataDiagnosticError(ValueError):
    pass


class DiagnosticReason(StrEnum):
    SOURCE_SNAPSHOT_MISMATCH = "source_snapshot_mismatch"
    ALL_ROWS_NULL = "all_rows_null"
    ALL_ROWS_LENGTH_INVALID = "all_rows_length_invalid"
    ALL_ROWS_CONTROL_CHARACTER_INVALID = "all_rows_control_character_invalid"
    ALL_ROWS_BIDI_CONTROL_INVALID = "all_rows_bidi_control_invalid"
    MIXED_INVALID_VALUES = "mixed_invalid_values"


def _invalid() -> NoReturn:
    raise WorkBaseDataDiagnosticError("employee.work_base_data_diagnostic_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def load_strict_json(path: Path, *, max_bytes: int = 65_536) -> dict[str, Any]:
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


def validate_source_evidence(repository_root: Path) -> None:
    source = repository_root / SOURCE_EVIDENCE_PATH
    if not source.is_file() or sha256_file(source) != SOURCE_EVIDENCE_SHA256:
        _invalid()


def _require_mapping(value: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _invalid()
    return value


def _require_non_negative_int(value: object) -> int:
    if type(value) is not int or value < 0:
        _invalid()
    return value


def _require_non_blank_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid()
    return value


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _validated_column(value: object) -> dict[str, object]:
    raw = _require_mapping(value, _COLUMN_KEYS)
    data_type = _require_non_blank_string(raw["dataType"])
    column_type = _require_non_blank_string(raw["columnType"])
    nullable = raw["isNullable"]
    if nullable not in {"YES", "NO"}:
        _invalid()
    maximum_length = raw["characterMaximumLength"]
    if maximum_length is not None:
        _require_non_negative_int(maximum_length)
    column_default = raw["columnDefault"]
    if column_default is not None and not isinstance(column_default, str):
        _invalid()
    collation = raw["collationName"]
    if collation is not None:
        _require_non_blank_string(collation)
    return {
        "dataType": data_type,
        "columnType": column_type,
        "isNullable": nullable,
        "characterMaximumLength": maximum_length,
        "columnDefault": column_default,
        "collationName": collation,
    }


def _validated_counts(value: object) -> dict[str, int]:
    raw = _require_mapping(value, _COUNT_KEYS)
    counts = {key: _require_non_negative_int(raw[key]) for key in _COUNT_KEYS}
    if (
        counts["metadataQueries"] != 1
        or counts["metadataResultRows"] != 1
        or counts["aggregateQueries"] != 1
        or counts["aggregateResultRows"] != 1
        or counts["employeeEndpointCalls"] != 0
        or counts["modelCalls"] != 0
        or counts["retryCount"] != 0
        or counts["resumeCount"] != 0
    ):
        _invalid()
    partition_total = sum(
        counts[key]
        for key in (
            "nullRows",
            "lengthInvalidRows",
            "controlCharacterRows",
            "bidiControlRows",
            "validRows",
        )
    )
    if partition_total != counts["totalRows"]:
        _invalid()
    return counts


def _diagnosis(counts: Mapping[str, int]) -> tuple[DiagnosticReason, bool, str]:
    source_matches = (
        counts["totalRows"] == EXPECTED_TOTAL_ROWS
        and counts["validRows"] == EXPECTED_VALID_ROWS
    )
    if not source_matches:
        return (
            DiagnosticReason.SOURCE_SNAPSHOT_MISMATCH,
            False,
            "reconcile_source_snapshot_required",
        )
    total = counts["totalRows"]
    for key, reason in (
        ("nullRows", DiagnosticReason.ALL_ROWS_NULL),
        ("lengthInvalidRows", DiagnosticReason.ALL_ROWS_LENGTH_INVALID),
        (
            "controlCharacterRows",
            DiagnosticReason.ALL_ROWS_CONTROL_CHARACTER_INVALID,
        ),
        ("bidiControlRows", DiagnosticReason.ALL_ROWS_BIDI_CONTROL_INVALID),
    ):
        if counts[key] == total:
            return reason, True, "separate_test_data_remediation_authorization_required"
    return (
        DiagnosticReason.MIXED_INVALID_VALUES,
        True,
        "separate_test_data_remediation_authorization_required",
    )


def _validate_evidence(
    value: Mapping[str, object], *, raw_logs_deleted: bool
) -> None:
    top = _require_mapping(value, _TOP_LEVEL_KEYS)
    if (
        top["schemaVersion"] != SCHEMA_VERSION
        or top["workPackageId"] != WORK_PACKAGE_ID
        or top["runId"] != RUN_ID
        or top["status"] != "completed"
        or not _is_utc_timestamp(top["recordedAt"])
    ):
        _invalid()
    source = _require_mapping(top["sourceEvidence"], _SOURCE_KEYS)
    if source != {
        "path": SOURCE_EVIDENCE_PATH,
        "sha256": SOURCE_EVIDENCE_SHA256,
        "expectedTotalRows": EXPECTED_TOTAL_ROWS,
        "expectedValidRows": EXPECTED_VALID_ROWS,
    }:
        _invalid()
    _validated_column(top["columnDefinition"])
    counts = _validated_counts(top["counts"])
    reason, source_matches, next_step = _diagnosis(counts)
    diagnosis = _require_mapping(top["diagnosis"], _DIAGNOSIS_KEYS)
    if diagnosis != {
        "reason": reason.value,
        "distributionProven": source_matches,
        "sourceSnapshotMatches": source_matches,
        "nextStep": next_step,
    }:
        _invalid()
    safety = _require_mapping(top["safety"], _SAFETY_KEYS)
    if safety != {
        "identifiersPersisted": False,
        "fieldValuesPersisted": False,
        "rawRowsPersisted": False,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "modelOutbound": False,
        "logLeakCount": 0,
        "rawLogsDeleted": raw_logs_deleted,
    }:
        _invalid()


def validate_evidence(value: Mapping[str, object]) -> None:
    _validate_evidence(value, raw_logs_deleted=True)


def validate_staging_evidence(value: Mapping[str, object]) -> None:
    _validate_evidence(value, raw_logs_deleted=False)


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    validate_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def finalize_staging_evidence(staging_path: Path, evidence_path: Path) -> None:
    staging = load_strict_json(staging_path)
    validate_staging_evidence(staging)
    final: dict[str, object] = dict(staging)
    safety = dict(_require_mapping(staging["safety"], _SAFETY_KEYS))
    safety["rawLogsDeleted"] = True
    final["safety"] = safety
    write_exclusive_json(evidence_path, final)


def build_evidence(
    *,
    column_definition: Mapping[str, object],
    counts: Mapping[str, int],
    recorded_at: str,
    raw_logs_deleted: bool = True,
) -> dict[str, object]:
    checked_column = _validated_column(column_definition)
    checked_counts = _validated_counts(counts)
    reason, source_matches, next_step = _diagnosis(checked_counts)
    evidence: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "workPackageId": WORK_PACKAGE_ID,
        "runId": RUN_ID,
        "recordedAt": recorded_at,
        "status": "completed",
        "sourceEvidence": {
            "path": SOURCE_EVIDENCE_PATH,
            "sha256": SOURCE_EVIDENCE_SHA256,
            "expectedTotalRows": EXPECTED_TOTAL_ROWS,
            "expectedValidRows": EXPECTED_VALID_ROWS,
        },
        "columnDefinition": checked_column,
        "counts": checked_counts,
        "diagnosis": {
            "reason": reason.value,
            "distributionProven": source_matches,
            "sourceSnapshotMatches": source_matches,
            "nextStep": next_step,
        },
        "safety": {
            "identifiersPersisted": False,
            "fieldValuesPersisted": False,
            "rawRowsPersisted": False,
            "jwtRead": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "logLeakCount": 0,
            "rawLogsDeleted": raw_logs_deleted,
        },
    }
    _validate_evidence(evidence, raw_logs_deleted=raw_logs_deleted)
    return evidence
