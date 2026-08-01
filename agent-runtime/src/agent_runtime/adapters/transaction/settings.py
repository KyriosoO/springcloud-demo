from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Self

from agent_runtime.business.contracts import BusinessActionSettings, BusinessFieldTransform, FieldTransformSelection

_PREFIX = "AGENT_TRANSACTION_SEARCH_"
_FILTERS = ("trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt")
_SORTS = ("trans_id", "trans_type", "amount")
_FIELDS = ("transaction_id_masked", "transaction_type", "amount")
_MODEL_FIELDS = frozenset({"transaction_type", "amount"})
_TRANSFORMS = {
    "transaction_id_masked": BusinessFieldTransform.MASK_KEEP_LAST4,
    "transaction_type": BusinessFieldTransform.BOUNDED_TEXT,
    "amount": BusinessFieldTransform.DECIMAL_2,
}
_KNOWN = frozenset({
    _PREFIX + "ENABLED", _PREFIX + "TIMEOUT_MS", _PREFIX + "MAX_PAGE_SIZE", _PREFIX + "MAX_RESULT_COUNT",
    _PREFIX + "FILTER_FIELDS", _PREFIX + "SORT_FIELDS", _PREFIX + "USER_FIELDS", _PREFIX + "MODEL_FIELDS",
    _PREFIX + "USER_TRANSFORMS", _PREFIX + "MODEL_TRANSFORMS",
})


def _boolean(raw: str | None) -> bool:
    if raw is None or raw == "false": return False
    if raw == "true": return True
    raise ValueError("business.transaction_settings_invalid")


def _integer(raw: str | None, default: int) -> int:
    value = str(default) if raw is None else raw
    if not value or not value.isascii() or not value.isdecimal() or value != str(int(value)):
        raise ValueError("business.transaction_settings_invalid")
    return int(value)


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
        if not 100 <= timeout <= 5000 or not 1 <= max_page <= 50 or not 1 <= max_results <= 50:
            raise ValueError("business.transaction_settings_invalid")
        filters = _subset(env.get(_PREFIX + "FILTER_FIELDS", ",".join(_FILTERS)), _FILTERS, allow_empty=False)
        sorts = _subset(env.get(_PREFIX + "SORT_FIELDS", ",".join(_SORTS)), _SORTS, allow_empty=True)
        user_fields = _subset(env.get(_PREFIX + "USER_FIELDS", ",".join(_FIELDS)), _FIELDS, allow_empty=False)
        if not {"transaction_type", "amount"}.issubset(user_fields):
            raise ValueError("business.transaction_settings_invalid")
        model_fields = _subset(env.get(_PREFIX + "MODEL_FIELDS", ""), _FIELDS, allow_empty=True)
        if not set(model_fields).issubset(_MODEL_FIELDS & set(user_fields)):
            raise ValueError("business.transaction_settings_invalid")
        return cls(action=BusinessActionSettings(
            enabled=_boolean(env.get(_PREFIX + "ENABLED")),
            max_page_size=max_page, max_result_count=max_results, max_time_range_days=None,
            allowed_filter_field_ids=filters, allowed_sort_field_ids=sorts,
            user_result_field_ids=user_fields, model_field_ids=model_fields,
            user_transforms=_selected_transforms(env.get(_PREFIX + "USER_TRANSFORMS"), user_fields),
            model_transforms=_selected_transforms(env.get(_PREFIX + "MODEL_TRANSFORMS"), model_fields),
            timeout_ms=timeout,
        ))
