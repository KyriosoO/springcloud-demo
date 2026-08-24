from __future__ import annotations

import re
import unicodedata

from agent_runtime.adapters.employee.codec import EmployeeDetailArgumentValidator
from agent_runtime.business.query_plan import InvalidProtectedValue, ProtectedValueSlots
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments


_EMPLOYEE_MARKER = re.compile(r"(?:员工|employee)", re.IGNORECASE)
_IDENTIFIER = re.compile(
    r"(?:员工标识|员工编号|工号|身份证号|证件号|employee\s*id)"
    r"\s*(?:为|是|=|:|：)?\s*([^\s,，;；。？?]{5,64})",
    re.IGNORECASE,
)


class EmployeeProtectedValueExtractor:
    """Extracts one request-local identifier without selecting an action or domain."""

    __slots__ = ("_validator",)

    def __init__(self) -> None:
        self._validator = EmployeeDetailArgumentValidator()

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
        if _EMPLOYEE_MARKER.search(normalized) is None:
            return ProtectedValueSlots(request_id=request_id, values={})
        matches = tuple(_IDENTIFIER.finditer(normalized))
        if not matches:
            return ProtectedValueSlots(request_id=request_id, values={})
        if len(matches) != 1:
            raise InvalidProtectedValue()
        raw = matches[0].group(1)
        try:
            validated = self._validator.validate({"employee_identifier": raw})
        except InvalidCapabilityArguments as exc:
            raise InvalidProtectedValue() from exc
        return ProtectedValueSlots(
            request_id=request_id,
            values={"slot-1": validated.employee_identifier},
        )
