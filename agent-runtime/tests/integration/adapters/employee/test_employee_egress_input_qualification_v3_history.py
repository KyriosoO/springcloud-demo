from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_input_qualification_v3 import (
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
EXPECTED_MANIFEST_SHA256 = "495063a328af6a233f5600bd4efff31fdae5ab4e28aad8287bfce194051680dd"


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


def test_prepared_candidate_has_no_live_outputs() -> None:
    for suffix in (
        "lifecycle.jsonl",
        "result.json",
        "pending.json",
        "qualification-staging.json",
    ):
        assert not (EVIDENCE / f"{RUN_ID}.{suffix}").exists()
