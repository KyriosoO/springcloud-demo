from __future__ import annotations

from typing import cast

from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityKind, JsonObject
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessAnswerMode,
    BusinessContractLimits,
    BusinessDomainId,
    BusinessHttpStatusSemantics,
    BusinessServiceKey,
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
        argument_validator=TransactionSearchArgumentValidator(), request_mapper=TransactionSearchRequestMapper(),
        wire_codec=TransactionSearchWireCodec(), response_normalizer=TransactionSearchResponseNormalizer(),
        http_status_semantics=BusinessHttpStatusSemantics(http_400_is_invalid_argument=True),
        applicable_dimensions=frozenset({ConstraintDimension.PAGE_SIZE, ConstraintDimension.RESULT_COUNT, ConstraintDimension.FILTER_FIELDS, ConstraintDimension.SORT_FIELDS}),
        filter_field_ids_by_code=frozenset({"trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt"}),
        sort_field_ids_by_code=frozenset({"trans_id", "trans_type", "amount"}),
        field_definitions=transaction_field_definitions(), required_user_field_ids=("transaction_type", "amount"),
        answer_mode=BusinessAnswerMode.MODEL_ASSISTED,
        contract_limits=BusinessContractLimits(max_page_size=50, max_result_count=50, max_time_range_days=None, max_timeout_ms=5000, max_request_bytes=4096),
    )
