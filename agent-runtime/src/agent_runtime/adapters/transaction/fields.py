from __future__ import annotations

from typing import Any, Callable

from agent_runtime.business.contracts import (
    BusinessFieldDefinition,
    BusinessFieldTransform,
    BusinessFieldValueType,
    DataClass,
    business_query_v2_result_contracts,
)
from agent_runtime.adapters.transaction.contracts import TransactionListRecord, TransactionRecord


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


def transaction_list_field_definitions() -> tuple[
    BusinessFieldDefinition[TransactionListRecord, Any], ...
]:
    definitions: list[BusinessFieldDefinition[TransactionListRecord, Any]] = []
    for contract in business_query_v2_result_contracts("transaction.search"):
        model_transforms = (
            frozenset({contract.model_transform})
            if contract.model_transform is not None
            else frozenset()
        )
        definitions.append(
            BusinessFieldDefinition(
                field_id=contract.field_id,
                value_type=contract.value_type,
                data_class=contract.data_class,
                extractor=_transaction_list_extractor(contract.field_id),
                user_visible_by_code=True,
                model_candidate_by_code=contract.model_transform is not None,
                allowed_user_transforms=frozenset({contract.user_transform}),
                allowed_model_transforms=model_transforms,
            )
        )
    return tuple(definitions)


def _transaction_list_extractor(field_id: str) -> Callable[[TransactionListRecord], Any]:
    def extract(record: TransactionListRecord) -> Any:
        value = getattr(record, field_id)
        if field_id == "trans_id" and isinstance(value, str) and len(value) < 5:
            return None
        return value

    return extract
