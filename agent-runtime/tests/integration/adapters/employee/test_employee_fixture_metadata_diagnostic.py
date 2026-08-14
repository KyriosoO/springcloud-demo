from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tests.integration.adapters.employee.fixture_metadata_diagnostic import (
    AUTHORIZATION_REFERENCE,
    LOGICAL_INSERT_COLUMNS,
    RUN_ID,
    SOURCE_EVIDENCE_SHA256,
    FixtureMetadataDiagnosticError,
    finalize_staging_evidence,
    load_strict_json,
    validate_evidence,
    validate_source_evidence,
    validate_staging_evidence,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_SCHEMA_PATH = Path(__file__).with_name("evidence") / (
    "employee-fixture-metadata-diagnostic-v1.schema.json"
)
_EVIDENCE_PATH = Path(__file__).with_name("evidence") / (
    "employee-fixture-metadata-diagnostic-v1-20260814-run-01.json"
)
_JAVA_PATH = _REPOSITORY_ROOT / (
    "employee-service/src/test/java/com/dylan/employee/live/"
    "EmployeeFixtureMetadataDiagnosticLiveIntegrationTest.java"
)
_PROVIDER_PATH = _REPOSITORY_ROOT / (
    "employee-service/src/main/java/com/dylan/employee/mapper/EmployeeSqlProvider.java"
)
_LAUNCHER_PATH = Path(__file__).with_name(
    "run_employee_fixture_metadata_diagnostic.ps1"
)


def _provider_columns() -> tuple[str, ...]:
    source = _PROVIDER_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"private\s+static\s+final\s+String\[\]\s+COLUMNS\s*=\s*\{(.*?)\};",
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    columns = tuple(re.findall(r'"([A-Z][A-Z0-9_]*)"', match.group(1)))
    assert len(columns) == 58
    return columns


def _column(name: str, ordinal: int) -> dict[str, object]:
    return {
        "columnName": name,
        "ordinalPosition": ordinal,
        "dataType": "varchar",
        "columnType": "varchar(256)",
        "isNullable": "NO" if name in LOGICAL_INSERT_COLUMNS else "YES",
        "columnDefault": None,
        "extra": "",
        "generationExpression": "",
        "characterMaximumLength": 256,
        "characterSetName": "utf8mb4",
        "collationName": "utf8mb4_general_ci",
    }


def _valid_staging() -> dict[str, object]:
    columns = [
        _column(name, ordinal)
        for ordinal, name in enumerate(_provider_columns(), start=1)
    ]
    constraints: list[dict[str, object]] = [
        {
            "direction": "owned",
            "constraintName": "PRIMARY",
            "constraintType": "PRIMARY KEY",
            "tableName": "employee",
            "columnName": "ID_CARD_NO",
            "ordinalPosition": 1,
            "referencedTableName": None,
            "referencedColumnName": None,
        }
    ]
    return {
        "schemaVersion": 1,
        "workPackageId": "WP-EMP-EGRESS-TEST-DATA-PREP-01",
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "recordedAt": "2026-08-14T12:00:00Z",
        "status": "collected",
        "sourceEvidence": {
            "path": (
                "agent-runtime/tests/integration/adapters/employee/evidence/"
                "employee-work-base-data-diagnostic-v1-20260814-run-01.json"
            ),
            "sha256": SOURCE_EVIDENCE_SHA256,
        },
        "tableMetadata": {
            "tableName": "employee",
            "engine": "InnoDB",
            "columns": columns,
        },
        "constraintMetadata": {"entries": constraints, "checks": []},
        "triggerMetadata": {"entries": []},
        "counts": {
            "maxQueries": 4,
            "executedQueries": 4,
            "columnQueries": 1,
            "columnResultRows": 58,
            "constraintQueries": 1,
            "constraintResultRows": 1,
            "checkQueries": 1,
            "checkResultRows": 0,
            "triggerQueries": 1,
            "triggerResultRows": 0,
            "employeeBusinessRowQueries": 0,
            "employeeEndpointCalls": 0,
            "authCalls": 0,
            "modelCalls": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "safety": {
            "businessRowsRead": False,
            "identifiersPersisted": False,
            "fieldValuesPersisted": False,
            "rawTriggerStatementsPersisted": False,
            "jwtRead": False,
            "llmApiKeyRead": False,
            "modelOutbound": False,
            "databaseWrites": 0,
            "schemaChanges": 0,
            "logLeakCount": 0,
            "rawLogsDeleted": False,
        },
    }


def _finalize(staging: dict[str, object], tmp_path: Path) -> dict[str, Any]:
    staging_path = tmp_path / "staging.json"
    evidence_path = tmp_path / "evidence.json"
    staging_path.write_text(
        json.dumps(staging, ensure_ascii=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    finalize_staging_evidence(staging_path, evidence_path, _REPOSITORY_ROOT)
    evidence = load_strict_json(evidence_path)
    validate_evidence(evidence, _REPOSITORY_ROOT)
    return evidence


def test_safe_metadata_closes_only_the_fixture_preparation_gate(tmp_path: Path) -> None:
    evidence = _finalize(_valid_staging(), tmp_path)

    assert evidence["assessment"] == {
        "result": "gate_closed",
        "reason": "safe_to_prepare_fixture",
        "metadataComplete": True,
        "transactionalEngine": True,
        "providerColumnSetMatches": True,
        "logicalFieldsPresent": True,
        "logicalFieldsWritable": True,
        "minimalInsertColumns": list(LOGICAL_INSERT_COLUMNS),
        "blockingRequiredColumns": [],
        "idCardNoUnique": True,
        "outboundForeignKeyConstraints": 0,
        "inboundForeignKeyConstraints": 0,
        "checkConstraints": 0,
        "triggers": 0,
        "exactCleanupSupported": True,
        "gateMayClose": True,
    }
    assert evidence["safety"]["rawLogsDeleted"] is True


def _unsupported_engine(value: dict[str, Any]) -> None:
    value["tableMetadata"]["engine"] = "MyISAM"


def _required_omitted_column(value: dict[str, Any]) -> None:
    columns = value["tableMetadata"]["columns"]
    member_no = next(item for item in columns if item["columnName"] == "MEMBER_NO")
    member_no["isNullable"] = "NO"


def _remove_identifier_key(value: dict[str, Any]) -> None:
    value["constraintMetadata"]["entries"] = []
    value["counts"]["constraintResultRows"] = 0


def _add_outbound_foreign_key(value: dict[str, Any]) -> None:
    value["constraintMetadata"]["entries"].append(
        {
            "direction": "owned",
            "constraintName": "FK_EMPLOYEE_TEST",
            "constraintType": "FOREIGN KEY",
            "tableName": "employee",
            "columnName": "MEMBER_NO",
            "ordinalPosition": 1,
            "referencedTableName": "member",
            "referencedColumnName": "MEMBER_NO",
        }
    )
    value["counts"]["constraintResultRows"] = 2


def _add_check(value: dict[str, Any]) -> None:
    value["constraintMetadata"]["checks"].append(
        {"constraintName": "CHK_EMPLOYEE_TEST", "checkClause": "POSITION <> ''"}
    )
    value["counts"]["checkResultRows"] = 1


def _add_trigger(value: dict[str, Any]) -> None:
    value["triggerMetadata"]["entries"].append(
        {
            "triggerName": "TR_EMPLOYEE_TEST",
            "timing": "AFTER",
            "event": "INSERT",
            "orientation": "ROW",
            "actionStatementSha256": "0" * 64,
            "sideEffectClassification": "present_requires_manual_review",
        }
    )
    value["counts"]["triggerResultRows"] = 1


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (_unsupported_engine, "unsupported_engine"),
        (_required_omitted_column, "omitted_required_columns"),
        (_remove_identifier_key, "identifier_not_unique"),
        (_add_outbound_foreign_key, "foreign_keys_present"),
        (_add_check, "checks_present"),
        (_add_trigger, "triggers_present"),
    ],
)
def test_physical_contract_risks_keep_gate_open(
    mutate: Callable[[dict[str, Any]], None], reason: str, tmp_path: Path
) -> None:
    staging = cast(dict[str, Any], _valid_staging())
    mutate(staging)

    evidence = _finalize(staging, tmp_path)

    assert evidence["assessment"]["result"] == "gate_open"
    assert evidence["assessment"]["reason"] == reason
    assert evidence["assessment"]["exactCleanupSupported"] is False
    assert evidence["assessment"]["gateMayClose"] is False


def test_query_budget_and_raw_trigger_statement_fail_closed() -> None:
    staging = cast(dict[str, Any], _valid_staging())
    staging["counts"]["executedQueries"] = 5
    with pytest.raises(FixtureMetadataDiagnosticError):
        validate_staging_evidence(staging)

    staging = cast(dict[str, Any], _valid_staging())
    _add_trigger(staging)
    staging["triggerMetadata"]["entries"][0]["actionStatement"] = "forbidden"
    with pytest.raises(FixtureMetadataDiagnosticError):
        validate_staging_evidence(staging)


@pytest.mark.parametrize(
    ("key", "value"),
    [("databaseWrites", False), ("businessRowsRead", 0)],
)
def test_safety_boolean_and_integer_types_are_not_interchangeable(
    key: str, value: object
) -> None:
    staging = cast(dict[str, Any], _valid_staging())
    staging["safety"][key] = value

    with pytest.raises(FixtureMetadataDiagnosticError):
        validate_staging_evidence(staging)


def test_schema_is_strict_and_binds_gate_and_query_budget() -> None:
    schema = load_strict_json(_SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    properties = cast(dict[str, Any], schema["properties"])
    assert properties["runId"]["const"] == RUN_ID
    assert properties["authorizationReference"]["const"] == AUTHORIZATION_REFERENCE
    assert properties["counts"]["properties"]["maxQueries"]["const"] == 4
    assert properties["counts"]["properties"]["executedQueries"]["const"] == 4
    assert properties["safety"]["properties"]["databaseWrites"]["const"] == 0
    assert properties["safety"]["properties"]["rawTriggerStatementsPersisted"][
        "const"
    ] is False


def test_java_probe_contains_exactly_four_information_schema_queries() -> None:
    source = _JAVA_PATH.read_text(encoding="utf-8")
    assert source.count("jdbcTemplate.queryForList(") == 4
    assert source.count("FROM information_schema.") == 5
    assert "FROM employee" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE employee" not in source
    assert "DELETE FROM" not in source
    assert "@Transactional(readOnly = true)" in source
    assert "EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_QUERIES" in source
    assert source.index("verifyHistory(") < source.index("jdbcTemplate.queryForList(")
    assert "actionStatementSha256" in source
    assert '.put("actionStatement",' not in source


def test_launcher_is_one_shot_and_never_reads_credentials_or_employee_values() -> None:
    source = _LAUNCHER_PATH.read_text(encoding="utf-8")
    assert source.count("EmployeeFixtureMetadataDiagnosticLiveIntegrationTest") == 1
    assert source.count("finalize_staging_evidence(Path") == 1
    assert ".TrimEnd(" in source
    assert "Remove-Item Env:\\LLM_API_KEY" in source
    assert "GetEnvironmentVariable('LLM_API_KEY'" not in source
    assert "EMPLOYEE_LIVE_TEST_IDENTIFIER" in source
    assert "Authorization" not in source
    assert "employee.detail" not in source
    assert SOURCE_EVIDENCE_SHA256 in source


def test_bound_source_evidence_is_unchanged() -> None:
    validate_source_evidence(_REPOSITORY_ROOT)


def test_live_evidence_is_strict_when_present() -> None:
    if not _EVIDENCE_PATH.is_file():
        pytest.skip("GATE-050 evidence has not been generated")
    evidence = load_strict_json(_EVIDENCE_PATH)
    validate_evidence(evidence, _REPOSITORY_ROOT)
