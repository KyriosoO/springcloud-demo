from __future__ import annotations

import unicodedata
from datetime import date, datetime
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from typing import Any

from agent_runtime.capability_api.contracts import JsonScalar
from agent_runtime.business.contracts import (
    BusinessFieldDefinition,
    BusinessFieldTransform,
    BusinessProjectionError,
)


def _safe_text(value: str, *, max_chars: int) -> str:
    normalized = unicodedata.normalize("NFC", value)
    forbidden_bidi = {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
    if not 1 <= len(normalized) <= max_chars or any(ord(character) < 32 or 0x7F <= ord(character) <= 0x9F or unicodedata.bidirectional(character) in forbidden_bidi for character in normalized):
        raise BusinessProjectionError("business.transform_failed")
    return normalized


class BusinessTransformRegistry:
    def __init__(self, *, max_text_value_chars: int = 256) -> None:
        self._max_text_value_chars = max_text_value_chars

    def apply(
        self,
        *,
        transform_id: BusinessFieldTransform,
        definition: BusinessFieldDefinition[Any, Any],
        value: Any,
    ) -> JsonScalar:
        allowed = definition.allowed_user_transforms | definition.allowed_model_transforms
        if transform_id not in allowed:
            raise BusinessProjectionError("business.transform_not_allowed")
        if transform_id is BusinessFieldTransform.IDENTITY_SCALAR:
            if type(value) is bool:
                return value
            if type(value) is int and abs(value) <= 2**53 - 1:
                return value
        elif transform_id is BusinessFieldTransform.BOUNDED_TEXT and type(value) is str:
            return _safe_text(value, max_chars=self._max_text_value_chars)
        elif transform_id is BusinessFieldTransform.MASK_KEEP_LAST4 and type(value) is str:
            normalized = _safe_text(value, max_chars=256)
            if len(normalized) >= 5:
                return _safe_text("***" + normalized[-4:], max_chars=self._max_text_value_chars)
        elif transform_id is BusinessFieldTransform.DATE_ONLY and type(value) in (date, datetime):
            result = value.date().isoformat() if type(value) is datetime else value.isoformat()
            return _safe_text(result, max_chars=self._max_text_value_chars)
        elif transform_id is BusinessFieldTransform.DECIMAL_2 and type(value) is Decimal and value.is_finite():
            try:
                result = format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
            except DecimalException as exc:
                raise BusinessProjectionError("business.transform_failed") from exc
            return _safe_text(result, max_chars=self._max_text_value_chars)
        elif transform_id is BusinessFieldTransform.ENUM_CODE and type(value) is str and value in definition.enum_values:
            return _safe_text(value, max_chars=self._max_text_value_chars)
        raise BusinessProjectionError("business.transform_failed")
