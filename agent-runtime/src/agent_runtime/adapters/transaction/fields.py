from __future__ import annotations

from typing import Any

from agent_runtime.business.contracts import (
    BusinessFieldDefinition,
    BusinessFieldTransform,
    BusinessFieldValueType,
    DataClass,
)
from agent_runtime.adapters.transaction.contracts import TransactionRecord


def transaction_field_definitions() -> tuple[BusinessFieldDefinition[TransactionRecord, Any], ...]:
    masked = frozenset({BusinessFieldTransform.MASK_KEEP_LAST4})
    bounded = frozenset({BusinessFieldTransform.BOUNDED_TEXT})
    decimal = frozenset({BusinessFieldTransform.DECIMAL_2})
    return (
        BusinessFieldDefinition(
            field_id="transaction_id_masked", value_type=BusinessFieldValueType.IDENTIFIER,
            data_class=DataClass.TRANSACTION_IDENTIFIER,
            extractor=lambda record: record.trans_id if len(record.trans_id) >= 5 else None,
            user_visible_by_code=True, model_candidate_by_code=False,
            allowed_user_transforms=masked, allowed_model_transforms=frozenset(),
        ),
        BusinessFieldDefinition(
            field_id="transaction_type", value_type=BusinessFieldValueType.TEXT,
            data_class=DataClass.BUSINESS_INTERNAL, extractor=lambda record: record.trans_type,
            user_visible_by_code=True, model_candidate_by_code=True,
            allowed_user_transforms=bounded, allowed_model_transforms=bounded,
        ),
        BusinessFieldDefinition(
            field_id="amount", value_type=BusinessFieldValueType.DECIMAL,
            data_class=DataClass.FINANCIAL_VALUE, extractor=lambda record: record.amount,
            user_visible_by_code=True, model_candidate_by_code=True,
            allowed_user_transforms=decimal, allowed_model_transforms=decimal,
        ),
    )

