from __future__ import annotations

from agent_runtime.business.contracts import (
    BusinessNoResult,
    BusinessRecordsResult,
    BusinessResultCoverage,
    BusinessServiceResult,
    BusinessServiceFailureKind,
    BusinessFailureResult,
)
from agent_runtime.adapters.transaction.contracts import TransactionRecord, TransactionSearchWireResponse


class TransactionSearchResponseNormalizer:
    def normalize_success(self, response: TransactionSearchWireResponse) -> BusinessServiceResult[TransactionRecord]:
        count = len(response.rows)
        if count == 0:
            if response.total == 0 and response.total_exact:
                return BusinessNoResult(coverage=BusinessResultCoverage(returned_count=0, truncated=False, total_count=0))
            return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
        if response.total_exact:
            if count != min(response.total, response.size):
                return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
            coverage = BusinessResultCoverage(returned_count=count, truncated=count < response.total, total_count=response.total)
        else:
            coverage = BusinessResultCoverage(returned_count=count, truncated=True, total_count=None)
        return BusinessRecordsResult(records=response.rows, coverage=coverage)

