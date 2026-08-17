from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.integration.adapters.employee.egress_candidate_v3 import (
    AUTHORIZATION_REFERENCE,
    EXPECTED_PASSED_RECORDS,
    GATE_ID,
    HISTORY_ASSETS,
    MAXIMUM_PAID_ANSWER_CALLS,
    PREPARATION_GATE_ID,
    REQUIRED_ASSET_PATHS,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    verify_history,
)


REPOSITORY = Path(__file__).parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
MANIFEST_SHA256 = "901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e"


def test_manifest_authorization_assets_and_history_are_frozen() -> None:
    manifest_sha = sha256_file(MANIFEST)
    assert manifest_sha == MANIFEST_SHA256
    manifest = load_strict_json(MANIFEST)
    authorization = validate_authorization(
        load_strict_json(AUTHORIZATION), manifest_sha256=manifest_sha
    )

    assert manifest["runId"] == RUN_ID
    assert manifest["preparationGateId"] == PREPARATION_GATE_ID
    assert manifest["gateId"] == GATE_ID
    assert manifest["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert len(manifest["historyHashes"]) == len(HISTORY_ASSETS)
    assert len(manifest["assetHashes"]) == len(REQUIRED_ASSET_PATHS)
    assert {item["path"] for item in manifest["assetHashes"]} == REQUIRED_ASSET_PATHS
    assert all(
        isinstance(item["sha256"], str) and len(item["sha256"]) == 64
        for item in manifest["assetHashes"]
    )
    assert authorization["liveExecutionAuthorized"] is False
    assert authorization["maximumPaidAnswerCalls"] == MAXIMUM_PAID_ANSWER_CALLS
    verify_history(REPOSITORY)


def test_five_schemas_are_strict_and_bind_candidate() -> None:
    names = ("lifecycle", "consumed", "staging", "pending", "result")
    for name in names:
        schema = json.loads(
            (EVIDENCE / f"employee-egress-v3-{name}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        assert schema["additionalProperties"] is False
        assert schema["properties"]["schemaVersion"]["const"] == 3
        assert schema["properties"]["runId"]["const"] == RUN_ID
    lifecycle = json.loads(
        (EVIDENCE / "employee-egress-v3-lifecycle.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert lifecycle["properties"]["sequence"]["maximum"] == EXPECTED_PASSED_RECORDS - 1


def test_java_host_is_disabled_and_has_exact_sql_and_cleanup_contract() -> None:
    source = (
        REPOSITORY
        / "employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressCandidateV3LiveIntegrationTest.java"
    ).read_text(encoding="utf-8")
    assert '@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_EGRESS_CANDIDATE_V3"' in source
    assert "classes = EmployeeServiceApplication.class" in source
    assert "BINARY ID_CARD_NO = BINARY ?" in source
    assert "INSERT INTO employee (ID_CARD_NO, CHINESE_NAME, POSITION, WORK_BASE_SI)" in source
    assert "DELETE FROM employee" in source
    assert 'stage(journal, "cleanup_delete"' in source
    assert 'stage(journal, "cleanup_verify"' in source
    assert "process.waitFor(600, TimeUnit.SECONDS)" in source


def test_launcher_has_valid_ast_and_pre_model_fail_closed_checks() -> None:
    launcher = REPOSITORY / "agent-runtime/scripts/run-employee-egress-live-candidate-03.ps1"
    command = (
        "$e=$null;$t=$null;"
        "[void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{launcher}',[ref]$t,[ref]$e);if($e){{exit 1}}"
    )
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        cwd=REPOSITORY,
        check=False,
    )
    assert completed.returncode == 0
    source = launcher.read_text(encoding="utf-8")
    assert "LifecycleJournal" in source
    assert source.index("LifecycleJournal") < source.index("& mvn")
    assert "write_fallback_pending" in source
    assert "EMPLOYEE_EGRESS_V3_LIVE_AUTHORIZED" in source
    assert "LLM_API_KEY" in source
    assert "Remove-Item -LiteralPath $pendingPath" in source
    assert "Remove-Item -LiteralPath $stagingPath" in source


def test_model_field_matrix_remains_position_and_work_base_only() -> None:
    matrix = json.loads(
        (REPOSITORY / "agent-runtime/tests/fixtures/employee_egress_field_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    assert matrix["maximumModelFields"] == ["position", "work_base_si"]
