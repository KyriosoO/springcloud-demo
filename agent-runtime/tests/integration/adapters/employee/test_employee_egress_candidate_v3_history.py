from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tests.integration.adapters.employee.egress_candidate_v3 import (
    HISTORY_ASSETS,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    verify_history,
)


REPOSITORY = Path(__file__).parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
FROZEN_COMMIT = "23ed432cef2c5d5509139e6d8921372ba6cb4501"
MANIFEST_SHA256 = "901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e"


def test_prepared_candidate_and_all_predecessor_evidence_remain_immutable() -> None:
    manifest_path = EVIDENCE / f"{RUN_ID}.manifest.json"
    authorization_path = EVIDENCE / f"{RUN_ID}.authorization.json"
    manifest_sha = sha256_file(manifest_path)

    assert manifest_sha == MANIFEST_SHA256
    manifest = load_strict_json(manifest_path)
    validate_authorization(
        load_strict_json(authorization_path), manifest_sha256=manifest_sha
    )
    verify_history(REPOSITORY)
    for _name, relative_path, expected_hash in HISTORY_ASSETS:
        assert sha256_file(REPOSITORY / relative_path) == expected_hash

    for asset in manifest["assetHashes"]:
        frozen = subprocess.run(
            ["git", "show", f"{FROZEN_COMMIT}:{asset['path']}"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset["sha256"]
