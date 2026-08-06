from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from tests.integration.adapters.employee.evidence_contract import (
    validate_final_evidence,
    validate_gateway_log_evidence,
    validate_probe_evidence,
)
from agent_runtime.capability_api.contracts import freeze_json_object
from tests.integration.adapters.employee.test_real_employee_live import (
    _contains_identifier,
    _safe_probe_failure_code,
)

ROOT = Path(__file__).parents[5]
SCHEMA = Path(__file__).parent / "evidence" / "employee-live-evidence-v1.schema.json"
GATEWAY_SCHEMA = Path(__file__).parent / "evidence" / "employee-gateway-log-evidence-v1.schema.json"


def _matrix() -> dict[str, str]:
    return {
        "adminPrimary": "allowed",
        "adminSecondary": "allowed",
        "viewer": "allowed",
        "unknownRole": "forbidden",
        "missingToken": "unauthenticated",
        "malformedToken": "unauthenticated",
        "serviceToken": "unauthenticated",
    }


def _final_evidence() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "workPackage": "WP-EMP-REAL-01",
        "status": "passed",
        "startedAtUtc": "2026-08-06T00:00:00Z",
        "completedAtUtc": "2026-08-06T00:00:01Z",
        "durationMs": 1000,
        "authorizationMatrix": _matrix(),
        "requestCounts": {
            "employee": 7,
            "adapter": 6,
            "serviceDetail": 3,
            "mapperSelectByIdCardNo": 3,
            "otherServiceMethods": 0,
            "otherEmployeeEndpoints": 0,
            "model": 0,
        },
        "responseVisibility": "validated_by_employee_adapter_and_fixture",
        "logSafety": {
            "logLeakCount": 0,
            "rawLogsDeleted": True,
            "identifierPersisted": False,
            "jwtPersisted": False,
            "hmacKeyPersisted": False,
        },
        "runtimeIsolation": {
            "authService": "isolated_local",
            "employeeService": "spring_boot_test",
            "gatewayStarted": False,
            "esCalled": False,
            "workflowCalled": False,
            "deepSeekCalled": False,
        },
    }


def _gateway_evidence() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "workPackage": "WP-EMP-REAL-01",
        "validation": "VAL-EMP-005",
        "status": "passed",
        "startedAtUtc": "2026-08-06T00:00:00Z",
        "completedAtUtc": "2026-08-06T00:00:01Z",
        "durationMs": 1000,
        "requestCounts": {
            "gateway": 1,
            "servlet": 1,
            "serviceDetail": 1,
            "mapperSelectByIdCardNo": 1,
            "otherServiceMethods": 0,
        },
        "responseStatus": 400,
        "logSafety": {
            "logLeakCount": 0,
            "rawLogsDeleted": True,
            "sentinelPersisted": False,
            "jwtPersisted": False,
            "hmacKeyPersisted": False,
            "fullPathPersisted": False,
        },
        "runtimeIsolation": {
            "gatewayService": "actual_jar_test_route",
            "employeeService": "spring_boot_test_servlet",
            "permanentEmployeeRoute": False,
            "realEmployeeIdentifierUsed": False,
            "deepSeekCalled": False,
        },
    }


def test_evidence_schema_and_strict_validator_freeze_finite_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(_final_evidence())
    assert schema["properties"]["requestCounts"]["properties"]["employee"]["const"] == 7
    assert validate_final_evidence(_final_evidence())["status"] == "passed"


def test_evidence_validator_rejects_extra_fields_and_false_success() -> None:
    extra = _final_evidence()
    extra["identifier"] = "forbidden"
    with pytest.raises(ValueError, match="employee.live_evidence_invalid"):
        validate_final_evidence(extra)
    wrong_count = _final_evidence()
    request_counts = wrong_count["requestCounts"]
    assert isinstance(request_counts, dict)
    wrong_count["requestCounts"] = {**request_counts, "employee": 8}
    with pytest.raises(ValueError, match="employee.live_evidence_invalid"):
        validate_final_evidence(wrong_count)


def test_gateway_log_evidence_schema_and_validator_are_strict() -> None:
    schema = json.loads(GATEWAY_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(_gateway_evidence())
    assert schema["properties"]["requestCounts"]["properties"]["gateway"]["const"] == 1
    assert validate_gateway_log_evidence(_gateway_evidence())["validation"] == "VAL-EMP-005"
    extra = _gateway_evidence()
    extra["sentinel"] = "forbidden"
    with pytest.raises(ValueError, match="employee.live_evidence_invalid"):
        validate_gateway_log_evidence(extra)
    repeated = _gateway_evidence()
    counts = repeated["requestCounts"]
    assert isinstance(counts, dict)
    repeated["requestCounts"] = {**counts, "gateway": 2}
    with pytest.raises(ValueError, match="employee.live_evidence_invalid"):
        validate_gateway_log_evidence(repeated)


def test_probe_contract_requires_all_seven_cases_and_bounded_calls() -> None:
    probe = {
        "schemaVersion": 1,
        "authorizationMatrix": _matrix(),
        "requestCounts": {"employee": 7, "adapter": 6, "otherEmployeeEndpoints": 0, "model": 0},
        "responseVisibility": "validated_by_employee_adapter_and_fixture",
    }
    assert validate_probe_evidence(probe)["schemaVersion"] == 1
    probe["authorizationMatrix"] = {**_matrix(), "missingToken": "allowed"}
    with pytest.raises(ValueError, match="employee.live_evidence_invalid"):
        validate_probe_evidence(probe)


def test_live_probe_failure_classification_never_returns_exception_payload() -> None:
    assert (
        _safe_probe_failure_code(AssertionError("employee.live_case_failed:adminPrimary"))
        == "employee.live_case_failed:adminPrimary"
    )
    assert _safe_probe_failure_code(RuntimeError("sensitive runtime payload")) == "employee.live_probe_runtime_error"
    assert _safe_probe_failure_code(httpx.ConnectError("sensitive request URL")) == "employee.live_probe_http_error"
    assert _safe_probe_failure_code(TypeError("sensitive typed payload")) == "employee.live_probe_exception_type_error"
    assert (
        _safe_probe_failure_code(AssertionError("employee.live_sensitive_identifier_sentinel"))
        == "employee.live_probe_unexpected_error"
    )


def test_live_probe_identifier_check_supports_frozen_domain_results() -> None:
    result = freeze_json_object(
        {"records": ({"fields": {"employee_id_masked": "***1222"}},)},
        max_bytes=1024,
        max_depth=8,
        max_collection_items=16,
    )
    assert not _contains_identifier(result, "SYNTHETIC-IDENTIFIER")


def test_runner_and_java_live_test_are_opt_in_and_test_scoped() -> None:
    runner = (ROOT / "agent-runtime" / "scripts" / "run-employee-live.ps1").read_text(encoding="utf-8")
    java_test = (
        ROOT
        / "employee-service"
        / "src"
        / "test"
        / "java"
        / "com"
        / "dylan"
        / "employee"
        / "live"
        / "EmployeeRealActionLiveIntegrationTest.java"
    ).read_text(encoding="utf-8")
    assert "EMPLOYEE_LIVE_TEST_IDENTIFIER" in runner
    assert "$maxEmployeeRequests = 10" in runner
    assert "Remove-RunRoot" in runner
    assert "@EnabledIfEnvironmentVariable(named = \"RUN_EMPLOYEE_LIVE\", matches = \"1\")" in java_test
    assert "@MockitoSpyBean" in java_test
    assert "common.security.secrets.source-order[0]=environment" in java_test
    assert "common.security.secrets.allow-config-values=false" in java_test
    assert "WorkflowInboxProcessor" in java_test
    assert "test_real_employee_live.py" in java_test
    assert "EMPLOYEE_LIVE_PYTHON_JUNIT_PATH" in runner
    assert '"--junitxml=" + pythonJunit' in java_test
    assert "employee.live_log_leak:$logLeakCategory" in runner
    assert "Remove-GeneratedSurefireReports" in runner
    assert "EmployeeRealActionLiveIntegrationTest.xml" in runner


def test_gateway_log_runner_is_synthetic_single_request_and_has_no_permanent_route() -> None:
    runner = (ROOT / "agent-runtime" / "scripts" / "run-employee-gateway-log-live.ps1").read_text(
        encoding="utf-8"
    )
    java_test = (
        ROOT
        / "employee-service"
        / "src"
        / "test"
        / "java"
        / "com"
        / "dylan"
        / "employee"
        / "live"
        / "EmployeeGatewayLogSafetyLiveIntegrationTest.java"
    ).read_text(encoding="utf-8")
    gateway_router = (
        ROOT / "gateway-service" / "src" / "main" / "java" / "com" / "dylan" / "springgateway" / "config"
        / "GatewayRouter.java"
    ).read_text(encoding="utf-8")
    assert "EMPLOYEE_LIVE_TEST_IDENTIFIER" not in runner
    assert "$maxGatewayRequests = 1" in runner
    assert "SYNTHETIC-EMPLOYEE-GATEWAY-" in runner
    assert "HMACSHA256]::new($keySeed)" in runner
    assert "HMACSHA256]::new($signingBytes)" not in runner
    assert "RUN_EMPLOYEE_GATEWAY_LOG_LIVE" in runner
    assert "Remove-RunRoot" in runner
    assert "Remove-GeneratedSurefireReports" in runner
    assert "@EnabledIfEnvironmentVariable(named = \"RUN_EMPLOYEE_GATEWAY_LOG_LIVE\", matches = \"1\")" in java_test
    assert "spring.cloud.gateway.server.webflux.routes[0]" in java_test
    assert "HttpResponse.BodyHandlers.discarding()" in java_test
    assert "employee-live-test" not in gateway_router
    assert "DeepSeek" not in runner


def test_log_scanner_rejects_sensitive_values_without_matching_project_namespace() -> None:
    helper = ROOT / "agent-runtime" / "scripts" / "employee-live-log-safety.ps1"
    runner = (ROOT / "agent-runtime" / "scripts" / "run-employee-live.ps1").read_text(encoding="utf-8")
    assert helper.is_file()
    assert ". (Join-Path $PSScriptRoot 'employee-live-log-safety.ps1')" in runner
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is required to execute the Windows-only live-runner scanner")
    helper_literal = str(helper).replace("'", "''")
    command = f"""
. '{helper_literal}'
$principals = @('admin', 'dylan', 'viewer_t')
if (Test-EmployeeLiveSensitiveText -Text '[INFO] Building com.dylan:employee-service' -LiteralSensitiveValues @('jwt-sentinel') -ExpectedPrincipals $principals) {{ exit 11 }}
if (-not (Test-EmployeeLiveSensitiveText -Text 'subject=dylan' -LiteralSensitiveValues @('jwt-sentinel') -ExpectedPrincipals $principals)) {{ exit 12 }}
if (-not (Test-EmployeeLiveSensitiveText -Text 'Authorization: Bearer jwt-sentinel' -LiteralSensitiveValues @('jwt-sentinel') -ExpectedPrincipals $principals)) {{ exit 13 }}
if ((Get-EmployeeLiveSafeFailureCode -Text 'AssertionError: employee.live_case_failed:adminPrimary') -ne 'employee.live_case_failed:adminPrimary') {{ exit 14 }}
if ((Get-EmployeeLiveSafeFailureCode -Text 'employee.live_case_failed:SENSITIVE-IDENTIFIER-SENTINEL') -ne 'employee.live_case_failed') {{ exit 15 }}
if ((Get-EmployeeLiveSafeFailureCode -Text 'unexpected provider traceback') -ne 'employee.live_integration_failed') {{ exit 16 }}
if ((Get-EmployeeLiveSafeFailureCode -Text 'employee.live_sensitive_identifier_sentinel') -ne 'employee.live_integration_failed') {{ exit 19 }}
$hostOnly = Remove-EmployeeLiveJUnitHostMetadata -Text '<testsuite hostname="dylan"><testcase /></testsuite>'
if (Test-EmployeeLiveSensitiveText -Text $hostOnly -LiteralSensitiveValues @() -ExpectedPrincipals $principals) {{ exit 17 }}
$subjectLeak = Remove-EmployeeLiveJUnitHostMetadata -Text '<testsuite hostname="dylan"><testcase><failure>subject=dylan</failure></testcase></testsuite>'
if (-not (Test-EmployeeLiveSensitiveText -Text $subjectLeak -LiteralSensitiveValues @() -ExpectedPrincipals $principals)) {{ exit 18 }}
"""
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
