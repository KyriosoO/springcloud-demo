from __future__ import annotations

from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityKind
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessAnswerMode,
    BusinessContractLimits,
    BusinessDomainId,
    BusinessHttpStatusSemantics,
    BusinessInputExposure,
    BusinessQueryFieldDefinition,
    BusinessQueryOperator,
    BusinessQueryValueType,
    BusinessServiceKey,
    ConstraintDimension,
    business_query_v2_action_contract,
    business_query_v3_action_contract,
)
from agent_runtime.adapters.employee.codec import (
    EmployeeDetailArgumentValidator,
    EmployeeDetailRequestMapper,
    EmployeeDetailWireCodec,
    EmployeeSearchArgumentValidator,
    EmployeeSearchRequestMapper,
    EmployeeSearchWireCodec,
    EmployeeSemanticSearchArgumentValidator,
    EmployeeSemanticSearchRequestMapper,
    EmployeeSemanticSearchWireCodec,
)
from agent_runtime.adapters.employee.contracts import (
    EmployeeDetailInput,
    EmployeeDetailRecord,
    EmployeeDetailWireRequest,
    EmployeeDetailWireResponse,
    EmployeeSearchInput,
    EmployeeSearchRecord,
    EmployeeSearchWireRequest,
    EmployeeSearchWireResponse,
    EmployeeSemanticSearchInput,
    EmployeeSemanticSearchWireRequest,
)
from agent_runtime.adapters.employee.fields import (
    employee_field_definitions,
    employee_search_field_definitions,
)
from agent_runtime.adapters.employee.normalizer import (
    EmployeeDetailResponseNormalizer,
    EmployeeSearchResponseNormalizer,
)


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
            description="查询单个员工的受控基础信息；不提供列表、聚合或写入。",
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
        query_fields=(
            BusinessQueryFieldDefinition(
                logical_name="employee_identifier",
                model_safe_description="当前请求中单一员工标识的受保护引用",
                value_type=BusinessQueryValueType.IDENTIFIER,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.PROTECTED_REF,
                required=True,
            ),
        ),
        combination_rules=(),
        code_contract_version="employee-detail-plan-v1",
        service_contract_ref="employee-detail-v1",
    )


def employee_search_definition(
    *,
    contract_version: str = "v3",
) -> BusinessActionDefinition[
    EmployeeSearchInput,
    EmployeeSearchWireRequest,
    EmployeeSearchWireResponse,
    EmployeeSearchRecord,
]:
    if contract_version == "v3":
        contract = business_query_v3_action_contract("employee.search")
    elif contract_version == "v2":
        contract = business_query_v2_action_contract("employee.search")
    else:
        raise ValueError("business.unknown_action_contract")
    return BusinessActionDefinition(
        descriptor=CapabilityDescriptor(
            capability_id=contract.action_id,
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Employee search",
            description="根据受控员工联系地点、姓名、标识或职位条件查询员工列表。",
            aliases=("员工条件查询", "employee search"),
            argument_schema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {
                                    "type": "string",
                                    "description": (
                                        "Scalar or bounded tuple after strict QueryPlan binding; "
                                        "the typed Business validator is authoritative."
                                    ),
                                },
                            },
                            "required": ("field", "operator", "value"),
                            "additionalProperties": False,
                        },
                    },
                    "page": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "size": {"type": "integer", "minimum": 1, "maximum": 50},
                    "sorts": {
                        "type": "array",
                        "maxItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "direction": {"type": "string", "enum": ("ASC", "DESC")},
                            },
                            "required": ("field", "direction"),
                            "additionalProperties": False,
                        },
                    },
                    "keyword": {"type": "string", "minLength": 1, "maxLength": 128},
                },
                "required": ("filters", "page", "size", "sorts"),
                "additionalProperties": False,
            },
        ),
        domain_id=contract.domain_id,
        service_key=contract.service_key,
        argument_validator=EmployeeSearchArgumentValidator(),
        request_mapper=EmployeeSearchRequestMapper(),
        wire_codec=EmployeeSearchWireCodec(),
        response_normalizer=EmployeeSearchResponseNormalizer(),
        http_status_semantics=BusinessHttpStatusSemantics(http_400_is_invalid_argument=True),
        applicable_dimensions=frozenset({
            ConstraintDimension.PAGE_SIZE,
            ConstraintDimension.RESULT_COUNT,
            ConstraintDimension.FILTER_FIELDS,
            ConstraintDimension.SORT_FIELDS,
        }),
        filter_field_ids_by_code=frozenset(
            field.logical_name for field in contract.query_fields
        ),
        sort_field_ids_by_code=contract.allowed_sort_fields,
        field_definitions=employee_search_field_definitions(),
        required_user_field_ids=("chinese_name", "employee_identifier"),
        answer_mode=BusinessAnswerMode.STRUCTURED_ONLY,
        contract_limits=BusinessContractLimits(
            max_page_size=contract.max_page_size,
            max_result_count=contract.max_result_count,
            max_time_range_days=None,
            max_timeout_ms=contract.max_timeout_ms,
            max_request_bytes=16384,
            allowed_sort_directions=frozenset({"ASC", "DESC"}),
            max_sort_items=2,
            max_page=contract.max_page,
        ),
        query_fields=contract.query_fields,
        combination_rules=(),
        code_contract_version=contract.code_contract_version,
        service_contract_ref=contract.service_contract_ref,
    )


def employee_semantic_search_definition() -> BusinessActionDefinition[
    EmployeeSemanticSearchInput,
    EmployeeSemanticSearchWireRequest,
    EmployeeSearchWireResponse,
    EmployeeSearchRecord,
]:
    contract = business_query_v2_action_contract("employee.semantic_search")
    return BusinessActionDefinition(
        descriptor=CapabilityDescriptor(
            capability_id=contract.action_id,
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Employee semantic search",
            description="依据非敏感员工专业能力语义描述查询员工列表。",
            aliases=("员工能力语义查询", "employee semantic search"),
            argument_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 256},
                    "size": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ("query", "size"),
                "additionalProperties": False,
            },
        ),
        domain_id=contract.domain_id,
        service_key=contract.service_key,
        argument_validator=EmployeeSemanticSearchArgumentValidator(),
        request_mapper=EmployeeSemanticSearchRequestMapper(),
        wire_codec=EmployeeSemanticSearchWireCodec(),
        response_normalizer=EmployeeSearchResponseNormalizer(),
        http_status_semantics=BusinessHttpStatusSemantics(http_400_is_invalid_argument=True),
        applicable_dimensions=frozenset({
            ConstraintDimension.PAGE_SIZE,
            ConstraintDimension.RESULT_COUNT,
        }),
        filter_field_ids_by_code=frozenset(),
        sort_field_ids_by_code=frozenset(),
        field_definitions=employee_search_field_definitions(),
        required_user_field_ids=("chinese_name", "employee_identifier"),
        answer_mode=BusinessAnswerMode.STRUCTURED_ONLY,
        contract_limits=BusinessContractLimits(
            max_page_size=contract.max_page_size,
            max_result_count=contract.max_result_count,
            max_time_range_days=None,
            max_timeout_ms=contract.max_timeout_ms,
            max_request_bytes=4096,
            fixed_page=1,
            max_page=contract.max_page,
        ),
        query_fields=contract.query_fields,
        combination_rules=(),
        code_contract_version=contract.code_contract_version,
        service_contract_ref=contract.service_contract_ref,
    )
