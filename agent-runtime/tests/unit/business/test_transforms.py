from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from agent_runtime.business.contracts import (
    BusinessFieldDefinition,
    BusinessFieldTransform,
    BusinessFieldValueType,
    BusinessProjectionError,
    DataClass,
)
from agent_runtime.business.transforms import BusinessTransformRegistry


@dataclass(frozen=True)
class Record:
    value: object


def _definition(*transforms: BusinessFieldTransform) -> BusinessFieldDefinition[Record, object]:
    return BusinessFieldDefinition(
        field_id="value", value_type=BusinessFieldValueType.TEXT, data_class=DataClass.BUSINESS_INTERNAL,
        extractor=lambda record: record.value, user_visible_by_code=True, model_candidate_by_code=True,
        allowed_user_transforms=frozenset(transforms), allowed_model_transforms=frozenset(transforms),
    )


def test_finite_transforms_are_deterministic() -> None:
    registry = BusinessTransformRegistry()
    assert registry.apply(transform_id=BusinessFieldTransform.MASK_KEEP_LAST4, definition=_definition(BusinessFieldTransform.MASK_KEEP_LAST4), value="ABCDEF") == "***CDEF"
    assert registry.apply(transform_id=BusinessFieldTransform.DECIMAL_2, definition=_definition(BusinessFieldTransform.DECIMAL_2), value=Decimal("1.235")) == "1.24"
    assert registry.apply(transform_id=BusinessFieldTransform.MASK_NAME, definition=_definition(BusinessFieldTransform.MASK_NAME), value="张三") == "张***"
    assert registry.apply(transform_id=BusinessFieldTransform.MASK_ADDRESS, definition=_definition(BusinessFieldTransform.MASK_ADDRESS), value="上海市浦东新区") == "上海***"
    assert registry.apply(transform_id=BusinessFieldTransform.MASK_CONTACT, definition=_definition(BusinessFieldTransform.MASK_CONTACT), value="13800138000") == "1***"


def test_transform_rejects_wrong_type_without_coercion() -> None:
    with pytest.raises(BusinessProjectionError):
        BusinessTransformRegistry().apply(
            transform_id=BusinessFieldTransform.DECIMAL_2,
            definition=_definition(BusinessFieldTransform.DECIMAL_2),
            value="1.23",
        )
