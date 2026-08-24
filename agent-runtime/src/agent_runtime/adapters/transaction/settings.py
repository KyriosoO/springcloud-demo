from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Self

from agent_runtime.business.contracts import (
    BusinessActionSettings,
    BusinessFieldTransform,
    BusinessQueryFieldSettings,
    BusinessQueryOperator,
    FieldTransformSelection,
)

_PREFIX = "AGENT_TRANSACTION_SEARCH_"
_FILTERS = ("trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt")
_SORTS = ("trans_id", "trans_type", "amount")
_FIELDS = ("transaction_id_masked", "transaction_type", "amount")
_MODEL_FIELDS = frozenset({"transaction_type", "amount"})
_SORT_DIRECTIONS = ("ASC", "DESC")
_TRANSFORMS = {
    "transaction_id_masked": BusinessFieldTransform.MASK_KEEP_LAST4,
    "transaction_type": BusinessFieldTransform.BOUNDED_TEXT,
    "amount": BusinessFieldTransform.DECIMAL_2,
}
_KNOWN = frozenset({
    _PREFIX + "ENABLED", _PREFIX + "TIMEOUT_MS", _PREFIX + "MAX_PAGE_SIZE", _PREFIX + "MAX_RESULT_COUNT",
    _PREFIX + "FILTER_FIELDS", _PREFIX + "SORT_FIELDS", _PREFIX + "USER_FIELDS", _PREFIX + "MODEL_FIELDS",
    _PREFIX + "USER_TRANSFORMS", _PREFIX + "MODEL_TRANSFORMS",
    _PREFIX + "CONFIG_VERSION", _PREFIX + "CODE_CONTRACT_VERSION", _PREFIX + "SERVICE_CONTRACT_REF",
    _PREFIX + "MAX_DECIMAL_ABS", _PREFIX + "MAX_DECIMAL_SCALE", _PREFIX + "FIXED_PAGE",
    _PREFIX + "SORT_DIRECTIONS", _PREFIX + "MAX_SORT_ITEMS",
})
_CONFIG_VERSION = "transaction-search-config-v1"
_CODE_CONTRACT_VERSION = "transaction-search-plan-v1"
_SERVICE_CONTRACT_REF = "transaction-search-v1"
_MAX_DECIMAL_ABS = "9999999999999999.99"
_VERSION = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_DECIMAL_LIMIT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_QUERY_FIELDS = (
    ("trans_id", "当前请求中单一交易标识的受保护引用", BusinessQueryOperator.EQ, None),
    ("trans_type", "交易类型的精确匹配值", BusinessQueryOperator.EQ, 128),
    ("trans_type_contains", "交易类型的包含匹配值", BusinessQueryOperator.CONTAINS, 128),
    ("amount", "交易金额的精确十进制值", BusinessQueryOperator.EQ, None),
    ("amount_gt", "交易金额的严格下界十进制值", BusinessQueryOperator.GT, None),
    ("amount_lt", "交易金额的严格上界十进制值", BusinessQueryOperator.LT, None),
    ("size", "第一页最多返回的记录条数", BusinessQueryOperator.EQ, None),
    ("sorts", "结果的有限排序列表", BusinessQueryOperator.EQ, None),
)
_COMBINATION_RULE_IDS = (
    "transaction-filter-at-least-one",
    "transaction-type-mutually-exclusive",
    "transaction-amount-exact-vs-gt",
    "transaction-amount-exact-vs-lt",
)


def _boolean(raw: str | None) -> bool:
    if raw is None or raw == "false": return False
    if raw == "true": return True
    raise ValueError("business.transaction_settings_invalid")


def _integer(raw: str | None, default: int) -> int:
    value = str(default) if raw is None else raw
    if not value or not value.isascii() or not value.isdecimal() or value != str(int(value)):
        raise ValueError("business.transaction_settings_invalid")
    return int(value)


def _version(raw: str | None, default: str) -> str:
    value = default if raw is None else raw
    if _VERSION.fullmatch(value) is None:
        raise ValueError("business.transaction_settings_invalid")
    return value


def _decimal_limit(raw: str | None) -> str:
    value = _MAX_DECIMAL_ABS if raw is None else raw
    try:
        decimal_value = Decimal(value)
        code_limit = Decimal(_MAX_DECIMAL_ABS)
    except InvalidOperation as exc:
        raise ValueError("business.transaction_settings_invalid") from exc
    if (
        _DECIMAL_LIMIT.fullmatch(value) is None
        or decimal_value <= 0
        or decimal_value > code_limit
    ):
        raise ValueError("business.transaction_settings_invalid")
    return value


def _subset(raw: str, ordered: tuple[str, ...], *, allow_empty: bool) -> tuple[str, ...]:
    if raw == "":
        if allow_empty: return ()
        raise ValueError("business.transaction_settings_invalid")
    items = tuple(raw.split(","))
    if len(items) != len(set(items)) or any(item not in ordered for item in items):
        raise ValueError("business.transaction_settings_invalid")
    return tuple(item for item in ordered if item in items)


def _selected_transforms(raw: str | None, fields: tuple[str, ...]) -> tuple[FieldTransformSelection, ...]:
    if raw is None:
        return tuple(FieldTransformSelection(field_id=field, transform_id=_TRANSFORMS[field]) for field in fields)
    parsed: dict[str, BusinessFieldTransform] = {}
    if raw:
        for item in raw.split(","):
            parts = item.split(":")
            if len(parts) != 2 or parts[0] in parsed:
                raise ValueError("business.transaction_settings_invalid")
            try:
                parsed[parts[0]] = BusinessFieldTransform(parts[1])
            except ValueError as exc:
                raise ValueError("business.transaction_settings_invalid") from exc
    if set(parsed) != set(fields) or any(parsed[field] is not _TRANSFORMS[field] for field in fields):
        raise ValueError("business.transaction_settings_invalid")
    return tuple(FieldTransformSelection(field_id=field, transform_id=parsed[field]) for field in fields)


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionAdapterSettings:
    action: BusinessActionSettings

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Self:
        if any(key.startswith(_PREFIX) and key not in _KNOWN for key in env):
            raise ValueError("business.transaction_settings_unknown_key")
        timeout = _integer(env.get(_PREFIX + "TIMEOUT_MS"), 3000)
        max_page = _integer(env.get(_PREFIX + "MAX_PAGE_SIZE"), 20)
        max_results = _integer(env.get(_PREFIX + "MAX_RESULT_COUNT"), 20)
        max_decimal_abs = _decimal_limit(env.get(_PREFIX + "MAX_DECIMAL_ABS"))
        max_decimal_scale = _integer(env.get(_PREFIX + "MAX_DECIMAL_SCALE"), 2)
        fixed_page = _integer(env.get(_PREFIX + "FIXED_PAGE"), 1)
        max_sort_items = _integer(env.get(_PREFIX + "MAX_SORT_ITEMS"), 2)
        if not 100 <= timeout <= 5000 or not 1 <= max_page <= 50 or not 1 <= max_results <= 50:
            raise ValueError("business.transaction_settings_invalid")
        if not 0 <= max_decimal_scale <= 2 or fixed_page != 1 or not 0 <= max_sort_items <= 2:
            raise ValueError("business.transaction_settings_invalid")
        filters = _subset(env.get(_PREFIX + "FILTER_FIELDS", ",".join(_FILTERS)), _FILTERS, allow_empty=False)
        sorts = _subset(env.get(_PREFIX + "SORT_FIELDS", ",".join(_SORTS)), _SORTS, allow_empty=True)
        sort_directions = _subset(
            env.get(_PREFIX + "SORT_DIRECTIONS", ",".join(_SORT_DIRECTIONS)),
            _SORT_DIRECTIONS,
            allow_empty=False,
        )
        user_fields = _subset(env.get(_PREFIX + "USER_FIELDS", ",".join(_FIELDS)), _FIELDS, allow_empty=False)
        if not {"transaction_type", "amount"}.issubset(user_fields):
            raise ValueError("business.transaction_settings_invalid")
        model_fields = _subset(env.get(_PREFIX + "MODEL_FIELDS", ""), _FIELDS, allow_empty=True)
        if not set(model_fields).issubset(_MODEL_FIELDS & set(user_fields)):
            raise ValueError("business.transaction_settings_invalid")
        config_version = _version(env.get(_PREFIX + "CONFIG_VERSION"), _CONFIG_VERSION)
        code_contract_version = _version(env.get(_PREFIX + "CODE_CONTRACT_VERSION"), _CODE_CONTRACT_VERSION)
        service_contract_ref = _version(env.get(_PREFIX + "SERVICE_CONTRACT_REF"), _SERVICE_CONTRACT_REF)
        if code_contract_version != _CODE_CONTRACT_VERSION or service_contract_ref != _SERVICE_CONTRACT_REF:
            raise ValueError("business.transaction_settings_invalid")
        return cls(action=BusinessActionSettings(
            enabled=_boolean(env.get(_PREFIX + "ENABLED")),
            max_page_size=max_page, max_result_count=max_results, max_time_range_days=None,
            allowed_filter_field_ids=filters, allowed_sort_field_ids=sorts,
            user_result_field_ids=user_fields, model_field_ids=model_fields,
            user_transforms=_selected_transforms(env.get(_PREFIX + "USER_TRANSFORMS"), user_fields),
            model_transforms=_selected_transforms(env.get(_PREFIX + "MODEL_TRANSFORMS"), model_fields),
            timeout_ms=timeout,
            config_version=config_version,
            code_contract_version=code_contract_version,
            service_contract_ref=service_contract_ref,
            query_fields=tuple(
                BusinessQueryFieldSettings(
                    logical_name=name,
                    enabled=(
                        name in filters
                        if name in _FILTERS
                        else name == "size" or (name == "sorts" and bool(sorts) and max_sort_items > 0)
                    ),
                    model_safe_description=description,
                    allowed_operators=(operator,),
                    required=False,
                    max_text_chars=max_text_chars,
                )
                for name, description, operator, max_text_chars in _QUERY_FIELDS
            ),
            combination_rule_ids=_COMBINATION_RULE_IDS,
            max_decimal_abs=max_decimal_abs,
            max_decimal_scale=max_decimal_scale,
            fixed_page=fixed_page,
            allowed_sort_directions=sort_directions,
            max_sort_items=max_sort_items,
        ))
