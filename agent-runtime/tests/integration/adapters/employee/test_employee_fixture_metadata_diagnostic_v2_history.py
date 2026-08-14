from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.fixture_metadata_diagnostic_v2 import (
    AUTHORIZATION_REFERENCE,
    MAX_QUERIES,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_manifest,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).with_name("evidence")
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
EXPECTED_MANIFEST_SHA256 = (
    "ce3dcd481352bbb59be01a2d3b975dfd1b9f35ae1479dd24d7408f11be7af6b7"
)


def test_prepared_manifest_authorization_and_assets_are_frozen() -> None:
    assert sha256_file(MANIFEST) == EXPECTED_MANIFEST_SHA256
    validate_manifest(MANIFEST, AUTHORIZATION, REPOSITORY)
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


def test_preparation_has_no_live_lifecycle_or_result() -> None:
    assert not (EVIDENCE / f"{RUN_ID}.lifecycle.jsonl").exists()
    assert not (EVIDENCE / f"{RUN_ID}.result.json").exists()


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
