from __future__ import annotations

import re
import unicodedata

from agent_runtime.adapters.transaction.codec import TransactionListSearchArgumentValidator
from agent_runtime.business.query_plan import InvalidProtectedValue, ProtectedValueSlots
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments


_TRANSACTION_MARKER = re.compile(r"(?:交易|transaction)", re.IGNORECASE)
_IDENTIFIER = re.compile(
    r"(?:交易标识|交易号|流水号|transaction\s*id)"
    r"\s*(?:为|是|=|:|：)?\s*([^\s,，;；。？?]{1,128})",
    re.IGNORECASE,
)


class TransactionProtectedValueExtractor:
    """Extracts one request-local transaction identifier without planning an action."""

    __slots__ = ("_validator",)

    def __init__(self) -> None:
        self._validator = TransactionListSearchArgumentValidator()

    def extract(self, question: str, *, request_id: str) -> ProtectedValueSlots:
        if (
            not isinstance(question, str)
            or not question
            or len(question) > 4096
            or not isinstance(request_id, str)
            or not request_id
        ):
            raise InvalidProtectedValue()
        normalized = unicodedata.normalize("NFC", question)
        if any(unicodedata.category(character) == "Cc" for character in normalized):
            raise InvalidProtectedValue()
        if _TRANSACTION_MARKER.search(normalized) is None:
            return ProtectedValueSlots(request_id=request_id, values={})
        matches = tuple(_IDENTIFIER.finditer(normalized))
        if not matches:
            return ProtectedValueSlots(request_id=request_id, values={})
        if len(matches) != 1:
            raise InvalidProtectedValue()
        raw = matches[0].group(1)
        try:
            validated = self._validator.validate(
                {
                    "filters": ({"field": "trans_id", "operator": "eq", "value": raw},),
                    "page": 1,
                    "size": 1,
                    "sorts": (),
                }
            )
        except InvalidCapabilityArguments as exc:
            raise InvalidProtectedValue() from exc
        identifier = validated.filters[0].value
        if not isinstance(identifier, str):
            raise InvalidProtectedValue()
        return ProtectedValueSlots(
            request_id=request_id,
            values={"slot-1": identifier},
        )
