from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tests.integration.adapters.employee.work_base_data_diagnostic import (
    SOURCE_EVIDENCE_SHA256,
    WorkBaseDataDiagnosticError,
    build_evidence,
    finalize_staging_evidence,
    load_strict_json,
    validate_evidence,
    validate_source_evidence,
    validate_staging_evidence,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_SCHEMA_PATH = Path(__file__).with_name("evidence") / (
    "employee-work-base-data-diagnostic-v1.schema.json"
)
_EVIDENCE_PATH = Path(__file__).with_name("evidence") / (
    "employee-work-base-data-diagnostic-v1-20260814-run-01.json"
)
_JAVA_PATH = _REPOSITORY_ROOT / (
    "employee-service/src/test/java/com/dylan/employee/live/"
    "EmployeeWorkBaseDataDiagnosticLiveIntegrationTest.java"
)
_LAUNCHER_PATH = Path(__file__).with_name(
    "run_employee_work_base_data_diagnostic.ps1"
)


def _column() -> dict[str, object]:
    return {
        "dataType": "varchar",
        "columnType": "varchar(256)",
        "isNullable": "YES",
        "characterMaximumLength": 256,
        "columnDefault": None,
        "collationName": "utf8mb4_0900_ai_ci",
    }


def _counts(**overrides: int) -> dict[str, int]:
    values = {
        "totalRows": 990,
        "nullRows": 990,
        "lengthInvalidRows": 0,
        "controlCharacterRows": 0,
        "bidiControlRows": 0,
        "validRows": 0,
        "metadataQueries": 1,
        "metadataResultRows": 1,
        "aggregateQueries": 1,
        "aggregateResultRows": 1,
        "employeeEndpointCalls": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    values.update(overrides)
    return values


def test_builds_strict_all_null_diagnosis() -> None:
    evidence = build_evidence(
        column_definition=_column(),
        counts=_counts(),
        recorded_at="2026-08-14T08:00:00Z",
    )

    assert evidence["diagnosis"] == {
        "reason": "all_rows_null",
        "distributionProven": True,
        "sourceSnapshotMatches": True,
        "nextStep": "separate_test_data_remediation_authorization_required",
    }
    assert cast(dict[str, Any], evidence["sourceEvidence"])["sha256"] == (
        SOURCE_EVIDENCE_SHA256
    )


def test_builds_mixed_invalid_diagnosis_from_a_complete_partition() -> None:
    evidence = build_evidence(
        column_definition=_column(),
        counts=_counts(nullRows=900, lengthInvalidRows=80, controlCharacterRows=10),
        recorded_at="2026-08-14T08:00:00Z",
    )

    assert cast(dict[str, Any], evidence["diagnosis"])["reason"] == (
        "mixed_invalid_values"
    )


def test_source_snapshot_drift_fails_closed_without_claiming_distribution() -> None:
    evidence = build_evidence(
        column_definition=_column(),
        counts=_counts(totalRows=991, nullRows=990, validRows=1),
        recorded_at="2026-08-14T08:00:00Z",
    )

    assert evidence["diagnosis"] == {
        "reason": "source_snapshot_mismatch",
        "distributionProven": False,
        "sourceSnapshotMatches": False,
        "nextStep": "reconcile_source_snapshot_required",
    }


def _add_extra(value: dict[str, Any]) -> None:
    value["extra"] = "forbidden"


def _break_partition(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["counts"])["nullRows"] = 989


def _add_query(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["counts"])["aggregateQueries"] = 2


def _claim_field_value(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["safety"])["fieldValuesPersisted"] = True


def _change_reason(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["diagnosis"])["reason"] = "mixed_invalid_values"


@pytest.mark.parametrize(
    "mutate",
    [_add_extra, _break_partition, _add_query, _claim_field_value, _change_reason],
)
def test_validator_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    value = build_evidence(
        column_definition=_column(),
        counts=_counts(),
        recorded_at="2026-08-14T08:00:00Z",
    )
    copied = cast(dict[str, Any], json.loads(json.dumps(value)))
    mutate(copied)

    with pytest.raises(WorkBaseDataDiagnosticError):
        validate_evidence(copied)


def test_staging_only_finalizes_after_raw_log_cleanup(tmp_path: Path) -> None:
    staging = build_evidence(
        column_definition=_column(),
        counts=_counts(),
        recorded_at="2026-08-14T08:00:00Z",
        raw_logs_deleted=False,
    )
    validate_staging_evidence(staging)
    with pytest.raises(WorkBaseDataDiagnosticError):
        validate_evidence(staging)

    staging_path = tmp_path / "staging.json"
    final_path = tmp_path / "evidence.json"
    staging_path.write_text(
        json.dumps(staging, ensure_ascii=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    finalize_staging_evidence(staging_path, final_path)

    validate_evidence(load_strict_json(final_path))


def test_schema_is_strict_and_limits_queries_and_external_calls() -> None:
    schema = load_strict_json(_SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    properties = cast(dict[str, Any], schema["properties"])
    for key in ("sourceEvidence", "columnDefinition", "counts", "diagnosis", "safety"):
        assert cast(dict[str, Any], properties[key])["additionalProperties"] is False
    counts = cast(dict[str, Any], properties["counts"])["properties"]
    assert cast(dict[str, Any], counts["metadataQueries"])["const"] == 1
    assert cast(dict[str, Any], counts["aggregateQueries"])["const"] == 1
    assert cast(dict[str, Any], counts["employeeEndpointCalls"])["const"] == 0
    assert cast(dict[str, Any], counts["modelCalls"])["const"] == 0


def test_java_diagnostic_contains_exactly_two_bounded_read_only_queries() -> None:
    source = _JAVA_PATH.read_text(encoding="utf-8")
    assert source.count("jdbcTemplate.queryForList(") == 1
    assert source.count("jdbcTemplate.queryForMap(") == 1
    assert "FROM information_schema.columns" in source
    for column in (
        "DATA_TYPE AS dataType",
        "COLUMN_TYPE AS columnType",
        "IS_NULLABLE AS isNullable",
        "CHARACTER_MAXIMUM_LENGTH AS characterMaximumLength",
        "COLUMN_DEFAULT AS columnDefault",
        "COLLATION_NAME AS collationName",
    ):
        assert column in source
    assert "FROM employee" in source
    assert source.count("SUM(CASE") == 5
    assert "@Transactional(readOnly = true)" in source
    assert "SELECT WORK_BASE_SI" not in source
    assert "GROUP BY" not in source
    assert "getString(" not in source
    assert "WebEnvironment.NONE" in source
    assert "RestTemplate" not in source
    assert "WebClient" not in source
    assert "EXECUTE_EMPLOYEE_WORK_BASE_DATA_DIAG_QUERIES" in source
    assert source.index("EXECUTE_EMPLOYEE_WORK_BASE_DATA_DIAG_QUERIES") < source.index(
        "jdbcTemplate.queryForList("
    )


def test_launcher_is_fail_closed_and_never_reads_auth_or_model_credentials() -> None:
    source = _LAUNCHER_PATH.read_text(encoding="utf-8")
    cleanup = source.index("Remove-Item -LiteralPath $mavenLog -Force")
    finalize = source.index("finalize_staging_evidence")
    assert cleanup < finalize
    assert "Remove-VerifiedTempTree -Path $reports" in source
    assert "Remove-Item Env:\\LLM_API_KEY" in source
    assert "GetEnvironmentVariable('LLM_API_KEY'" not in source
    assert "EMPLOYEE_LIVE_TEST_IDENTIFIER" not in source
    assert "Authorization" not in source
    assert "employee.detail" not in source
    assert SOURCE_EVIDENCE_SHA256 in source


def test_static_source_evidence_is_unchanged() -> None:
    validate_source_evidence(_REPOSITORY_ROOT)


def test_live_evidence_is_strict_when_explicitly_requested() -> None:
    raw_path = os.environ.get("EMPLOYEE_WORK_BASE_DATA_DIAG_EVIDENCE")
    if raw_path is None:
        pytest.skip("work-base data diagnostic evidence validation is opt-in")
    validate_evidence(load_strict_json(Path(raw_path)))
