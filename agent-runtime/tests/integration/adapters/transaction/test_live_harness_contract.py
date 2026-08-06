from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from tests.integration.adapters.transaction.evidence_contract import (
    validate_final_evidence,
    validate_probe_evidence,
)
from tests.integration.adapters.transaction.test_real_transaction_live import _safe_probe_failure_code

ROOT = Path(__file__).parents[5]
SCHEMA = Path(__file__).parent / "evidence" / "transaction-live-evidence-v1.schema.json"


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
        "workPackage": "WP-TXN-REAL-01",
        "validations": ["VAL-TXN-004", "VAL-TXN-005"],
        "status": "passed",
        "startedAtUtc": "2026-08-06T00:00:00Z",
        "completedAtUtc": "2026-08-06T00:00:01Z",
        "durationMs": 1000,
        "authorizationMatrix": _matrix(),
        "precisionMatrix": {
            "amountExact": True,
            "amountGtExact": True,
            "amountLtExact": True,
            "gatewayAmountExact": True,
            "jsonNumberOnly": True,
            "mapperValuesUnmodified": True,
        },
        "requestCounts": {
            "transaction": 7,
            "adapter": 6,
            "gateway": 1,
            "serviceSearch": 4,
            "mapperCountUpTo": 4,
            "mapperQuery": 0,
            "otherServiceMethods": 0,
            "otherTransactionEndpoints": 0,
            "model": 0,
        },
        "responseVisibility": "provider_contract_and_empty_live_response",
        "logSafety": {
            "logLeakCount": 0,
            "rawLogsDeleted": True,
            "transactionValuePersisted": False,
            "jwtPersisted": False,
            "hmacKeyPersisted": False,
            "bodyPersisted": False,
            "principalPersisted": False,
        },
        "runtimeIsolation": {
            "authService": "isolated_local",
            "transactionService": "spring_boot_test_netty",
            "gatewayService": "actual_jar_formal_mq_route",
            "databaseAccessed": False,
            "permanentRouteUsed": True,
            "deepSeekCalled": False,
        },
    }


def test_evidence_schema_and_strict_validator_freeze_finite_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(_final_evidence())
    assert schema["properties"]["requestCounts"]["properties"]["gateway"]["const"] == 1
    assert validate_final_evidence(_final_evidence())["status"] == "passed"


def test_evidence_validator_rejects_extra_fields_false_success_and_wrong_counts() -> None:
    extra = _final_evidence()
    extra["transactionId"] = "forbidden"
    with pytest.raises(ValueError, match="transaction.live_evidence_invalid"):
        validate_final_evidence(extra)
    wrong_precision = _final_evidence()
    precision = wrong_precision["precisionMatrix"]
    assert isinstance(precision, dict)
    wrong_precision["precisionMatrix"] = {**precision, "amountExact": False}
    with pytest.raises(ValueError, match="transaction.live_evidence_invalid"):
        validate_final_evidence(wrong_precision)
    wrong_count = _final_evidence()
    counts = wrong_count["requestCounts"]
    assert isinstance(counts, dict)
    wrong_count["requestCounts"] = {**counts, "gateway": 2}
    with pytest.raises(ValueError, match="transaction.live_evidence_invalid"):
        validate_final_evidence(wrong_count)


def test_probe_contract_requires_all_cases_and_json_number() -> None:
    probe = {
        "schemaVersion": 1,
        "authorizationMatrix": _matrix(),
        "precisionMatrix": {"jsonNumberOnly": True},
        "requestCounts": {"transaction": 7, "adapter": 6, "otherTransactionEndpoints": 0, "model": 0},
        "responseVisibility": "empty_response_with_provider_contract",
    }
    assert validate_probe_evidence(probe)["schemaVersion"] == 1
    probe["precisionMatrix"] = {"jsonNumberOnly": False}
    with pytest.raises(ValueError, match="transaction.live_evidence_invalid"):
        validate_probe_evidence(probe)


def test_live_probe_failure_classification_never_returns_exception_payload() -> None:
    assert (
        _safe_probe_failure_code(AssertionError("transaction.live_case_failed:adminPrimary"))
        == "transaction.live_case_failed:adminPrimary"
    )
    assert _safe_probe_failure_code(RuntimeError("sensitive runtime payload")) == "transaction.live_probe_runtime_error"
    assert _safe_probe_failure_code(httpx.ConnectError("sensitive request URL")) == "transaction.live_probe_http_error"
    assert _safe_probe_failure_code(TypeError("sensitive typed payload")) == "transaction.live_probe_exception_type_error"


def test_runner_and_java_live_test_are_opt_in_bounded_and_use_formal_route() -> None:
    runner = (ROOT / "agent-runtime" / "scripts" / "run-transaction-live.ps1").read_text(encoding="utf-8")
    java_test = (
        ROOT
        / "mq-procedure-service"
        / "src"
        / "test"
        / "java"
        / "com"
        / "dylan"
        / "mqprocedureserver"
        / "live"
        / "TransactionRealActionLiveIntegrationTest.java"
    ).read_text(encoding="utf-8")
    gateway_router = (
        ROOT / "gateway-service" / "src" / "main" / "java" / "com" / "dylan" / "springgateway" / "config"
        / "GatewayRouter.java"
    ).read_text(encoding="utf-8")
    assert "$maxTransactionRequests = 8" in runner
    assert "$maxGatewayRequests = 1" in runner
    assert "RUN_TRANSACTION_LIVE" in runner
    assert "Remove-RunRoot" in runner
    assert "Remove-GeneratedSurefireReports" in runner
    assert "HMACSHA256]::new($keyBytes)" in runner
    assert "@EnabledIfEnvironmentVariable(named = \"RUN_TRANSACTION_LIVE\", matches = \"1\")" in java_test
    assert "spring.cloud.discovery.client.simple.instances.mq-procedure-service[0].uri" in java_test
    assert "spring.cloud.gateway.server.webflux.routes[0]" not in java_test
    assert "test_real_transaction_live.py" in java_test
    assert "countUpTo" in java_test
    assert "getAmountGt" in java_test and "getAmountLt" in java_test
    assert '.route("mq_route"' in gateway_router and 'r.path("/txn/**")' in gateway_router


def test_powershell_runner_parses_when_available() -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    runner = ROOT / "agent-runtime" / "scripts" / "run-transaction-live.ps1"
    command = (
        "$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile(" 
        + repr(str(runner)).replace("'", '"')
        + ",[ref]$null,[ref]$errors) > $null; if($errors.Count){$errors | % Message; exit 1}"
    )
    result = subprocess.run([pwsh, "-NoProfile", "-Command", command], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
