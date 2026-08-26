from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Self

from agent_runtime.business.contracts import (
    BusinessActionSettings,
    BusinessFieldTransform,
    BusinessQueryFieldSettings,
    BusinessQueryOperator,
    FieldTransformSelection,
)

_PREFIX = "AGENT_EMPLOYEE_DETAIL_"
_FIELDS = ("employee_id_masked", "member_no_masked", "chinese_name", "public_email", "position")
_MODEL_FIELDS = frozenset({"position"})
_DEFAULT_USER_TRANSFORMS = {
    "employee_id_masked": BusinessFieldTransform.MASK_KEEP_LAST4,
    "member_no_masked": BusinessFieldTransform.MASK_KEEP_LAST4,
    "chinese_name": BusinessFieldTransform.BOUNDED_TEXT,
    "public_email": BusinessFieldTransform.BOUNDED_TEXT,
    "position": BusinessFieldTransform.BOUNDED_TEXT,
}
_KNOWN = frozenset({
    _PREFIX + "ENABLED", _PREFIX + "TIMEOUT_MS", _PREFIX + "MAX_RESULT_COUNT",
    _PREFIX + "USER_FIELDS", _PREFIX + "MODEL_FIELDS", _PREFIX + "USER_TRANSFORMS", _PREFIX + "MODEL_TRANSFORMS",
    _PREFIX + "CONFIG_VERSION", _PREFIX + "CODE_CONTRACT_VERSION", _PREFIX + "SERVICE_CONTRACT_REF",
})
_CONFIG_VERSION = "employee-detail-config-v1"
_CODE_CONTRACT_VERSION = "employee-detail-plan-v1"
_SERVICE_CONTRACT_REF = "employee-detail-v1"
_QUERY_DESCRIPTION = "当前请求中单一员工标识的受保护引用"
_VERSION = re.compile(r"[a-z][a-z0-9_.-]{0,63}")


def _bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    if raw == "true": return True
    if raw == "false": return False
    raise ValueError("business.employee_settings_invalid")


def _integer(raw: str | None, default: int) -> int:
    value = str(default) if raw is None else raw
    if not value or not value.isascii() or not value.isdecimal() or value != str(int(value)):
        raise ValueError("business.employee_settings_invalid")
    return int(value)


def _version(raw: str | None, default: str) -> str:
    value = default if raw is None else raw
    if _VERSION.fullmatch(value) is None:
        raise ValueError("business.employee_settings_invalid")
    return value


def _list(raw: str, allowed: frozenset[str]) -> tuple[str, ...]:
    if raw == "":
        return ()
    parts = tuple(raw.split(","))
    if len(parts) != len(set(parts)) or any(item not in allowed for item in parts):
        raise ValueError("business.employee_settings_invalid")
    return tuple(item for item in _FIELDS if item in parts)


def _transforms(raw: str | None, fields: tuple[str, ...], defaults: Mapping[str, BusinessFieldTransform]) -> tuple[FieldTransformSelection, ...]:
    if raw is None:
        return tuple(FieldTransformSelection(field_id=item, transform_id=defaults[item]) for item in fields)
    values: dict[str, BusinessFieldTransform] = {}
    if raw:
        for fragment in raw.split(","):
            parts = fragment.split(":")
            if len(parts) != 2 or parts[0] in values:
                raise ValueError("business.employee_settings_invalid")
            try:
                values[parts[0]] = BusinessFieldTransform(parts[1])
            except ValueError as exc:
                raise ValueError("business.employee_settings_invalid") from exc
    if set(values) != set(fields) or any(values[field] is not defaults[field] for field in fields):
        raise ValueError("business.employee_settings_invalid")
    return tuple(FieldTransformSelection(field_id=field, transform_id=values[field]) for field in fields)


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeAdapterSettings:
    action: BusinessActionSettings

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Self:
        if any(key.startswith(_PREFIX) and key not in _KNOWN for key in env):
            raise ValueError("business.employee_settings_unknown_key")
        timeout = _integer(env.get(_PREFIX + "TIMEOUT_MS"), 2000)
        max_results = _integer(env.get(_PREFIX + "MAX_RESULT_COUNT"), 1)
        if not 100 <= timeout <= 3000 or max_results != 1:
            raise ValueError("business.employee_settings_invalid")
        user_fields = _list(env.get(_PREFIX + "USER_FIELDS", ",".join(_FIELDS)), frozenset(_FIELDS))
        if not {"employee_id_masked", "chinese_name"}.issubset(user_fields):
            raise ValueError("business.employee_settings_invalid")
        model_fields = _list(env.get(_PREFIX + "MODEL_FIELDS", ""), _MODEL_FIELDS)
        if not set(model_fields).issubset(user_fields):
            raise ValueError("business.employee_settings_invalid")
        user_transforms = _transforms(env.get(_PREFIX + "USER_TRANSFORMS"), user_fields, _DEFAULT_USER_TRANSFORMS)
        model_defaults = {field: BusinessFieldTransform.BOUNDED_TEXT for field in model_fields}
        model_transforms = _transforms(env.get(_PREFIX + "MODEL_TRANSFORMS"), model_fields, model_defaults)
        config_version = _version(env.get(_PREFIX + "CONFIG_VERSION"), _CONFIG_VERSION)
        code_contract_version = _version(env.get(_PREFIX + "CODE_CONTRACT_VERSION"), _CODE_CONTRACT_VERSION)
        service_contract_ref = _version(env.get(_PREFIX + "SERVICE_CONTRACT_REF"), _SERVICE_CONTRACT_REF)
        if code_contract_version != _CODE_CONTRACT_VERSION or service_contract_ref != _SERVICE_CONTRACT_REF:
            raise ValueError("business.employee_settings_invalid")
        return cls(action=BusinessActionSettings(
            enabled=_bool(env.get(_PREFIX + "ENABLED"), False),
            max_page_size=None, max_result_count=1, max_time_range_days=None,
            allowed_filter_field_ids=None, allowed_sort_field_ids=None,
            user_result_field_ids=user_fields, model_field_ids=model_fields,
            user_transforms=user_transforms, model_transforms=model_transforms,
            timeout_ms=timeout,
            config_version=config_version,
            code_contract_version=code_contract_version,
            service_contract_ref=service_contract_ref,
            query_fields=(
                BusinessQueryFieldSettings(
                    logical_name="employee_identifier",
                    enabled=True,
                    model_safe_description=_QUERY_DESCRIPTION,
                    allowed_operators=(BusinessQueryOperator.EQ,),
                    required=True,
                ),
            ),
            combination_rule_ids=(),
        ))
