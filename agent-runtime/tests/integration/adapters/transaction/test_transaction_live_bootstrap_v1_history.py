from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    load_strict_json,
    sha256_file,
    validate_prepared_assets,
)
from tests.integration.adapters.frozen_manifest import (
    materialize_current_hash_bindings,
    materialize_manifest_at_commit,
)
from tests.integration.adapters.transaction.live_bootstrap_v1 import (
    AUTHORIZATION_REFERENCE,
    BOOTSTRAP_ASSET_PATHS,
    BOOTSTRAP_HISTORY_PATHS,
    CANDIDATE_AUTHORIZATION_SHA256,
    CANDIDATE_MANIFEST_SHA256,
    CANDIDATE_RUN_ID,
    RUN_ID,
    authorization_path,
    candidate_output_paths,
    manifest_path,
    output_paths,
)


ROOT = Path(__file__).resolve().parents[5]
MANIFEST = manifest_path(ROOT)
AUTHORIZATION = authorization_path(ROOT)


def _require_prepared_assets() -> None:
    if not MANIFEST.is_file() or not AUTHORIZATION.is_file():
        pytest.skip("transaction bootstrap manifest is generated after wrapper source commit")


def _frozen_repository(tmp_path: Path) -> Path:
    manifest = load_strict_json(MANIFEST)
    frozen = materialize_manifest_at_commit(
        manifest,
        repository_root=ROOT,
        destination=tmp_path / "frozen-repository",
        source_commit=manifest["wrapperSourceCommit"],
        collection_names=("assetHashes", "historyHashes"),
    )
    candidate = manifest["candidate"]
    return materialize_current_hash_bindings(
        {
            candidate["manifestPath"]: candidate["manifestSha256"],
            candidate["authorizationPath"]: candidate["authorizationSha256"],
        },
        repository_root=ROOT,
        destination=frozen,
    )


def test_transaction_bootstrap_manifest_authorization_assets_and_history_are_frozen(
    tmp_path: Path,
) -> None:
    _require_prepared_assets()
    binding = validate_prepared_assets(
        repository_root=_frozen_repository(tmp_path),
        manifest_path=MANIFEST,
        authorization_path=AUTHORIZATION,
    )
    manifest = load_strict_json(MANIFEST)
    assert binding.run_id == RUN_ID
    assert binding.authorization_reference == AUTHORIZATION_REFERENCE
    assert binding.candidate_run_id == CANDIDATE_RUN_ID
    assert binding.candidate_manifest_sha256 == CANDIDATE_MANIFEST_SHA256
    assert binding.candidate_authorization_sha256 == CANDIDATE_AUTHORIZATION_SHA256
    assert {row["path"] for row in manifest["assetHashes"]} == BOOTSTRAP_ASSET_PATHS
    assert {row["path"] for row in manifest["historyHashes"]} == BOOTSTRAP_HISTORY_PATHS
    assert sha256_file(MANIFEST) == load_strict_json(AUTHORIZATION)["manifestSha256"]


def test_transaction_bootstrap_assets_exist_at_frozen_source_commit() -> None:
    _require_prepared_assets()
    manifest = load_strict_json(MANIFEST)
    source_commit = manifest["wrapperSourceCommit"]
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


def test_transaction_bootstrap_has_recorded_outer_failure_and_no_inner_outputs() -> None:
    _require_prepared_assets()
    assert all(path.is_file() for path in output_paths(ROOT))
    assert all(not path.exists() for path in candidate_output_paths(ROOT))
