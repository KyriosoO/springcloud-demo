from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate import sha256_file


ROOT = Path(__file__).resolve().parents[5]
REAL_EVIDENCE = (
    ROOT
    / "agent-runtime/tests/integration/adapters/transaction/evidence/wp-txn-real-01-20260806T134518Z.json"
)
REAL_EVIDENCE_SHA256 = "1109da47183a822c9ad82fbcc2ef3619163a8089d8f0f420d045e0d30d80f7d1"


def test_transaction_real_authorization_and_precision_evidence_is_immutable() -> None:
    assert sha256_file(REAL_EVIDENCE) == REAL_EVIDENCE_SHA256
