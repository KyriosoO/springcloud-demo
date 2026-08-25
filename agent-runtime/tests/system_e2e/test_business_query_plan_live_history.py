from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

from tests.system_e2e.business_query_plan_live_contracts import (
    sha256_file,
    validate_attempt_journal,
    validate_authorization_template,
    validate_consumed,
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
HISTORICAL_TASK_VERSION = "business-query-plan-v1"
HISTORICAL_PROMPT_SHA256 = "59ed646d9b77659ad4ca3b6b555aae6e21985f4d875ee12bfdc2f5dc14b0f3b4"
CANDIDATE_02_RUN_ID = "business-query-plan-live-v1-20260825-candidate-02"
CANDIDATE_02_FROZEN_HEAD = "0334c4404e63c01d2ad72f8b31248c82a9ce4375"
CANDIDATE_02_MANIFEST_SHA256 = "af57c8c8d032a83383670368addee24240bf6894ae9b543457feb4c0a910db3f"
CANDIDATE_02_AUTHORIZATION_SHA256 = "938e36a6001c90ec167e097353dee76750930192d468c2df4e6785eb7105e1a3"
CANDIDATE_02_LIFECYCLE_SHA256 = "75f11bf84cb0c8bfc77f7e831409511aba08b12379b8c8fc225655e00fd44c97"
CANDIDATE_02_CONSUMED_SHA256 = "bb766f5262bea97429a09516c316c6633153490b70da0e1ccd5df1b8cd7776e7"
CANDIDATE_02_JOURNAL_SHA256 = "6f552ca379bb4d4825f76be483fb67aba80be0cceb2b24ffd56c02904d7c6b9a"
CANDIDATE_02_RESULT_SHA256 = "ef3f8f2a50eb69cfc75cbf81638b26fe99027ebf1716aebee937011b375a4d79"


def test_candidate_01_manifest_and_source_assets_match_frozen_commit() -> None:
    assert sha256_file(MANIFEST) == MANIFEST_SHA256
    manifest = validate_manifest(
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        expected_run_id=RUN_ID,
        expected_task_version=HISTORICAL_TASK_VERSION,
        expected_system_instruction_sha256=HISTORICAL_PROMPT_SHA256,
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


def test_candidate_02_manifest_and_source_assets_match_frozen_commit() -> None:
    manifest_path = EVIDENCE / f"{CANDIDATE_02_RUN_ID}.manifest.json"
    authorization_path = EVIDENCE / f"{CANDIDATE_02_RUN_ID}.authorization-template.json"
    assert sha256_file(manifest_path) == CANDIDATE_02_MANIFEST_SHA256
    assert sha256_file(authorization_path) == CANDIDATE_02_AUTHORIZATION_SHA256
    manifest = validate_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        expected_run_id=CANDIDATE_02_RUN_ID,
        expected_task_version=HISTORICAL_TASK_VERSION,
        expected_system_instruction_sha256=HISTORICAL_PROMPT_SHA256,
    )
    validate_authorization_template(
        json.loads(authorization_path.read_text(encoding="utf-8")),
        manifest_sha256=CANDIDATE_02_MANIFEST_SHA256,
        prepared_head=cast(str, manifest["preparedHead"]),
        expected_run_id=CANDIDATE_02_RUN_ID,
    )
    for asset in cast(list[dict[str, str]], manifest["assets"]):
        blob = subprocess.run(
            ["git", "show", f"{CANDIDATE_02_FROZEN_HEAD}:{asset['path']}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(blob).hexdigest() == asset["sha256"]


def test_candidate_02_failed_consumed_evidence_remains_immutable() -> None:
    results = ROOT / f"agent-runtime/tests/system_e2e/live/results/{CANDIDATE_02_RUN_ID}"
    lifecycle_path = results / "lifecycle.jsonl"
    consumed_path = results / "authorization.consumed.json"
    journal_path = results / "model-attempts.jsonl"
    result_path = results / "result.json"
    assert sha256_file(lifecycle_path) == CANDIDATE_02_LIFECYCLE_SHA256
    assert sha256_file(consumed_path) == CANDIDATE_02_CONSUMED_SHA256
    assert sha256_file(journal_path) == CANDIDATE_02_JOURNAL_SHA256
    assert sha256_file(result_path) == CANDIDATE_02_RESULT_SHA256
    validate_lifecycle(
        json.loads(lifecycle_path.read_text(encoding="utf-8")),
        manifest_sha256=CANDIDATE_02_MANIFEST_SHA256,
        expected_run_id=CANDIDATE_02_RUN_ID,
    )
    validate_consumed(
        json.loads(consumed_path.read_text(encoding="utf-8")),
        manifest_sha256=CANDIDATE_02_MANIFEST_SHA256,
        expected_run_id=CANDIDATE_02_RUN_ID,
    )
    validate_attempt_journal(
        tuple(json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()),
        expected_calls=6,
    )
    result = validate_result(
        json.loads(result_path.read_text(encoding="utf-8")),
        require_passed=False,
        expected_run_id=CANDIDATE_02_RUN_ID,
    )
    assert result["status"] == "failed_consumed"
    assert result["reason"] == "business_query_plan_live.assertion_failed"
    assert len(cast(list[object], result["cases"])) == 5
    assert result["counts"] == {
        "modelCalls": 6,
        "employeeDetail": 2,
        "transactionSearch": 2,
        "otherBusinessEndpoints": 0,
        "fallbackSelector": 0,
        "answerGeneration": 0,
        "knowledge": 0,
        "retry": 0,
        "resume": 0,
    }
