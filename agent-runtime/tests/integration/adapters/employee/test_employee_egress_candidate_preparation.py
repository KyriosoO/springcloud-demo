from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tests.integration.adapters.employee.egress_candidate import (
    AUTHORIZATION_REFERENCE,
    MAXIMUM_PAID_ANSWER_CALLS,
    MODEL_VISIBLE_FIELD_IDS,
    RUN_ID,
    EmployeeEgressCandidateError,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_live_evidence,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[5]
RUNTIME = ROOT / "agent-runtime"
EVIDENCE = RUNTIME / "tests/integration/adapters/employee/evidence"
MANIFEST = EVIDENCE / "employee-egress-v1-20260813-candidate-01.manifest.json"
AUTHORIZATION = EVIDENCE / "employee-egress-v1-20260813-candidate-01.authorization.json"
SCHEMA = EVIDENCE / "employee-egress-live-evidence-v1.schema.json"
CONSUMED = EVIDENCE / "employee-egress-v1-20260813-candidate-01.authorization.consumed.json"
RESULT = EVIDENCE / "employee-egress-v1-20260813-candidate-01.result.json"
MANIFEST_SHA256 = "c3cdfacd32797474f68e11758ec094df97a95d56fb0efed9355ccfaa6a145c57"


def _evidence(*, status: str = "passed", actual: int = 30, valid: int = 27) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": status,
        "workPackageId": "WP-EMP-EGRESS-01",
        "gateId": "GATE-024",
        "runId": RUN_ID,
        "manifestSha256": MANIFEST_SHA256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "recordedAt": "2026-08-13T10:00:00Z",
        "modelBinding": {
            "taskId": "answer_generation",
            "taskVersion": "answer-generation-v1",
            "modelName": "deepseek-v4-pro",
        },
        "fieldBoundary": {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)},
        "businessSnapshot": {
            "policyVersion": "business-egress-v1",
            "configSnapshotId": "14b609a7d9ca95a97e830e570f8b48ed84e8476a3cf3d4b198558e8a4f6efd28",
        },
        "authorizationEvidenceRefs": [
            "WP-EMP-REAL-01:authorizationMatrix.admin",
            "WP-EMP-REAL-01:VAL-EMP-005",
        ],
        "attemptJournal": {
            "recordCount": 61 if actual == 30 else 1 + actual * 2,
            "sha256": "b" * 64,
        },
        "counts": {
            "employeeDetailRequests": 1,
            "otherEmployeeEndpoints": 0,
            "plannedAnswerCalls": 30,
            "maximumPaidAnswerCalls": 30,
            "actualAnswerCalls": actual,
            "terminalAnswerRecords": actual,
            "validAnswers": valid,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "safety": {
            "forbiddenPayloadFieldCount": 0,
            "forbiddenLiteralCount": 0,
            "logLeakCount": 0,
            "jwtPersisted": False,
            "identifierPersisted": False,
            "employeeDataPersisted": False,
            "rawModelResponsePersisted": False,
        },
        "outcomes": [
            {"attemptOrdinal": ordinal, "status": "answer" if ordinal <= valid else "invalid_output"}
            for ordinal in range(1, actual + 1)
        ],
    }


def test_candidate_manifest_authorization_assets_and_history_are_frozen() -> None:
    assert sha256_file(MANIFEST) == MANIFEST_SHA256
    manifest = validate_manifest(load_strict_json(MANIFEST), repository_root=ROOT)
    authorization = validate_authorization(
        load_strict_json(AUTHORIZATION),
        manifest_sha256=MANIFEST_SHA256,
    )

    assert manifest["runId"] == authorization["runId"] == RUN_ID
    assert manifest["authorizationReference"] == authorization["authorizationReference"]
    assert authorization["liveExecutionAuthorized"] is False
    assert manifest["executionBoundary"]["maximumPaidAnswerCalls"] == MAXIMUM_PAID_ANSWER_CALLS
    assert len(manifest["assetHashes"]) == 23
    assert not CONSUMED.exists()
    assert not RESULT.exists()


def test_evidence_contract_is_strict_and_threshold_is_not_weakened() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(_evidence())
    assert schema["properties"]["fieldBoundary"]["properties"]["modelVisibleFieldIds"]["const"] == [
        "position",
        "work_base_si",
    ]
    assert validate_live_evidence(_evidence())["status"] == "passed"
    assert validate_live_evidence(_evidence(status="failed", valid=26))["status"] == "failed"

    mutations: tuple[Callable[[dict[str, Any]], object], ...] = (
        lambda item: item["counts"].update(retryCount=1),
        lambda item: item["safety"].update(identifierPersisted=True),
        lambda item: item["attemptJournal"].update(recordCount=60),
        lambda item: item["fieldBoundary"].update(modelVisibleFieldIds=["position", "chinese_name"]),
        lambda item: item.update(status="passed"),
    )
    for mutation in mutations:
        invalid = _evidence(status="failed", actual=29, valid=29)
        mutation(invalid)
        with pytest.raises(EmployeeEgressCandidateError):
            validate_live_evidence(invalid)


def test_launcher_binds_before_secret_read_and_never_starts_services() -> None:
    script = (RUNTIME / "scripts/run-employee-egress-live-candidate-01.ps1").read_text(
        encoding="utf-8"
    )
    binding = script.index("employee.egress_candidate_authorization_binding_invalid")
    assert binding < script.index("GetEnvironmentVariable('LLM_API_KEY'")
    assert "$maximumPaidAnswerCalls = 30" in script
    assert "test_real_employee_egress_candidate.py" in script
    assert "RUN_EMPLOYEE_EGRESS_CANDIDATE" in script
    assert "Start-Process -FilePath 'java'" not in script
    assert "mvn" not in script
    assert "Invoke-WebRequest" not in script
    assert "$baseUrl -cne 'http://127.0.0.1:9210'" in script
    assert "--tb=no" in script

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell parser unavailable")
    escaped = str(RUNTIME / "scripts/run-employee-egress-live-candidate-01.ps1").replace("'", "''")
    command = (
        f"$tokens=$null;$errors=$null;"
        f"[Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -ne 0){exit 7}"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr


def test_live_entry_is_opt_in_and_does_not_persist_sensitive_inputs() -> None:
    path = RUNTIME / "tests/integration/adapters/employee/test_real_employee_egress_candidate.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "RUN_EMPLOYEE_EGRESS_CANDIDATE" in source
    assert "EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER" in source
    assert "EMPLOYEE_EGRESS_LIVE_USER_JWT" in source
    assert "write_exclusive_json" in source
    assert "retryCount\": 0" in source
    assert "resumeCount\": 0" in source
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"write_text", "write_bytes"}
        for node in ast.walk(tree)
    )


def test_manifest_and_authorization_contain_no_secret_or_employee_record_values() -> None:
    raw = (MANIFEST.read_text(encoding="utf-8") + AUTHORIZATION.read_text(encoding="utf-8")).lower()
    assert all(
        marker not in raw
        for marker in (
            "llm_api_key",
            "employee_egress_live_user_jwt",
            "employee_egress_live_test_identifier",
            "身份证",
            "合成员工",
            "synthetic@example.invalid",
        )
    )
