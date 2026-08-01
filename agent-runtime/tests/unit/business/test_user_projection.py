from __future__ import annotations

from decimal import Decimal

import pytest

from agent_runtime.adapters.transaction.contracts import TransactionRecord
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import (
    BusinessProjectionError,
    BusinessRecordsResult,
    BusinessResultCoverage,
)
from agent_runtime.business.user_projection import BusinessUserResultProjector


def test_user_projection_rejects_coverage_that_does_not_match_records() -> None:
    result = BusinessRecordsResult(
        records=(TransactionRecord(trans_id="T0001", trans_type="PAY", amount=Decimal("1.24")),),
        coverage=BusinessResultCoverage(returned_count=2, truncated=False, total_count=2),
    )

    with pytest.raises(BusinessProjectionError, match="business.minimum_user_result_not_met"):
        BusinessUserResultProjector().project(
            definition=transaction_search_definition(),
            settings=TransactionAdapterSettings.from_env({}).action,
            result=result,
            max_user_result_bytes=262144,
        )
