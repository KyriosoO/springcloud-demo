from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, cast

from tests.integration.adapters.employee.employee_test_data_fixture_candidate import (
    AUTHORIZATION_REFERENCE,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_lifecycle,
    validate_result,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).with_name("evidence")
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
LIFECYCLE = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
RESULT = EVIDENCE / f"{RUN_ID}.result.json"
FROZEN_COMMIT = "fd95e181993caec1263529ebf6ff357daad5bcaa"
EXPECTED_MANIFEST_SHA256 = (
    "e0c74e5a21d4b80c292cf20266227f7c8f1a11037d1816a6513f6de604e98b11"
)
EXPECTED_AUTHORIZATION_SHA256 = (
    "00e44c6df2d04edbc03ee9eaa51541041b6263a73bc91c3fdf9ed57bf11c3a2f"
)
EXPECTED_LIFECYCLE_SHA256 = (
    "4d5ab81e68d24ac76a7c1d6f7b1a57204b7cb81c99f40f93afe444f4077f5b6c"
)
EXPECTED_RESULT_SHA256 = (
    "f0003ec559fa4606edda2982f0ae6878bfa066262168236128705d0c40aa0e4a"
)


def _frozen_blob(path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{FROZEN_COMMIT}:{path}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def test_prepared_manifest_authorization_history_and_assets_are_frozen() -> None:
    assert sha256_file(MANIFEST) == EXPECTED_MANIFEST_SHA256
    assert sha256_file(AUTHORIZATION) == EXPECTED_AUTHORIZATION_SHA256
    manifest = load_strict_json(MANIFEST)
    authorization = load_strict_json(AUTHORIZATION)
    assert manifest["runId"] == RUN_ID
    assert manifest["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert authorization["manifestSha256"] == EXPECTED_MANIFEST_SHA256
    assert authorization["liveExecutionAuthorized"] is False
    assert hashlib.sha256(
        _frozen_blob(MANIFEST.relative_to(REPOSITORY).as_posix())
    ).hexdigest() == EXPECTED_MANIFEST_SHA256
    assert _frozen_blob(AUTHORIZATION.relative_to(REPOSITORY).as_posix()) == (
        AUTHORIZATION.read_bytes()
    )
    for untyped_asset in [*manifest["sourceHistory"], *manifest["assetHashes"]]:
        asset = cast(dict[str, Any], untyped_asset)
        assert hashlib.sha256(_frozen_blob(cast(str, asset["path"]))).hexdigest() == (
            asset["sha256"]
        )


def test_post_consumption_lifecycle_and_result_are_frozen_and_passed() -> None:
    assert sha256_file(LIFECYCLE) == EXPECTED_LIFECYCLE_SHA256
    assert sha256_file(RESULT) == EXPECTED_RESULT_SHA256
    assert _frozen_blob(LIFECYCLE.relative_to(REPOSITORY).as_posix()) == (
        LIFECYCLE.read_bytes()
    )
    assert _frozen_blob(RESULT.relative_to(REPOSITORY).as_posix()) == RESULT.read_bytes()

    lifecycle = validate_lifecycle(
        LIFECYCLE,
        manifest_sha256=EXPECTED_MANIFEST_SHA256,
    )
    result = validate_result(load_strict_json(RESULT))
    assert len(lifecycle) == 16
    assert result["status"] == "passed"
    assert result["reason"] == "none"
    assert result["lifecycleSha256"] == EXPECTED_LIFECYCLE_SHA256
    assert result["counts"] == {
        "databaseSelectStarted": 3,
        "databaseSelectTerminal": 3,
        "databaseInsertStarted": 1,
        "databaseInsertTerminal": 1,
        "databaseDeleteStarted": 1,
        "databaseDeleteTerminal": 1,
        "preexisting": 0,
        "inserted": 1,
        "verified": 1,
        "deleted": 1,
        "remaining": 0,
        "consumerCalls": 1,
        "employeeEndpointCalls": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    assert result["safety"] == {
        "synthetic": True,
        "nonRealIdentifier": True,
        "identifierPersisted": False,
        "fixtureFingerprintPersisted": False,
        "fieldValuesPersisted": False,
        "existingRowsModified": 0,
        "publicApiCalls": 0,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "modelOutbound": False,
        "logLeakCount": 0,
        "rawLogsDeleted": True,
    }


def test_append_only_evidence_contains_no_fixture_values() -> None:
    persisted = LIFECYCLE.read_text(encoding="utf-8") + RESULT.read_text(encoding="utf-8")
    for forbidden in (
        "synthetic-employee-",
        "Synthetic Employee",
        "Synthetic Position",
        "Synthetic Work Base",
    ):
        assert forbidden not in persisted
