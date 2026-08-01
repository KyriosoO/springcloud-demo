from __future__ import annotations

from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityKind
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessAnswerMode,
    BusinessContractLimits,
    BusinessDomainId,
    BusinessHttpStatusSemantics,
    BusinessServiceKey,
    ConstraintDimension,
)
from agent_runtime.adapters.employee.codec import (
    EmployeeDetailArgumentValidator,
    EmployeeDetailRequestMapper,
    EmployeeDetailWireCodec,
)
from agent_runtime.adapters.employee.contracts import (
    EmployeeDetailInput,
    EmployeeDetailRecord,
    EmployeeDetailWireRequest,
    EmployeeDetailWireResponse,
)
from agent_runtime.adapters.employee.fields import employee_field_definitions
from agent_runtime.adapters.employee.normalizer import EmployeeDetailResponseNormalizer


def employee_detail_definition() -> BusinessActionDefinition[
    EmployeeDetailInput,
    EmployeeDetailWireRequest,
    EmployeeDetailWireResponse,
    EmployeeDetailRecord,
]:
    return BusinessActionDefinition(
        descriptor=CapabilityDescriptor(
            capability_id="employee.detail", api_version=1, kind=CapabilityKind.QUERY,
            display_name="Employee detail",
            description="查询单个员工的受控基础信息；只接受 employee_identifier，不提供列表、聚合或写入。",
            aliases=("员工详情", "employee profile"),
            argument_schema={
                "type": "object",
                "properties": {"employee_identifier": {
                    "type": "string", "minLength": 5, "maxLength": 64,
                    "description": "Employee service identifier; never a URL or query expression.",
                }},
                "required": ("employee_identifier",), "additionalProperties": False,
            },
        ),
        domain_id=BusinessDomainId("employee"),
        service_key=BusinessServiceKey("employee-service"),
        argument_validator=EmployeeDetailArgumentValidator(),
        request_mapper=EmployeeDetailRequestMapper(),
        wire_codec=EmployeeDetailWireCodec(),
        response_normalizer=EmployeeDetailResponseNormalizer(),
        http_status_semantics=BusinessHttpStatusSemantics(http_400_is_invalid_argument=True),
        applicable_dimensions=frozenset({ConstraintDimension.RESULT_COUNT}),
        filter_field_ids_by_code=frozenset(), sort_field_ids_by_code=frozenset(),
        field_definitions=employee_field_definitions(),
        required_user_field_ids=("employee_id_masked", "chinese_name"),
        answer_mode=BusinessAnswerMode.MODEL_ASSISTED,
        contract_limits=BusinessContractLimits(
            max_page_size=None, max_result_count=1, max_time_range_days=None,
            max_timeout_ms=3000, max_request_bytes=1024,
        ),
    )

