from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from collections.abc import Mapping
from typing import Any, Literal, cast

from agent_runtime.capability_api.contracts import InvalidCapabilityArguments, JsonObject
from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessActionSettings,
    BusinessHttpRequest,
    InvalidBusinessArguments,
    InvalidBusinessWireResponse,
    BusinessQueryOperator,
    business_query_v2_action_contract,
)
from agent_runtime.business.wire_json import (
    BusinessWireJsonEncoder,
    BusinessWireJsonValue,
    ExactDecimal,
)
from agent_runtime.adapters.transaction.contracts import (
    TransactionRecord,
    TransactionSearchCondition,
    TransactionSearchInput,
    TransactionSearchWireRequest,
    TransactionSearchWireResponse,
    TransactionSort,
    TransactionListFilter,
    TransactionListRecord,
    TransactionListSearchCondition,
    TransactionListSearchInput,
    TransactionListSearchWireRequest,
    TransactionListSearchWireResponse,
    TransactionListSort,
)

_AMOUNT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?")
_MAX_AMOUNT = Decimal("9999999999999999.99")
_MAX_AMOUNT_SCALE = 2
_BIDI = {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
_ARGUMENT_KEYS = {"trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt", "size", "sorts"}
_FILTER_KEYS = ("trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt")
_ROW_WIDE = {"transDate", "transDateGt", "transDateLt", "amountGt", "amountLt", "transTypeContains"}
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}"
)
_SHANGHAI = timezone(timedelta(hours=8))


def _text(value: object, *, contains: bool = False) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    normalized = unicodedata.normalize("NFC", value.strip())
    if not 1 <= len(normalized) <= 128 or any(unicodedata.category(character) == "Cc" or unicodedata.bidirectional(character) in _BIDI for character in normalized):
        raise InvalidCapabilityArguments("business.invalid_arguments")
    if contains and any(character in "%_\\" for character in normalized):
        raise InvalidCapabilityArguments("business.invalid_arguments")
    return normalized


def _amount(value: object) -> Decimal | None:
    if value is None:
        return None
    if type(value) is not str or _AMOUNT.fullmatch(value) is None:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    try:
        decimal = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidCapabilityArguments("business.invalid_arguments") from exc
    exponent = decimal.as_tuple().exponent
    if not isinstance(exponent, int) or not decimal.is_finite() or abs(decimal) > _MAX_AMOUNT or max(0, -exponent) > _MAX_AMOUNT_SCALE:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    return decimal


class TransactionSearchArgumentValidator:
    def validate(self, arguments: JsonObject) -> TransactionSearchInput:
        if not set(arguments).issubset(_ARGUMENT_KEYS):
            raise InvalidCapabilityArguments("business.invalid_arguments")
        trans_id = _text(arguments.get("trans_id"))
        trans_type = _text(arguments.get("trans_type"))
        trans_type_contains = _text(arguments.get("trans_type_contains"), contains=True)
        amount = _amount(arguments.get("amount"))
        amount_gt = _amount(arguments.get("amount_gt"))
        amount_lt = _amount(arguments.get("amount_lt"))
        if trans_type is not None and trans_type_contains is not None:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        if amount is not None and (amount_gt is not None or amount_lt is not None):
            raise InvalidCapabilityArguments("business.invalid_arguments")
        if amount_gt is not None and amount_lt is not None and amount_gt >= amount_lt:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        if not any(value is not None for value in (trans_id, trans_type, trans_type_contains, amount, amount_gt, amount_lt)):
            raise InvalidCapabilityArguments("business.invalid_arguments")
        raw_size = arguments.get("size")
        if raw_size is None:
            size = None
        elif type(raw_size) is int and 1 <= raw_size <= 50:
            size = raw_size
        else:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        raw_sorts = arguments.get("sorts", ())
        if type(raw_sorts) is not tuple or len(raw_sorts) > 2:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        sorts: list[TransactionSort] = []
        seen: set[str] = set()
        for raw in raw_sorts:
            if not isinstance(raw, Mapping):
                raise InvalidCapabilityArguments("business.invalid_arguments")
            if set(raw) != {"field", "direction"}:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            field, direction = raw["field"], raw["direction"]
            if type(field) is not str or type(direction) is not str:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            if field not in {"trans_id", "trans_type", "amount"} or direction not in {"ASC", "DESC"} or field in seen:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            seen.add(field)
            sorts.append(TransactionSort(field=cast(Any, field), direction=cast(Any, direction)))
        return TransactionSearchInput(
            trans_id=trans_id, trans_type=trans_type, trans_type_contains=trans_type_contains,
            amount=amount, amount_gt=amount_gt, amount_lt=amount_lt,
            size=size, sorts=tuple(sorts),
        )


class TransactionSearchRequestMapper:
    def map(self, input: TransactionSearchInput, settings: BusinessActionSettings) -> TransactionSearchWireRequest:
        allowed_filters = set(settings.allowed_filter_field_ids or ())
        present = {name for name in _FILTER_KEYS if getattr(input, name) is not None}
        if not present.issubset(allowed_filters):
            raise InvalidBusinessArguments("business.invalid_arguments")
        allowed_sorts = set(settings.allowed_sort_field_ids or ())
        if any(item.field not in allowed_sorts for item in input.sorts):
            raise InvalidBusinessArguments("business.invalid_arguments")
        if settings.max_page_size is None or settings.max_result_count is None:
            raise InvalidBusinessArguments("business.invalid_arguments")
        effective_max = min(settings.max_page_size, settings.max_result_count)
        size = min(20, effective_max) if input.size is None else input.size
        if not 1 <= size <= effective_max:
            raise InvalidBusinessArguments("business.invalid_arguments")
        return TransactionSearchWireRequest(
            condition=TransactionSearchCondition(
                trans_id=input.trans_id, trans_type=input.trans_type, trans_type_contains=input.trans_type_contains,
                amount=input.amount, amount_gt=input.amount_gt, amount_lt=input.amount_lt,
            ),
            sorts=input.sorts, page=1, size=size,
        )


class TransactionSearchWireCodec:
    _CONDITION_NAMES = {
        "trans_id": "transId", "trans_type": "transType", "trans_type_contains": "transTypeContains",
        "amount": "amount", "amount_gt": "amountGt", "amount_lt": "amountLt",
    }
    _SORT_NAMES = {"trans_id": "transId", "trans_type": "transType", "amount": "amount"}

    def encode(self, request: TransactionSearchWireRequest) -> BusinessHttpRequest:
        condition: dict[str, BusinessWireJsonValue] = {}
        for source, target in self._CONDITION_NAMES.items():
            value = getattr(request.condition, source)
            if value is None:
                continue
            condition[target] = ExactDecimal.from_decimal(value) if type(value) is Decimal else value
        sorts = tuple({"field": self._SORT_NAMES[item.field], "direction": item.direction} for item in request.sorts)
        wire_body: dict[str, BusinessWireJsonValue] = {
            "condition": condition,
            "page": request.page,
            "size": request.size,
            "sorts": sorts,
        }
        body = BusinessWireJsonEncoder().encode(
            wire_body,
            max_bytes=4096,
        )
        return BusinessHttpRequest(method="POST", relative_path="/txn/search", query=(), json_body=body)

    def decode_success(
        self,
        *,
        request: TransactionSearchWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> TransactionSearchWireResponse:
        if not 200 <= response.status_code < 300 or response.status_code == 204 or response.content_type != "application/json" or response.body is None or len(response.body) > 262144:
            raise InvalidBusinessWireResponse("business.invalid_response")
        if response.body.startswith(b"\xef\xbb\xbf"):
            raise InvalidBusinessWireResponse("business.invalid_response")
        try:
            raw = json.loads(
                response.body.decode("utf-8"),
                object_pairs_hook=_unique,
                parse_float=Decimal,
                parse_int=int,
                parse_constant=lambda _: (_ for _ in ()).throw(InvalidBusinessWireResponse("business.invalid_response")),
            )
        except (UnicodeError, json.JSONDecodeError, InvalidBusinessWireResponse) as exc:
            raise InvalidBusinessWireResponse("business.invalid_response") from exc
        if type(raw) is not dict or set(raw) != {"rows", "total", "totalExact", "page", "size"}:
            raise InvalidBusinessWireResponse("business.invalid_response")
        if type(raw["rows"]) is not list or type(raw["total"]) is not int or type(raw["totalExact"]) is not bool or type(raw["page"]) is not int or type(raw["size"]) is not int:
            raise InvalidBusinessWireResponse("business.invalid_response")
        if raw["page"] != request.page or raw["size"] != request.size or not 0 <= raw["total"] <= 2**63 - 1 or len(raw["rows"]) > request.size:
            raise InvalidBusinessWireResponse("business.invalid_response")
        rows = tuple(self._row(item) for item in raw["rows"])
        return TransactionSearchWireResponse(rows=rows, total=raw["total"], total_exact=raw["totalExact"], page=raw["page"], size=raw["size"])

    @staticmethod
    def _row(raw: object) -> TransactionRecord:
        if type(raw) is not dict or not {"transId", "transType", "amount"}.issubset(raw) or not set(raw).issubset({"transId", "transType", "amount"} | _ROW_WIDE):
            raise InvalidBusinessWireResponse("business.invalid_response")
        trans_id = _wire_text(raw["transId"])
        trans_type = _wire_text(raw["transType"])
        amount_raw = raw["amount"]
        if type(amount_raw) is int:
            amount = Decimal(amount_raw)
        elif type(amount_raw) is Decimal:
            amount = amount_raw
        else:
            raise InvalidBusinessWireResponse("business.invalid_response")
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int) or not amount.is_finite() or abs(amount) > _MAX_AMOUNT or max(0, -exponent) > _MAX_AMOUNT_SCALE:
            raise InvalidBusinessWireResponse("business.invalid_response")
        return TransactionRecord(trans_id=trans_id, trans_type=trans_type, amount=amount)


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidBusinessWireResponse("business.invalid_response")
        result[key] = value
    return result


def _wire_text(value: object) -> str:
    if type(value) is not str:
        raise InvalidBusinessWireResponse("business.invalid_response")
    normalized = unicodedata.normalize("NFC", value)
    if not 1 <= len(normalized) <= 128 or any(unicodedata.category(character) == "Cc" or unicodedata.bidirectional(character) in _BIDI for character in normalized):
        raise InvalidBusinessWireResponse("business.invalid_response")
    return normalized


def _strict_text(value: object, *, contains: bool = False) -> str:
    normalized = _text(value, contains=contains)
    if normalized is None or normalized != value:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    return normalized


def _strict_datetime(value: object) -> datetime:
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidCapabilityArguments("business.invalid_arguments") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    return result


class TransactionListSearchArgumentValidator:
    def validate(self, arguments: JsonObject) -> TransactionListSearchInput:
        if set(arguments) != {"filters", "page", "size", "sorts"}:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        raw_filters = arguments["filters"]
        raw_sorts = arguments["sorts"]
        page = arguments["page"]
        size = arguments["size"]
        if (
            type(raw_filters) is not tuple
            or not 1 <= len(raw_filters) <= 8
            or type(raw_sorts) is not tuple
            or len(raw_sorts) > 2
            or type(page) is not int
            or not 1 <= page <= 1000
            or type(size) is not int
            or not 1 <= size <= 50
            or (page - 1) * size > 2147483647
        ):
            raise InvalidCapabilityArguments("business.invalid_arguments")

        contract = business_query_v2_action_contract("transaction.search")
        definitions = {field.logical_name: field for field in contract.query_fields}
        filters: list[TransactionListFilter] = []
        operators: dict[str, set[str]] = {}
        bounds: dict[str, dict[str, Decimal | datetime]] = {}
        for raw in raw_filters:
            if not isinstance(raw, Mapping) or set(raw) != {"field", "operator", "value"}:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            field = raw["field"]
            operator = raw["operator"]
            if type(field) is not str or type(operator) is not str or field not in definitions:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            try:
                selected_operator = BusinessQueryOperator(operator)
            except ValueError as exc:
                raise InvalidCapabilityArguments("business.invalid_arguments") from exc
            if selected_operator not in definitions[field].allowed_operators:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            selected = operators.setdefault(field, set())
            if operator in selected or "eq" in selected or operator == "eq" and selected:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            if operator == "contains" and selected:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            selected.add(operator)

            value: str | Decimal | datetime
            if field in {"trans_id", "trans_type"}:
                value = _strict_text(raw["value"], contains=operator == "contains")
            elif field == "trans_date":
                value = _strict_datetime(raw["value"])
            else:
                decimal = _amount(raw["value"])
                if decimal is None or decimal.is_zero() and str(raw["value"]).startswith("-"):
                    raise InvalidCapabilityArguments("business.invalid_arguments")
                value = decimal
            if operator in {"gt", "lt"}:
                if not isinstance(value, (datetime, Decimal)):
                    raise InvalidCapabilityArguments("business.invalid_arguments")
                bounds.setdefault(field, {})[operator] = value
            filters.append(TransactionListFilter(field=field, operator=operator, value=value))

        for values in bounds.values():
            lower, upper = values.get("gt"), values.get("lt")
            if lower is not None and upper is not None and lower >= upper:  # type: ignore[operator]
                raise InvalidCapabilityArguments("business.invalid_arguments")

        sorts: list[TransactionListSort] = []
        seen: set[str] = set()
        for raw in raw_sorts:
            if not isinstance(raw, Mapping) or set(raw) != {"field", "direction"}:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            field, direction = raw["field"], raw["direction"]
            if (
                type(field) is not str
                or field not in contract.allowed_sort_fields
                or field in seen
                or type(direction) is not str
                or direction not in {"ASC", "DESC"}
            ):
                raise InvalidCapabilityArguments("business.invalid_arguments")
            seen.add(field)
            sorts.append(TransactionListSort(field=field, direction=direction))

        return TransactionListSearchInput(
            filters=tuple(filters), page=page, size=size, sorts=tuple(sorts)
        )


class TransactionListSearchRequestMapper:
    _CONDITION_ATTRIBUTES: dict[tuple[str, str], str] = {
        ("trans_id", "eq"): "trans_id",
        ("trans_type", "eq"): "trans_type",
        ("trans_type", "contains"): "trans_type_contains",
        ("trans_date", "eq"): "trans_date",
        ("trans_date", "gt"): "trans_date_gt",
        ("trans_date", "lt"): "trans_date_lt",
        ("amount", "eq"): "amount",
        ("amount", "gt"): "amount_gt",
        ("amount", "lt"): "amount_lt",
    }

    def map(
        self, input: TransactionListSearchInput, settings: BusinessActionSettings
    ) -> TransactionListSearchWireRequest:
        if (
            settings.config_version != "business-query-v2"
            or settings.code_contract_version != "transaction-search-plan-v2"
            or settings.service_contract_ref != "transaction.search.v1"
            or settings.max_page_size is None
            or settings.max_result_count is None
            or settings.max_page is None
            or input.page > settings.max_page
            or input.size > min(settings.max_page_size, settings.max_result_count)
            or (input.page - 1) * input.size > 2147483647
            or not input.filters
        ):
            raise InvalidBusinessArguments("business.invalid_arguments")

        enabled = {item.logical_name: item for item in settings.query_fields if item.enabled}
        allowed_fields = frozenset(settings.allowed_filter_field_ids or ())
        values: dict[str, str | Decimal | datetime] = {}
        for item in input.filters:
            configured = enabled.get(item.field)
            target = self._CONDITION_ATTRIBUTES.get((item.field, item.operator))
            if (
                item.field not in allowed_fields
                or configured is None
                or target is None
                or item.operator not in {operator.value for operator in configured.allowed_operators}
            ):
                raise InvalidBusinessArguments("business.invalid_arguments")
            if isinstance(item.value, Decimal):
                self._validate_configured_amount(item.value, settings)
            values[target] = item.value

        lower = values.get("trans_date_gt")
        upper = values.get("trans_date_lt")
        if isinstance(lower, datetime) and isinstance(upper, datetime):
            if (
                settings.max_time_range_days is None
                or upper - lower > timedelta(days=settings.max_time_range_days)
            ):
                raise InvalidBusinessArguments("business.invalid_arguments")

        directions = frozenset(settings.allowed_sort_directions or ())
        allowed_sorts = frozenset(settings.allowed_sort_field_ids or ())
        if settings.max_sort_items is None or len(input.sorts) > settings.max_sort_items:
            raise InvalidBusinessArguments("business.invalid_arguments")
        for sort_item in input.sorts:
            if sort_item.field not in allowed_sorts or sort_item.direction not in directions:
                raise InvalidBusinessArguments("business.invalid_arguments")

        return TransactionListSearchWireRequest(
            condition=TransactionListSearchCondition(**values),  # type: ignore[arg-type]
            sorts=input.sorts,
            page=input.page,
            size=input.size,
        )

    @staticmethod
    def _validate_configured_amount(value: Decimal, settings: BusinessActionSettings) -> None:
        if settings.max_decimal_abs is None or settings.max_decimal_scale is None:
            raise InvalidBusinessArguments("business.invalid_arguments")
        exponent = value.as_tuple().exponent
        if (
            not isinstance(exponent, int)
            or abs(value) > Decimal(settings.max_decimal_abs)
            or max(0, -exponent) > settings.max_decimal_scale
        ):
            raise InvalidBusinessArguments("business.invalid_arguments")


class TransactionListSearchWireCodec:
    _CONDITION_NAMES = {
        "trans_id": "transId",
        "trans_type": "transType",
        "trans_type_contains": "transTypeContains",
        "trans_date": "transDate",
        "trans_date_gt": "transDateGt",
        "trans_date_lt": "transDateLt",
        "amount": "amount",
        "amount_gt": "amountGt",
        "amount_lt": "amountLt",
    }
    _SORT_NAMES = {
        "trans_id": "transId",
        "trans_type": "transType",
        "trans_date": "transDate",
        "amount": "amount",
    }
    _ROW_FIELDS = frozenset(_CONDITION_NAMES.values())

    def encode(self, request: TransactionListSearchWireRequest) -> BusinessHttpRequest:
        condition: dict[str, BusinessWireJsonValue] = {}
        for source, target in self._CONDITION_NAMES.items():
            value = getattr(request.condition, source)
            if isinstance(value, Decimal):
                condition[target] = ExactDecimal.from_decimal(value)
            elif isinstance(value, datetime):
                condition[target] = value.isoformat(timespec="seconds")
            elif value is not None:
                condition[target] = value
        sorts = tuple(
            {"field": self._SORT_NAMES[item.field], "direction": item.direction}
            for item in request.sorts
        )
        return BusinessHttpRequest(
            method="POST",
            relative_path="/txn/search",
            query=(),
            json_body=BusinessWireJsonEncoder().encode(
                {"condition": condition, "page": request.page, "size": request.size, "sorts": sorts},
                max_bytes=4096,
            ),
        )

    def decode_success(
        self,
        *,
        request: TransactionListSearchWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> TransactionListSearchWireResponse:
        if (
            not 200 <= response.status_code < 300
            or response.status_code == 204
            or response.content_type != "application/json"
            or response.body is None
            or len(response.body) > 262144
            or response.body.startswith(b"\xef\xbb\xbf")
        ):
            raise InvalidBusinessWireResponse("business.invalid_response")
        try:
            raw = json.loads(
                response.body.decode("utf-8"),
                object_pairs_hook=_unique,
                parse_float=Decimal,
                parse_int=int,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    InvalidBusinessWireResponse("business.invalid_response")
                ),
            )
        except (UnicodeError, json.JSONDecodeError, InvalidBusinessWireResponse) as exc:
            raise InvalidBusinessWireResponse("business.invalid_response") from exc
        if type(raw) is not dict or set(raw) != {"rows", "total", "totalExact", "page", "size"}:
            raise InvalidBusinessWireResponse("business.invalid_response")
        if (
            type(raw["rows"]) is not list
            or type(raw["total"]) is not int
            or type(raw["totalExact"]) is not bool
            or type(raw["page"]) is not int
            or type(raw["size"]) is not int
            or raw["page"] != request.page
            or raw["size"] != request.size
            or not 0 <= raw["total"] <= 2**63 - 1
            or len(raw["rows"]) > request.size
        ):
            raise InvalidBusinessWireResponse("business.invalid_response")
        return TransactionListSearchWireResponse(
            rows=tuple(self._row(item) for item in raw["rows"]),
            total=raw["total"],
            total_exact=raw["totalExact"],
            page=raw["page"],
            size=raw["size"],
        )

    @classmethod
    def _row(cls, raw: object) -> TransactionListRecord:
        if (
            type(raw) is not dict
            or not {"transId", "transType", "transDate", "amount"}.issubset(raw)
            or not set(raw).issubset(cls._ROW_FIELDS)
        ):
            raise InvalidBusinessWireResponse("business.invalid_response")
        trans_date = cls._date(raw["transDate"])
        raw_amount = raw["amount"]
        if type(raw_amount) is int:
            amount = Decimal(raw_amount)
        elif type(raw_amount) is Decimal:
            amount = raw_amount
        else:
            raise InvalidBusinessWireResponse("business.invalid_response")
        exponent = amount.as_tuple().exponent
        if (
            not isinstance(exponent, int)
            or not amount.is_finite()
            or abs(amount) > _MAX_AMOUNT
            or max(0, -exponent) > _MAX_AMOUNT_SCALE
        ):
            raise InvalidBusinessWireResponse("business.invalid_response")
        return TransactionListRecord(
            trans_id=_wire_text(raw["transId"]),
            trans_type=_wire_text(raw["transType"]),
            trans_date=trans_date,
            amount=amount,
        )

    @staticmethod
    def _date(value: object) -> datetime | None:
        if value is None:
            return None
        if type(value) is not int or value % 1000 != 0:
            raise InvalidBusinessWireResponse("business.invalid_response")
        try:
            return datetime.fromtimestamp(value // 1000, tz=timezone.utc).astimezone(_SHANGHAI)
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidBusinessWireResponse("business.invalid_response") from exc
