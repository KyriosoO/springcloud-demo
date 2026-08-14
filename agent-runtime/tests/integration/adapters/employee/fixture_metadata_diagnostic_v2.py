from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, NoReturn, TypeVar


PREPARATION_WORK_PACKAGE_ID: Final = (
    "WP-EMP-EGRESS-FIXTURE-METADATA-CANDIDATE-02-PREP"
)
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-TEST-DATA-PREP-01"
GATE_ID: Final = "GATE-050"
RUN_ID: Final = "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-050"
PREPARED_AT: Final = "2026-08-14T08:00:00Z"
MAX_QUERIES: Final = 4
QUERY_PHASES: Final = (
    "column_and_engine",
    "key_and_foreign_key",
    "check_constraints",
    "triggers",
)
SOURCE_EVIDENCE_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-work-base-data-diagnostic-v1-20260814-run-01.json"
)
SOURCE_EVIDENCE_SHA256: Final = (
    "b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6"
)
RUN_01_FAILURE_EVIDENCE_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-fixture-metadata-diagnostic-v1-20260814-run-01.failure.json"
)
RUN_01_FAILURE_EVIDENCE_SHA256: Final = (
    "dce5e7659ed9cc49b52aa9cca6b70c9701c22cc55867f26cfa6a50ead291e7a1"
)
RUN_01_FAILURE_SCHEMA_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-fixture-metadata-diagnostic-v1-failure.schema.json"
)
RUN_01_FAILURE_SCHEMA_SHA256: Final = (
    "e9182239e7425a071c7daaf4c2a74fb3ef354fec9907ca0da5cef92f8ac85adc"
)

_HISTORY: Final = {
    SOURCE_EVIDENCE_PATH: SOURCE_EVIDENCE_SHA256,
    RUN_01_FAILURE_EVIDENCE_PATH: RUN_01_FAILURE_EVIDENCE_SHA256,
    RUN_01_FAILURE_SCHEMA_PATH: RUN_01_FAILURE_SCHEMA_SHA256,
}
_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/tests/integration/adapters/employee/fixture_metadata_diagnostic_v2.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_fixture_metadata_diagnostic_v2.py",
        "agent-runtime/tests/integration/adapters/employee/run_employee_fixture_metadata_diagnostic_v2.ps1",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-fixture-metadata-diagnostic-v2-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-fixture-metadata-diagnostic-v2-success.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-fixture-metadata-diagnostic-v2-failure.schema.json",
        "employee-service/src/test/java/com/dylan/employee/live/EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest.java",
    }
)
_RESULT_COMMON_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "preparationWorkPackageId",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "status",
        "history",
        "queryCounts",
        "safety",
    }
)
_QUERY_COUNT_KEYS: Final = frozenset(
    {
        "maximum",
        "started",
        "terminal",
        "succeeded",
        "failed",
        "retryCount",
        "resumeCount",
    }
)
_SAFETY_KEYS: Final = frozenset(
    {
        "businessRowsRead",
        "employeeEndpointCalls",
        "authCalls",
        "jwtRead",
        "llmApiKeyRead",
        "modelCalls",
        "modelOutbound",
        "databaseWrites",
        "schemaChanges",
        "identifiersPersisted",
        "fieldValuesPersisted",
        "rawTriggerStatementsPersisted",
        "logLeakCount",
        "rawLogsDeleted",
    }
)
_FORBIDDEN_SERIALIZED_KEYS: Final = (
    "idCardNo",
    "chineseName",
    "position",
    "workBaseSi",
    "rawResponse",
    "sqlText",
    "exceptionMessage",
)

T = TypeVar("T")


class FixtureMetadataCandidateV2Error(ValueError):
    """Finite fail-closed error for the test-only metadata candidate."""


def _invalid() -> NoReturn:
    raise FixtureMetadataCandidateV2Error("employee.fixture_metadata_v2_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def load_strict_json(path: Path, *, max_bytes: int = 524_288) -> dict[str, Any]:
    size = path.stat().st_size
    if size <= 0 or size > max_bytes:
        _invalid()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _invalid()
    if not isinstance(parsed, dict):
        _invalid()
    return parsed


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_history(repository_root: Path) -> None:
    for relative_path, expected in _HISTORY.items():
        path = repository_root / relative_path
        if not path.is_file() or sha256_file(path) != expected:
            raise FixtureMetadataCandidateV2Error(
                "employee.fixture_metadata_v2_history_mismatch"
            )


def _write_all_and_fsync(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    payload = (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    _write_all_and_fsync(path, payload)


def _append_jsonl_and_fsync(path: Path, value: Mapping[str, object]) -> None:
    payload = (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_WRONLY)
    try:
        with os.fdopen(descriptor, "ab", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _base_result(status: str, *, raw_logs_deleted: bool) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "status": status,
        "history": [
            {"path": path, "sha256": sha256}
            for path, sha256 in _HISTORY.items()
        ],
        "queryCounts": {
            "maximum": MAX_QUERIES,
            "started": 0,
            "terminal": 0,
            "succeeded": 0,
            "failed": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "safety": {
            "businessRowsRead": False,
            "employeeEndpointCalls": 0,
            "authCalls": 0,
            "jwtRead": False,
            "llmApiKeyRead": False,
            "modelCalls": 0,
            "modelOutbound": False,
            "databaseWrites": 0,
            "schemaChanges": 0,
            "identifiersPersisted": False,
            "fieldValuesPersisted": False,
            "rawTriggerStatementsPersisted": False,
            "logLeakCount": 0,
            "rawLogsDeleted": raw_logs_deleted,
        },
    }


class LifecycleJournal:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._sequence = 0
        self._closed = False
        _write_all_and_fsync(path, b"")
        self._append("run_started", "run", "started", None, 0)

    def _append(
        self,
        event: str,
        phase: str,
        status: str,
        reason: str | None,
        query_ordinal: int,
    ) -> None:
        if self._closed:
            raise FixtureMetadataCandidateV2Error(
                "employee.fixture_metadata_v2_lifecycle_closed"
            )
        self._sequence += 1
        _append_jsonl_and_fsync(
            self._path,
            {
                "schemaVersion": 2,
                "runId": RUN_ID,
                "authorizationReference": AUTHORIZATION_REFERENCE,
                "sequence": self._sequence,
                "event": event,
                "phase": phase,
                "status": status,
                "reason": reason,
                "queryOrdinal": query_ordinal,
                "retryCount": 0,
                "resumeCount": 0,
            },
        )

    def query_started(self, phase: str, query_ordinal: int) -> None:
        self._append("query_started", phase, "started", None, query_ordinal)

    def query_terminal(
        self, phase: str, query_ordinal: int, *, succeeded: bool
    ) -> None:
        self._append(
            "query_terminal",
            phase,
            "succeeded" if succeeded else "failed",
            None if succeeded else "information_schema_query_failed",
            query_ordinal,
        )

    def terminal(self, *, succeeded: bool) -> None:
        self._append(
            "run_terminal",
            "run",
            "passed" if succeeded else "failed",
            None if succeeded else "information_schema_query_failed",
            0,
        )
        self._closed = True


def execute_fake_candidate(
    lifecycle_path: Path,
    result_path: Path,
    operations: Sequence[Callable[[], object]],
) -> None:
    if len(operations) != MAX_QUERIES:
        _invalid()
    journal = LifecycleJournal(lifecycle_path)
    succeeded = 0
    for ordinal, (phase, operation) in enumerate(zip(QUERY_PHASES, operations), start=1):
        journal.query_started(phase, ordinal)
        try:
            operation()
        except Exception:
            journal.query_terminal(phase, ordinal, succeeded=False)
            journal.terminal(succeeded=False)
            result = _base_result("failed", raw_logs_deleted=True)
            counts = result["queryCounts"]
            assert isinstance(counts, dict)
            counts.update(
                {
                    "started": ordinal,
                    "terminal": ordinal,
                    "succeeded": succeeded,
                    "failed": 1,
                }
            )
            result["failure"] = {
                "phase": phase,
                "reason": "information_schema_query_failed",
                "queryOrdinal": ordinal,
                "sqlState": None,
                "vendorCode": None,
            }
            write_exclusive_json(result_path, result)
            return
        journal.query_terminal(phase, ordinal, succeeded=True)
        succeeded += 1
    journal.terminal(succeeded=True)
    result = _base_result("passed", raw_logs_deleted=True)
    counts = result["queryCounts"]
    assert isinstance(counts, dict)
    counts.update(
        {
            "started": MAX_QUERIES,
            "terminal": MAX_QUERIES,
            "succeeded": MAX_QUERIES,
            "failed": 0,
        }
    )
    result["metadata"] = {
        "table": {
            "name": "employee",
            "engine": "InnoDB",
            "columns": [
                {
                    "name": "ID_CARD_NO",
                    "ordinal": 1,
                    "dataType": "varchar",
                    "columnType": "varchar(64)",
                    "nullable": "NO",
                    "default": None,
                    "extra": "",
                    "generationExpression": "",
                    "maximumLength": 64,
                    "characterSet": "utf8mb4",
                    "collation": "utf8mb4_bin",
                }
            ],
        },
        "constraints": [],
        "checks": [],
        "triggers": [],
    }
    write_exclusive_json(result_path, result)


def _mapping(value: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(value, dict) or frozenset(value) != keys:
        _invalid()
    return value


def _integer(value: object, *, minimum: int = 0, maximum: int = MAX_QUERIES) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _invalid()
    if value < minimum or value > maximum:
        _invalid()
    return value


def _string(
    value: object, *, nullable: bool = False, allow_empty: bool = False
) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or (not allow_empty and not value):
        _invalid()
    return value


def _sha256(value: object) -> str:
    digest = _string(value)
    assert isinstance(digest, str)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        _invalid()
    return digest


def _items(value: object, *, minimum: int = 0, maximum: int = 128) -> list[object]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _invalid()
    return value


def _validate_metadata(value: object) -> None:
    metadata = _mapping(
        value, frozenset({"table", "constraints", "checks", "triggers"})
    )
    table = _mapping(metadata["table"], frozenset({"name", "engine", "columns"}))
    if table["name"] != "employee":
        _invalid()
    _string(table["engine"])
    for item in _items(table["columns"], minimum=1):
        column = _mapping(
            item,
            frozenset(
                {
                    "name",
                    "ordinal",
                    "dataType",
                    "columnType",
                    "nullable",
                    "default",
                    "extra",
                    "generationExpression",
                    "maximumLength",
                    "characterSet",
                    "collation",
                }
            ),
        )
        name = _string(column["name"])
        assert isinstance(name, str)
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name) is None:
            _invalid()
        _integer(column["ordinal"], minimum=1, maximum=128)
        _string(column["dataType"])
        _string(column["columnType"])
        if column["nullable"] not in {"YES", "NO"}:
            _invalid()
        _string(column["default"], nullable=True, allow_empty=True)
        if not isinstance(column["extra"], str) or not isinstance(
            column["generationExpression"], str
        ):
            _invalid()
        maximum_length = column["maximumLength"]
        if maximum_length is not None:
            _integer(maximum_length, maximum=4_294_967_295)
        _string(column["characterSet"], nullable=True, allow_empty=True)
        _string(column["collation"], nullable=True, allow_empty=True)
    for item in _items(metadata["constraints"]):
        constraint = _mapping(
            item,
            frozenset(
                {
                    "direction",
                    "name",
                    "type",
                    "table",
                    "column",
                    "ordinal",
                    "referencedTable",
                    "referencedColumn",
                }
            ),
        )
        if constraint["direction"] not in {"owned", "inbound"}:
            _invalid()
        if constraint["type"] not in {"PRIMARY KEY", "UNIQUE", "FOREIGN KEY"}:
            _invalid()
        for key in ("name", "table", "column"):
            _string(constraint[key])
        _integer(constraint["ordinal"], minimum=1, maximum=128)
        _string(constraint["referencedTable"], nullable=True, allow_empty=True)
        _string(constraint["referencedColumn"], nullable=True, allow_empty=True)
    for item in _items(metadata["checks"]):
        check = _mapping(item, frozenset({"name", "expressionSha256"}))
        _string(check["name"])
        _sha256(check["expressionSha256"])
    for item in _items(metadata["triggers"]):
        trigger = _mapping(
            item,
            frozenset(
                {
                    "name",
                    "timing",
                    "event",
                    "orientation",
                    "actionSha256",
                    "sideEffectClassification",
                }
            ),
        )
        _string(trigger["name"])
        if trigger["timing"] not in {"BEFORE", "AFTER"}:
            _invalid()
        if trigger["event"] not in {"INSERT", "UPDATE", "DELETE"}:
            _invalid()
        if trigger["orientation"] != "ROW":
            _invalid()
        _sha256(trigger["actionSha256"])
        if trigger["sideEffectClassification"] != "present_requires_manual_review":
            _invalid()


def validate_result(value: Mapping[str, object]) -> None:
    status = value.get("status")
    expected_keys = set(_RESULT_COMMON_KEYS)
    expected_keys.add("metadata" if status == "passed" else "failure")
    if set(value) != expected_keys:
        _invalid()
    expected_scalars = {
        "schemaVersion": 2,
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }
    for key, expected in expected_scalars.items():
        if value[key] != expected:
            _invalid()
    if status not in {"passed", "failed"}:
        _invalid()
    history = value["history"]
    if not isinstance(history, list) or len(history) != len(_HISTORY):
        _invalid()
    observed: dict[str, str] = {}
    for item in history:
        pair = _mapping(item, frozenset({"path", "sha256"}))
        path = pair["path"]
        sha256 = pair["sha256"]
        if not isinstance(path, str) or not isinstance(sha256, str):
            _invalid()
        observed[path] = sha256
    if observed != _HISTORY:
        _invalid()
    counts = _mapping(value["queryCounts"], _QUERY_COUNT_KEYS)
    if counts["maximum"] != MAX_QUERIES:
        _invalid()
    started = _integer(counts["started"])
    terminal = _integer(counts["terminal"])
    succeeded = _integer(counts["succeeded"])
    failed = _integer(counts["failed"], maximum=1)
    if terminal != started or succeeded + failed != terminal:
        _invalid()
    if counts["retryCount"] != 0 or counts["resumeCount"] != 0:
        _invalid()
    if status == "passed" and (started != MAX_QUERIES or failed != 0):
        _invalid()
    if status == "failed" and started < 1:
        _invalid()
    if status == "passed":
        _validate_metadata(value["metadata"])
    else:
        failure = _mapping(
            value["failure"],
            frozenset({"phase", "reason", "queryOrdinal", "sqlState", "vendorCode"}),
        )
        phase = failure["phase"]
        reason = failure["reason"]
        ordinal = _integer(failure["queryOrdinal"], minimum=1)
        if ordinal != started:
            _invalid()
        sql_state = _string(failure["sqlState"], nullable=True, allow_empty=True)
        if isinstance(sql_state, str) and len(sql_state) > 5:
            _invalid()
        vendor_code = failure["vendorCode"]
        if vendor_code is not None:
            _integer(vendor_code, maximum=2_147_483_647)
        if phase == "result_assembly":
            if (
                reason != "metadata_invalid"
                or ordinal != MAX_QUERIES
                or started != MAX_QUERIES
                or terminal != MAX_QUERIES
                or succeeded != MAX_QUERIES
                or failed != 0
                or sql_state is not None
                or vendor_code is not None
            ):
                _invalid()
        elif (
            phase not in QUERY_PHASES
            or reason != "information_schema_query_failed"
            or QUERY_PHASES[ordinal - 1] != phase
            or failed != 1
            or succeeded != ordinal - 1
        ):
            _invalid()
    safety = _mapping(value["safety"], _SAFETY_KEYS)
    expected_safety = _base_result(
        "failed", raw_logs_deleted=bool(safety["rawLogsDeleted"])
    )["safety"]
    if safety != expected_safety:
        _invalid()
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if any(key in serialized for key in _FORBIDDEN_SERIALIZED_KEYS):
        _invalid()


def validate_lifecycle(path: Path) -> list[Mapping[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        _invalid()
    if len(lines) < 4 or len(lines) > 10:
        _invalid()
    records: list[Mapping[str, object]] = []
    for sequence, line in enumerate(lines, start=1):
        try:
            value = json.loads(line, object_pairs_hook=_unique_object)
        except json.JSONDecodeError:
            _invalid()
        record = _mapping(
            value,
            frozenset(
                {
                    "schemaVersion",
                    "runId",
                    "authorizationReference",
                    "sequence",
                    "event",
                    "phase",
                    "status",
                    "reason",
                    "queryOrdinal",
                    "retryCount",
                    "resumeCount",
                }
            ),
        )
        if (
            record["schemaVersion"] != 2
            or record["runId"] != RUN_ID
            or record["authorizationReference"] != AUTHORIZATION_REFERENCE
            or record["sequence"] != sequence
            or record["retryCount"] != 0
            or record["resumeCount"] != 0
        ):
            _invalid()
        records.append(record)
    first = records[0]
    last = records[-1]
    if (
        first["event"] != "run_started"
        or first["phase"] != "run"
        or first["status"] != "started"
        or first["reason"] is not None
        or first["queryOrdinal"] != 0
        or last["event"] != "run_terminal"
        or last["phase"] != "run"
        or last["queryOrdinal"] != 0
    ):
        _invalid()
    query_records = records[1:-1]
    if len(query_records) % 2 != 0:
        _invalid()
    for index in range(0, len(query_records), 2):
        started = query_records[index]
        terminal = query_records[index + 1]
        ordinal = index // 2 + 1
        phase = QUERY_PHASES[ordinal - 1]
        if (
            started["event"] != "query_started"
            or terminal["event"] != "query_terminal"
            or started["phase"] != phase
            or terminal["phase"] != phase
            or started["queryOrdinal"] != ordinal
            or terminal["queryOrdinal"] != ordinal
            or started["status"] != "started"
            or started["reason"] is not None
        ):
            _invalid()
        if terminal["status"] not in {"succeeded", "failed"}:
            _invalid()
        if terminal["status"] == "succeeded" and terminal["reason"] is not None:
            _invalid()
        if terminal["status"] == "failed" and (
            terminal["reason"] != "information_schema_query_failed"
            or index + 2 != len(query_records)
        ):
            _invalid()
    query_failed = query_records[-1]["status"] == "failed"
    if query_failed:
        if last["status"] != "failed" or last["reason"] != "information_schema_query_failed":
            _invalid()
    else:
        if len(query_records) != MAX_QUERIES * 2:
            _invalid()
        if (last["status"], last["reason"]) not in {
            ("passed", None),
            ("failed", "metadata_invalid"),
        }:
            _invalid()
    return records


def finalize_staging_result(staging_path: Path, result_path: Path) -> None:
    value = load_strict_json(staging_path)
    safety = value.get("safety")
    if not isinstance(safety, dict) or safety.get("rawLogsDeleted") is not False:
        _invalid()
    final = dict(value)
    final_safety = dict(safety)
    final_safety["rawLogsDeleted"] = True
    final["safety"] = final_safety
    validate_result(final)
    write_exclusive_json(result_path, final)


def validate_manifest(
    manifest_path: Path, authorization_path: Path, repository_root: Path
) -> None:
    manifest = load_strict_json(manifest_path)
    authorization = load_strict_json(authorization_path)
    required_manifest = frozenset(
        {
            "schemaVersion",
            "status",
            "preparationWorkPackageId",
            "workPackageId",
            "gateId",
            "runId",
            "authorizationReference",
            "preparedAt",
            "queryBudget",
            "executionBoundary",
            "history",
            "assetHashes",
        }
    )
    if frozenset(manifest) != required_manifest:
        _invalid()
    expected = {
        "schemaVersion": 2,
        "status": "prepared_unconsumed",
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "preparedAt": PREPARED_AT,
        "queryBudget": MAX_QUERIES,
    }
    for key, value in expected.items():
        if manifest[key] != value:
            _invalid()
    boundary = _mapping(
        manifest["executionBoundary"],
        frozenset(
            {
                "databaseAccessAuthorized",
                "liveExecutionAuthorized",
                "retryAllowed",
                "resumeAllowed",
                "lifecycleOutputPath",
                "resultOutputPath",
            }
        ),
    )
    if (
        boundary["databaseAccessAuthorized"] is not False
        or boundary["liveExecutionAuthorized"] is not False
        or boundary["retryAllowed"] is not False
        or boundary["resumeAllowed"] is not False
    ):
        _invalid()
    expected_prefix = (
        "agent-runtime/tests/integration/adapters/employee/evidence/" + RUN_ID
    )
    if (
        boundary["lifecycleOutputPath"] != expected_prefix + ".lifecycle.jsonl"
        or boundary["resultOutputPath"] != expected_prefix + ".result.json"
    ):
        _invalid()
    history = manifest["history"]
    if not isinstance(history, list) or len(history) != len(_HISTORY):
        _invalid()
    manifest_history: dict[str, str] = {}
    for item in history:
        pair = _mapping(item, frozenset({"path", "sha256"}))
        path = pair["path"]
        digest = pair["sha256"]
        if not isinstance(path, str) or path in manifest_history:
            _invalid()
        manifest_history[path] = _sha256(digest)
    if manifest_history != _HISTORY:
        _invalid()
    assets = manifest["assetHashes"]
    if not isinstance(assets, list) or len(assets) != len(_ASSET_PATHS):
        _invalid()
    observed_assets: set[str] = set()
    for item in assets:
        pair = _mapping(item, frozenset({"path", "sha256"}))
        path = pair["path"]
        digest = pair["sha256"]
        if (
            not isinstance(path, str)
            or path in observed_assets
        ):
            _invalid()
        observed_assets.add(path)
        digest = _sha256(digest)
        candidate = repository_root / path
        if not candidate.is_file() or sha256_file(candidate) != digest:
            _invalid()
    if observed_assets != _ASSET_PATHS:
        _invalid()
    verify_history(repository_root)
    manifest_sha = sha256_file(manifest_path)
    expected_authorization = {
        "schemaVersion": 2,
        "status": "prepared_unconsumed",
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "maximumQueries": MAX_QUERIES,
        "databaseAccessAuthorized": False,
        "liveExecutionAuthorized": False,
        "retryAllowed": False,
        "resumeAllowed": False,
        "confirmedBy": "project-maintainer-pending-gate-050-live-authorization",
        "preparedAt": PREPARED_AT,
    }
    if authorization != expected_authorization:
        _invalid()
