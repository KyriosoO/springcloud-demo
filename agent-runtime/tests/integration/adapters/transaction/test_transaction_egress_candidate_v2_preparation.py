from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate_v2 import (
    AUTHORIZATION_REFERENCE,
    MAXIMUM_PAID_ANSWER_CALLS,
    MINIMUM_VALID_ANSWER_CALLS,
    MODEL_VISIBLE_FIELD_IDS,
    REQUIRED_ASSET_PATHS,
    REQUIRED_HISTORY_PATHS,
    RUN_ID,
    consumed_path_for,
    lifecycle_path_for,
    load_strict_json,
    result_path_for,
    sha256_file,
    validate_authorization,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[5]
RUNTIME = ROOT / "agent-runtime"
EVIDENCE = RUNTIME / "tests/integration/adapters/transaction/evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
LIFECYCLE_SCHEMA = EVIDENCE / "transaction-egress-candidate-v2-lifecycle.schema.json"
RESULT_SCHEMA = EVIDENCE / "transaction-egress-candidate-v2-result.schema.json"


def test_candidate_manifest_authorization_and_all_assets_are_frozen() -> None:
    manifest_sha256 = sha256_file(MANIFEST)
    manifest = validate_manifest(load_strict_json(MANIFEST), repository_root=ROOT)
    raw_authorization = load_strict_json(AUTHORIZATION)
    assert raw_authorization["manifestSha256"] == manifest_sha256
    authorization = validate_authorization(
        raw_authorization,
        manifest_sha256=manifest_sha256,
    )

    assert manifest["runId"] == authorization["runId"] == RUN_ID
    assert manifest["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert manifest["executionBoundary"] == {
        "transactionSearchMaximum": 1,
        "paidAnswerMaximum": MAXIMUM_PAID_ANSWER_CALLS,
        "minimumValidAnswers": MINIMUM_VALID_ANSWER_CALLS,
        "modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS),
        "liveExecutionAuthorized": False,
        "transactionAccessAuthorized": False,
        "modelAccessAuthorized": False,
        "retryAllowed": False,
        "resumeAllowed": False,
    }
    assert {item["path"] for item in manifest["assetHashes"]} == REQUIRED_ASSET_PATHS
    assert {item["path"] for item in manifest["history"]} == REQUIRED_HISTORY_PATHS
    assert all(
        isinstance(item["sha256"], str) and len(item["sha256"]) == 64
        for item in manifest["assetHashes"]
    )
    assert authorization["liveExecutionAuthorized"] is False
    assert not lifecycle_path_for(EVIDENCE).exists()
    assert not consumed_path_for(EVIDENCE).exists()
    assert not result_path_for(EVIDENCE).exists()


def test_manifest_binds_answer_v2_current_bootstrap_and_retired_history() -> None:
    manifest = load_strict_json(MANIFEST)
    assets = {item["path"] for item in manifest["assetHashes"]}
    history = {item["path"] for item in manifest["history"]}

    assert "agent-runtime/src/agent_runtime/model/deepseek/answer_generator_v2.py" in assets
    assert "agent-runtime/src/agent_runtime/bootstrap.py" in assets
    assert "agent-runtime/tests/model_helpers.py" in assets
    assert "agent-runtime/src/agent_runtime/model/deepseek/answer_generator.py" not in assets
    assert any(path.endswith("candidate-01.manifest.json") for path in history)
    assert any(path.endswith("candidate-01.authorization.json") for path in history)

    live_source = (
        RUNTIME
        / "tests/integration/adapters/transaction/test_real_transaction_egress_candidate_v2.py"
    ).read_text(encoding="utf-8")
    candidate_source = (
        RUNTIME / "tests/integration/adapters/transaction/egress_candidate_v2.py"
    ).read_text(encoding="utf-8")
    assert "LocalModelCompositionRoot.build" in live_source
    assert 'request.task_version != "answer-generation-v2"' in candidate_source


def test_strict_schemas_match_three_states_budgets_and_no_extra_fields() -> None:
    lifecycle = json.loads(LIFECYCLE_SCHEMA.read_text(encoding="utf-8"))
    result = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))

    assert lifecycle["additionalProperties"] is False
    assert lifecycle["properties"]["schemaVersion"] == {"const": 2}
    assert lifecycle["properties"]["retryCount"] == {"const": 0}
    assert lifecycle["properties"]["resumeCount"] == {"const": 0}
    assert result["additionalProperties"] is False
    assert result["properties"]["schemaVersion"] == {"const": 2}
    assert result["properties"]["status"]["enum"] == [
        "passed",
        "failed_unconsumed",
        "failed_consumed",
    ]
    counts = result["properties"]["counts"]["properties"]
    assert counts["transactionSearchStarted"]["maximum"] == 1
    assert counts["answerStarted"]["maximum"] == 30
    assert result["properties"]["threshold"]["const"] == {
        "maximumAnswerCalls": 30,
        "minimumValidAnswers": 27,
    }


def test_launcher_binds_all_assets_before_reading_secrets_and_never_starts_services() -> None:
    path = RUNTIME / "scripts/run-transaction-egress-live-candidate-02.ps1"
    script = path.read_text(encoding="utf-8")
    binding = script.index("transaction.egress_candidate_authorization_binding_invalid")
    asset_binding = script.index("transaction.egress_candidate_asset_hash_invalid")
    secret_read = script.index("GetEnvironmentVariable('LLM_API_KEY'")

    assert binding < asset_binding < secret_read
    assert "$maximumPaidAnswerCalls = 30" in script
    assert "test_real_transaction_egress_candidate_v2.py" in script
    assert "RUN_TRANSACTION_EGRESS_CANDIDATE_02" in script
    assert "Start-Process -FilePath 'java'" not in script
    assert "mvn" not in script
    assert "Invoke-WebRequest" not in script
    assert "--tb=no" in script

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is not None:
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


def test_live_entry_is_opt_in_and_has_no_direct_evidence_overwrite() -> None:
    path = RUNTIME / "tests/integration/adapters/transaction/test_real_transaction_egress_candidate_v2.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "RUN_TRANSACTION_EGRESS_CANDIDATE_02" in source
    assert "TRANSACTION_EGRESS_LIVE_TEST_TYPE" in source
    assert "TRANSACTION_EGRESS_LIVE_USER_JWT" in source
    assert "TransactionEgressLifecycleJournal" in source
    assert "JournaledTransactionSearchTransport" in source
    assert "BudgetedTransactionAnswerTransport" in source
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"write_text", "write_bytes"}
        for node in ast.walk(tree)
    )


def test_prepared_assets_do_not_persist_query_or_transaction_values() -> None:
    prepared = (
        MANIFEST.read_text(encoding="utf-8")
        + AUTHORIZATION.read_text(encoding="utf-8")
        + LIFECYCLE_SCHEMA.read_text(encoding="utf-8")
        + RESULT_SCHEMA.read_text(encoding="utf-8")
    )
    assert "SYNTHETIC_PAYMENT" not in prepared
    assert "SYNTH-TXN-0001" not in prepared
    assert "100.10" not in prepared
    assert "header.payload.signature" not in prepared
