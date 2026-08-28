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

_COMPOUND_SURNAMES = (
    "欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙",
    "慕容", "令狐", "宇文", "长孙", "司徒", "司空", "夏侯", "南宫",
)
_SURNAME_TOKEN = rf"(?:{'|'.join(_COMPOUND_SURNAMES)}|[\u4e00-\u9fff])"
_SURNAME_PREFIX = re.compile(
    rf"(?:^|帮我查询|帮我找|请查一下|查询|查找|查一下|找一下|是否有|有没有|有|且|或|、|，|,|\s)"
    rf"姓(?!名)(?:氏)?\s*(?:为|是|=|:|：)?\s*(?P<value>{_SURNAME_TOKEN})"
)
_SURNAME_SUFFIX = re.compile(
    rf"(?P<value>{_SURNAME_TOKEN})姓(?!名)(?=(?:员工|、|，|,|或|和|的|$))"
)
_NAME_FRAGMENT = re.compile(
    r"(?:员工姓名|姓名|名字)(?:中)?\s*(?:包含|含有)\s*[“\"]?"
    r"(?P<value>[\u4e00-\u9fff]{1,4}?)[”\"]?"
    r"(?=\s*(?:的?员工|的?[。？?]|的?$|[。？?]|$))"
)
_NAME_LIST = re.compile(
    r"(?:员工姓名|姓名|名叫)(?!\s*中?\s*(?:包含|含有))\s*(?:为|是|=|:|：)?\s*"
    r"(?P<values>[\u4e00-\u9fff]{1,4}?(?:\s*(?:或|、|,|，|和)\s*[\u4e00-\u9fff]{1,4}?)*?)"
    r"(?=\s*(?:的?员工|的?[。？?]|的?$|[。？?]|$))"
)
_TRAILING_NAME_LIST = re.compile(
    r"(?:帮我找|请查一下|查询|查找|查一下|找一下)\s*"
    r"(?P<values>[\u4e00-\u9fff]{2,4}?(?:\s*(?:或|、|,|，|和)\s*[\u4e00-\u9fff]{2,4}?)+?)"
    r"\s*(?:这几名|这些)?员工"
)
_NAME_SEPARATOR = re.compile(r"\s*(?:或|、|,|，|和)\s*")

_SINGLE_VALUE_PATTERNS = (
    ("employee_identifier", _IDENTIFIER),
    ("member_no", _MEMBER_NO),
    ("phone_no", _PHONE),
    ("email", _EMAIL),
    ("contact_address", _DETAILED_ADDRESS),
)


class EmployeeProtectedValueExtractor:
    """Extracts opaque values only; it never selects an action, operator, or filter."""

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
        if normalized != question or any(
            unicodedata.category(character).startswith("C") for character in normalized
        ):
            raise InvalidProtectedValue()

        selected: list[tuple[int, int, str, str]] = []
        for logical_field, pattern in _SINGLE_VALUE_PATTERNS:
            matches = tuple(pattern.finditer(normalized))
            if len(matches) > 1:
                raise InvalidProtectedValue()
            if matches:
                match = matches[0]
                selected.append(
                    (match.start(1), match.end(1), match.group(1), logical_field)
                )

        for pattern in (_SURNAME_PREFIX, _SURNAME_SUFFIX, _NAME_FRAGMENT):
            for match in pattern.finditer(normalized):
                selected.append(
                    (
                        match.start("value"),
                        match.end("value"),
                        match.group("value"),
                        "chinese_name",
                    )
                )

        for pattern in (_NAME_LIST, _TRAILING_NAME_LIST):
            for match in pattern.finditer(normalized):
                raw_values = match.group("values")
                if pattern is _TRAILING_NAME_LIST and any(
                    marker in raw_values for marker in ("姓", "的")
                ):
                    continue
                offset = match.start("values")
                for relative_start, relative_end, value in _name_value_spans(raw_values):
                    selected.append(
                        (
                            offset + relative_start,
                            offset + relative_end,
                            value,
                            "chinese_name",
                        )
                    )

        if _EMPLOYEE_MARKER.search(normalized) is None and not any(
            item[3] == "chinese_name" for item in selected
        ):
            return ProtectedValueSlots(request_id=request_id, values={})

        unique_by_span: dict[tuple[int, int], tuple[int, int, str, str]] = {}
        for item in selected:
            existing = unique_by_span.get((item[0], item[1]))
            if existing is not None and existing[2:] != item[2:]:
                raise InvalidProtectedValue()
            unique_by_span[(item[0], item[1])] = item
        ordered = sorted(unique_by_span.values(), key=lambda item: (item[0], item[1]))
        if not 0 <= len(ordered) <= 16:
            raise InvalidProtectedValue()
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if previous[1] > current[0]:
                raise InvalidProtectedValue()
        if len({item[2] for item in ordered}) != len(ordered):
            raise InvalidProtectedValue()
        for _, _, value, logical_field in ordered:
            if not _valid_value(value, logical_field=logical_field):
                raise InvalidProtectedValue()

        values = {
            f"slot-{index}": value
            for index, (_, _, value, _) in enumerate(ordered, 1)
        }
        logical_fields = {
            f"slot-{index}": logical_field
            for index, (_, _, _, logical_field) in enumerate(ordered, 1)
        }
        return ProtectedValueSlots(
            request_id=request_id,
            values=values,
            logical_fields=logical_fields,
        )


def _valid_value(value: str, *, logical_field: str) -> bool:
    if (
        not 1 <= len(value) <= 128
        or value != unicodedata.normalize("NFC", value)
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        return False
    if logical_field in {"employee_identifier", "member_no"}:
        return len(value) >= 5 and not any(
            character.isspace() or character in "/\\%?#" for character in value
        )
    if logical_field == "chinese_name":
        return bool(
            re.fullmatch(r"[\u4e00-\u9fff]{1,4}", value)
            and value not in {"姓名", "员工", "姓氏", "包含", "含有"}
        )
    return True


def _name_value_spans(raw_values: str) -> tuple[tuple[int, int, str], ...]:
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for separator in _NAME_SEPARATOR.finditer(raw_values):
        start = cursor
        end = separator.start()
        while start < end and raw_values[start].isspace():
            start += 1
        while end > start and raw_values[end - 1].isspace():
            end -= 1
        if start == end:
            raise InvalidProtectedValue()
        spans.append((start, end, raw_values[start:end]))
        cursor = separator.end()
    start = cursor
    end = len(raw_values)
    while start < end and raw_values[start].isspace():
        start += 1
    while end > start and raw_values[end - 1].isspace():
        end -= 1
    if start == end:
        raise InvalidProtectedValue()
    spans.append((start, end, raw_values[start:end]))
    return tuple(spans)
