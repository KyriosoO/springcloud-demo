from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    BootstrapBinding,
    load_strict_json,
    read_lifecycle,
    sha256_file,
    validate_result,
)
from tests.integration.adapters.frozen_manifest import (
    bind_historical_bootstrap,
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
)


ROOT = Path(__file__).resolve().parents[5]
MANIFEST = manifest_path(ROOT)
AUTHORIZATION = authorization_path(ROOT)
EXPECTED_SHA256 = {
    f"{RUN_ID}.manifest.json": "899eb378df014085c6e419a1720be96994698457b1f248215e8df2374118b383",
    f"{RUN_ID}.authorization.json": "0f9d71d0636f956aa12c4928a91137e53a211a74718a66a30b8f29fd8eb63000",
    f"{RUN_ID}.lifecycle.jsonl": "58d315f6ee87dde24b166ef7c58fdcbd74ef8e0c61ae6c5f97596d419f539abc",
    f"{RUN_ID}.result.json": "0b320ff1ab9bc28d759531cacca44d3fc01392c6d6058eae0f20ff1f13bac6d0",
}


def _require_prepared_assets() -> None:
    if not MANIFEST.is_file() or not AUTHORIZATION.is_file():
        pytest.skip("employee bootstrap v2 manifest is generated after source commit")


def _historical_binding(tmp_path: Path) -> BootstrapBinding:
    return bind_historical_bootstrap(
        repository_root=ROOT,
        destination=tmp_path / "frozen-repository",
        manifest_path=MANIFEST,
        authorization_path=AUTHORIZATION,
        executable_paths=EMPLOYEE_EXECUTABLE_ASSET_PATHS,
    )


def test_employee_v2_manifest_authorization_and_histories_are_frozen(
    tmp_path: Path,
) -> None:
    _require_prepared_assets()
    binding = _historical_binding(tmp_path)
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


def test_employee_v2_failed_history_is_exact_and_non_reusable(tmp_path: Path) -> None:
    _require_prepared_assets()
    evidence = MANIFEST.parent
    paths = {name: evidence / name for name in EXPECTED_SHA256}
    assert {name: sha256_file(path) for name, path in paths.items()} == EXPECTED_SHA256

    binding = _historical_binding(tmp_path)
    lifecycle_path, result_path, diagnostic_path = output_paths(ROOT)
    lifecycle = read_lifecycle(lifecycle_path, binding=binding)
    result = load_strict_json(result_path)
    validate_result(result, binding=binding)

    assert len(lifecycle) == 4
    assert lifecycle[1]["phase"] == "asset_preflight"
    assert lifecycle[1]["status"] == "failed"
    assert lifecycle[1]["reason"] == "asset_hash_invalid"
    assert result["status"] == "failed_pre_candidate_unconsumed"
    assert result["candidateInvoked"] is False
    assert result["failure"] == {
        "phase": "asset_preflight",
        "reason": "asset_hash_invalid",
    }
    assert result["counts"]["retry"] == 0
    assert result["counts"]["resume"] == 0
    assert not diagnostic_path.exists()
    assert all(not path.exists() for path in candidate_output_paths(ROOT))
