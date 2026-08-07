from __future__ import annotations

import unicodedata

from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolution,
    LocalActionResolutionKind,
)

_STRUCTURAL_SPACES = " \u3000"
_POLITE_TOKENS = ("请帮我", "请")
_INTENT_TOKENS = ("查询员工详情", "查看员工详情", "查询员工", "查看员工", "员工详情")
_LABEL_TOKENS = ("员工标识", "员工编号", "身份证号", "证件号")
_OPERATOR_TOKENS = ("为", "是", "=", ":", "：")
_TERMINATORS = frozenset({"。", "？", "?"})
_CLAUSE_SEPARATORS = frozenset({",", "，", ";", "；"})
_UNSUPPORTED_TAIL_TERMS = (
    "列表",
    "分页",
    "聚合",
    "合计",
    "创建",
    "写入",
    "更新",
    "修改",
    "删除",
    "审批",
)
_FORBIDDEN_BIDI = frozenset({"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"})


class EmployeeDetailLocalActionResolver:
    __slots__ = ()

    @property
    def capability_id(self) -> str:
        return "employee.detail"

    def resolve(self, question: str) -> LocalActionResolution:
        normalized = unicodedata.normalize("NFC", question).strip(_STRUCTURAL_SPACES)
        intent_end, malformed_prefix = _match_intent_prefix(normalized)
        if intent_end is None:
            return _no_match()
        if malformed_prefix or _contains_forbidden_unicode(normalized):
            return _invalid(LocalActionInvalidReason.MALFORMED_VALUE)

        position, overflow = _consume_structural_spaces(normalized, intent_end)
        if overflow:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        if position < len(normalized) and normalized[position] in {",", "，"}:
            position += 1
            position, overflow = _consume_structural_spaces(normalized, position)
            if overflow:
                return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)

        label = _match_longest(normalized, position, _LABEL_TOKENS)
        if label is None:
            reason = LocalActionInvalidReason.MISSING_REQUIRED if position == len(normalized) else LocalActionInvalidReason.UNSUPPORTED_CLAUSE
            return _invalid(reason)
        position += len(label)
        position, overflow = _consume_structural_spaces(normalized, position)
        if overflow:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)

        operator = _match_longest(normalized, position, _OPERATOR_TOKENS)
        if operator is None:
            reason = LocalActionInvalidReason.MISSING_REQUIRED if position == len(normalized) else LocalActionInvalidReason.UNSUPPORTED_CLAUSE
            return _invalid(reason)
        position += len(operator)
        position, overflow = _consume_structural_spaces(normalized, position)
        if overflow:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)

        value_text = normalized[position:]
        value_text, terminal_error = _remove_single_terminator(value_text)
        if terminal_error:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        value_text, overflow = _trim_structural_tail(value_text)
        if overflow:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        if not value_text:
            return _invalid(LocalActionInvalidReason.MISSING_REQUIRED)
        if _contains_second_labeled_argument(value_text):
            return _invalid(LocalActionInvalidReason.DUPLICATE_ARGUMENT)
        if (
            any(character in _CLAUSE_SEPARATORS | _TERMINATORS for character in value_text)
            or _contains_unsupported_tail(value_text)
        ):
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        return LocalActionResolution(
            kind=LocalActionResolutionKind.CANDIDATE,
            arguments={"employee_identifier": value_text},
        )


def _match_intent_prefix(text: str) -> tuple[int | None, bool]:
    direct = _match_longest(text, 0, _INTENT_TOKENS)
    if direct is not None:
        return len(direct), False

    polite = _match_longest(text, 0, _POLITE_TOKENS)
    if polite is None:
        return None, False
    position = len(polite)
    position, overflow = _consume_structural_spaces(text, position)
    if overflow:
        while position < len(text) and text[position] in _STRUCTURAL_SPACES:
            position += 1
        intent = _match_longest(text, position, _INTENT_TOKENS)
        return (position + len(intent), True) if intent is not None else (None, False)
    intent = _match_longest(text, position, _INTENT_TOKENS)
    return (position + len(intent), False) if intent is not None else (None, False)


def _match_longest(text: str, position: int, tokens: tuple[str, ...]) -> str | None:
    matches = (token for token in tokens if text.startswith(token, position))
    return max(matches, key=len, default=None)


def _consume_structural_spaces(text: str, position: int) -> tuple[int, bool]:
    start = position
    while position < len(text) and text[position] in _STRUCTURAL_SPACES:
        position += 1
    return position, position - start > 4


def _trim_structural_tail(text: str) -> tuple[str, bool]:
    end = len(text)
    while end > 0 and text[end - 1] in _STRUCTURAL_SPACES:
        end -= 1
    return text[:end], len(text) - end > 4


def _remove_single_terminator(text: str) -> tuple[str, bool]:
    if not text or text[-1] not in _TERMINATORS:
        return text, False
    remaining = text[:-1]
    without_spaces, _ = _trim_structural_tail(remaining)
    return remaining, bool(without_spaces and without_spaces[-1] in _TERMINATORS)


def _contains_second_labeled_argument(value: str) -> bool:
    for position in range(len(value)):
        label = _match_longest(value, position, _LABEL_TOKENS)
        if label is None:
            continue
        operator_position, overflow = _consume_structural_spaces(value, position + len(label))
        if not overflow and _match_longest(value, operator_position, _OPERATOR_TOKENS) is not None:
            return True
    return False


def _contains_unsupported_tail(value: str) -> bool:
    return any(
        marker + term in value
        for marker in (" ", "　", "并", "且", "然后")
        for term in _UNSUPPORTED_TAIL_TERMS
    )


def _contains_forbidden_unicode(text: str) -> bool:
    return any(
        unicodedata.category(character) == "Cc"
        or unicodedata.bidirectional(character) in _FORBIDDEN_BIDI
        for character in text
    )


def _no_match() -> LocalActionResolution:
    return LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)


def _invalid(reason: LocalActionInvalidReason) -> LocalActionResolution:
    return LocalActionResolution(kind=LocalActionResolutionKind.INVALID, reason=reason)
