from __future__ import annotations

import ast
import json
import shutil
import subprocess
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tests.integration.adapters.employee.egress_candidate_v2 import (
    AUTHORIZATION_REFERENCE,
    MAXIMUM_PAID_ANSWER_CALLS,
    MODEL_VISIBLE_FIELD_IDS,
    RUN_ID,
    EmployeeEgressCandidateV2Error,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_live_evidence,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[5]
RUNTIME = ROOT / "agent-runtime"
EVIDENCE = RUNTIME / "tests/integration/adapters/employee/evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
SCHEMA = EVIDENCE / "employee-egress-live-evidence-v2.schema.json"
LIFECYCLE = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
CONSUMED = EVIDENCE / f"{RUN_ID}.authorization.consumed.json"
RESULT = EVIDENCE / f"{RUN_ID}.result.json"
MANIFEST_SHA256 = "28cd7b04b0700b43e5feed7bdef22e9da0494cd941e2e9f96b698a75b21b03b1"


def _failed_evidence(*, consumed: bool) -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "status": "failed_consumed" if consumed else "failed_unconsumed",
        "workPackageId": "WP-EMP-EGRESS-01",
        "gateId": "GATE-024",
        "runId": RUN_ID,
        "manifestSha256": MANIFEST_SHA256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "recordedAt": "2026-08-14T02:00:00Z",
        "modelBinding": {
            "taskId": "answer_generation",
            "taskVersion": "answer-generation-v1",
            "modelName": "deepseek-v4-pro",
        },
        "fieldBoundary": {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)},
        "businessSnapshot": {
            "policyVersion": "business-egress-v1",
            "configSnapshotId": "a" * 64,
        },
        "authorizationEvidenceRefs": [
            "WP-EMP-REAL-01:authorizationMatrix.admin",
            "WP-EMP-REAL-01:VAL-EMP-005",
        ],
        "authorizationState": {
            "consumed": consumed,
            "consumedMarkerSha256": "b" * 64 if consumed else None,
        },
        "lifecycleJournal": {"recordCount": 4 if consumed else 2, "sha256": "c" * 64},
        "counts": {
            "employeeDetailRequests": 0,
            "otherEmployeeEndpoints": 0,
            "plannedAnswerCalls": 30,
            "maximumPaidAnswerCalls": 30,
            "actualAnswerCalls": 0,
            "terminalAnswerRecords": 0,
            "validAnswers": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "failure": {"phase": "model_call", "reason": "model_call_failed"},
        "safety": {
            "forbiddenPayloadFieldCount": 0,
            "forbiddenLiteralCount": 0,
            "logLeakCount": 0,
            "jwtPersisted": False,
            "identifierPersisted": False,
            "employeeDataPersisted": False,
            "rawModelResponsePersisted": False,
        },
        "outcomes": [],
    }


def test_candidate02_manifest_authorization_and_assets_are_frozen() -> None:
    assert sha256_file(MANIFEST) == MANIFEST_SHA256
    manifest = validate_manifest(load_strict_json(MANIFEST), repository_root=ROOT)
    authorization = validate_authorization(
        load_strict_json(AUTHORIZATION),
        manifest_sha256=MANIFEST_SHA256,
    )

    assert manifest["runId"] == authorization["runId"] == RUN_ID
    assert manifest["authorizationReference"] == authorization["authorizationReference"]
    assert manifest["preparationGateId"] == "GATE-048"
    assert authorization["liveExecutionAuthorized"] is False
    assert manifest["executionBoundary"]["maximumPaidAnswerCalls"] == (
        MAXIMUM_PAID_ANSWER_CALLS
    )
    assert len(manifest["assetHashes"]) == 24
    assert len(manifest["candidate01History"]) == 4
    assert not LIFECYCLE.exists()
    assert not CONSUMED.exists()
    assert not RESULT.exists()


def test_v2_evidence_schema_and_python_validator_keep_three_terminal_states_strict() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["status"]["enum"] == [
        "passed",
        "failed_unconsumed",
        "failed_consumed",
    ]
    assert schema["properties"]["counts"]["properties"]["employeeDetailRequests"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 1,
    }
    assert validate_live_evidence(_failed_evidence(consumed=False))["status"] == (
        "failed_unconsumed"
    )
    assert validate_live_evidence(_failed_evidence(consumed=True))["status"] == "failed_consumed"

    mutations: tuple[Callable[[dict[str, Any]], object], ...] = (
        lambda value: value["counts"].update(retryCount=1),
        lambda value: value["counts"].update(resumeCount=1),
        lambda value: value["counts"].update(employeeDetailRequests=2),
        lambda value: value["authorizationState"].update(consumed=True),
        lambda value: value["failure"].update(reason="raw-exception-text"),
        lambda value: value.update(status="passed"),
    )
    for mutation in mutations:
        invalid = deepcopy(_failed_evidence(consumed=False))
        mutation(invalid)
        with pytest.raises(EmployeeEgressCandidateV2Error):
            validate_live_evidence(invalid)


def test_candidate02_launcher_binds_assets_before_secret_read_and_never_starts_services() -> None:
    path = RUNTIME / "scripts/run-employee-egress-live-candidate-02.ps1"
    script = path.read_text(encoding="utf-8")
    binding = script.index("employee.egress_candidate_v2_authorization_binding_invalid")
    asset_binding = script.index("employee.egress_candidate_v2_asset_hash_invalid")
    secret_read = script.index("GetEnvironmentVariable('LLM_API_KEY'")

    assert binding < asset_binding < secret_read
    assert "$maximumPaidAnswerCalls = 30" in script
    assert "test_real_employee_egress_candidate_v2.py" in script
    assert "RUN_EMPLOYEE_EGRESS_CANDIDATE_V2" in script
    assert "$baseUrl -cne 'http://127.0.0.1:9210'" in script
    assert "Start-Process -FilePath 'java'" not in script
    assert "mvn" not in script
    assert "Invoke-WebRequest" not in script
    assert "--tb=no" in script

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell parser unavailable")
    escaped = str(path).replace("'", "''")
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


def test_candidate02_live_entry_is_opt_in_and_uses_exclusive_evidence_writes() -> None:
    path = RUNTIME / "tests/integration/adapters/employee/test_real_employee_egress_candidate_v2.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "RUN_EMPLOYEE_EGRESS_CANDIDATE_V2" in source
    assert "EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER" in source
    assert "EMPLOYEE_EGRESS_LIVE_USER_JWT" in source
    assert "EmployeeEgressLifecycleJournalV2" in source
    assert "record_failure_terminal" in source
    assert "count_forbidden_log_literals" in source
    assert "LOG_LEAK_DETECTED" in source
    assert source.index("capfd.readouterr") < source.index(
        'journal.record_run_terminal(status="passed"'
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"write_text", "write_bytes"}
        for node in ast.walk(tree)
    )


def test_candidate02_prepared_assets_contain_no_secret_or_employee_values() -> None:
    raw = (
        MANIFEST.read_text(encoding="utf-8")
        + AUTHORIZATION.read_text(encoding="utf-8")
        + SCHEMA.read_text(encoding="utf-8")
    ).lower()
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
