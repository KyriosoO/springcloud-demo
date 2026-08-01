from __future__ import annotations

import json
import re
import unicodedata
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
)

_AMOUNT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,4})?")
_MAX_AMOUNT = Decimal("9999999999999999.9999")
_BIDI = {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
_ARGUMENT_KEYS = {"trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt", "size", "sorts"}
_FILTER_KEYS = ("trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt")
_ROW_WIDE = {"transDate", "transDateGt", "transDateLt", "amountGt", "amountLt", "transTypeContains"}


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
    if not isinstance(exponent, int) or not decimal.is_finite() or abs(decimal) > _MAX_AMOUNT or max(0, -exponent) > 4:
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
        if not isinstance(exponent, int) or not amount.is_finite() or abs(amount) > _MAX_AMOUNT or max(0, -exponent) > 4:
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
