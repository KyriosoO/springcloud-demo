from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

from tests.system_e2e.business_query_plan_live_contracts import (
    sha256_file,
    validate_authorization_template,
    validate_lifecycle,
    validate_manifest,
    validate_result,
)


ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "business-query-plan-live-v1-20260824-candidate-01"
FROZEN_HEAD = "fd2d84b87d161255c19650470d3eb3eff8f0dd8b"
EVIDENCE = ROOT / "agent-runtime/tests/system_e2e/live/evidence"
RESULTS = ROOT / f"agent-runtime/tests/system_e2e/live/results/{RUN_ID}"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization-template.json"
MANIFEST_SHA256 = "eed2e0c3b84649823bcfc0fd52a899f6336d8de8bf3fe5f83731e96dd3daa2b8"
AUTHORIZATION_SHA256 = "82a95b17047021342e563515c616ff7980c16455b24a1f0487772f68a854afc9"
LIFECYCLE_SHA256 = "478962f96c7c61b94418ac8723f5180511ff0ea84523e87a76d28022c1efc7c2"
RESULT_SHA256 = "9511c5ece2d167e51e81f94a17dbf799d76df3aa20526e7f46481672de3c8492"


def test_candidate_01_manifest_and_source_assets_match_frozen_commit() -> None:
    assert sha256_file(MANIFEST) == MANIFEST_SHA256
    manifest = validate_manifest(
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        expected_run_id=RUN_ID,
    )
    assert sha256_file(AUTHORIZATION) == AUTHORIZATION_SHA256
    validate_authorization_template(
        json.loads(AUTHORIZATION.read_text(encoding="utf-8")),
        manifest_sha256=MANIFEST_SHA256,
        prepared_head=cast(str, manifest["preparedHead"]),
        expected_run_id=RUN_ID,
    )
    for asset in cast(list[dict[str, str]], manifest["assets"]):
        blob = subprocess.run(
            ["git", "show", f"{FROZEN_HEAD}:{asset['path']}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(blob).hexdigest() == asset["sha256"]


def test_candidate_01_failed_unconsumed_evidence_remains_immutable() -> None:
    lifecycle_path = RESULTS / "lifecycle.jsonl"
    result_path = RESULTS / "result.json"
    assert sha256_file(lifecycle_path) == LIFECYCLE_SHA256
    assert sha256_file(result_path) == RESULT_SHA256
    validate_lifecycle(
        json.loads(lifecycle_path.read_text(encoding="utf-8")),
        manifest_sha256=MANIFEST_SHA256,
        expected_run_id=RUN_ID,
    )
    result = validate_result(
        json.loads(result_path.read_text(encoding="utf-8")),
        require_passed=False,
        expected_run_id=RUN_ID,
    )
    assert result["status"] == "failed_unconsumed"
    assert result["reason"] == "business_query_plan_live.execution_failed"
    assert result["cases"] == []
    assert result["counts"] == {
        "modelCalls": 0,
        "employeeDetail": 0,
        "transactionSearch": 0,
        "otherBusinessEndpoints": 0,
        "fallbackSelector": 0,
        "answerGeneration": 0,
        "knowledge": 0,
        "retry": 0,
        "resume": 0,
    }
    assert not (RESULTS / "authorization.consumed.json").exists()
    assert not (RESULTS / "model-attempts.jsonl").exists()
