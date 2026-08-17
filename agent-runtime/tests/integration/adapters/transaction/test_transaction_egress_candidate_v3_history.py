from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate_v2 import (
    consumed_path_for as candidate02_consumed_path_for,
)
from tests.integration.adapters.transaction.egress_candidate_v2 import (
    lifecycle_path_for as candidate02_lifecycle_path_for,
)
from tests.integration.adapters.transaction.egress_candidate_v2 import (
    result_path_for as candidate02_result_path_for,
)
from tests.integration.adapters.transaction.egress_candidate_v3 import sha256_file


EVIDENCE = Path(__file__).resolve().parent / "evidence"
TRANSACTION_TESTS = EVIDENCE.parent
EXPECTED = {
    "transaction-egress-v2-20260817-candidate-02.manifest.json": (
        "527845915ad15aa6f24fe59ed31885dcd3fef245109e7cee820217a86cbafa9c"
    ),
    "transaction-egress-v2-20260817-candidate-02.authorization.json": (
        "79733dd70d86c0acec44341d024c38849d45d58bb23dbf9ea9b98d9852c9cd38"
    ),
    "transaction-egress-v2-20260817-candidate-02.initialization-failure.json": (
        "37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9"
    ),
}


def test_candidate02_immutable_assets_and_absent_live_outputs_are_preserved() -> None:
    for name, expected in EXPECTED.items():
        assert sha256_file(EVIDENCE / name) == expected
    assert sha256_file(
        TRANSACTION_TESTS / "test_transaction_egress_candidate_v2_failed_history.py"
    ) == "f9ef153547cc4d8dc7362ed62a39260effab501f6948f6dd4759730b42eb6ce3"

    assert not candidate02_lifecycle_path_for(EVIDENCE).exists()
    assert not candidate02_consumed_path_for(EVIDENCE).exists()
    assert not candidate02_result_path_for(EVIDENCE).exists()
