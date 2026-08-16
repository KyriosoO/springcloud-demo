from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_input_qualification_v6 import (
    ASSET_PATHS,
    AUTHORIZATION_REFERENCE,
    HISTORY,
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


def test_prepared_manifest_authorization_assets_and_history_are_exact() -> None:
    verify_history(REPOSITORY)
    manifest_sha256 = sha256_file(MANIFEST)
    manifest = validate_manifest(load_strict_json(MANIFEST), repository_root=REPOSITORY)
    authorization = validate_authorization(
        load_strict_json(AUTHORIZATION), manifest_sha256=manifest_sha256
    )
    assert manifest["runId"] == RUN_ID
    assert authorization["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert authorization["liveExecutionAuthorized"] is False
    assert manifest["budgets"] == authorization["budgets"]
    assert len(manifest["history"]) == len(HISTORY) == 23
    assert len(manifest["assetHashes"]) == len(ASSET_PATHS) == 12
    assert {item["path"] for item in manifest["assetHashes"]} == ASSET_PATHS


def test_candidate_v5_post_consumption_history_is_bound_and_immutable() -> None:
    expected = {
        "qualification_v5_manifest",
        "qualification_v5_authorization",
        "qualification_v5_host_lifecycle",
        "qualification_v5_lifecycle",
        "qualification_v5_result",
        "qualification_v5_consumed_history_test",
    }
    assert {
        kind for kind, _, _ in HISTORY if kind.startswith("qualification_v5_")
    } == expected
    verify_history(REPOSITORY)
