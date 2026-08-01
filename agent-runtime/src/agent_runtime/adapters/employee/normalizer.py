from __future__ import annotations

from agent_runtime.business.contracts import BusinessRecordsResult, BusinessResultCoverage
from agent_runtime.adapters.employee.contracts import EmployeeDetailRecord, EmployeeDetailWireResponse


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

