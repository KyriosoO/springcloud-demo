from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tests.integration.adapters.employee.egress_input_qualification_diagnostic_v2 import (
    CANDIDATE_LIFECYCLE_SHA256,
    CANDIDATE_RESULT_SHA256,
    DiagnosticV2Error,
    build_evidence,
    finalize_staging_evidence,
    load_strict_json,
    validate_candidate_history,
    validate_evidence,
    validate_staging_evidence,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_SCHEMA_PATH = Path(__file__).with_name("evidence") / (
    "employee-egress-input-qualification-diagnostic-v2.schema.json"
)
_JAVA_PATH = _REPOSITORY_ROOT / (
    "employee-service/src/test/java/com/dylan/employee/live/"
    "EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest.java"
)
_LAUNCHER_PATH = Path(__file__).with_name(
    "run_employee_egress_input_qualification_diagnostic_v2.ps1"
)


def _counts(*, full: int = 0) -> dict[str, int]:
    return {
        "totalRows": 10,
        "idCardNoCondition": 9,
        "chineseNameCondition": 8,
        "positionCondition": 7,
        "workBaseSiCondition": 6,
        "cumulativeIdCardNo": 9,
        "cumulativeChineseName": 8,
        "cumulativePosition": 3,
        "cumulativeWorkBaseSi": full,
        "aggregateQueries": 1,
        "resultRows": 1,
        "employeeDetailCalls": 0,
        "otherEmployeeEndpointCalls": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }


def test_builds_strict_finite_no_qualified_input_evidence() -> None:
    evidence = build_evidence(_counts(), recorded_at="2026-08-14T00:00:00Z")

    assert evidence["diagnosis"] == {
        "reason": "no_qualified_input",
        "qualifiedInputAvailable": False,
        "firstZeroStage": "work_base_si",
    }
    encoded = json.dumps(evidence, ensure_ascii=True)
    assert CANDIDATE_LIFECYCLE_SHA256 in encoded
    assert CANDIDATE_RESULT_SHA256 in encoded
    assert "idCardNoCondition" in encoded
    assert "employeeDetailCalls\": 0" in encoded


def test_builds_available_diagnosis_without_claiming_qualification() -> None:
    evidence = build_evidence(_counts(full=2), recorded_at="2026-08-14T00:00:00Z")

    assert evidence["status"] == "completed"
    assert evidence["diagnosis"] == {
        "reason": "qualified_input_available",
        "qualifiedInputAvailable": True,
        "firstZeroStage": "none",
    }


def _add_extra(value: dict[str, Any]) -> None:
    value["extra"] = "forbidden"


def _set_model_call(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["counts"])["modelCalls"] = 1


def _set_non_monotonic(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["counts"])["cumulativePosition"] = 9


def _set_wrong_zero_stage(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["diagnosis"])["firstZeroStage"] = "position"


def _set_identifier_persisted(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["safety"])["identifierPersisted"] = True


@pytest.mark.parametrize(
    "mutate",
    [
        _add_extra,
        _set_model_call,
        _set_non_monotonic,
        _set_wrong_zero_stage,
        _set_identifier_persisted,
    ],
)
def test_validator_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    value = build_evidence(_counts(), recorded_at="2026-08-14T00:00:00Z")
    copied = cast(dict[str, Any], json.loads(json.dumps(value)))
    mutate(copied)

    with pytest.raises(DiagnosticV2Error):
        validate_evidence(copied)


def test_reports_the_first_cumulative_zero_stage() -> None:
    counts = _counts()
    counts.update(
        {
            "chineseNameCondition": 0,
            "cumulativeChineseName": 0,
            "cumulativePosition": 0,
            "cumulativeWorkBaseSi": 0,
        }
    )
    evidence = build_evidence(counts, recorded_at="2026-08-14T00:00:00Z")

    assert cast(dict[str, object], evidence["diagnosis"])["firstZeroStage"] == (
        "chinese_name"
    )


def test_schema_is_structurally_strict() -> None:
    schema = load_strict_json(_SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    properties = cast(dict[str, Any], schema["properties"])
    for key in ("sourceEvidence", "counts", "diagnosis", "safety"):
        assert cast(dict[str, Any], properties[key])["additionalProperties"] is False
    count_properties = cast(dict[str, Any], properties["counts"])["properties"]
    assert cast(dict[str, Any], count_properties["aggregateQueries"])["const"] == 1
    assert cast(dict[str, Any], count_properties["employeeDetailCalls"])["const"] == 0
    assert cast(dict[str, Any], count_properties["modelCalls"])["const"] == 0


def test_staging_can_only_be_finalized_after_log_cleanup(tmp_path: Path) -> None:
    staging_value = build_evidence(_counts(), recorded_at="2026-08-14T00:00:00Z")
    cast(dict[str, Any], staging_value["safety"])["rawLogsDeleted"] = False
    validate_staging_evidence(staging_value)
    with pytest.raises(DiagnosticV2Error):
        validate_evidence(staging_value)

    staging_path = tmp_path / "staging.json"
    final_path = tmp_path / "evidence.json"
    staging_path.write_text(
        json.dumps(staging_value, ensure_ascii=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    finalize_staging_evidence(staging_path, final_path)

    final = load_strict_json(final_path)
    validate_evidence(final)
    assert cast(dict[str, object], final["safety"])["rawLogsDeleted"] is True


def test_java_diagnostic_is_one_aggregate_query_and_never_selects_raw_values() -> None:
    source = _JAVA_PATH.read_text(encoding="utf-8")
    assert source.count("jdbcTemplate.queryForMap(") == 1
    assert source.count("SUM(CASE WHEN") == 8
    assert "COUNT(*) AS totalRows" in source
    assert "SELECT ID_CARD_NO" not in source
    assert "SELECT CHINESE_NAME" not in source
    assert "SELECT POSITION" not in source
    assert "SELECT WORK_BASE_SI" not in source
    assert "getString(" not in source
    assert "WebEnvironment.NONE" in source
    assert "@LocalServerPort" not in source
    assert "RestTemplate" not in source
    assert "WebClient" not in source
    assert "verifyHistory(" in source
    assert "rawLogsDeleted\", false" in source
    assert "classes = EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest." in source
    assert "DiagnosticApplication.class" in source
    assert "EXECUTE_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_QUERY" in source
    assert source.index("EXECUTE_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_QUERY") < source.index(
        "jdbcTemplate.queryForMap("
    )


def test_launcher_cleans_logs_before_final_evidence_and_never_reads_model_key() -> None:
    source = _LAUNCHER_PATH.read_text(encoding="utf-8")
    cleanup = source.index("Remove-Item -LiteralPath $mavenLog -Force")
    finalize = source.index("finalize_staging_evidence")
    assert cleanup < finalize
    assert "Remove-VerifiedTempTree -Path $reports" in source
    assert "Remove-Item Env:\\LLM_API_KEY" in source
    assert "GetEnvironmentVariable('LLM_API_KEY'" not in source
    assert "RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2" in source
    assert "employee.detail" not in source


def test_candidate_02_history_hashes_are_unchanged() -> None:
    validate_candidate_history(_REPOSITORY_ROOT)


def test_live_evidence_is_strict_when_explicitly_requested() -> None:
    raw_path = os.environ.get("EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_EVIDENCE")
    if raw_path is None:
        pytest.skip("diagnostic evidence validation is opt-in")
    value = load_strict_json(Path(raw_path))
    validate_evidence(value)
