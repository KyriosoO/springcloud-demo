from __future__ import annotations

import re
import unicodedata

from agent_runtime.business.query_plan import InvalidProtectedValue, ProtectedValueSlots


_EMPLOYEE_MARKER = re.compile(r"(?:员工|employee)", re.IGNORECASE)
_IDENTIFIER = re.compile(
    r"(?:员工标识|员工编号|工号|身份证号|证件号|employee\s*id)"
    r"\s*(?:为|是|=|:|：)?\s*([^\s,，;；。？?]{5,64})",
    re.IGNORECASE,
)
_MEMBER_NO = re.compile(
    r"(?:会员编号|会员号|member\s*(?:number|no))"
    r"\s*(?:为|是|=|:|：)?\s*([^\s,，;；。？?]{5,64})",
    re.IGNORECASE,
)
_NAME = re.compile(
    r"(?:员工姓名|姓名|名叫)\s*(?:为|是|=|:|：)?\s*"
    r"([^\s,，;；。？?]{1,32})",
    re.IGNORECASE,
)
_PHONE = re.compile(
    r"(?:联系电话|手机号码|手机号|电话|phone)"
    r"\s*(?:为|是|=|:|：)?\s*(1[3-9]\d{9})(?!\d)",
    re.IGNORECASE,
)
_EMAIL = re.compile(
    r"(?:电子邮箱|邮箱|email)\s*(?:为|是|=|:|：)?\s*"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)
_DETAILED_ADDRESS = re.compile(
    r"(?:详细联系地址|联系地址|详细地址)"
    r"\s*(?:为|是|=|:|：)?\s*([^\s,，;；。？?]{4,128})",
    re.IGNORECASE,
)
_PROTECTED_PATTERNS = (
    ("employee_identifier", _IDENTIFIER),
    ("member_no", _MEMBER_NO),
    ("chinese_name", _NAME),
    ("phone_no", _PHONE),
    ("email", _EMAIL),
    ("contact_address", _DETAILED_ADDRESS),
)


class EmployeeProtectedValueExtractor:
    """Protects configured employee values without selecting a domain or action."""

    __slots__ = ()

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
        selected: list[tuple[int, int, str]] = []
        for kind, pattern in _PROTECTED_PATTERNS:
            matches = tuple(pattern.finditer(normalized))
            if len(matches) > 1:
                raise InvalidProtectedValue()
            if not matches:
                continue
            match = matches[0]
            value = match.group(1)
            if (
                not 1 <= len(value) <= 128
                or value != unicodedata.normalize("NFC", value)
                or any(unicodedata.category(character).startswith("C") for character in value)
                or kind in {"employee_identifier", "member_no"}
                and (
                    len(value) < 5
                    or any(character.isspace() or character in "/\\%?#" for character in value)
                )
            ):
                raise InvalidProtectedValue()
            selected.append((match.start(1), match.end(1), value))
        selected.sort(key=lambda item: item[0])
        if len(selected) > 8:
            raise InvalidProtectedValue()
        for previous, current in zip(selected, selected[1:], strict=False):
            if previous[1] > current[0]:
                raise InvalidProtectedValue()
        return ProtectedValueSlots(
            request_id=request_id,
            values={f"slot-{index}": value for index, (_, _, value) in enumerate(selected, 1)},
        )
