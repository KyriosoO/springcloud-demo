from __future__ import annotations

from agent_runtime.business.contracts import (
    BusinessFailureResult,
    BusinessNoResult,
    BusinessRecordsResult,
    BusinessResultCoverage,
    BusinessServiceFailureKind,
    BusinessServiceResult,
)
from agent_runtime.adapters.employee.contracts import (
    EmployeeDetailRecord,
    EmployeeDetailWireResponse,
    EmployeeSearchRecord,
    EmployeeSearchWireResponse,
)


class EmployeeDetailResponseNormalizer:
    def normalize_success(self, response: EmployeeDetailWireResponse) -> BusinessRecordsResult[EmployeeDetailRecord]:
        record = EmployeeDetailRecord(
            id_card_no=response.id_card_no,
            member_no=response.member_no,
            chinese_name=response.chinese_name,
            public_email=response.public_email,
            position=response.position,
            work_base_si=response.work_base_si,
        )
        return BusinessRecordsResult(
            records=(record,),
            coverage=BusinessResultCoverage(returned_count=1, truncated=False, total_count=1),
        )


class EmployeeSearchResponseNormalizer:
    def normalize_success(
        self, response: EmployeeSearchWireResponse
    ) -> BusinessServiceResult[EmployeeSearchRecord]:
        count = len(response.rows)
        upstream_count = response.upstream_hit_count
        if (
            type(upstream_count) is not int
            or type(response.allow_partial_page) is not bool
            or not count <= upstream_count <= response.size
            or response.total < upstream_count
        ):
            return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
        if response.total_exact:
            expected = min(response.size, max(response.total - response.from_index, 0))
            if (
                upstream_count > expected
                or not response.allow_partial_page and upstream_count != expected
                or response.allow_partial_page and upstream_count == 0 and response.total != 0
            ):
                return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
            if count == 0:
                if upstream_count != 0:
                    return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
                return BusinessNoResult(
                    coverage=BusinessResultCoverage(
                        returned_count=0, truncated=False, total_count=response.total
                    )
                )
            coverage = BusinessResultCoverage(
                returned_count=count,
                truncated=(
                    response.from_index + upstream_count < response.total
                    or count < upstream_count
                    or response.allow_partial_page and upstream_count < expected
                ),
                total_count=response.total,
            )
        else:
            if count == 0 or upstream_count == 0 or response.total < upstream_count:
                return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
            coverage = BusinessResultCoverage(
                returned_count=count, truncated=True, total_count=None
            )
        return BusinessRecordsResult(records=response.rows, coverage=coverage)
