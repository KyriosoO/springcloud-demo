from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tests.integration.adapters.employee.fixture_metadata_diagnostic_v2 import (
    AUTHORIZATION_REFERENCE,
    MAX_QUERIES,
    RUN_ID,
    load_strict_json,
    sha256_file,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).with_name("evidence")
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
EXPECTED_MANIFEST_SHA256 = (
    "ce3dcd481352bbb59be01a2d3b975dfd1b9f35ae1479dd24d7408f11be7af6b7"
)
FROZEN_COMMIT = "80c52e030f41111aa1394d990a0af94568487b2c"
EXPECTED_LIFECYCLE_SHA256 = (
    "affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105"
)
EXPECTED_RESULT_SHA256 = (
    "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51"
)


def _frozen_blob(path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{FROZEN_COMMIT}:{path}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def test_prepared_manifest_authorization_and_assets_are_frozen() -> None:
    assert sha256_file(MANIFEST) == EXPECTED_MANIFEST_SHA256
    manifest = load_strict_json(MANIFEST)
    authorization = load_strict_json(AUTHORIZATION)
    assert manifest["runId"] == RUN_ID
    assert manifest["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert manifest["queryBudget"] == MAX_QUERIES
    assert len(manifest["assetHashes"]) == 7
    assert len(manifest["history"]) == 3
    assert authorization["manifestSha256"] == EXPECTED_MANIFEST_SHA256
    assert authorization["databaseAccessAuthorized"] is False
    assert authorization["liveExecutionAuthorized"] is False
    assert authorization["retryAllowed"] is False
    assert authorization["resumeAllowed"] is False
    assert hashlib.sha256(_frozen_blob(MANIFEST.relative_to(REPOSITORY).as_posix())).hexdigest() == (
        EXPECTED_MANIFEST_SHA256
    )
    assert _frozen_blob(AUTHORIZATION.relative_to(REPOSITORY).as_posix()) == (
        AUTHORIZATION.read_bytes()
    )
    for asset in manifest["assetHashes"]:
        blob = _frozen_blob(asset["path"])
        assert hashlib.sha256(blob).hexdigest() == asset["sha256"]


def test_post_consumption_lifecycle_and_result_are_frozen() -> None:
    lifecycle = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
    result = EVIDENCE / f"{RUN_ID}.result.json"
    assert sha256_file(lifecycle) == EXPECTED_LIFECYCLE_SHA256
    assert sha256_file(result) == EXPECTED_RESULT_SHA256
    assert _frozen_blob(lifecycle.relative_to(REPOSITORY).as_posix()) == lifecycle.read_bytes()
    assert _frozen_blob(result.relative_to(REPOSITORY).as_posix()) == result.read_bytes()


def test_run_01_bound_assets_remain_byte_identical() -> None:
    expected = {
        "employee-work-base-data-diagnostic-v1-20260814-run-01.json":
            "b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6",
        "employee-fixture-metadata-diagnostic-v1-20260814-run-01.failure.json":
            "dce5e7659ed9cc49b52aa9cca6b70c9701c22cc55867f26cfa6a50ead291e7a1",
        "employee-fixture-metadata-diagnostic-v1-failure.schema.json":
            "e9182239e7425a071c7daaf4c2a74fb3ef354fec9907ca0da5cef92f8ac85adc",
    }
    for name, digest in expected.items():
        assert sha256_file(EVIDENCE / name) == digest
