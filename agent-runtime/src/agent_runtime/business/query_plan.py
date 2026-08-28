from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
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
    BusinessQueryOperator,
    BusinessQueryValueType,
    BusinessTextPolicyId,
)
from agent_runtime.business.settings import BusinessConfigurationSnapshot
from agent_runtime.business.region_normalization import normalize_admin_region


_ID = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SLOT_ID = re.compile(r"slot-[1-9][0-9]{0,5}")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}"
)
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
_MULTI_VALUE_OPERATORS = frozenset(
    {
        BusinessQueryOperator.IN,
        BusinessQueryOperator.PREFIX_ANY,
        BusinessQueryOperator.CONTAINS_ANY,
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


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryPlanValueRefs:
    value_refs: tuple[str, ...]


QueryPlanArgumentValue: TypeAlias = QueryPlanLiteral | QueryPlanValueRef | QueryPlanValueRefs


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryFilter:
    field: str
    operator: BusinessQueryOperator
    value: QueryPlanArgumentValue


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQuerySort:
    field: str
    direction: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessListQueryArguments:
    filters: tuple[BusinessQueryFilter, ...]
    page: int
    size: int
    sorts: tuple[BusinessQuerySort, ...]
    keyword: QueryPlanArgumentValue | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeSemanticQueryArguments:
    query: QueryPlanArgumentValue
    size: int


BusinessQueryArguments: TypeAlias = (
    Mapping[str, QueryPlanArgumentValue]
    | BusinessListQueryArguments
    | EmployeeSemanticQueryArguments
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryPlan:
    domain: str
    action: str
    arguments: BusinessQueryArguments

    def __post_init__(self) -> None:
        if isinstance(self.arguments, Mapping):
            object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class ProtectedValueSlots:
    request_id: str
    values: Mapping[str, object]
    logical_fields: Mapping[str, str] = field(default_factory=dict)

    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id or len(self.request_id) > 128:
            raise InvalidProtectedValue()
        copied = dict(self.values)
        if len(copied) > 32 or any(_SLOT_ID.fullmatch(key) is None for key in copied):
            raise InvalidProtectedValue()
        typed = dict(self.logical_fields)
        if (
            any(_SLOT_ID.fullmatch(key) is None or _ID.fullmatch(value) is None for key, value in typed.items())
            or not set(typed).issubset(copied)
        ):
            raise InvalidProtectedValue()
        object.__setattr__(self, "values", MappingProxyType(copied))
        object.__setattr__(self, "logical_fields", MappingProxyType(typed))

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
        if action in {"employee.search", "transaction.search"} and "filters" in arguments:
            return BusinessQueryPlan(
                domain=domain,
                action=action,
                arguments=self._decode_list_arguments(action, arguments),
            )
        if action == "employee.semantic_search":
            return BusinessQueryPlan(
                domain=domain,
                action=action,
                arguments=self._decode_semantic_arguments(arguments),
            )
        decoded: dict[str, QueryPlanArgumentValue] = {}
        for key, raw in arguments.items():
            if not isinstance(key, str) or _ID.fullmatch(key) is None:
                raise InvalidBusinessQueryPlan()
            decoded[key] = self._decode_tagged_value(raw)
        return BusinessQueryPlan(domain=domain, action=action, arguments=decoded)

    @staticmethod
    def _decode_tagged_value(raw: JsonValue) -> QueryPlanArgumentValue:
        if not isinstance(raw, Mapping):
            raise InvalidBusinessQueryPlan()
        if set(raw) == {"literal"}:
            if raw["literal"] is None:
                raise InvalidBusinessQueryPlan()
            return QueryPlanLiteral(value=raw["literal"])
        if set(raw) == {"value_ref"}:
            value_ref = raw["value_ref"]
            if not isinstance(value_ref, str) or _SLOT_ID.fullmatch(value_ref) is None:
                raise InvalidBusinessQueryPlan()
            return QueryPlanValueRef(value_ref=value_ref)
        if set(raw) == {"value_refs"}:
            value_refs = raw["value_refs"]
            if (
                not isinstance(value_refs, tuple)
                or not 1 <= len(value_refs) <= 16
                or len(value_refs) != len(set(value_refs))
                or any(
                    not isinstance(value_ref, str) or _SLOT_ID.fullmatch(value_ref) is None
                    for value_ref in value_refs
                )
            ):
                raise InvalidBusinessQueryPlan()
            return QueryPlanValueRefs(value_refs=tuple(str(value_ref) for value_ref in value_refs))
        raise InvalidBusinessQueryPlan()

    @classmethod
    def _decode_list_arguments(
        cls,
        action: str,
        raw: Mapping[str, JsonValue],
    ) -> BusinessListQueryArguments:
        required = {"filters", "page", "size", "sorts"}
        allowed = required | ({"keyword"} if action == "employee.search" else set())
        if not required.issubset(raw) or not set(raw).issubset(allowed):
            raise InvalidBusinessQueryPlan()
        raw_filters = raw["filters"]
        raw_sorts = raw["sorts"]
        page = raw["page"]
        size = raw["size"]
        if (
            not isinstance(raw_filters, tuple)
            or len(raw_filters) > 8
            or not isinstance(raw_sorts, tuple)
            or len(raw_sorts) > 2
            or type(page) is not int
            or not 1 <= page <= 1000
            or type(size) is not int
            or not 1 <= size <= 50
        ):
            raise InvalidBusinessQueryPlan()
        filters: list[BusinessQueryFilter] = []
        for item in raw_filters:
            if not isinstance(item, Mapping) or set(item) != {"field", "operator", "value"}:
                raise InvalidBusinessQueryPlan()
            field = item["field"]
            operator = item["operator"]
            if not isinstance(field, str) or _ID.fullmatch(field) is None or not isinstance(operator, str):
                raise InvalidBusinessQueryPlan()
            try:
                typed_operator = BusinessQueryOperator(operator)
            except ValueError as exc:
                raise InvalidBusinessQueryPlan() from exc
            value = cls._decode_tagged_value(item["value"])
            if typed_operator in _MULTI_VALUE_OPERATORS and isinstance(value, QueryPlanLiteral):
                if not isinstance(value.value, tuple) or not 1 <= len(value.value) <= 16:
                    raise InvalidBusinessQueryPlan()
            filters.append(BusinessQueryFilter(field=field, operator=typed_operator, value=value))
        sorts: list[BusinessQuerySort] = []
        for item in raw_sorts:
            if not isinstance(item, Mapping) or set(item) != {"field", "direction"}:
                raise InvalidBusinessQueryPlan()
            field = item["field"]
            direction = item["direction"]
            if (
                not isinstance(field, str)
                or _ID.fullmatch(field) is None
                or not isinstance(direction, str)
                or direction not in {"ASC", "DESC"}
            ):
                raise InvalidBusinessQueryPlan()
            sorts.append(BusinessQuerySort(field=field, direction=direction))
        keyword = cls._decode_tagged_value(raw["keyword"]) if "keyword" in raw else None
        if not filters and keyword is None:
            raise InvalidBusinessQueryPlan()
        return BusinessListQueryArguments(
            filters=tuple(filters),
            page=page,
            size=size,
            sorts=tuple(sorts),
            keyword=keyword,
        )

    @classmethod
    def _decode_semantic_arguments(
        cls,
        raw: Mapping[str, JsonValue],
    ) -> EmployeeSemanticQueryArguments:
        if set(raw) != {"query", "size"}:
            raise InvalidBusinessQueryPlan()
        size = raw["size"]
        if type(size) is not int or not 1 <= size <= 50:
            raise InvalidBusinessQueryPlan()
        return EmployeeSemanticQueryArguments(
            query=cls._decode_tagged_value(raw["query"]),
            size=size,
        )


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
            if (
                not isinstance(plan.arguments, Mapping)
                or plan.arguments
                or plan.domain not in self._domains | {"unsupported"}
            ):
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
        if isinstance(plan.arguments, BusinessListQueryArguments):
            if plan.action not in {"employee.search", "transaction.search"}:
                raise InvalidBusinessQueryPlan()
            present_fields = {item.field for item in plan.arguments.filters}
        elif isinstance(plan.arguments, EmployeeSemanticQueryArguments):
            if plan.action != "employee.semantic_search":
                raise InvalidBusinessQueryPlan()
            present_fields = {"query"}
        elif isinstance(plan.arguments, Mapping):
            if plan.action in {"employee.search", "employee.semantic_search"} or (
                definition.code_contract_version.endswith("-v2")
            ):
                raise InvalidBusinessQueryPlan()
            present_fields = set(plan.arguments)
        else:
            raise InvalidBusinessQueryPlan()
        unknown = present_fields - set(definition_fields)
        disabled = present_fields - set(configured_fields)
        if unknown or disabled:
            return UnsupportedBusinessQueryPlan(
                domain=plan.domain,
                config_snapshot_id=snapshot.snapshot_id,
            )
        for logical_name, field in configured_fields.items():
            if field.required and logical_name not in present_fields:
                raise InvalidBusinessQueryPlan()
        if isinstance(plan.arguments, BusinessListQueryArguments):
            self._validate_list_arguments(
                plan.arguments,
                definition_fields=definition_fields,
                configured_fields=configured_fields,
                settings=settings,
                definition=definition,
            )
        elif isinstance(plan.arguments, EmployeeSemanticQueryArguments):
            self._validate_value(
                plan.arguments.query,
                definition=definition_fields["query"],
                settings=configured_fields["query"],
                action_settings=settings,
                definition_action=definition,
            )
            if settings.max_page_size is None or plan.arguments.size > settings.max_page_size:
                raise InvalidBusinessQueryPlan()
        else:
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
            present_fields=present_fields,
        )
        return ValidatedBusinessQueryPlan(
            plan=plan,
            config_snapshot_id=snapshot.snapshot_id,
        )

    @classmethod
    def _validate_list_arguments(
        cls,
        arguments: BusinessListQueryArguments,
        *,
        definition_fields: Mapping[str, BusinessQueryFieldDefinition],
        configured_fields: Mapping[str, BusinessQueryFieldSettings],
        settings: BusinessActionSettings,
        definition: BusinessActionDefinition[Any, Any, Any, Any],
    ) -> None:
        if (
            settings.max_page_size is None
            or arguments.size > settings.max_page_size
            or (settings.max_page is not None and arguments.page > settings.max_page)
            or (arguments.page - 1) * arguments.size > 2147483647
            or (settings.fixed_page is not None and arguments.page != settings.fixed_page)
        ):
            raise InvalidBusinessQueryPlan()
        seen_operators: dict[str, set[BusinessQueryOperator]] = {}
        bounds: dict[str, dict[BusinessQueryOperator, Decimal | datetime]] = {}
        for item in arguments.filters:
            field = definition_fields[item.field]
            configured = configured_fields[item.field]
            if item.operator not in field.allowed_operators or item.operator not in configured.allowed_operators:
                raise InvalidBusinessQueryPlan()
            previous = seen_operators.setdefault(item.field, set())
            if item.operator in previous:
                raise InvalidBusinessQueryPlan()
            if previous:
                selected_combination = frozenset((*previous, item.operator))
                range_combination = frozenset(
                    {BusinessQueryOperator.GT, BusinessQueryOperator.LT}
                )
                allowed_combinations = set(field.allowed_operator_combinations) & set(
                    configured.allowed_operator_combinations
                )
                if (
                    selected_combination != range_combination
                    and selected_combination not in allowed_combinations
                ):
                    raise InvalidBusinessQueryPlan()
            previous.add(item.operator)
            if item.operator in _MULTI_VALUE_OPERATORS and isinstance(item.value, QueryPlanLiteral):
                literal_values = item.value.value
                if not isinstance(literal_values, tuple) or not 1 <= len(literal_values) <= 16:
                    raise InvalidBusinessQueryPlan()
                for literal in literal_values:
                    cls._validate_value(
                        QueryPlanLiteral(value=literal),
                        definition=field,
                        settings=configured,
                        action_settings=settings,
                        definition_action=definition,
                        operator=item.operator,
                    )
            elif item.operator in _MULTI_VALUE_OPERATORS:
                if not isinstance(item.value, QueryPlanValueRefs):
                    raise InvalidBusinessQueryPlan()
                cls._validate_value(
                    item.value,
                    definition=field,
                    settings=configured,
                    action_settings=settings,
                    definition_action=definition,
                    operator=item.operator,
                )
            else:
                if isinstance(item.value, QueryPlanValueRefs) or (
                    isinstance(item.value, QueryPlanLiteral)
                    and isinstance(item.value.value, tuple)
                ):
                    raise InvalidBusinessQueryPlan()
                cls._validate_value(
                    item.value,
                    definition=field,
                    settings=configured,
                    action_settings=settings,
                    definition_action=definition,
                    operator=item.operator,
                )
            if item.operator in {BusinessQueryOperator.GT, BusinessQueryOperator.LT}:
                if not isinstance(item.value, QueryPlanLiteral) or not isinstance(item.value.value, str):
                    raise InvalidBusinessQueryPlan()
                bound: Decimal | datetime
                if field.value_type is BusinessQueryValueType.DECIMAL:
                    bound = Decimal(item.value.value)
                elif field.value_type is BusinessQueryValueType.DATETIME:
                    bound = datetime.fromisoformat(item.value.value)
                else:
                    raise InvalidBusinessQueryPlan()
                bounds.setdefault(item.field, {})[item.operator] = bound
        for values in bounds.values():
            lower = values.get(BusinessQueryOperator.GT)
            upper = values.get(BusinessQueryOperator.LT)
            if lower is not None and upper is not None and lower >= upper:  # type: ignore[operator]
                raise InvalidBusinessQueryPlan()
        _validate_sort_list(
            tuple({"field": item.field, "direction": item.direction} for item in arguments.sorts),
            allowed_fields=settings.allowed_sort_field_ids,
            allowed_directions=settings.allowed_sort_directions,
            maximum_items=settings.max_sort_items,
        )
        if arguments.keyword is not None:
            if (
                definition.descriptor.capability_id != "employee.search"
                or not settings.keyword_enabled
            ):
                raise InvalidBusinessQueryPlan()
            keyword_definition = definition_fields.get("contact_address")
            keyword_settings = configured_fields.get("contact_address")
            if keyword_definition is None or keyword_settings is None:
                raise InvalidBusinessQueryPlan()
            cls._validate_value(
                arguments.keyword,
                definition=keyword_definition,
                settings=keyword_settings,
                action_settings=settings,
                definition_action=definition,
            )

    @staticmethod
    def _validate_value(
        value: QueryPlanArgumentValue,
        *,
        definition: BusinessQueryFieldDefinition,
        settings: BusinessQueryFieldSettings,
        action_settings: BusinessActionSettings,
        definition_action: BusinessActionDefinition[Any, Any, Any, Any],
        operator: BusinessQueryOperator | None = None,
    ) -> None:
        if not settings.allowed_operators or not set(settings.allowed_operators).issubset(
            definition.allowed_operators
        ):
            raise InvalidBusinessQueryPlan("business.plan_snapshot_mismatch")
        if isinstance(value, (QueryPlanValueRef, QueryPlanValueRefs)):
            if definition.input_exposure not in {
                BusinessInputExposure.PROTECTED_REF,
                BusinessInputExposure.LITERAL_OR_PROTECTED_REF,
            }:
                raise InvalidBusinessQueryPlan()
            if isinstance(value, QueryPlanValueRefs) and (
                operator not in _MULTI_VALUE_OPERATORS
                or not 1 <= len(value.value_refs) <= 16
                or len(value.value_refs) != len(set(value.value_refs))
            ):
                raise InvalidBusinessQueryPlan()
            return
        if definition.input_exposure is BusinessInputExposure.PROTECTED_REF:
            raise InvalidBusinessQueryPlan()
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
            text_policy = definition.text_policy_id
            if (
                operator is BusinessQueryOperator.CONTAINS
                and text_policy is BusinessTextPolicyId.SAFE_TOKEN
            ):
                text_policy = BusinessTextPolicyId.SAFE_CONTAINS_TOKEN
            if not _matches_text_policy(literal, text_policy):
                raise InvalidBusinessQueryPlan()
            if definition.normalization_profile is not None and normalize_admin_region(
                literal,
                profile=settings.normalization_profile,
            ) is None:
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
        if definition.value_type is BusinessQueryValueType.DATETIME:
            if not isinstance(literal, str) or _TIMESTAMP.fullmatch(literal) is None:
                raise InvalidBusinessQueryPlan()
            try:
                parsed = datetime.fromisoformat(literal)
            except ValueError as exc:
                raise InvalidBusinessQueryPlan() from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
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
        present_fields: set[str],
    ) -> None:
        active_rules = set(settings.combination_rule_ids)
        rules = {item.rule_id: item for item in definition.combination_rules}
        if active_rules != set(rules):
            raise InvalidBusinessQueryPlan("business.plan_snapshot_mismatch")
        present = present_fields
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
        planned = plan.plan.arguments
        if isinstance(planned, BusinessListQueryArguments):
            arguments["filters"] = tuple(
                {
                    "field": item.field,
                    "operator": item.operator.value,
                    "value": self._bind_value(
                        item.value,
                        slots=slots,
                        used_refs=used_refs,
                        expected_logical_name=item.field,
                    ),
                }
                for item in planned.filters
            )
            arguments["page"] = planned.page
            arguments["size"] = planned.size
            arguments["sorts"] = tuple(
                {"field": item.field, "direction": item.direction}
                for item in planned.sorts
            )
            if planned.keyword is not None:
                arguments["keyword"] = self._bind_value(
                    planned.keyword,
                    slots=slots,
                    used_refs=used_refs,
                    expected_logical_name="contact_address",
                )
        elif isinstance(planned, EmployeeSemanticQueryArguments):
            arguments["query"] = self._bind_value(
                planned.query,
                slots=slots,
                used_refs=used_refs,
                expected_logical_name="query",
            )
            arguments["size"] = planned.size
        else:
            for logical_name, value in planned.items():
                arguments[logical_name] = self._bind_value(
                    value,
                    slots=slots,
                    used_refs=used_refs,
                    expected_logical_name=logical_name,
                )
        return ActionCandidate(
            capability_id=plan.plan.action,
            arguments=arguments,
        )

    @staticmethod
    def _bind_value(
        value: QueryPlanArgumentValue,
        *,
        slots: ProtectedValueSlots,
        used_refs: set[str],
        expected_logical_name: str,
    ) -> JsonValue:
        if isinstance(value, QueryPlanLiteral):
            return value.value
        references = (
            (value.value_ref,)
            if isinstance(value, QueryPlanValueRef)
            else value.value_refs
        )
        if (
            any(reference in used_refs or reference not in slots.values for reference in references)
            or any(
                reference in slots.logical_fields
                and slots.logical_fields[reference] != expected_logical_name
                for reference in references
            )
            or isinstance(value, QueryPlanValueRefs)
            and any(reference not in slots.logical_fields for reference in references)
        ):
            raise InvalidProtectedValue()
        used_refs.update(references)
        raw: object = (
            tuple(slots.values[reference] for reference in references)
            if isinstance(value, QueryPlanValueRefs)
            else slots.values[references[0]]
        )
        try:
            frozen = freeze_json_object(
                {"value": raw},
                max_bytes=65536,
                max_depth=8,
                max_collection_items=128,
            )
        except ContractViolation as exc:
            raise InvalidProtectedValue() from exc
        return frozen["value"]


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
