from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_input_qualification_v4 import (
    AUTHORIZATION_REFERENCE,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_manifest,
    verify_history,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
EXPECTED_MANIFEST_SHA256 = "7dcae58a2a503a97fe89de0d01e63cb0450ccb0dd5945e4da5947d2df0875bb9"


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


def test_prepared_candidate_has_no_live_outputs() -> None:
    for suffix in (
        "host-lifecycle.jsonl",
        "lifecycle.jsonl",
        "result.json",
        "pre-sql-failure.json",
        "pending.json",
        "qualification-staging.json",
    ):
        assert not (EVIDENCE / f"{RUN_ID}.{suffix}").exists()
