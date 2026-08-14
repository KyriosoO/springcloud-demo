from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, NoReturn


SCHEMA_VERSION: Final = 1
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-INPUT-QUALIFY-DIAG-02"
RUN_ID: Final = "employee-egress-input-qualification-diagnostic-v2-20260814-run-01"
CANDIDATE_RUN_ID: Final = "employee-egress-input-qualification-v2-20260814-candidate-02"
CANDIDATE_LIFECYCLE_SHA256: Final = (
    "570295951f8bf1a109156c017c30609ca548bfba3f021bff4cd2825f978ac231"
)
CANDIDATE_RESULT_SHA256: Final = (
    "7534b1d04a1512720dcbee1fe630114fb1f08bf9c3615dec1d2cb18bec4d5054"
)
CANDIDATE_LIFECYCLE_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-egress-input-qualification-v2-20260814-candidate-02.lifecycle.jsonl"
)
CANDIDATE_RESULT_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-egress-input-qualification-v2-20260814-candidate-02.result.json"
)

_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "workPackageId",
        "runId",
        "recordedAt",
        "status",
        "sourceEvidence",
        "counts",
        "diagnosis",
        "safety",
    }
)
_SOURCE_KEYS: Final = frozenset(
    {"candidateRunId", "candidateLifecycleSha256", "candidateResultSha256"}
)
_COUNT_KEYS: Final = frozenset(
    {
        "totalRows",
        "idCardNoCondition",
        "chineseNameCondition",
        "positionCondition",
        "workBaseSiCondition",
        "cumulativeIdCardNo",
        "cumulativeChineseName",
        "cumulativePosition",
        "cumulativeWorkBaseSi",
        "aggregateQueries",
        "resultRows",
        "employeeDetailCalls",
        "otherEmployeeEndpointCalls",
        "modelCalls",
        "retryCount",
        "resumeCount",
    }
)
_DIAGNOSIS_KEYS: Final = frozenset(
    {"reason", "qualifiedInputAvailable", "firstZeroStage"}
)
_SAFETY_KEYS: Final = frozenset(
    {
        "identifierPersisted",
        "fieldValuesPersisted",
        "rawRowsPersisted",
        "jwtRead",
        "llmApiKeyRead",
        "modelOutbound",
        "logLeakCount",
        "rawLogsDeleted",
    }
)


class DiagnosticV2Error(ValueError):
    pass


class FirstZeroStage(StrEnum):
    NONE = "none"
    TOTAL_RECORDS = "total_records"
    ID_CARD_NO = "id_card_no"
    CHINESE_NAME = "chinese_name"
    POSITION = "position"
    WORK_BASE_SI = "work_base_si"


class DiagnosticReason(StrEnum):
    QUALIFIED_INPUT_AVAILABLE = "qualified_input_available"
    NO_QUALIFIED_INPUT = "no_qualified_input"


def _invalid() -> NoReturn:
    raise DiagnosticV2Error("employee.egress_input_qualification_diagnostic_v2_invalid")


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


def validate_candidate_history(repository_root: Path) -> None:
    expected = (
        (CANDIDATE_LIFECYCLE_PATH, CANDIDATE_LIFECYCLE_SHA256),
        (CANDIDATE_RESULT_PATH, CANDIDATE_RESULT_SHA256),
    )
    for relative_path, expected_sha256 in expected:
        path = repository_root / relative_path
        if not path.is_file() or sha256_file(path) != expected_sha256:
            _invalid()


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    validate_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _require_mapping(value: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _invalid()
    return value


def _require_non_negative_int(value: object) -> int:
    if type(value) is not int or value < 0:
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


def _first_zero_stage(counts: Mapping[str, int]) -> FirstZeroStage:
    ordered = (
        (FirstZeroStage.TOTAL_RECORDS, counts["totalRows"]),
        (FirstZeroStage.ID_CARD_NO, counts["cumulativeIdCardNo"]),
        (FirstZeroStage.CHINESE_NAME, counts["cumulativeChineseName"]),
        (FirstZeroStage.POSITION, counts["cumulativePosition"]),
        (FirstZeroStage.WORK_BASE_SI, counts["cumulativeWorkBaseSi"]),
    )
    for stage, value in ordered:
        if value == 0:
            return stage
    return FirstZeroStage.NONE


def _validated_counts(value: object) -> dict[str, int]:
    raw = _require_mapping(value, _COUNT_KEYS)
    counts = {key: _require_non_negative_int(raw[key]) for key in _COUNT_KEYS}
    if (
        counts["aggregateQueries"] != 1
        or counts["resultRows"] != 1
        or counts["employeeDetailCalls"] != 0
        or counts["otherEmployeeEndpointCalls"] != 0
        or counts["modelCalls"] != 0
        or counts["retryCount"] != 0
        or counts["resumeCount"] != 0
    ):
        _invalid()

    total = counts["totalRows"]
    for key in (
        "idCardNoCondition",
        "chineseNameCondition",
        "positionCondition",
        "workBaseSiCondition",
    ):
        if counts[key] > total:
            _invalid()
    if counts["cumulativeIdCardNo"] != counts["idCardNoCondition"]:
        _invalid()
    if not (
        counts["cumulativeChineseName"]
        <= counts["cumulativeIdCardNo"]
        and counts["cumulativeChineseName"] <= counts["chineseNameCondition"]
        and counts["cumulativePosition"] <= counts["cumulativeChineseName"]
        and counts["cumulativePosition"] <= counts["positionCondition"]
        and counts["cumulativeWorkBaseSi"] <= counts["cumulativePosition"]
        and counts["cumulativeWorkBaseSi"] <= counts["workBaseSiCondition"]
    ):
        _invalid()
    return counts


def _validate_evidence(
    value: Mapping[str, object],
    *,
    raw_logs_deleted: bool,
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
        "candidateRunId": CANDIDATE_RUN_ID,
        "candidateLifecycleSha256": CANDIDATE_LIFECYCLE_SHA256,
        "candidateResultSha256": CANDIDATE_RESULT_SHA256,
    }:
        _invalid()

    counts = _validated_counts(top["counts"])
    diagnosis = _require_mapping(top["diagnosis"], _DIAGNOSIS_KEYS)
    qualified = counts["cumulativeWorkBaseSi"] > 0
    expected_reason = (
        DiagnosticReason.QUALIFIED_INPUT_AVAILABLE
        if qualified
        else DiagnosticReason.NO_QUALIFIED_INPUT
    )
    expected_stage = _first_zero_stage(counts)
    if (
        diagnosis["qualifiedInputAvailable"] is not qualified
        or diagnosis["reason"] != expected_reason.value
        or diagnosis["firstZeroStage"] != expected_stage.value
    ):
        _invalid()

    safety = _require_mapping(top["safety"], _SAFETY_KEYS)
    expected_safety: Mapping[str, object] = {
        "identifierPersisted": False,
        "fieldValuesPersisted": False,
        "rawRowsPersisted": False,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "modelOutbound": False,
        "logLeakCount": 0,
        "rawLogsDeleted": raw_logs_deleted,
    }
    if safety != expected_safety:
        _invalid()


def validate_evidence(value: Mapping[str, object]) -> None:
    _validate_evidence(value, raw_logs_deleted=True)


def validate_staging_evidence(value: Mapping[str, object]) -> None:
    _validate_evidence(value, raw_logs_deleted=False)


def finalize_staging_evidence(staging_path: Path, evidence_path: Path) -> None:
    staging = load_strict_json(staging_path)
    validate_staging_evidence(staging)
    final: dict[str, object] = dict(staging)
    safety = dict(_require_mapping(staging["safety"], _SAFETY_KEYS))
    safety["rawLogsDeleted"] = True
    final["safety"] = safety
    write_exclusive_json(evidence_path, final)


def build_evidence(
    counts: Mapping[str, int],
    *,
    recorded_at: str | None = None,
) -> dict[str, object]:
    checked_counts = _validated_counts(counts)
    qualified = checked_counts["cumulativeWorkBaseSi"] > 0
    evidence: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "workPackageId": WORK_PACKAGE_ID,
        "runId": RUN_ID,
        "recordedAt": recorded_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "completed",
        "sourceEvidence": {
            "candidateRunId": CANDIDATE_RUN_ID,
            "candidateLifecycleSha256": CANDIDATE_LIFECYCLE_SHA256,
            "candidateResultSha256": CANDIDATE_RESULT_SHA256,
        },
        "counts": checked_counts,
        "diagnosis": {
            "reason": (
                DiagnosticReason.QUALIFIED_INPUT_AVAILABLE.value
                if qualified
                else DiagnosticReason.NO_QUALIFIED_INPUT.value
            ),
            "qualifiedInputAvailable": qualified,
            "firstZeroStage": _first_zero_stage(checked_counts).value,
        },
        "safety": {
            "identifierPersisted": False,
            "fieldValuesPersisted": False,
            "rawRowsPersisted": False,
            "jwtRead": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "logLeakCount": 0,
            "rawLogsDeleted": True,
        },
    }
    validate_evidence(evidence)
    return evidence
