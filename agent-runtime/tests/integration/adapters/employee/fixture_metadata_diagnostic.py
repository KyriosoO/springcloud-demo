from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Final, NoReturn


SCHEMA_VERSION: Final = 1
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-TEST-DATA-PREP-01"
RUN_ID: Final = "employee-fixture-metadata-diagnostic-v1-20260814-run-01"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-050"
SOURCE_EVIDENCE_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-work-base-data-diagnostic-v1-20260814-run-01.json"
)
SOURCE_EVIDENCE_SHA256: Final = (
    "b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6"
)

IMPLEMENTATION_SOURCE_PATHS: Final = (
    "employee-service/src/main/java/com/dylan/employee/mapper/EmployeeSqlProvider.java",
    "employee-service/src/main/java/com/dylan/employee/mapper/EmployeeMapper.java",
    "employee-service/src/main/java/com/dylan/employee/service/EmployeeService.java",
)
LOGICAL_INSERT_COLUMNS: Final = (
    "ID_CARD_NO",
    "CHINESE_NAME",
    "POSITION",
    "WORK_BASE_SI",
)
_MINIMUM_VALUE_LENGTHS: Final = {
    "ID_CARD_NO": 17,
    "CHINESE_NAME": 18,
    "POSITION": 16,
    "WORK_BASE_SI": 14,
}
_TEXT_TYPES: Final = frozenset(
    {"char", "varchar", "tinytext", "text", "mediumtext", "longtext"}
)

_STAGING_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "workPackageId",
        "runId",
        "authorizationReference",
        "recordedAt",
        "status",
        "sourceEvidence",
        "tableMetadata",
        "constraintMetadata",
        "triggerMetadata",
        "counts",
        "safety",
    }
)
_FINAL_TOP_LEVEL_KEYS: Final = _STAGING_TOP_LEVEL_KEYS | frozenset(
    {"implementationSources", "assessment"}
)
_SOURCE_KEYS: Final = frozenset({"path", "sha256"})
_TABLE_KEYS: Final = frozenset({"tableName", "engine", "columns"})
_COLUMN_KEYS: Final = frozenset(
    {
        "columnName",
        "ordinalPosition",
        "dataType",
        "columnType",
        "isNullable",
        "columnDefault",
        "extra",
        "generationExpression",
        "characterMaximumLength",
        "characterSetName",
        "collationName",
    }
)
_CONSTRAINT_METADATA_KEYS: Final = frozenset({"entries", "checks"})
_CONSTRAINT_KEYS: Final = frozenset(
    {
        "direction",
        "constraintName",
        "constraintType",
        "tableName",
        "columnName",
        "ordinalPosition",
        "referencedTableName",
        "referencedColumnName",
    }
)
_CHECK_KEYS: Final = frozenset({"constraintName", "checkClause"})
_TRIGGER_METADATA_KEYS: Final = frozenset({"entries"})
_TRIGGER_KEYS: Final = frozenset(
    {
        "triggerName",
        "timing",
        "event",
        "orientation",
        "actionStatementSha256",
        "sideEffectClassification",
    }
)
_COUNT_KEYS: Final = frozenset(
    {
        "maxQueries",
        "executedQueries",
        "columnQueries",
        "columnResultRows",
        "constraintQueries",
        "constraintResultRows",
        "checkQueries",
        "checkResultRows",
        "triggerQueries",
        "triggerResultRows",
        "employeeBusinessRowQueries",
        "employeeEndpointCalls",
        "authCalls",
        "modelCalls",
        "retryCount",
        "resumeCount",
    }
)
_SAFETY_KEYS: Final = frozenset(
    {
        "businessRowsRead",
        "identifiersPersisted",
        "fieldValuesPersisted",
        "rawTriggerStatementsPersisted",
        "jwtRead",
        "llmApiKeyRead",
        "modelOutbound",
        "databaseWrites",
        "schemaChanges",
        "logLeakCount",
        "rawLogsDeleted",
    }
)
_ASSESSMENT_KEYS: Final = frozenset(
    {
        "result",
        "reason",
        "metadataComplete",
        "transactionalEngine",
        "providerColumnSetMatches",
        "logicalFieldsPresent",
        "logicalFieldsWritable",
        "minimalInsertColumns",
        "blockingRequiredColumns",
        "idCardNoUnique",
        "outboundForeignKeyConstraints",
        "inboundForeignKeyConstraints",
        "checkConstraints",
        "triggers",
        "exactCleanupSupported",
        "gateMayClose",
    }
)


class FixtureMetadataDiagnosticError(ValueError):
    pass


def _invalid() -> NoReturn:
    raise FixtureMetadataDiagnosticError("employee.fixture_metadata_diagnostic_invalid")


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


def validate_source_evidence(repository_root: Path) -> None:
    source = repository_root / SOURCE_EVIDENCE_PATH
    if not source.is_file() or sha256_file(source) != SOURCE_EVIDENCE_SHA256:
        _invalid()


def _require_mapping(value: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _invalid()
    return value


def _require_list(value: object, *, max_items: int) -> list[object]:
    if not isinstance(value, list) or len(value) > max_items:
        _invalid()
    return value


def _require_non_blank_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid()
    return value


def _require_string(value: object) -> str:
    if not isinstance(value, str):
        _invalid()
    return value


def _require_nullable_string(value: object) -> str | None:
    if value is None:
        return None
    return _require_string(value)


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


def _validated_columns(value: object) -> list[dict[str, object]]:
    rows = _require_list(value, max_items=128)
    columns: list[dict[str, object]] = []
    names: set[str] = set()
    ordinals: set[int] = set()
    for item in rows:
        raw = _require_mapping(item, _COLUMN_KEYS)
        name = _require_non_blank_string(raw["columnName"]).upper()
        ordinal = _require_non_negative_int(raw["ordinalPosition"])
        if ordinal < 1 or name in names or ordinal in ordinals:
            _invalid()
        names.add(name)
        ordinals.add(ordinal)
        nullable = raw["isNullable"]
        if nullable not in {"YES", "NO"}:
            _invalid()
        maximum_length = raw["characterMaximumLength"]
        if maximum_length is not None:
            _require_non_negative_int(maximum_length)
        columns.append(
            {
                "columnName": name,
                "ordinalPosition": ordinal,
                "dataType": _require_non_blank_string(raw["dataType"]).lower(),
                "columnType": _require_non_blank_string(raw["columnType"]),
                "isNullable": nullable,
                "columnDefault": _require_nullable_string(raw["columnDefault"]),
                "extra": _require_string(raw["extra"]),
                "generationExpression": _require_string(raw["generationExpression"]),
                "characterMaximumLength": maximum_length,
                "characterSetName": _require_nullable_string(raw["characterSetName"]),
                "collationName": _require_nullable_string(raw["collationName"]),
            }
        )
    return columns


def _validated_constraints(value: object) -> list[dict[str, object]]:
    rows = _require_list(value, max_items=128)
    result: list[dict[str, object]] = []
    identities: set[tuple[object, ...]] = set()
    for item in rows:
        raw = _require_mapping(item, _CONSTRAINT_KEYS)
        direction = raw["direction"]
        constraint_type = raw["constraintType"]
        if direction not in {"owned", "inbound"} or constraint_type not in {
            "PRIMARY KEY",
            "UNIQUE",
            "FOREIGN KEY",
        }:
            _invalid()
        ordinal = _require_non_negative_int(raw["ordinalPosition"])
        row = {
            "direction": direction,
            "constraintName": _require_non_blank_string(raw["constraintName"]),
            "constraintType": constraint_type,
            "tableName": _require_non_blank_string(raw["tableName"]),
            "columnName": _require_non_blank_string(raw["columnName"]).upper(),
            "ordinalPosition": ordinal,
            "referencedTableName": _require_nullable_string(
                raw["referencedTableName"]
            ),
            "referencedColumnName": (
                None
                if raw["referencedColumnName"] is None
                else _require_non_blank_string(raw["referencedColumnName"]).upper()
            ),
        }
        identity = tuple(row[key] for key in _CONSTRAINT_KEYS)
        if ordinal < 1 or identity in identities:
            _invalid()
        identities.add(identity)
        result.append(row)
    return result


def _validated_checks(value: object) -> list[dict[str, str]]:
    rows = _require_list(value, max_items=128)
    result: list[dict[str, str]] = []
    names: set[str] = set()
    for item in rows:
        raw = _require_mapping(item, _CHECK_KEYS)
        name = _require_non_blank_string(raw["constraintName"])
        if name in names:
            _invalid()
        names.add(name)
        result.append(
            {
                "constraintName": name,
                "checkClause": _require_non_blank_string(raw["checkClause"]),
            }
        )
    return result


def _validated_triggers(value: object) -> list[dict[str, str]]:
    rows = _require_list(value, max_items=128)
    result: list[dict[str, str]] = []
    names: set[str] = set()
    for item in rows:
        raw = _require_mapping(item, _TRIGGER_KEYS)
        name = _require_non_blank_string(raw["triggerName"])
        digest = _require_non_blank_string(raw["actionStatementSha256"])
        if name in names or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            _invalid()
        names.add(name)
        if raw["timing"] not in {"BEFORE", "AFTER"}:
            _invalid()
        if raw["event"] not in {"INSERT", "UPDATE", "DELETE"}:
            _invalid()
        if raw["orientation"] != "ROW":
            _invalid()
        if raw["sideEffectClassification"] != "present_requires_manual_review":
            _invalid()
        result.append(
            {
                "triggerName": name,
                "timing": str(raw["timing"]),
                "event": str(raw["event"]),
                "orientation": str(raw["orientation"]),
                "actionStatementSha256": digest,
                "sideEffectClassification": "present_requires_manual_review",
            }
        )
    return result


def _validated_counts(
    value: object,
    *,
    columns: Sequence[object],
    constraints: Sequence[object],
    checks: Sequence[object],
    triggers: Sequence[object],
) -> dict[str, int]:
    raw = _require_mapping(value, _COUNT_KEYS)
    counts = {key: _require_non_negative_int(raw[key]) for key in _COUNT_KEYS}
    if counts != {
        "maxQueries": 4,
        "executedQueries": 4,
        "columnQueries": 1,
        "columnResultRows": len(columns),
        "constraintQueries": 1,
        "constraintResultRows": len(constraints),
        "checkQueries": 1,
        "checkResultRows": len(checks),
        "triggerQueries": 1,
        "triggerResultRows": len(triggers),
        "employeeBusinessRowQueries": 0,
        "employeeEndpointCalls": 0,
        "authCalls": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }:
        _invalid()
    return counts


def _validated_safety(value: object, *, raw_logs_deleted: bool) -> None:
    safety = _require_mapping(value, _SAFETY_KEYS)
    for key in (
        "businessRowsRead",
        "identifiersPersisted",
        "fieldValuesPersisted",
        "rawTriggerStatementsPersisted",
        "jwtRead",
        "llmApiKeyRead",
        "modelOutbound",
    ):
        if type(safety[key]) is not bool or safety[key] is not False:
            _invalid()
    for key in ("databaseWrites", "schemaChanges", "logLeakCount"):
        if type(safety[key]) is not int or safety[key] != 0:
            _invalid()
    if (
        type(safety["rawLogsDeleted"]) is not bool
        or safety["rawLogsDeleted"] is not raw_logs_deleted
    ):
        _invalid()


def _validate_common(
    value: Mapping[str, object], *, final: bool
) -> tuple[
    Mapping[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    keys = _FINAL_TOP_LEVEL_KEYS if final else _STAGING_TOP_LEVEL_KEYS
    top = _require_mapping(value, keys)
    if (
        type(top["schemaVersion"]) is not int
        or top["schemaVersion"] != SCHEMA_VERSION
        or top["workPackageId"] != WORK_PACKAGE_ID
        or top["runId"] != RUN_ID
        or top["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_utc_timestamp(top["recordedAt"])
        or top["status"] != ("completed" if final else "collected")
    ):
        _invalid()
    source = _require_mapping(top["sourceEvidence"], _SOURCE_KEYS)
    if source != {"path": SOURCE_EVIDENCE_PATH, "sha256": SOURCE_EVIDENCE_SHA256}:
        _invalid()
    table = _require_mapping(top["tableMetadata"], _TABLE_KEYS)
    if str(table["tableName"]).lower() != "employee":
        _invalid()
    _require_non_blank_string(table["engine"])
    columns = _validated_columns(table["columns"])
    constraint_metadata = _require_mapping(
        top["constraintMetadata"], _CONSTRAINT_METADATA_KEYS
    )
    constraints = _validated_constraints(constraint_metadata["entries"])
    checks = _validated_checks(constraint_metadata["checks"])
    trigger_metadata = _require_mapping(
        top["triggerMetadata"], _TRIGGER_METADATA_KEYS
    )
    triggers = _validated_triggers(trigger_metadata["entries"])
    _validated_counts(
        top["counts"],
        columns=columns,
        constraints=constraints,
        checks=checks,
        triggers=triggers,
    )
    _validated_safety(top["safety"], raw_logs_deleted=final)
    return table, columns, constraints, checks, triggers


def validate_staging_evidence(value: Mapping[str, object]) -> None:
    _validate_common(value, final=False)


def _provider_columns(repository_root: Path) -> tuple[str, ...]:
    source = (repository_root / IMPLEMENTATION_SOURCE_PATHS[0]).read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"private\s+static\s+final\s+String\[\]\s+COLUMNS\s*=\s*\{(.*?)\};",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        _invalid()
    columns = tuple(re.findall(r'"([A-Z][A-Z0-9_]*)"', match.group(1)))
    if len(columns) != 58 or len(set(columns)) != len(columns):
        _invalid()
    return columns


def _implementation_sources(repository_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in IMPLEMENTATION_SOURCE_PATHS:
        path = repository_root / relative
        if not path.is_file():
            _invalid()
        result[relative] = sha256_file(path)
    return result


def _supports_value(column: Mapping[str, object], minimum_length: int) -> bool:
    if column["dataType"] not in _TEXT_TYPES or column["generationExpression"] != "":
        return False
    maximum_length = column["characterMaximumLength"]
    return maximum_length is None or (
        type(maximum_length) is int and maximum_length >= minimum_length
    )


def _single_column_identifier_unique(
    constraints: Sequence[Mapping[str, object]],
) -> bool:
    grouped: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for row in constraints:
        if row["direction"] != "owned" or row["constraintType"] not in {
            "PRIMARY KEY",
            "UNIQUE",
        }:
            continue
        key = (str(row["constraintName"]), str(row["constraintType"]))
        grouped.setdefault(key, []).append(
            (_require_non_negative_int(row["ordinalPosition"]), str(row["columnName"]))
        )
    return any(
        [column for _, column in sorted(entries)] == ["ID_CARD_NO"]
        for entries in grouped.values()
    )


def _constraint_count(
    constraints: Sequence[Mapping[str, object]], *, direction: str
) -> int:
    return len(
        {
            (str(row["tableName"]), str(row["constraintName"]))
            for row in constraints
            if row["direction"] == direction
            and row["constraintType"] == "FOREIGN KEY"
        }
    )


def _assessment(
    *,
    table: Mapping[str, object],
    columns: Sequence[Mapping[str, object]],
    constraints: Sequence[Mapping[str, object]],
    checks: Sequence[Mapping[str, object]],
    triggers: Sequence[Mapping[str, object]],
    provider_columns: Sequence[str],
) -> dict[str, object]:
    by_name = {str(column["columnName"]): column for column in columns}
    metadata_complete = (
        len(columns) == 58
        and {
            _require_non_negative_int(column["ordinalPosition"])
            for column in columns
        }
        == set(range(1, 59))
    )
    transactional_engine = str(table["engine"]).upper() == "INNODB"
    provider_matches = set(provider_columns) == set(by_name) and len(by_name) == 58
    logical_present = set(LOGICAL_INSERT_COLUMNS).issubset(by_name)
    logical_writable = logical_present and all(
        _supports_value(by_name[name], _MINIMUM_VALUE_LENGTHS[name])
        for name in LOGICAL_INSERT_COLUMNS
    )
    blocking_required = sorted(
        name
        for name, column in by_name.items()
        if name not in LOGICAL_INSERT_COLUMNS
        and column["isNullable"] == "NO"
        and column["columnDefault"] is None
        and "auto_increment" not in str(column["extra"]).lower()
        and str(column["generationExpression"]) == ""
    )
    identifier_unique = _single_column_identifier_unique(constraints)
    outbound = _constraint_count(constraints, direction="owned")
    inbound = _constraint_count(constraints, direction="inbound")

    checks_count = len(checks)
    triggers_count = len(triggers)
    exact_cleanup = all(
        (
            metadata_complete,
            transactional_engine,
            provider_matches,
            logical_present,
            logical_writable,
            not blocking_required,
            identifier_unique,
            outbound == 0,
            inbound == 0,
            checks_count == 0,
            triggers_count == 0,
        )
    )
    if not metadata_complete:
        reason = "metadata_incomplete"
    elif not transactional_engine:
        reason = "unsupported_engine"
    elif not provider_matches:
        reason = "provider_column_set_mismatch"
    elif not logical_present:
        reason = "logical_fields_missing"
    elif not logical_writable:
        reason = "logical_fields_not_writable"
    elif blocking_required:
        reason = "omitted_required_columns"
    elif not identifier_unique:
        reason = "identifier_not_unique"
    elif outbound or inbound:
        reason = "foreign_keys_present"
    elif checks_count:
        reason = "checks_present"
    elif triggers_count:
        reason = "triggers_present"
    else:
        reason = "safe_to_prepare_fixture"
    return {
        "result": "gate_closed" if exact_cleanup else "gate_open",
        "reason": reason,
        "metadataComplete": metadata_complete,
        "transactionalEngine": transactional_engine,
        "providerColumnSetMatches": provider_matches,
        "logicalFieldsPresent": logical_present,
        "logicalFieldsWritable": logical_writable,
        "minimalInsertColumns": list(LOGICAL_INSERT_COLUMNS),
        "blockingRequiredColumns": blocking_required,
        "idCardNoUnique": identifier_unique,
        "outboundForeignKeyConstraints": outbound,
        "inboundForeignKeyConstraints": inbound,
        "checkConstraints": checks_count,
        "triggers": triggers_count,
        "exactCleanupSupported": exact_cleanup,
        "gateMayClose": exact_cleanup,
    }


def _validated_assessment(value: object) -> Mapping[str, object]:
    assessment = _require_mapping(value, _ASSESSMENT_KEYS)
    if assessment["result"] not in {"gate_closed", "gate_open"}:
        _invalid()
    if assessment["reason"] not in {
        "metadata_incomplete",
        "unsupported_engine",
        "provider_column_set_mismatch",
        "logical_fields_missing",
        "logical_fields_not_writable",
        "omitted_required_columns",
        "identifier_not_unique",
        "foreign_keys_present",
        "checks_present",
        "triggers_present",
        "safe_to_prepare_fixture",
    }:
        _invalid()
    for key in (
        "metadataComplete",
        "transactionalEngine",
        "providerColumnSetMatches",
        "logicalFieldsPresent",
        "logicalFieldsWritable",
        "idCardNoUnique",
        "exactCleanupSupported",
        "gateMayClose",
    ):
        if type(assessment[key]) is not bool:
            _invalid()
    if assessment["minimalInsertColumns"] != list(LOGICAL_INSERT_COLUMNS):
        _invalid()
    blocking = _require_list(assessment["blockingRequiredColumns"], max_items=58)
    if any(not isinstance(item, str) or not item for item in blocking):
        _invalid()
    for key in (
        "outboundForeignKeyConstraints",
        "inboundForeignKeyConstraints",
        "checkConstraints",
        "triggers",
    ):
        _require_non_negative_int(assessment[key])
    return assessment


def validate_evidence(value: Mapping[str, object], repository_root: Path) -> None:
    table, columns, constraints, checks, triggers = _validate_common(value, final=True)
    validate_source_evidence(repository_root)
    sources = _require_mapping(
        value["implementationSources"], frozenset(IMPLEMENTATION_SOURCE_PATHS)
    )
    if sources != _implementation_sources(repository_root):
        _invalid()
    expected = _assessment(
        table=table,
        columns=columns,
        constraints=constraints,
        checks=checks,
        triggers=triggers,
        provider_columns=_provider_columns(repository_root),
    )
    if _validated_assessment(value["assessment"]) != expected:
        _invalid()


def write_exclusive_json(
    path: Path, value: Mapping[str, object], repository_root: Path
) -> None:
    validate_evidence(value, repository_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def finalize_staging_evidence(
    staging_path: Path, evidence_path: Path, repository_root: Path
) -> None:
    staging = load_strict_json(staging_path)
    table, columns, constraints, checks, triggers = _validate_common(
        staging, final=False
    )
    validate_source_evidence(repository_root)
    final: dict[str, object] = dict(staging)
    final["status"] = "completed"
    final["implementationSources"] = _implementation_sources(repository_root)
    final["assessment"] = _assessment(
        table=table,
        columns=columns,
        constraints=constraints,
        checks=checks,
        triggers=triggers,
        provider_columns=_provider_columns(repository_root),
    )
    safety = dict(_require_mapping(staging["safety"], _SAFETY_KEYS))
    safety["rawLogsDeleted"] = True
    final["safety"] = safety
    write_exclusive_json(evidence_path, final, repository_root)
