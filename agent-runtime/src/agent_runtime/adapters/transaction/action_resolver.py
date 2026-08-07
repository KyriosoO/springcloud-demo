from __future__ import annotations

import re
import unicodedata

from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolution,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import JsonValue

_STRUCTURAL_SPACES = " \u3000"
_POLITE_TOKENS = ("请帮我", "请")
_INTENT_TOKENS = ("查询交易记录", "交易记录查询", "查询交易", "交易查询")
_LABEL_TOKENS = ("交易标识", "交易类型", "交易号", "金额", "条数", "排序")
_EXACT_OPERATORS = ("为", "是", "=", ":", "：")
_AMOUNT_OPERATORS = ("大于", "小于", ">", "<", *_EXACT_OPERATORS)
_TERMINATORS = frozenset({"。", "？", "?"})
_CLAUSE_SEPARATORS = frozenset({",", "，", ";", "；"})
_FORBIDDEN_BIDI = frozenset({"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"})
_AMOUNT_PATTERN = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]{1,2})?$")
_MAX_AMOUNT_SCALED = 999999999999999999
_FILTER_KEYS = frozenset({"trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt"})
_SORT_FIELDS = {"交易号": "trans_id", "交易类型": "trans_type", "金额": "amount"}
_SORT_DIRECTIONS = {"升序": "ASC", "降序": "DESC"}
_BOOLEAN_EXPRESSION = re.compile(r"(?:^|\s)(?:or|not)(?:\s|$)", re.IGNORECASE)


class TransactionSearchLocalActionResolver:
    __slots__ = ()

    @property
    def capability_id(self) -> str:
        return "transaction.search"

    def resolve(self, question: str) -> LocalActionResolution:
        normalized = unicodedata.normalize("NFC", question).strip(_STRUCTURAL_SPACES)
        intent_end, malformed_prefix = _match_intent_prefix(normalized)
        if intent_end is None:
            return _no_match()
        if malformed_prefix or _contains_forbidden_unicode(normalized):
            return _invalid(LocalActionInvalidReason.MALFORMED_VALUE)

        body_start, space_count = _consume_structural_spaces(normalized, intent_end)
        if space_count > 4:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        if body_start < len(normalized) and normalized[body_start] in _CLAUSE_SEPARATORS:
            body_start += 1
            body_start, space_count = _consume_structural_spaces(normalized, body_start)
            if space_count > 4:
                return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        elif space_count == 0:
            return _invalid(LocalActionInvalidReason.MISSING_REQUIRED)

        body = normalized[body_start:]
        body, terminal_error = _remove_single_terminator(body)
        if terminal_error:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        body, overflow = _trim_structural_tail(body)
        if overflow:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        clauses = _split_clauses(body)
        if clauses is None:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
        if not clauses:
            return _invalid(LocalActionInvalidReason.MISSING_REQUIRED)
        if len(clauses) > 8:
            return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)

        arguments: dict[str, JsonValue] = {}
        sort_items: list[dict[str, JsonValue]] = []
        sort_fields: set[str] = set()
        amount_scaled: dict[str, int] = {}
        for raw_clause in clauses:
            clause, invalid_reason = _normalize_clause(raw_clause)
            if invalid_reason is not None:
                return _invalid(invalid_reason)
            parsed = _parse_clause(clause)
            if isinstance(parsed, LocalActionInvalidReason):
                return _invalid(parsed)
            key, value, scaled = parsed
            if key == "sorts":
                assert isinstance(value, dict)
                field = value["field"]
                assert isinstance(field, str)
                if field in sort_fields:
                    return _invalid(LocalActionInvalidReason.DUPLICATE_ARGUMENT)
                if len(sort_items) >= 2:
                    return _invalid(LocalActionInvalidReason.UNSUPPORTED_CLAUSE)
                sort_fields.add(field)
                sort_items.append(value)
                if "sorts" not in arguments:
                    arguments["sorts"] = ()
                arguments["sorts"] = tuple(sort_items)
                continue
            if key in arguments:
                return _invalid(LocalActionInvalidReason.DUPLICATE_ARGUMENT)
            arguments[key] = value
            if scaled is not None:
                amount_scaled[key] = scaled

        if "trans_type" in arguments and "trans_type_contains" in arguments:
            return _invalid(LocalActionInvalidReason.CONFLICTING_ARGUMENT)
        if "amount" in arguments and ({"amount_gt", "amount_lt"} & arguments.keys()):
            return _invalid(LocalActionInvalidReason.CONFLICTING_ARGUMENT)
        if (
            "amount_gt" in amount_scaled
            and "amount_lt" in amount_scaled
            and amount_scaled["amount_gt"] >= amount_scaled["amount_lt"]
        ):
            return _invalid(LocalActionInvalidReason.CONFLICTING_ARGUMENT)
        if not (_FILTER_KEYS & arguments.keys()):
            return _invalid(LocalActionInvalidReason.MISSING_REQUIRED)
        return LocalActionResolution(kind=LocalActionResolutionKind.CANDIDATE, arguments=arguments)


def _parse_clause(
    clause: str,
) -> tuple[str, JsonValue, int | None] | LocalActionInvalidReason:
    label = _match_longest(clause, 0, _LABEL_TOKENS)
    if label is None:
        return LocalActionInvalidReason.UNSUPPORTED_CLAUSE
    position = len(label)
    position, space_count = _consume_structural_spaces(clause, position)
    if space_count > 4:
        return LocalActionInvalidReason.UNSUPPORTED_CLAUSE

    operators = _AMOUNT_OPERATORS if label == "金额" else (("包含", *_EXACT_OPERATORS) if label == "交易类型" else _EXACT_OPERATORS)
    operator = _match_longest(clause, position, operators)
    if operator is None:
        return LocalActionInvalidReason.MISSING_REQUIRED if position == len(clause) else LocalActionInvalidReason.UNSUPPORTED_CLAUSE
    position += len(operator)
    position, space_count = _consume_structural_spaces(clause, position)
    if space_count > 4:
        return LocalActionInvalidReason.UNSUPPORTED_CLAUSE
    value = clause[position:]
    if not value:
        return LocalActionInvalidReason.MISSING_REQUIRED
    if _contains_unsupported_value_syntax(value):
        return LocalActionInvalidReason.UNSUPPORTED_CLAUSE

    if label in {"交易号", "交易标识"}:
        if operator not in _EXACT_OPERATORS:
            return LocalActionInvalidReason.UNSUPPORTED_CLAUSE
        return "trans_id", value, None
    if label == "交易类型":
        if operator == "包含":
            return "trans_type_contains", value, None
        if operator in _EXACT_OPERATORS:
            return "trans_type", value, None
        return LocalActionInvalidReason.UNSUPPORTED_CLAUSE
    if label == "金额":
        scaled = _canonical_amount_scaled(value)
        if scaled is None:
            return LocalActionInvalidReason.MALFORMED_VALUE
        if operator in _EXACT_OPERATORS:
            return "amount", value, scaled
        if operator in {"大于", ">"}:
            return "amount_gt", value, scaled
        if operator in {"小于", "<"}:
            return "amount_lt", value, scaled
        return LocalActionInvalidReason.UNSUPPORTED_CLAUSE
    if label == "条数":
        if operator not in _EXACT_OPERATORS or not value.isascii() or not value.isdecimal():
            return LocalActionInvalidReason.MALFORMED_VALUE
        if value != str(int(value)) or not 1 <= int(value) <= 50:
            return LocalActionInvalidReason.MALFORMED_VALUE
        return "size", int(value), None
    if label == "排序":
        if operator not in _EXACT_OPERATORS:
            return LocalActionInvalidReason.UNSUPPORTED_CLAUSE
        sort = _parse_sort(value)
        if sort is None:
            return LocalActionInvalidReason.MALFORMED_VALUE
        return "sorts", sort, None
    return LocalActionInvalidReason.UNSUPPORTED_CLAUSE


def _parse_sort(value: str) -> dict[str, JsonValue] | None:
    field_token = _match_longest(value, 0, tuple(_SORT_FIELDS))
    if field_token is None:
        return None
    position, space_count = _consume_structural_spaces(value, len(field_token))
    if space_count > 4:
        return None
    direction_token = _match_longest(value, position, tuple(_SORT_DIRECTIONS))
    if direction_token is None or position + len(direction_token) != len(value):
        return None
    return {"field": _SORT_FIELDS[field_token], "direction": _SORT_DIRECTIONS[direction_token]}


def _canonical_amount_scaled(value: str) -> int | None:
    match = _AMOUNT_PATTERN.fullmatch(value)
    if match is None:
        return None
    unsigned = value[1:] if value.startswith("-") else value
    integer, separator, fraction = unsigned.partition(".")
    scaled = int(integer) * 100 + int((fraction if separator else "").ljust(2, "0") or "0")
    if scaled > _MAX_AMOUNT_SCALED:
        return None
    return -scaled if value.startswith("-") else scaled


def _contains_unsupported_value_syntax(value: str) -> bool:
    return (
        any(character in "()（）" or character in _TERMINATORS for character in value)
        or _BOOLEAN_EXPRESSION.search(value) is not None
    )


def _split_clauses(body: str) -> tuple[str, ...] | None:
    if not body:
        return ()
    clauses: list[str] = []
    start = 0
    for position, character in enumerate(body):
        if character not in _CLAUSE_SEPARATORS:
            continue
        clauses.append(body[start:position])
        start = position + 1
    clauses.append(body[start:])
    if any(not clause for clause in clauses):
        return None
    return tuple(clauses)


def _normalize_clause(clause: str) -> tuple[str, LocalActionInvalidReason | None]:
    start = 0
    while start < len(clause) and clause[start] in _STRUCTURAL_SPACES:
        start += 1
    end = len(clause)
    while end > start and clause[end - 1] in _STRUCTURAL_SPACES:
        end -= 1
    if start > 4 or len(clause) - end > 4:
        return "", LocalActionInvalidReason.UNSUPPORTED_CLAUSE
    normalized = clause[start:end]
    if not normalized:
        return "", LocalActionInvalidReason.MISSING_REQUIRED
    return normalized, None


def _match_intent_prefix(text: str) -> tuple[int | None, bool]:
    direct = _match_longest(text, 0, _INTENT_TOKENS)
    if direct is not None:
        return len(direct), False
    polite = _match_longest(text, 0, _POLITE_TOKENS)
    if polite is None:
        return None, False
    position = len(polite)
    position, space_count = _consume_structural_spaces(text, position)
    intent = _match_longest(text, position, _INTENT_TOKENS)
    if intent is None:
        return None, False
    return position + len(intent), space_count > 4


def _match_longest(text: str, position: int, tokens: tuple[str, ...]) -> str | None:
    matches = (token for token in tokens if text.startswith(token, position))
    return max(matches, key=len, default=None)


def _consume_structural_spaces(text: str, position: int) -> tuple[int, int]:
    start = position
    while position < len(text) and text[position] in _STRUCTURAL_SPACES:
        position += 1
    return position, position - start


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
