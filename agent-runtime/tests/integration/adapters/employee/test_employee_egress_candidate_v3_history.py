from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_candidate_v3 import (
    HISTORY_ASSETS,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_manifest,
    verify_history,
)


REPOSITORY = Path(__file__).parents[5]
EVIDENCE = Path(__file__).parent / "evidence"


def test_prepared_candidate_and_all_predecessor_evidence_remain_replayable() -> None:
    manifest_path = EVIDENCE / f"{RUN_ID}.manifest.json"
    authorization_path = EVIDENCE / f"{RUN_ID}.authorization.json"
    manifest_sha = sha256_file(manifest_path)

    validate_manifest(load_strict_json(manifest_path), repository_root=REPOSITORY)
    validate_authorization(
        load_strict_json(authorization_path), manifest_sha256=manifest_sha
    )
    verify_history(REPOSITORY)
    for _name, relative_path, expected_hash in HISTORY_ASSETS:
        assert sha256_file(REPOSITORY / relative_path) == expected_hash
