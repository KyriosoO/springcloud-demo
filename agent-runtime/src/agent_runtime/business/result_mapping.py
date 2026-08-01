from __future__ import annotations

from typing import Never

from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessFailureResult,
    BusinessHttpStatusSemantics,
    BusinessNoResult,
    BusinessResultCoverage,
    BusinessServiceFailureKind,
    BusinessServiceResult,
)


def map_business_http_status(
    response: BoundedBusinessHttpResponse,
    semantics: BusinessHttpStatusSemantics,
) -> BusinessServiceResult[Never] | None:
    status = response.status_code
    if 200 <= status < 300 and status != 204:
        return None
    if status == 204:
        if semantics.http_204_is_no_result:
            return BusinessNoResult(coverage=BusinessResultCoverage(returned_count=0, truncated=False, total_count=None))
        return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
    if status == 400 and semantics.http_400_is_invalid_argument:
        return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_ARGUMENT)
    if status == 404 and semantics.http_404_is_no_result:
        return BusinessNoResult(coverage=BusinessResultCoverage(returned_count=0, truncated=False, total_count=None))
    if status == 401:
        return BusinessFailureResult(kind=BusinessServiceFailureKind.UNAUTHENTICATED)
    if status == 403:
        return BusinessFailureResult(kind=BusinessServiceFailureKind.FORBIDDEN)
    if status == 429:
        return BusinessFailureResult(kind=BusinessServiceFailureKind.RATE_LIMITED)
    return BusinessFailureResult(kind=BusinessServiceFailureKind.UNAVAILABLE)

