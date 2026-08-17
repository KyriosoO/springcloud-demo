from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate import load_strict_json, sha256_file


ROOT = Path(__file__).resolve().parents[5]
REAL_EVIDENCE = (
    ROOT
    / "agent-runtime/tests/integration/adapters/transaction/evidence/wp-txn-real-01-20260806T134518Z.json"
)
REAL_EVIDENCE_SHA256 = "1109da47183a822c9ad82fbcc2ef3619163a8089d8f0f420d045e0d30d80f7d1"
FROZEN_COMMIT = "c028f4548ee8b99b1722876cccb7c0e4f69feb92"
MANIFEST = (
    ROOT
    / "agent-runtime/tests/integration/adapters/transaction/evidence/"
    "transaction-egress-v1-20260814-candidate-01.manifest.json"
)
MANIFEST_SHA256 = "dba4610cc0e578e65c45b49b288ce9d4b74b90eea9f9d05609e7935dd2feac44"


def test_transaction_real_authorization_and_precision_evidence_is_immutable() -> None:
    assert sha256_file(REAL_EVIDENCE) == REAL_EVIDENCE_SHA256


def test_retired_candidate_assets_match_the_frozen_commit() -> None:
    assert sha256_file(MANIFEST) == MANIFEST_SHA256
    manifest = load_strict_json(MANIFEST)
    for asset in manifest["assetHashes"]:
        frozen = subprocess.run(
            ["git", "show", f"{FROZEN_COMMIT}:{asset['path']}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset["sha256"]
