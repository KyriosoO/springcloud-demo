from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from tests.integration.adapters.employee.egress_input_qualification_v4 import (
    AUTHORIZATION_REFERENCE,
    QualificationV4Error,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_lifecycle,
    validate_manifest,
    validate_result,
    verify_history,
)
from tests.integration.adapters.employee.egress_input_qualification_v4_host import (
    validate_host_lifecycle,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
EXPECTED_MANIFEST_SHA256 = "7dcae58a2a503a97fe89de0d01e63cb0450ccb0dd5945e4da5947d2df0875bb9"
FROZEN_HEAD = "d0d35447b25cb0980b6eb055fdbc485765a7272f"
EXPECTED_HOST_LIFECYCLE_SHA256 = "73bd37aaec1c3c57d7debea5f1120cd3cff828057bcaee84afbdb4495658472a"
EXPECTED_LIFECYCLE_SHA256 = "aa2479fc8051cb4741f9826b81521583285ede692d31b9c6bed01bf1b2a922c3"
EXPECTED_RESULT_SHA256 = "757bd4840143bbe5158facec89f7035cf72f99eac88b4c345d70cbc8ea0b5975"


def _frozen_blob(path: Path) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{FROZEN_HEAD}:{path.relative_to(REPOSITORY).as_posix()}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def test_prepared_manifest_authorization_and_history_are_exact() -> None:
    verify_history(REPOSITORY)
    assert sha256_file(MANIFEST) == EXPECTED_MANIFEST_SHA256
    manifest = validate_manifest(load_strict_json(MANIFEST), repository_root=REPOSITORY)
    authorization = validate_authorization(
        load_strict_json(AUTHORIZATION), manifest_sha256=EXPECTED_MANIFEST_SHA256
    )
    assert manifest["runId"] == RUN_ID
    assert authorization["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert authorization["liveExecutionAuthorized"] is False
    assert manifest["budgets"] == authorization["budgets"]
    assert len(manifest["history"]) == 11
    assert len(manifest["assetHashes"]) == 11
    assert _frozen_blob(MANIFEST) == MANIFEST.read_bytes()
    assert _frozen_blob(AUTHORIZATION) == AUTHORIZATION.read_bytes()
    for asset in manifest["assetHashes"]:
        path = REPOSITORY / asset["path"]
        assert _frozen_blob(path) == path.read_bytes()


def test_post_consumption_evidence_is_exact_and_qualified() -> None:
    host_lifecycle = EVIDENCE / f"{RUN_ID}.host-lifecycle.jsonl"
    lifecycle = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
    result_path = EVIDENCE / f"{RUN_ID}.result.json"
    assert sha256_file(host_lifecycle) == EXPECTED_HOST_LIFECYCLE_SHA256
    assert sha256_file(lifecycle) == EXPECTED_LIFECYCLE_SHA256
    assert sha256_file(result_path) == EXPECTED_RESULT_SHA256

    host_records = validate_host_lifecycle(
        host_lifecycle, manifest_sha256=EXPECTED_MANIFEST_SHA256
    )
    lifecycle_records = [
        json.loads(line) for line in lifecycle.read_text(encoding="utf-8").splitlines()
    ]
    result = validate_result(load_strict_json(result_path))
    assert len(host_records) == 4
    assert host_records[-1]["state"] == "succeeded"
    assert len(lifecycle_records) == 15
    assert [
        (record["sequence"], record["phase"], record["state"], record["reason"])
        for record in lifecycle_records
    ] == [
        (1, "run", "started", "none"),
        (2, "fixture_precheck", "started", "none"),
        (3, "fixture_precheck", "succeeded", "none"),
        (4, "fixture_insert", "started", "none"),
        (5, "fixture_insert", "succeeded", "none"),
        (6, "fixture_verify", "started", "none"),
        (7, "fixture_verify", "succeeded", "none"),
        (8, "employee_detail", "started", "none"),
        (9, "employee_detail", "succeeded", "none"),
        (10, "cleanup_delete", "started", "none"),
        (11, "cleanup_delete", "succeeded", "none"),
        (12, "cleanup_verify", "started", "none"),
        (13, "cleanup_verify", "succeeded", "none"),
        (14, "host_validation", "succeeded", "none"),
        (15, "run", "succeeded", "none"),
    ]
    assert result["status"] == "qualified"
    assert result["reason"] == "none"
    assert result["lifecycleSha256"] == EXPECTED_LIFECYCLE_SHA256
    assert result["counts"] == {
        "databaseDeleteStarted": 1,
        "databaseDeleteTerminal": 1,
        "databaseInsertStarted": 1,
        "databaseInsertTerminal": 1,
        "databaseSelectStarted": 3,
        "databaseSelectTerminal": 3,
        "deleted": 1,
        "employeeDetailStarted": 1,
        "employeeDetailTerminal": 1,
        "inserted": 1,
        "modelCalls": 0,
        "otherEmployeeEndpoints": 0,
        "preexisting": 0,
        "remaining": 0,
        "resumeCount": 0,
        "retryCount": 0,
        "verified": 1,
    }
    assert all(result["fieldPresence"]["codec"].values())
    assert all(result["fieldPresence"]["requiredUser"].values())
    assert result["fieldPresence"]["egressAllowed"] is True
    assert result["safety"] == {
        "existingRowsModified": 0,
        "fieldValuesPersisted": False,
        "identifierPersisted": False,
        "jwtPersisted": False,
        "llmApiKeyRead": False,
        "logLeakCount": 0,
        "modelOutbound": False,
        "nonRealIdentifier": True,
        "rawLogsDeleted": True,
        "rawResponsePersisted": False,
        "synthetic": True,
    }

    for suffix in ("pre-sql-failure.json", "pending.json", "qualification-staging.json"):
        assert not (EVIDENCE / f"{RUN_ID}.{suffix}").exists()


def test_frozen_validator_rejects_unpaired_host_validation_terminal() -> None:
    lifecycle = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
    with pytest.raises(QualificationV4Error, match="employee.qualification_v4_invalid"):
        validate_lifecycle(lifecycle, manifest_sha256=EXPECTED_MANIFEST_SHA256)
