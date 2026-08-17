from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate import (
    consumed_path_for as retired_consumed_path_for,
)
from tests.integration.adapters.transaction.egress_candidate import (
    lifecycle_path_for as retired_lifecycle_path_for,
)
from tests.integration.adapters.transaction.egress_candidate import (
    load_strict_json,
    result_path_for as retired_result_path_for,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = ROOT / "agent-runtime/tests/integration/adapters/transaction/evidence"
REAL_EVIDENCE = EVIDENCE / "wp-txn-real-01-20260806T134518Z.json"
RETIRED_MANIFEST = EVIDENCE / "transaction-egress-v1-20260814-candidate-01.manifest.json"
RETIRED_AUTHORIZATION = (
    EVIDENCE / "transaction-egress-v1-20260814-candidate-01.authorization.json"
)
REAL_EVIDENCE_SHA256 = "1109da47183a822c9ad82fbcc2ef3619163a8089d8f0f420d045e0d30d80f7d1"
RETIRED_MANIFEST_SHA256 = "dba4610cc0e578e65c45b49b288ce9d4b74b90eea9f9d05609e7935dd2feac44"
RETIRED_AUTHORIZATION_SHA256 = (
    "067b7d79f7e7e3d744e79a670378c9219aecf795b570522f7bd98335a09cc038"
)
RETIRED_FROZEN_COMMIT = "c028f4548ee8b99b1722876cccb7c0e4f69feb92"


def test_real_authorization_precision_and_retired_bindings_are_immutable() -> None:
    assert sha256_file(REAL_EVIDENCE) == REAL_EVIDENCE_SHA256
    assert sha256_file(RETIRED_MANIFEST) == RETIRED_MANIFEST_SHA256
    assert sha256_file(RETIRED_AUTHORIZATION) == RETIRED_AUTHORIZATION_SHA256


def test_retired_candidate_assets_match_its_frozen_commit() -> None:
    manifest = load_strict_json(RETIRED_MANIFEST)
    assert manifest["status"] == "prepared_unconsumed"
    for asset in manifest["assetHashes"]:
        frozen = subprocess.run(
            ["git", "show", f"{RETIRED_FROZEN_COMMIT}:{asset['path']}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset["sha256"]


def test_retired_candidate_remains_unconsumed_and_cannot_be_reused() -> None:
    assert not retired_lifecycle_path_for(EVIDENCE).exists()
    assert not retired_consumed_path_for(EVIDENCE).exists()
    assert not retired_result_path_for(EVIDENCE).exists()
    authorization = load_strict_json(RETIRED_AUTHORIZATION)
    assert authorization["liveExecutionAuthorized"] is False
    assert authorization["runId"] == "transaction-egress-v1-20260814-candidate-01"
