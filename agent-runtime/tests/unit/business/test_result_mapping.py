from __future__ import annotations

import pytest

from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessFailureResult,
    BusinessHttpStatusSemantics,
    BusinessNoResult,
    BusinessServiceFailureKind,
)
from agent_runtime.business.result_mapping import map_business_http_status


@pytest.mark.parametrize(
    "status,kind",
    [(401, BusinessServiceFailureKind.UNAUTHENTICATED), (403, BusinessServiceFailureKind.FORBIDDEN),
     (429, BusinessServiceFailureKind.RATE_LIMITED), (500, BusinessServiceFailureKind.UNAVAILABLE),
     (404, BusinessServiceFailureKind.UNAVAILABLE)],
)
def test_status_mapping_is_finite(status: int, kind: BusinessServiceFailureKind) -> None:
    result = map_business_http_status(
        BoundedBusinessHttpResponse(status_code=status, content_type=None, body=None),
        BusinessHttpStatusSemantics(),
    )
    assert isinstance(result, BusinessFailureResult) and result.kind is kind


def test_only_code_bound_404_semantics_can_produce_no_result() -> None:
    result = map_business_http_status(
        BoundedBusinessHttpResponse(status_code=404, content_type=None, body=None),
        BusinessHttpStatusSemantics(http_404_is_no_result=True),
    )
    assert isinstance(result, BusinessNoResult)

