from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    load_strict_json,
    sha256_file,
)
from tests.integration.adapters.employee.live_bootstrap_v2 import (
    AUTHORIZATION_REFERENCE,
    BOOTSTRAP_ASSET_PATHS,
    BOOTSTRAP_HISTORY_PATHS,
    CANDIDATE_AUTHORIZATION_REFERENCE,
    CANDIDATE_AUTHORIZATION_SHA256,
    CANDIDATE_MANIFEST_SHA256,
    CANDIDATE_RUN_ID,
    EMPLOYEE_EXECUTABLE_ASSET_PATHS,
    RUN_ID,
    authorization_path,
    candidate_output_paths,
    manifest_path,
    output_paths,
    validate_prepared_assets,
)


ROOT = Path(__file__).resolve().parents[5]
MANIFEST = manifest_path(ROOT)
AUTHORIZATION = authorization_path(ROOT)


def _require_prepared_assets() -> None:
    if not MANIFEST.is_file() or not AUTHORIZATION.is_file():
        pytest.skip("employee bootstrap v2 manifest is generated after source commit")


def test_employee_v2_manifest_authorization_and_histories_are_frozen() -> None:
    _require_prepared_assets()
    binding = validate_prepared_assets(ROOT)
    manifest = load_strict_json(MANIFEST)
    assert binding.run_id == RUN_ID
    assert binding.authorization_reference == AUTHORIZATION_REFERENCE
    assert binding.candidate_run_id == CANDIDATE_RUN_ID
    candidate_authorization = load_strict_json(
        ROOT
        / "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v4-20260817-candidate-04.authorization.json"
    )
    assert candidate_authorization["authorizationReference"] == CANDIDATE_AUTHORIZATION_REFERENCE
    assert binding.candidate_manifest_sha256 == CANDIDATE_MANIFEST_SHA256
    assert binding.candidate_authorization_sha256 == CANDIDATE_AUTHORIZATION_SHA256
    assert {row["path"] for row in manifest["assetHashes"]} == BOOTSTRAP_ASSET_PATHS
    assert {row["path"] for row in manifest["historyHashes"]} == BOOTSTRAP_HISTORY_PATHS
    assert {row["path"] for row in manifest["executableHashes"]} == (
        EMPLOYEE_EXECUTABLE_ASSET_PATHS
    )
    assert sha256_file(MANIFEST) == load_strict_json(AUTHORIZATION)["manifestSha256"]


def test_employee_v2_assets_exist_at_frozen_source_commit() -> None:
    _require_prepared_assets()
    manifest = load_strict_json(MANIFEST)
    source_commit = manifest["wrapperSourceCommit"]
    assert manifest["buildProvenance"]["sourceCommit"] == source_commit
    expected = {row["path"]: row["sha256"] for row in manifest["assetHashes"]}
    for relative, expected_sha256 in expected.items():
        completed = subprocess.run(
            ["git", "show", f"{source_commit}:{relative}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        assert completed.returncode == 0
        assert hashlib.sha256(completed.stdout).hexdigest() == expected_sha256


def test_employee_v2_is_prepared_without_outer_or_inner_outputs() -> None:
    _require_prepared_assets()
    assert all(not path.exists() for path in output_paths(ROOT))
    assert all(not path.exists() for path in candidate_output_paths(ROOT))
