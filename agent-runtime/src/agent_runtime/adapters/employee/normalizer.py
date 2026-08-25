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
        if response.total_exact:
            expected = min(response.size, max(response.total - response.from_index, 0))
            if count != expected:
                return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
            if count == 0:
                return BusinessNoResult(
                    coverage=BusinessResultCoverage(
                        returned_count=0, truncated=False, total_count=response.total
                    )
                )
            coverage = BusinessResultCoverage(
                returned_count=count,
                truncated=response.from_index + count < response.total,
                total_count=response.total,
            )
        else:
            if count == 0 or response.total < count:
                return BusinessFailureResult(kind=BusinessServiceFailureKind.INVALID_RESPONSE)
            coverage = BusinessResultCoverage(
                returned_count=count, truncated=True, total_count=None
            )
        return BusinessRecordsResult(records=response.rows, coverage=coverage)
