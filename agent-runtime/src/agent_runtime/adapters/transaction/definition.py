from __future__ import annotations

from typing import cast

from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityKind, JsonObject
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessAnswerMode,
    BusinessCombinationRule,
    BusinessCombinationRuleKind,
    BusinessContractLimits,
    BusinessDomainId,
    BusinessHttpStatusSemantics,
    BusinessInputExposure,
    BusinessQueryFieldDefinition,
    BusinessQueryOperator,
    BusinessQueryValueType,
    BusinessServiceKey,
    BusinessTextPolicyId,
    ConstraintDimension,
)
from agent_runtime.adapters.transaction.codec import (
    TransactionSearchArgumentValidator,
    TransactionSearchRequestMapper,
    TransactionSearchWireCodec,
)
from agent_runtime.adapters.transaction.contracts import (
    TransactionRecord,
    TransactionSearchInput,
    TransactionSearchWireRequest,
    TransactionSearchWireResponse,
)
from agent_runtime.adapters.transaction.fields import transaction_field_definitions
from agent_runtime.adapters.transaction.normalizer import TransactionSearchResponseNormalizer


def transaction_search_definition() -> BusinessActionDefinition[
    TransactionSearchInput,
    TransactionSearchWireRequest,
    TransactionSearchWireResponse,
    TransactionRecord,
]:
    properties = {
        "trans_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "trans_type": {"type": "string", "minLength": 1, "maxLength": 128},
        "trans_type_contains": {"type": "string", "minLength": 1, "maxLength": 128},
        "amount": {"type": "string", "minLength": 1, "maxLength": 32},
        "amount_gt": {"type": "string", "minLength": 1, "maxLength": 32},
        "amount_lt": {"type": "string", "minLength": 1, "maxLength": 32},
        "size": {"type": "integer", "minimum": 1, "maximum": 50},
        "sorts": {
            "type": "array", "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": ("trans_id", "trans_type", "amount")},
                    "direction": {"type": "string", "enum": ("ASC", "DESC")},
                },
                "required": ("field", "direction"), "additionalProperties": False,
            },
        },
    }
    return BusinessActionDefinition(
        descriptor=CapabilityDescriptor(
            capability_id="transaction.search", api_version=1, kind=CapabilityKind.QUERY,
            display_name="Transaction search",
            description="按交易标识、交易类型或精确金额条件查询第一页受控交易记录；不提供日期条件、聚合或写入。",
            aliases=("交易查询", "transaction lookup"),
            argument_schema=cast(
                JsonObject,
                {"type": "object", "properties": properties, "additionalProperties": False},
            ),
        ),
        domain_id=BusinessDomainId("transaction"), service_key=BusinessServiceKey("mq-procedure-service"),
        argument_validator=TransactionSearchArgumentValidator(),
        request_mapper=TransactionSearchRequestMapper(),
        wire_codec=TransactionSearchWireCodec(), response_normalizer=TransactionSearchResponseNormalizer(),
        http_status_semantics=BusinessHttpStatusSemantics(http_400_is_invalid_argument=True),
        applicable_dimensions=frozenset({ConstraintDimension.PAGE_SIZE, ConstraintDimension.RESULT_COUNT, ConstraintDimension.FILTER_FIELDS, ConstraintDimension.SORT_FIELDS}),
        filter_field_ids_by_code=frozenset({"trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt"}),
        sort_field_ids_by_code=frozenset({"trans_id", "trans_type", "amount"}),
        field_definitions=transaction_field_definitions(), required_user_field_ids=("transaction_type", "amount"),
        answer_mode=BusinessAnswerMode.MODEL_ASSISTED,
        contract_limits=BusinessContractLimits(
            max_page_size=50,
            max_result_count=50,
            max_time_range_days=None,
            max_timeout_ms=5000,
            max_request_bytes=4096,
            max_decimal_abs="9999999999999999.99",
            max_decimal_scale=2,
            fixed_page=1,
            allowed_sort_directions=frozenset({"ASC", "DESC"}),
            max_sort_items=2,
        ),
        query_fields=(
            BusinessQueryFieldDefinition(
                logical_name="trans_id",
                model_safe_description="当前请求中单一交易标识的受保护引用",
                value_type=BusinessQueryValueType.IDENTIFIER,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.PROTECTED_REF,
                required=False,
            ),
            BusinessQueryFieldDefinition(
                logical_name="trans_type",
                model_safe_description="交易类型的精确匹配值",
                value_type=BusinessQueryValueType.TEXT,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                max_text_chars=128,
                text_policy_id=BusinessTextPolicyId.SAFE_TOKEN,
            ),
            BusinessQueryFieldDefinition(
                logical_name="trans_type_contains",
                model_safe_description="交易类型的包含匹配值",
                value_type=BusinessQueryValueType.TEXT,
                allowed_operators=frozenset({BusinessQueryOperator.CONTAINS}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                max_text_chars=128,
                text_policy_id=BusinessTextPolicyId.SAFE_CONTAINS_TOKEN,
            ),
            BusinessQueryFieldDefinition(
                logical_name="amount",
                model_safe_description="交易金额的精确十进制值",
                value_type=BusinessQueryValueType.DECIMAL,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                allow_negative=True,
            ),
            BusinessQueryFieldDefinition(
                logical_name="amount_gt",
                model_safe_description="交易金额的严格下界十进制值",
                value_type=BusinessQueryValueType.DECIMAL,
                allowed_operators=frozenset({BusinessQueryOperator.GT}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                allow_negative=True,
            ),
            BusinessQueryFieldDefinition(
                logical_name="amount_lt",
                model_safe_description="交易金额的严格上界十进制值",
                value_type=BusinessQueryValueType.DECIMAL,
                allowed_operators=frozenset({BusinessQueryOperator.LT}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                allow_negative=True,
            ),
            BusinessQueryFieldDefinition(
                logical_name="size",
                model_safe_description="第一页最多返回的记录条数",
                value_type=BusinessQueryValueType.INTEGER,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                minimum_integer=1,
                maximum_integer=50,
            ),
            BusinessQueryFieldDefinition(
                logical_name="sorts",
                model_safe_description="结果的有限排序列表",
                value_type=BusinessQueryValueType.SORT_LIST,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
            ),
        ),
        combination_rules=(
            BusinessCombinationRule(
                rule_id="transaction-filter-at-least-one",
                kind=BusinessCombinationRuleKind.AT_LEAST_ONE,
                field_names=("trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt"),
            ),
            BusinessCombinationRule(
                rule_id="transaction-type-mutually-exclusive",
                kind=BusinessCombinationRuleKind.MUTUALLY_EXCLUSIVE,
                field_names=("trans_type", "trans_type_contains"),
            ),
            BusinessCombinationRule(
                rule_id="transaction-amount-exact-vs-gt",
                kind=BusinessCombinationRuleKind.MUTUALLY_EXCLUSIVE,
                field_names=("amount", "amount_gt"),
            ),
            BusinessCombinationRule(
                rule_id="transaction-amount-exact-vs-lt",
                kind=BusinessCombinationRuleKind.MUTUALLY_EXCLUSIVE,
                field_names=("amount", "amount_lt"),
            ),
        ),
        code_contract_version="transaction-search-plan-v1",
        service_contract_ref="transaction-search-v1",
    )
