from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate_v4 import sha256_file
from tests.integration.adapters.transaction.test_transaction_egress_candidate_v3_failed_history import (
    EXPECTED_SHA256,
)


EVIDENCE = Path(__file__).resolve().parent / "evidence"


def test_candidate04_binds_candidate03_failed_history_without_mutation() -> None:
    assert {
        name: sha256_file(EVIDENCE / name)
        for name in EXPECTED_SHA256
    } == EXPECTED_SHA256
