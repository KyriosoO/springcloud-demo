from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from agent_runtime.capability_api.contracts import CapabilityKind

from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessAnswerMode,
    BusinessCombinationRuleKind,
    BusinessFieldValueType,
    BusinessFieldTransform,
    BusinessInputExposure,
    BusinessQueryOperator,
    BusinessQueryValueType,
    BusinessServiceKey,
    BusinessTextPolicyId,
    ConstraintDimension,
    DataClass,
)


class BusinessConfigurationError(ValueError):
    pass


_GLOBAL_PREFIX = "AGENT_BUSINESS_"
_GLOBAL_KEYS = frozenset(
    {
        "AGENT_BUSINESS_EGRESS_ENABLED",
        "AGENT_BUSINESS_MAX_SAFE_FACTS",
        "AGENT_BUSINESS_MAX_SAFE_PAYLOAD_BYTES",
        "AGENT_BUSINESS_MAX_TEXT_VALUE_CHARS",
        "AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES",
        "AGENT_BUSINESS_MAX_FIELDS_PER_RECORD",
        "AGENT_BUSINESS_MAX_USER_RESULT_BYTES",
    }
)
_ID = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_UNSAFE_DESCRIPTION_MARKERS = (
    "http://",
    "https://",
    " sql ",
    "select ",
    "es dsl",
    "index",
    "class",
    "method",
    "role_",
    "jwt",
)


def _strict_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise BusinessConfigurationError("business.global_settings_invalid")


def _strict_int(env: Mapping[str, str], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = env.get(key, str(default))
    if not raw or not raw.isascii() or not raw.isdecimal() or raw != str(int(raw)):
        raise BusinessConfigurationError("business.global_settings_invalid")
    value = int(raw)
    if not minimum <= value <= maximum:
        raise BusinessConfigurationError("business.global_settings_invalid")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessGlobalSettings:
    egress_enabled: bool = False
    max_safe_facts: int = 20
    max_safe_payload_bytes: int = 32768
    max_text_value_chars: int = 256
    http_max_response_bytes: int = 1048576
    max_fields_per_record: int = 32
    max_user_result_bytes: int = 262144

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "BusinessGlobalSettings":
        if any(key.startswith(_GLOBAL_PREFIX) and key not in _GLOBAL_KEYS for key in env):
            raise BusinessConfigurationError("business.global_settings_unknown_key")
        return cls(
            egress_enabled=_strict_bool(env, "AGENT_BUSINESS_EGRESS_ENABLED", False),
            max_safe_facts=_strict_int(env, "AGENT_BUSINESS_MAX_SAFE_FACTS", 20, 1, 20),
            max_safe_payload_bytes=_strict_int(env, "AGENT_BUSINESS_MAX_SAFE_PAYLOAD_BYTES", 32768, 4096, 32768),
            max_text_value_chars=_strict_int(env, "AGENT_BUSINESS_MAX_TEXT_VALUE_CHARS", 256, 32, 256),
            http_max_response_bytes=_strict_int(env, "AGENT_BUSINESS_HTTP_MAX_RESPONSE_BYTES", 1048576, 65536, 1048576),
            max_fields_per_record=_strict_int(env, "AGENT_BUSINESS_MAX_FIELDS_PER_RECORD", 32, 1, 32),
            max_user_result_bytes=_strict_int(env, "AGENT_BUSINESS_MAX_USER_RESULT_BYTES", 262144, 16384, 262144),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessServiceBinding:
    service_key: BusinessServiceKey
    base_endpoint: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessConfigurationSource:
    global_settings: BusinessGlobalSettings
    actions: tuple[tuple[str, BusinessActionSettings], ...]
    service_bindings: tuple[BusinessServiceBinding, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessConfigurationFragment:
    actions: tuple[tuple[str, BusinessActionSettings], ...]
    service_bindings: tuple[BusinessServiceBinding, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class GlobalBusinessEgressPolicy:
    enabled: bool
    policy_version: str
    always_denied_classes: frozenset[DataClass]
    max_safe_facts: int
    max_safe_payload_bytes: int
    max_text_value_chars: int
    max_fields_per_record: int

    @classmethod
    def from_settings(cls, settings: BusinessGlobalSettings) -> "GlobalBusinessEgressPolicy":
        return cls(
            enabled=settings.egress_enabled,
            policy_version="business-egress-v1",
            always_denied_classes=frozenset({DataClass.CREDENTIAL_OR_SECRET, DataClass.FREE_TEXT_SENSITIVE, DataClass.UNKNOWN}),
            max_safe_facts=settings.max_safe_facts,
            max_safe_payload_bytes=settings.max_safe_payload_bytes,
            max_text_value_chars=settings.max_text_value_chars,
            max_fields_per_record=settings.max_fields_per_record,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessConfigurationSnapshot:
    global_settings: BusinessGlobalSettings
    actions: tuple[tuple[str, BusinessActionSettings], ...]
    service_bindings: tuple[BusinessServiceBinding, ...]
    snapshot_id: str


class BusinessSettingsValidator:
    def validate(
        self,
        definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
        raw: BusinessConfigurationSource,
        *,
        core_max_domain_result_bytes: int,
    ) -> BusinessConfigurationSnapshot:
        definitions = tuple(definitions)
        by_id = {item.descriptor.capability_id: item for item in definitions}
        settings = dict(raw.actions)
        if not definitions or len(by_id) != len(definitions) or len(settings) != len(raw.actions) or set(settings) != set(by_id):
            raise BusinessConfigurationError("business.configuration_action_mismatch")
        self._validate_global(raw.global_settings)
        if type(core_max_domain_result_bytes) is not int or core_max_domain_result_bytes <= 0:
            raise BusinessConfigurationError("business.invalid_core_limit")
        if raw.global_settings.max_user_result_bytes > core_max_domain_result_bytes:
            raise BusinessConfigurationError("business.user_result_limit_exceeds_core")
        normalized_settings: dict[str, BusinessActionSettings] = {}
        for capability_id, value in settings.items():
            definition = by_id[capability_id]
            self._validate_definition(definition)
            self._validate_query_plan_contract(definition, value)
            code_fields = {item.field_id for item in definition.field_definitions}
            user_code = {item.field_id for item in definition.field_definitions if item.user_visible_by_code}
            model_code = {item.field_id for item in definition.field_definitions if item.model_candidate_by_code}
            if (
                type(value.enabled) is not bool
                or type(value.user_result_field_ids) is not tuple
                or len(set(value.user_result_field_ids)) != len(value.user_result_field_ids)
                or not set(value.user_result_field_ids).issubset(user_code)
                or not set(definition.required_user_field_ids).issubset(value.user_result_field_ids)
                or len(value.user_result_field_ids) > raw.global_settings.max_fields_per_record
            ):
                raise BusinessConfigurationError("business.invalid_user_fields")
            if type(value.model_field_ids) is not tuple or len(set(value.model_field_ids)) != len(value.model_field_ids) or not set(value.model_field_ids).issubset(set(value.user_result_field_ids) & model_code):
                raise BusinessConfigurationError("business.invalid_model_fields")
            if len(value.user_transforms) != len(value.user_result_field_ids) or {item.field_id for item in value.user_transforms} != set(value.user_result_field_ids):
                raise BusinessConfigurationError("business.invalid_user_transforms")
            if len(value.model_transforms) != len(value.model_field_ids) or {item.field_id for item in value.model_transforms} != set(value.model_field_ids):
                raise BusinessConfigurationError("business.invalid_model_transforms")
            if any(item.field_id not in code_fields for item in (*value.user_transforms, *value.model_transforms)):
                raise BusinessConfigurationError("business.invalid_transform_field")
            fields_by_id = {item.field_id: item for item in definition.field_definitions}
            if any(item.transform_id not in fields_by_id[item.field_id].allowed_user_transforms for item in value.user_transforms):
                raise BusinessConfigurationError("business.invalid_user_transforms")
            if any(item.transform_id not in fields_by_id[item.field_id].allowed_model_transforms for item in value.model_transforms):
                raise BusinessConfigurationError("business.invalid_model_transforms")
            if type(value.timeout_ms) is not int or not 100 <= value.timeout_ms <= definition.contract_limits.max_timeout_ms:
                raise BusinessConfigurationError("business.invalid_timeout")
            self._validate_dimensions(definition, value)
            field_order = tuple(item.field_id for item in definition.field_definitions)
            user_fields = tuple(item for item in field_order if item in value.user_result_field_ids)
            model_fields = tuple(item for item in field_order if item in value.model_field_ids)
            user_transform_map = {item.field_id: item for item in value.user_transforms}
            model_transform_map = {item.field_id: item for item in value.model_transforms}
            query_settings_by_name = {
                item.logical_name: item for item in value.query_fields
            }
            normalized_settings[capability_id] = replace(
                value,
                allowed_filter_field_ids=None if value.allowed_filter_field_ids is None else tuple(sorted(value.allowed_filter_field_ids)),
                allowed_sort_field_ids=None if value.allowed_sort_field_ids is None else tuple(sorted(value.allowed_sort_field_ids)),
                user_result_field_ids=user_fields,
                model_field_ids=model_fields,
                user_transforms=tuple(user_transform_map[item] for item in user_fields),
                model_transforms=tuple(model_transform_map[item] for item in model_fields),
                query_fields=tuple(
                    replace(
                        query_settings_by_name[item.logical_name],
                        allowed_operators=tuple(
                            sorted(
                                query_settings_by_name[item.logical_name].allowed_operators,
                                key=lambda operator: operator.value,
                            )
                        ),
                    )
                    for item in definition.query_fields
                    if item.logical_name in query_settings_by_name
                ),
                combination_rule_ids=tuple(
                    rule.rule_id for rule in definition.combination_rules
                ),
                allowed_sort_directions=(
                    None
                    if value.allowed_sort_directions is None
                    else tuple(sorted(value.allowed_sort_directions))
                ),
            )
        bindings = {item.service_key: item for item in raw.service_bindings}
        expected_services = {item.service_key for item in definitions}
        if len(bindings) != len(raw.service_bindings) or set(bindings) != expected_services:
            raise BusinessConfigurationError("business.service_binding_missing")
        for binding in bindings.values():
            self._validate_endpoint(binding.base_endpoint)
        material = {
            "actions": [
                self._action_material(key, value)
                for key, value in sorted(normalized_settings.items())
            ],
            "bindings": [{"service_key": str(key), "base_endpoint": bindings[key].base_endpoint} for key in sorted(bindings)],
            "definitions": [self._definition_material(by_id[key]) for key in sorted(by_id)],
            "global": {
                name: getattr(raw.global_settings, name) for name in raw.global_settings.__dataclass_fields__
            },
        }
        snapshot_id = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return BusinessConfigurationSnapshot(
            global_settings=raw.global_settings,
            actions=tuple(sorted(normalized_settings.items())),
            service_bindings=tuple(bindings[key] for key in sorted(bindings)),
            snapshot_id=snapshot_id,
        )

    @staticmethod
    def _validate_global(settings: BusinessGlobalSettings) -> None:
        values = (
            (settings.max_safe_facts, 1, 20),
            (settings.max_safe_payload_bytes, 4096, 32768),
            (settings.max_text_value_chars, 32, 256),
            (settings.http_max_response_bytes, 65536, 1048576),
            (settings.max_fields_per_record, 1, 32),
            (settings.max_user_result_bytes, 16384, 262144),
        )
        if type(settings.egress_enabled) is not bool or any(type(value) is not int or not minimum <= value <= maximum for value, minimum, maximum in values):
            raise BusinessConfigurationError("business.global_settings_invalid")

    @staticmethod
    def _validate_definition(definition: BusinessActionDefinition[Any, Any, Any, Any]) -> None:
        descriptor = definition.descriptor
        limits = definition.contract_limits
        fields = definition.field_definitions
        field_ids = tuple(item.field_id for item in fields)
        resolver = definition.local_action_resolver
        resolver_capability_id: str | None = None
        resolver_method: object | None = None
        if (resolver is None) == (not definition.query_fields):
            raise BusinessConfigurationError("business.invalid_local_action_resolver")
        if resolver is not None:
            try:
                resolver_capability_id = resolver.capability_id
                resolver_method = resolver.resolve
            except Exception:
                raise BusinessConfigurationError("business.invalid_local_action_resolver") from None
        if (
            _ID.fullmatch(descriptor.capability_id) is None
            or descriptor.api_version != 1
            or descriptor.kind is not CapabilityKind.QUERY
            or _ID.fullmatch(str(definition.domain_id)) is None
            or _ID.fullmatch(str(definition.service_key)) is None
            or not fields
            or len(set(field_ids)) != len(field_ids)
            or len(set(definition.required_user_field_ids)) != len(definition.required_user_field_ids)
            or not set(definition.required_user_field_ids).issubset({item.field_id for item in fields if item.user_visible_by_code})
            or type(limits.max_timeout_ms) is not int
            or not 100 <= limits.max_timeout_ms <= 60000
            or type(limits.max_request_bytes) is not int
            or not 1024 <= limits.max_request_bytes <= 65536
            or any(item.model_candidate_by_code and not item.user_visible_by_code for item in fields)
            or any(item.model_candidate_by_code and item.data_class in {DataClass.CREDENTIAL_OR_SECRET, DataClass.FREE_TEXT_SENSITIVE, DataClass.UNKNOWN} for item in fields)
            or definition.answer_mode not in {BusinessAnswerMode.STRUCTURED_ONLY, BusinessAnswerMode.MODEL_ASSISTED}
            or (
                resolver is not None
                and (
                    resolver_capability_id != descriptor.capability_id
                    or not callable(resolver_method)
                )
            )
        ):
            raise BusinessConfigurationError("business.invalid_definition")
        for item in fields:
            transform_inputs = {
                BusinessFieldValueType.BOOLEAN: {BusinessFieldTransform.IDENTITY_SCALAR},
                BusinessFieldValueType.INTEGER: {BusinessFieldTransform.IDENTITY_SCALAR},
                BusinessFieldValueType.DECIMAL: {BusinessFieldTransform.DECIMAL_2},
                BusinessFieldValueType.DATE: {BusinessFieldTransform.DATE_ONLY},
                BusinessFieldValueType.DATETIME: {BusinessFieldTransform.DATE_ONLY},
                BusinessFieldValueType.ENUM: {BusinessFieldTransform.ENUM_CODE},
                BusinessFieldValueType.TEXT: {BusinessFieldTransform.BOUNDED_TEXT},
                BusinessFieldValueType.IDENTIFIER: {BusinessFieldTransform.BOUNDED_TEXT, BusinessFieldTransform.MASK_KEEP_LAST4},
            }
            if (
                _ID.fullmatch(item.field_id) is None
                or (item.user_visible_by_code and not item.allowed_user_transforms)
                or (item.model_candidate_by_code and not item.allowed_model_transforms)
                or (item.value_type.value == "enum") != bool(item.enum_values)
                or any(not isinstance(transform, BusinessFieldTransform) for transform in item.allowed_user_transforms | item.allowed_model_transforms)
                or not (item.allowed_user_transforms | item.allowed_model_transforms).issubset(transform_inputs[item.value_type])
            ):
                raise BusinessConfigurationError("business.invalid_definition")

    @staticmethod
    def _validate_dimensions(
        definition: BusinessActionDefinition[Any, Any, Any, Any],
        settings: BusinessActionSettings,
    ) -> None:
        numeric = (
            (ConstraintDimension.PAGE_SIZE, "max_page_size", 1000),
            (ConstraintDimension.RESULT_COUNT, "max_result_count", 1000),
            (ConstraintDimension.TIME_RANGE_DAYS, "max_time_range_days", 3660),
        )
        for dimension, name, maximum in numeric:
            code_value = getattr(definition.contract_limits, name)
            configured = getattr(settings, name)
            applicable = dimension in definition.applicable_dimensions
            if applicable:
                if type(code_value) is not int or not 1 <= code_value <= maximum or type(configured) is not int or not 1 <= configured <= code_value:
                    raise BusinessConfigurationError("business.invalid_dimension")
            elif code_value is not None or configured is not None:
                raise BusinessConfigurationError("business.invalid_dimension")
        set_dimensions = (
            (ConstraintDimension.FILTER_FIELDS, definition.filter_field_ids_by_code, settings.allowed_filter_field_ids),
            (ConstraintDimension.SORT_FIELDS, definition.sort_field_ids_by_code, settings.allowed_sort_field_ids),
        )
        for dimension, code_values, configured in set_dimensions:
            applicable = dimension in definition.applicable_dimensions
            if applicable:
                if not code_values or type(configured) is not tuple or len(configured) != len(set(configured)) or not set(configured).issubset(code_values):
                    raise BusinessConfigurationError("business.invalid_dimension")
            elif code_values or configured is not None:
                raise BusinessConfigurationError("business.invalid_dimension")

    @staticmethod
    def _validate_endpoint(raw: str) -> None:
        try:
            parsed = urlsplit(raw)
            port = parsed.port
        except (TypeError, ValueError) as exc:
            raise BusinessConfigurationError("business.invalid_service_binding") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise BusinessConfigurationError("business.invalid_service_binding")
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        canonical = f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")
        if raw.rstrip("/") != canonical:
            raise BusinessConfigurationError("business.invalid_service_binding")

    @staticmethod
    def _action_material(capability_id: str, value: BusinessActionSettings) -> dict[str, object]:
        return {
            "capability_id": capability_id,
            "enabled": value.enabled,
            "max_page_size": value.max_page_size,
            "max_result_count": value.max_result_count,
            "max_time_range_days": value.max_time_range_days,
            "allowed_filter_field_ids": value.allowed_filter_field_ids,
            "allowed_sort_field_ids": value.allowed_sort_field_ids,
            "user_result_field_ids": value.user_result_field_ids,
            "model_field_ids": value.model_field_ids,
            "user_transforms": tuple((item.field_id, item.transform_id.value) for item in value.user_transforms),
            "model_transforms": tuple((item.field_id, item.transform_id.value) for item in value.model_transforms),
            "timeout_ms": value.timeout_ms,
            "config_version": value.config_version,
            "code_contract_version": value.code_contract_version,
            "service_contract_ref": value.service_contract_ref,
            "query_fields": tuple(
                {
                    "logical_name": item.logical_name,
                    "enabled": item.enabled,
                    "model_safe_description": item.model_safe_description,
                    "allowed_operators": tuple(operator.value for operator in item.allowed_operators),
                    "required": item.required,
                    "max_text_chars": item.max_text_chars,
                }
                for item in value.query_fields
            ),
            "combination_rule_ids": value.combination_rule_ids,
            "max_decimal_abs": value.max_decimal_abs,
            "max_decimal_scale": value.max_decimal_scale,
            "fixed_page": value.fixed_page,
            "allowed_sort_directions": value.allowed_sort_directions,
            "max_sort_items": value.max_sort_items,
        }

    @staticmethod
    def _definition_material(definition: BusinessActionDefinition[Any, Any, Any, Any]) -> dict[str, object]:
        limits = definition.contract_limits
        return {
            "capability_id": definition.descriptor.capability_id,
            "api_version": definition.descriptor.api_version,
            "domain_id": str(definition.domain_id),
            "service_key": str(definition.service_key),
            "code_contract_version": definition.code_contract_version,
            "service_contract_ref": definition.service_contract_ref,
            "query_fields": tuple(
                {
                    "logical_name": item.logical_name,
                    "model_safe_description": item.model_safe_description,
                    "value_type": item.value_type.value,
                    "allowed_operators": sorted(value.value for value in item.allowed_operators),
                    "input_exposure": item.input_exposure.value,
                    "required": item.required,
                    "allow_negative": item.allow_negative,
                    "max_text_chars": item.max_text_chars,
                    "minimum_integer": item.minimum_integer,
                    "maximum_integer": item.maximum_integer,
                    "text_policy_id": None if item.text_policy_id is None else item.text_policy_id.value,
                    "enum_values": sorted(item.enum_values),
                }
                for item in definition.query_fields
            ),
            "combination_rules": tuple(
                {
                    "rule_id": item.rule_id,
                    "kind": item.kind.value,
                    "field_names": item.field_names,
                }
                for item in definition.combination_rules
            ),
            "applicable_dimensions": sorted(item.value for item in definition.applicable_dimensions),
            "filter_field_ids_by_code": sorted(definition.filter_field_ids_by_code),
            "sort_field_ids_by_code": sorted(definition.sort_field_ids_by_code),
            "fields": tuple(
                {
                    "field_id": item.field_id,
                    "value_type": item.value_type.value,
                    "data_class": item.data_class.value,
                    "user_visible": item.user_visible_by_code,
                    "model_candidate": item.model_candidate_by_code,
                    "user_transforms": sorted(value.value for value in item.allowed_user_transforms),
                    "model_transforms": sorted(value.value for value in item.allowed_model_transforms),
                    "enum_values": sorted(item.enum_values),
                }
                for item in definition.field_definitions
            ),
            "required_user_field_ids": definition.required_user_field_ids,
            "answer_mode": definition.answer_mode.value,
            "contract_limits": {
                "max_page_size": limits.max_page_size,
                "max_result_count": limits.max_result_count,
                "max_time_range_days": limits.max_time_range_days,
                "max_timeout_ms": limits.max_timeout_ms,
                "max_request_bytes": limits.max_request_bytes,
                "max_decimal_abs": limits.max_decimal_abs,
                "max_decimal_scale": limits.max_decimal_scale,
                "fixed_page": limits.fixed_page,
                "allowed_sort_directions": sorted(limits.allowed_sort_directions),
                "max_sort_items": limits.max_sort_items,
            },
        }

    @staticmethod
    def _validate_query_plan_contract(
        definition: BusinessActionDefinition[Any, Any, Any, Any],
        settings: BusinessActionSettings,
    ) -> None:
        if (
            _ID.fullmatch(definition.code_contract_version) is None
            or _ID.fullmatch(definition.service_contract_ref) is None
            or _ID.fullmatch(settings.config_version) is None
            or settings.code_contract_version != definition.code_contract_version
            or settings.service_contract_ref != definition.service_contract_ref
        ):
            raise BusinessConfigurationError("business.invalid_query_plan_contract")
        definitions = {item.logical_name: item for item in definition.query_fields}
        configured = {item.logical_name: item for item in settings.query_fields}
        if len(definitions) != len(definition.query_fields) or len(configured) != len(settings.query_fields):
            raise BusinessConfigurationError("business.invalid_query_fields")
        if not definitions:
            if configured or definition.combination_rules or settings.combination_rule_ids:
                raise BusinessConfigurationError("business.invalid_query_fields")
            return
        if not configured or not set(configured).issubset(definitions):
            raise BusinessConfigurationError("business.invalid_query_fields")
        for logical_name, field in definitions.items():
            if (
                _ID.fullmatch(logical_name) is None
                or not field.model_safe_description
                or len(field.model_safe_description) > 256
                or any(marker in f" {field.model_safe_description.casefold()} " for marker in _UNSAFE_DESCRIPTION_MARKERS)
                or not field.allowed_operators
                or any(not isinstance(operator, BusinessQueryOperator) for operator in field.allowed_operators)
                or not isinstance(field.value_type, BusinessQueryValueType)
                or not isinstance(field.input_exposure, BusinessInputExposure)
                or type(field.required) is not bool
                or type(field.allow_negative) is not bool
            ):
                raise BusinessConfigurationError("business.invalid_query_fields")
            if field.value_type is BusinessQueryValueType.TEXT:
                if (
                    field.text_policy_id not in {BusinessTextPolicyId.SAFE_TOKEN, BusinessTextPolicyId.SAFE_CONTAINS_TOKEN}
                    or type(field.max_text_chars) is not int
                    or not 1 <= field.max_text_chars <= 512
                ):
                    raise BusinessConfigurationError("business.invalid_query_fields")
            elif field.text_policy_id is not None or field.max_text_chars is not None or field.enum_values:
                raise BusinessConfigurationError("business.invalid_query_fields")
            if field.value_type is BusinessQueryValueType.INTEGER:
                if (
                    type(field.minimum_integer) is not int
                    or type(field.maximum_integer) is not int
                    or field.minimum_integer > field.maximum_integer
                ):
                    raise BusinessConfigurationError("business.invalid_query_fields")
            elif field.minimum_integer is not None or field.maximum_integer is not None:
                raise BusinessConfigurationError("business.invalid_query_fields")
            selected = configured.get(logical_name)
            if field.required and (selected is None or not selected.enabled or not selected.required):
                raise BusinessConfigurationError("business.invalid_query_fields")
            if selected is None:
                continue
            if (
                type(selected.enabled) is not bool
                or type(selected.required) is not bool
                or selected.model_safe_description != field.model_safe_description
                or not selected.allowed_operators
                or len(selected.allowed_operators) != len(set(selected.allowed_operators))
                or not set(selected.allowed_operators).issubset(field.allowed_operators)
                or (selected.required and not selected.enabled)
                or (
                    field.max_text_chars is None
                    and selected.max_text_chars is not None
                )
                or (
                    field.max_text_chars is not None
                    and (
                        type(selected.max_text_chars) is not int
                        or not 1 <= selected.max_text_chars <= field.max_text_chars
                    )
                )
            ):
                raise BusinessConfigurationError("business.invalid_query_fields")
        enabled_fields = {name for name, item in configured.items() if item.enabled}
        if settings.enabled and not enabled_fields:
            raise BusinessConfigurationError("business.invalid_query_fields")
        rules = {item.rule_id: item for item in definition.combination_rules}
        if (
            len(rules) != len(definition.combination_rules)
            or len(settings.combination_rule_ids) != len(set(settings.combination_rule_ids))
            or set(settings.combination_rule_ids) != set(rules)
        ):
            raise BusinessConfigurationError("business.invalid_combination_rules")
        for rule in rules.values():
            if (
                _ID.fullmatch(rule.rule_id) is None
                or not isinstance(rule.kind, BusinessCombinationRuleKind)
                or not rule.field_names
                or len(rule.field_names) != len(set(rule.field_names))
                or not set(rule.field_names).issubset(definitions)
                or (
                    rule.kind is BusinessCombinationRuleKind.MUTUALLY_EXCLUSIVE
                    and len(rule.field_names) < 2
                )
            ):
                raise BusinessConfigurationError("business.invalid_combination_rules")
        limits = definition.contract_limits
        has_decimal = any(
            field.value_type is BusinessQueryValueType.DECIMAL
            for field in definitions.values()
        )
        if has_decimal:
            try:
                code_abs = Decimal(limits.max_decimal_abs or "")
                configured_abs = Decimal(settings.max_decimal_abs or "")
            except InvalidOperation:
                raise BusinessConfigurationError("business.invalid_decimal_limits") from None
            if (
                _DECIMAL.fullmatch(limits.max_decimal_abs or "") is None
                or _DECIMAL.fullmatch(settings.max_decimal_abs or "") is None
                or configured_abs > code_abs
                or configured_abs <= 0
                or type(limits.max_decimal_scale) is not int
                or type(settings.max_decimal_scale) is not int
                or not 0 <= settings.max_decimal_scale <= limits.max_decimal_scale
            ):
                raise BusinessConfigurationError("business.invalid_decimal_limits")
        elif any(
            value is not None
            for value in (
                limits.max_decimal_abs,
                limits.max_decimal_scale,
                settings.max_decimal_abs,
                settings.max_decimal_scale,
            )
        ):
            raise BusinessConfigurationError("business.invalid_decimal_limits")
        has_sort = any(
            field.value_type is BusinessQueryValueType.SORT_LIST
            for field in definitions.values()
        )
        if has_sort:
            if (
                not limits.allowed_sort_directions
                or type(settings.allowed_sort_directions) is not tuple
                or not settings.allowed_sort_directions
                or len(settings.allowed_sort_directions) != len(set(settings.allowed_sort_directions))
                or not set(settings.allowed_sort_directions).issubset(limits.allowed_sort_directions)
                or type(limits.max_sort_items) is not int
                or type(settings.max_sort_items) is not int
                or not 0 <= settings.max_sort_items <= limits.max_sort_items
            ):
                raise BusinessConfigurationError("business.invalid_sort_limits")
        elif limits.allowed_sort_directions or limits.max_sort_items is not None or settings.allowed_sort_directions is not None or settings.max_sort_items is not None:
            raise BusinessConfigurationError("business.invalid_sort_limits")
        if limits.fixed_page != settings.fixed_page:
            raise BusinessConfigurationError("business.invalid_fixed_page")
