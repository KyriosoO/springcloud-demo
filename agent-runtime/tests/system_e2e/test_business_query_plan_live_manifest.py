from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.system_e2e.business_query_plan_live_contracts import (
    RUN_ID,
    sha256_file,
    validate_attempt_journal,
    validate_authorization_template,
    validate_consumed,
    validate_lifecycle,
    validate_manifest,
    validate_result,
)
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "agent-runtime/tests/system_e2e/live/evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION_TEMPLATE = EVIDENCE / f"{RUN_ID}.authorization-template.json"
FROZEN_SOURCE_COMMIT = "956a80f4993cae1c3ce88a7ffd9ad295e73fa098"
HISTORICAL_TASK_VERSION = "business-query-plan-v2"
HISTORICAL_PROMPT_SHA256 = "a9c312fc0ab0ab6924da63fa0a5a3b79829b4a967502d3e74e3b18a564a8b2fc"
HISTORICAL_SNAPSHOT_SHA256 = "79b7045d68be4e2934707d63fd25cd6c60c729a36460f87fd3ccdd67b41a539b"


def test_candidate_manifest_authorization_and_assets_are_strict_in_prepared_or_passed_state() -> None:
    manifest_sha256 = sha256_file(MANIFEST)
    manifest = validate_manifest(
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        expected_task_version=HISTORICAL_TASK_VERSION,
        expected_system_instruction_sha256=HISTORICAL_PROMPT_SHA256,
    )
    assert manifest["snapshots"] == {
        "catalogSha256": HISTORICAL_SNAPSHOT_SHA256,
        "configSha256": HISTORICAL_SNAPSHOT_SHA256,
    }
    assets = cast(list[dict[str, str]], manifest["assets"])
    historical_run = "business-query-plan-live-v1-20260824-candidate-01"
    consumed_run = "business-query-plan-live-v1-20260825-candidate-02"
    assert {
        f"agent-runtime/tests/system_e2e/live/evidence/{historical_run}.manifest.json",
        f"agent-runtime/tests/system_e2e/live/evidence/{historical_run}.authorization-template.json",
        f"agent-runtime/tests/system_e2e/live/results/{historical_run}/lifecycle.jsonl",
        f"agent-runtime/tests/system_e2e/live/results/{historical_run}/result.json",
        f"agent-runtime/tests/system_e2e/live/evidence/{consumed_run}.manifest.json",
        f"agent-runtime/tests/system_e2e/live/evidence/{consumed_run}.authorization-template.json",
        f"agent-runtime/tests/system_e2e/live/results/{consumed_run}/lifecycle.jsonl",
        f"agent-runtime/tests/system_e2e/live/results/{consumed_run}/authorization.consumed.json",
        f"agent-runtime/tests/system_e2e/live/results/{consumed_run}/model-attempts.jsonl",
        f"agent-runtime/tests/system_e2e/live/results/{consumed_run}/result.json",
    }.issubset({asset["path"] for asset in assets})
    for asset in assets:
        path = (ROOT / asset["path"]).resolve()
        assert path.is_relative_to(ROOT)
        frozen = subprocess.run(
            ["git", "show", f"{FROZEN_SOURCE_COMMIT}:{asset['path']}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset["sha256"]

    authorization = json.loads(AUTHORIZATION_TEMPLATE.read_text(encoding="utf-8"))
    validate_authorization_template(
        authorization,
        manifest_sha256=manifest_sha256,
        prepared_head=cast(str, manifest["preparedHead"]),
    )
    assert authorization["liveExecutionAuthorized"] is False
    result_root = ROOT / f"agent-runtime/tests/system_e2e/live/results/{RUN_ID}"
    if result_root.exists():
        assert {path.name for path in result_root.iterdir()} == {
            "lifecycle.jsonl",
            "authorization.consumed.json",
            "model-attempts.jsonl",
            "result.json",
        }
        validate_lifecycle(
            json.loads((result_root / "lifecycle.jsonl").read_text(encoding="utf-8")),
            manifest_sha256=manifest_sha256,
        )
        validate_consumed(
            json.loads((result_root / "authorization.consumed.json").read_text(encoding="utf-8")),
            manifest_sha256=manifest_sha256,
        )
        validate_attempt_journal(
            tuple(
                json.loads(line)
                for line in (result_root / "model-attempts.jsonl").read_text(encoding="utf-8").splitlines()
            ),
            expected_calls=6,
        )
        result = validate_result(
            json.loads((result_root / "result.json").read_text(encoding="utf-8")),
            require_passed=True,
        )
        assert result["schemaVersion"] == 2
        assert result["failureCase"] is None


def test_candidate_manifest_rejects_catalog_configuration_snapshot_drift() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["snapshots"]["catalogSha256"] = "0" * 64
    with pytest.raises(ValueError, match="business_query_plan_live.manifest_snapshot_invalid"):
        validate_manifest(
            manifest,
            expected_task_version=HISTORICAL_TASK_VERSION,
            expected_system_instruction_sha256=HISTORICAL_PROMPT_SHA256,
        )


def test_candidate_assets_contain_no_secret_or_runtime_value_fields() -> None:
    raw = MANIFEST.read_text(encoding="utf-8") + AUTHORIZATION_TEMPLATE.read_text(encoding="utf-8")
    for forbidden in (
        "LLM_API_KEY",
        "Authorization: Bearer",
        "employeeIdentifierValue",
        "employeeJwtValue",
        "transactionJwtValue",
    ):
        assert forbidden not in raw
