from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence, TypeAlias

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    ContractViolation,
    JsonObject,
    JsonValue,
    freeze_json_object,
)
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessCombinationRuleKind,
    BusinessInputExposure,
    BusinessQueryFieldDefinition,
    BusinessQueryFieldSettings,
    BusinessQueryValueType,
    BusinessTextPolicyId,
)
from agent_runtime.business.settings import BusinessConfigurationSnapshot


_ID = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SLOT_ID = re.compile(r"slot-[1-9][0-9]{0,5}")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_PROHIBITED_KEYS = frozenset(
    {
        "sql",
        "dsl",
        "url",
        "index",
        "table",
        "column",
        "class",
        "method",
        "endpoint",
        "http",
        "headers",
        "jwt",
        "role",
    }
)


class InvalidBusinessQueryPlan(ValueError):
    def __init__(self, code: str = "business.plan_invalid") -> None:
        super().__init__(code)
        self.code = code


class InvalidProtectedValue(ValueError):
    def __init__(self) -> None:
        super().__init__("business.protected_value_invalid")
        self.code = "business.protected_value_invalid"


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryPlanLiteral:
    value: JsonValue


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryPlanValueRef:
    value_ref: str


QueryPlanArgumentValue: TypeAlias = QueryPlanLiteral | QueryPlanValueRef


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryPlan:
    domain: str
    action: str
    arguments: Mapping[str, QueryPlanArgumentValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class ProtectedValueSlots:
    request_id: str
    values: Mapping[str, object]

    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id or len(self.request_id) > 128:
            raise InvalidProtectedValue()
        copied = dict(self.values)
        if len(copied) > 32 or any(_SLOT_ID.fullmatch(key) is None for key in copied):
            raise InvalidProtectedValue()
        object.__setattr__(self, "values", MappingProxyType(copied))

    def __repr__(self) -> str:
        return f"ProtectedValueSlots(request_id=<redacted>, count={len(self.values)})"


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatedBusinessQueryPlan:
    plan: BusinessQueryPlan
    config_snapshot_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnsupportedBusinessQueryPlan:
    domain: str
    config_snapshot_id: str


BusinessQueryPlanValidationResult: TypeAlias = (
    ValidatedBusinessQueryPlan | UnsupportedBusinessQueryPlan
)


class BusinessQueryPlanDecoder(Protocol):
    def decode(self, payload: JsonObject) -> BusinessQueryPlan: ...


class BusinessQueryPlanValidator(Protocol):
    def validate(
        self,
        plan: BusinessQueryPlan,
        *,
        snapshot: BusinessConfigurationSnapshot,
    ) -> BusinessQueryPlanValidationResult: ...


class ProtectedValueBinder(Protocol):
    def bind(
        self,
        plan: ValidatedBusinessQueryPlan,
        *,
        slots: ProtectedValueSlots,
        request_id: str,
    ) -> ActionCandidate: ...


class ExactBusinessQueryPlanDecoder:
    """Decodes only the provider-neutral three-field QueryPlan payload."""

    def decode(self, payload: JsonObject) -> BusinessQueryPlan:
        try:
            frozen = freeze_json_object(
                payload,
                max_bytes=16384,
                max_depth=8,
                max_collection_items=128,
            )
        except ContractViolation as exc:
            raise InvalidBusinessQueryPlan() from exc
        if _contains_float(frozen) or set(frozen) != {"domain", "action", "arguments"}:
            raise InvalidBusinessQueryPlan()
        domain = frozen["domain"]
        action = frozen["action"]
        arguments = frozen["arguments"]
        if (
            not isinstance(domain, str)
            or not isinstance(action, str)
            or len(domain) > 128
            or len(action) > 128
            or not isinstance(arguments, Mapping)
            or len(arguments) > 32
        ):
            raise InvalidBusinessQueryPlan()
        _reject_prohibited_keys(frozen)
        decoded: dict[str, QueryPlanArgumentValue] = {}
        for key, raw in arguments.items():
            if not isinstance(key, str) or _ID.fullmatch(key) is None or not isinstance(raw, Mapping):
                raise InvalidBusinessQueryPlan()
            if set(raw) == {"literal"}:
                decoded[key] = QueryPlanLiteral(value=raw["literal"])
            elif set(raw) == {"value_ref"}:
                value_ref = raw["value_ref"]
                if not isinstance(value_ref, str) or _SLOT_ID.fullmatch(value_ref) is None:
                    raise InvalidBusinessQueryPlan()
                decoded[key] = QueryPlanValueRef(value_ref=value_ref)
            else:
                raise InvalidBusinessQueryPlan()
        return BusinessQueryPlan(domain=domain, action=action, arguments=decoded)


class DefaultBusinessQueryPlanValidator:
    def __init__(
        self,
        definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
    ) -> None:
        definition_tuple = tuple(definitions)
        by_action = {item.descriptor.capability_id: item for item in definition_tuple}
        if not definition_tuple or len(by_action) != len(definition_tuple):
            raise ValueError("business.configuration_invalid")
        self._definitions = MappingProxyType(by_action)
        self._domains = frozenset(str(item.domain_id) for item in definition_tuple)

    def validate(
        self,
        plan: BusinessQueryPlan,
        *,
        snapshot: BusinessConfigurationSnapshot,
    ) -> BusinessQueryPlanValidationResult:
        if plan.action == "unsupported":
            if plan.arguments or plan.domain not in self._domains | {"unsupported"}:
                raise InvalidBusinessQueryPlan()
            return UnsupportedBusinessQueryPlan(
                domain=plan.domain,
                config_snapshot_id=snapshot.snapshot_id,
            )
        definition = self._definitions.get(plan.action)
        if definition is None or plan.domain != str(definition.domain_id):
            return UnsupportedBusinessQueryPlan(
                domain=plan.domain if plan.domain in self._domains else "unsupported",
                config_snapshot_id=snapshot.snapshot_id,
            )
        settings_by_action = dict(snapshot.actions)
        settings = settings_by_action.get(plan.action)
        if settings is None:
            raise InvalidBusinessQueryPlan("business.plan_snapshot_mismatch")
        if not settings.enabled:
            return UnsupportedBusinessQueryPlan(
                domain=plan.domain,
                config_snapshot_id=snapshot.snapshot_id,
            )
        definition_fields = {item.logical_name: item for item in definition.query_fields}
        configured_fields = {
            item.logical_name: item for item in settings.query_fields if item.enabled
        }
        if not definition_fields or not configured_fields:
            raise InvalidBusinessQueryPlan("business.plan_snapshot_mismatch")
        unknown = set(plan.arguments) - set(definition_fields)
        disabled = set(plan.arguments) - set(configured_fields)
        if unknown or disabled:
            return UnsupportedBusinessQueryPlan(
                domain=plan.domain,
                config_snapshot_id=snapshot.snapshot_id,
            )
        for logical_name, field in configured_fields.items():
            if field.required and logical_name not in plan.arguments:
                raise InvalidBusinessQueryPlan()
        for logical_name, value in plan.arguments.items():
            self._validate_value(
                value,
                definition=definition_fields[logical_name],
                settings=configured_fields[logical_name],
                action_settings=settings,
                definition_action=definition,
            )
        self._validate_combinations(
            plan=plan,
            definition=definition,
            settings=settings,
            configured_fields=frozenset(configured_fields),
        )
        return ValidatedBusinessQueryPlan(
            plan=plan,
            config_snapshot_id=snapshot.snapshot_id,
        )

    @staticmethod
    def _validate_value(
        value: QueryPlanArgumentValue,
        *,
        definition: BusinessQueryFieldDefinition,
        settings: BusinessQueryFieldSettings,
        action_settings: BusinessActionSettings,
        definition_action: BusinessActionDefinition[Any, Any, Any, Any],
    ) -> None:
        if not settings.allowed_operators or not set(settings.allowed_operators).issubset(
            definition.allowed_operators
        ):
            raise InvalidBusinessQueryPlan("business.plan_snapshot_mismatch")
        if definition.input_exposure is BusinessInputExposure.PROTECTED_REF:
            if not isinstance(value, QueryPlanValueRef):
                raise InvalidBusinessQueryPlan()
            return
        if not isinstance(value, QueryPlanLiteral):
            raise InvalidBusinessQueryPlan()
        literal = value.value
        if definition.value_type is BusinessQueryValueType.TEXT:
            if not isinstance(literal, str):
                raise InvalidBusinessQueryPlan()
            maximum = settings.max_text_chars
            if maximum is None or maximum <= 0 or len(literal) > maximum:
                raise InvalidBusinessQueryPlan()
            if definition.enum_values and literal not in definition.enum_values:
                raise InvalidBusinessQueryPlan()
            if not _matches_text_policy(literal, definition.text_policy_id):
                raise InvalidBusinessQueryPlan()
            return
        if definition.value_type is BusinessQueryValueType.DECIMAL:
            if not isinstance(literal, str) or _DECIMAL.fullmatch(literal) is None:
                raise InvalidBusinessQueryPlan()
            if literal.startswith("-") and not definition.allow_negative:
                raise InvalidBusinessQueryPlan()
            try:
                decimal_value = Decimal(literal)
                configured_abs = Decimal(action_settings.max_decimal_abs or "")
                code_abs = Decimal(definition_action.contract_limits.max_decimal_abs or "")
            except (InvalidOperation, ValueError):
                raise InvalidBusinessQueryPlan() from None
            if decimal_value.is_zero() and literal.startswith("-"):
                raise InvalidBusinessQueryPlan()
            exponent = decimal_value.as_tuple().exponent
            if not isinstance(exponent, int):
                raise InvalidBusinessQueryPlan()
            scale = max(0, -exponent)
            configured_scale = action_settings.max_decimal_scale
            code_scale = definition_action.contract_limits.max_decimal_scale
            if (
                configured_scale is None
                or code_scale is None
                or configured_scale > code_scale
                or configured_abs > code_abs
                or abs(decimal_value) > configured_abs
                or scale > configured_scale
            ):
                raise InvalidBusinessQueryPlan()
            return
        if definition.value_type is BusinessQueryValueType.INTEGER:
            if isinstance(literal, bool) or not isinstance(literal, int):
                raise InvalidBusinessQueryPlan()
            if definition.minimum_integer is not None and literal < definition.minimum_integer:
                raise InvalidBusinessQueryPlan()
            if definition.maximum_integer is not None and literal > definition.maximum_integer:
                raise InvalidBusinessQueryPlan()
            if definition.logical_name == "size" and (
                action_settings.max_page_size is None
                or literal > action_settings.max_page_size
            ):
                raise InvalidBusinessQueryPlan()
            return
        if definition.value_type is BusinessQueryValueType.SORT_LIST:
            _validate_sort_list(
                literal,
                allowed_fields=action_settings.allowed_sort_field_ids,
                allowed_directions=action_settings.allowed_sort_directions,
                maximum_items=action_settings.max_sort_items,
            )
            return
        raise InvalidBusinessQueryPlan()

    @staticmethod
    def _validate_combinations(
        *,
        plan: BusinessQueryPlan,
        definition: BusinessActionDefinition[Any, Any, Any, Any],
        settings: BusinessActionSettings,
        configured_fields: frozenset[str],
    ) -> None:
        active_rules = set(settings.combination_rule_ids)
        rules = {item.rule_id: item for item in definition.combination_rules}
        if active_rules != set(rules):
            raise InvalidBusinessQueryPlan("business.plan_snapshot_mismatch")
        present = set(plan.arguments)
        for rule in rules.values():
            fields = set(rule.field_names) & set(configured_fields)
            count = len(present & fields)
            if rule.kind is BusinessCombinationRuleKind.AT_LEAST_ONE and fields and count == 0:
                raise InvalidBusinessQueryPlan()
            if rule.kind is BusinessCombinationRuleKind.MUTUALLY_EXCLUSIVE and count > 1:
                raise InvalidBusinessQueryPlan()
            if rule.kind is BusinessCombinationRuleKind.ALL_OR_NONE and count not in {0, len(fields)}:
                raise InvalidBusinessQueryPlan()


class RequestProtectedValueBinder:
    def bind(
        self,
        plan: ValidatedBusinessQueryPlan,
        *,
        slots: ProtectedValueSlots,
        request_id: str,
    ) -> ActionCandidate:
        if (
            not isinstance(request_id, str)
            or not request_id
            or request_id != slots.request_id
        ):
            raise InvalidProtectedValue()
        arguments: dict[str, JsonValue] = {}
        used_refs: set[str] = set()
        for logical_name, value in plan.plan.arguments.items():
            if isinstance(value, QueryPlanLiteral):
                arguments[logical_name] = value.value
                continue
            if value.value_ref in used_refs or value.value_ref not in slots.values:
                raise InvalidProtectedValue()
            used_refs.add(value.value_ref)
            raw = slots.values[value.value_ref]
            try:
                frozen = freeze_json_object(
                    {"value": raw},
                    max_bytes=65536,
                    max_depth=8,
                    max_collection_items=128,
                )
            except ContractViolation as exc:
                raise InvalidProtectedValue() from exc
            arguments[logical_name] = frozen["value"]
        return ActionCandidate(
            capability_id=plan.plan.action,
            arguments=arguments,
        )


def _contains_float(value: JsonValue) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, Mapping):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, tuple):
        return any(_contains_float(item) for item in value)
    return False


def _reject_prohibited_keys(value: JsonValue) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key.casefold() in _PROHIBITED_KEYS:
                raise InvalidBusinessQueryPlan()
            _reject_prohibited_keys(item)
    elif isinstance(value, tuple):
        for item in value:
            _reject_prohibited_keys(item)


def _matches_text_policy(value: str, policy: BusinessTextPolicyId | None) -> bool:
    if (
        not value
        or policy is None
        or value != value.strip()
        or value != unicodedata.normalize("NFC", value)
    ):
        return False
    punctuation = {"-", "."}
    if policy is BusinessTextPolicyId.SAFE_TOKEN:
        punctuation.add("_")
    for character in value:
        if unicodedata.category(character).startswith("C"):
            return False
        if character.isalnum() or character == " " or character in punctuation:
            continue
        return False
    return True


def _validate_sort_list(
    value: JsonValue,
    *,
    allowed_fields: tuple[str, ...] | None,
    allowed_directions: tuple[str, ...] | None,
    maximum_items: int | None,
) -> None:
    if (
        not isinstance(value, tuple)
        or maximum_items is None
        or len(value) > maximum_items
        or allowed_fields is None
        or allowed_directions is None
    ):
        raise InvalidBusinessQueryPlan()
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"field", "direction"}:
            raise InvalidBusinessQueryPlan()
        field = item["field"]
        direction = item["direction"]
        if (
            not isinstance(field, str)
            or not isinstance(direction, str)
            or field not in allowed_fields
            or direction not in allowed_directions
            or field in seen
        ):
            raise InvalidBusinessQueryPlan()
        seen.add(field)
