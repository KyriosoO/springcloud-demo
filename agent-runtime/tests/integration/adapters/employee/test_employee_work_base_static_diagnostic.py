from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tests.integration.adapters.employee.work_base_static_diagnostic import (
    SOURCE_EVIDENCE_SHA256,
    WorkBaseStaticDiagnosticError,
    _employee_asset_counts,
    inspect_current_repository,
    load_strict_json,
    validate_evidence,
    validate_repository_snapshot,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_SCHEMA_PATH = Path(__file__).with_name("evidence") / (
    "employee-work-base-static-diagnostic-v1.schema.json"
)
_EVIDENCE_PATH = Path(__file__).with_name("evidence") / (
    "employee-work-base-static-diagnostic-v1-20260814-run-01.json"
)


def test_repository_inspection_excludes_read_mapping_as_the_zero_count_cause() -> None:
    inspection = inspect_current_repository(_REPOSITORY_ROOT)

    assert all(cast(dict[str, bool], inspection["mapping"]).values())
    assert inspection["writeSources"] == {
        "controllerUsesMapPayload": True,
        "serviceUsesMapPayload": True,
        "insertWritesOnlyPresentKey": True,
        "updateWritesOnlyPresentKey": True,
        "typedWriteRequestDto": False,
        "workBaseRequiredValidation": False,
        "workBaseDefaulting": False,
        "workBaseBackfill": False,
        "esRebuildIsDownstream": True,
    }
    assert inspection["repositoryAssets"] == {
        "employeeDdlAssets": 0,
        "employeeDataAssets": 0,
        "employeeInitializationComponents": 0,
        "employeeImportComponents": 0,
        "employeeBackfillComponents": 0,
    }


def test_repository_asset_scan_detects_employee_population_sources(
    tmp_path: Path,
) -> None:
    employee_resources = tmp_path / "employee-service" / "src" / "main" / "resources"
    employee_resources.mkdir(parents=True)
    (employee_resources / "schema.ddl").write_text(
        "CREATE TABLE EMPLOYEE (WORK_BASE_SI VARCHAR(256));",
        encoding="utf-8",
    )
    (employee_resources / "employees.csv").write_text(
        "employee,workBaseSi\nsynthetic,synthetic\n",
        encoding="utf-8",
    )
    employee_main = tmp_path / "employee-service" / "src" / "main" / "java"
    employee_main.mkdir(parents=True)
    (employee_main / "EmployeeImporter.java").write_text(
        "final class EmployeeImporter {}",
        encoding="utf-8",
    )

    counts = _employee_asset_counts(tmp_path)

    assert counts["employeeDdlAssets"] == 1
    assert counts["employeeDataAssets"] == 1
    assert counts["employeeImportComponents"] == 1


def test_repository_asset_scan_ignores_ordinary_language_imports(
    tmp_path: Path,
) -> None:
    employee_main = tmp_path / "employee-service" / "src" / "main" / "java"
    employee_main.mkdir(parents=True)
    (employee_main / "Employee.java").write_text(
        "import java.util.Map; final class Employee { String workBaseSi; }",
        encoding="utf-8",
    )

    assert _employee_asset_counts(tmp_path)["employeeImportComponents"] == 0


def test_repository_asset_scan_ignores_mypy_cache(
    tmp_path: Path,
) -> None:
    cache = tmp_path / ".mypy_cache" / "3.12" / "agent_runtime"
    cache.mkdir(parents=True)
    (cache / "bootstrap.data.json").write_text(
        '{"employee":"applicationrunner"}',
        encoding="utf-8",
    )

    assert _employee_asset_counts(tmp_path)["employeeInitializationComponents"] == 0


def test_frozen_evidence_has_strict_static_limited_conclusion() -> None:
    evidence = load_strict_json(_EVIDENCE_PATH)
    validate_evidence(evidence)

    assert evidence["sourceEvidence"] == {
        "path": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            "employee-egress-input-qualification-diagnostic-v2-20260814-run-01.json"
        ),
        "sha256": SOURCE_EVIDENCE_SHA256,
        "totalRows": 990,
        "workBaseSiValidRows": 0,
    }
    assert evidence["diagnosis"] == {
        "reason": "data_population_provenance_gap",
        "readMappingCauseExcluded": True,
        "physicalColumnDefinition": "not_versioned",
        "rawValueDistribution": "not_observable_without_separate_query",
        "confidence": "strong_static_mapping_limited_physical_state",
        "nextStep": "separate_metadata_and_aggregate_authorization_required",
    }
    assert evidence["safety"] == {
        "databaseQueries": 0,
        "employeeEndpointCalls": 0,
        "serviceStarts": 0,
        "modelCalls": 0,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "identifiersPersisted": False,
        "fieldValuesPersisted": False,
    }


def _add_extra(value: dict[str, Any]) -> None:
    value["extra"] = "forbidden"


def _claim_known_physical_definition(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["diagnosis"])["physicalColumnDefinition"] = "known"


def _claim_query(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["safety"])["databaseQueries"] = 1


def _claim_required_write(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["writeSources"])["workBaseRequiredValidation"] = True


@pytest.mark.parametrize(
    "mutate",
    [_add_extra, _claim_known_physical_definition, _claim_query, _claim_required_write],
)
def test_validator_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    value = load_strict_json(_EVIDENCE_PATH)
    copied = cast(dict[str, Any], json.loads(json.dumps(value)))
    mutate(copied)

    with pytest.raises(WorkBaseStaticDiagnosticError):
        validate_evidence(copied)


def test_schema_is_strict_and_forbids_external_activity() -> None:
    schema = load_strict_json(_SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    properties = cast(dict[str, Any], schema["properties"])
    for key in (
        "sourceEvidence",
        "mapping",
        "writeSources",
        "repositoryAssets",
        "diagnosis",
        "safety",
    ):
        assert cast(dict[str, Any], properties[key])["additionalProperties"] is False
    safety = cast(dict[str, Any], properties["safety"])["properties"]
    for key in ("databaseQueries", "employeeEndpointCalls", "serviceStarts", "modelCalls"):
        assert cast(dict[str, Any], safety[key])["const"] == 0


def test_frozen_evidence_remains_valid_without_rebinding_current_sources() -> None:
    evidence = load_strict_json(_EVIDENCE_PATH)
    validate_evidence(evidence)


def test_historical_snapshot_validation_fails_closed_for_missing_sources(
    tmp_path: Path,
) -> None:
    with pytest.raises(WorkBaseStaticDiagnosticError):
        validate_repository_snapshot(tmp_path)


def test_evidence_contains_no_employee_values_or_credentials() -> None:
    raw = _EVIDENCE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "employeeIdentifier",
        "idCardNoValue",
        '"fieldValue":',
        "rawRecord",
        "Authorization: Bearer",
        "LLM_API_KEY=",
    ):
        assert forbidden not in raw
