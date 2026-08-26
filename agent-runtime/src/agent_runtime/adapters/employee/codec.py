from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from typing import cast
from urllib.parse import quote

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
from agent_runtime.adapters.employee.contracts import (
    EmployeeDetailInput,
    EmployeeDetailWireRequest,
    EmployeeDetailWireResponse,
    EmployeeSearchFilter,
    EmployeeSearchInput,
    EmployeeSearchRecord,
    EmployeeSearchSort,
    EmployeeSearchWireFilter,
    EmployeeSearchWireRequest,
    EmployeeSearchWireResponse,
    EmployeeSemanticSearchInput,
    EmployeeSemanticSearchWireRequest,
)
from agent_runtime.business.wire_json import BusinessWireJsonEncoder, BusinessWireJsonValue
from agent_runtime.model.contracts import QuestionDataClass
from agent_runtime.model.question_policy import DENY_CLASSES, classify_question

_BIDI = {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
_TARGETS = {"idCardNo", "memberNo", "chineseName", "publicEmail", "position"}


def _normalize(value: object, *, minimum: int, maximum: int, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if type(value) is not str:
        raise InvalidBusinessWireResponse("business.invalid_response")
    normalized = unicodedata.normalize("NFC", value)
    if not minimum <= len(normalized) <= maximum or any(unicodedata.category(character) == "Cc" or unicodedata.bidirectional(character) in _BIDI for character in normalized):
        raise InvalidBusinessWireResponse("business.invalid_response")
    return normalized


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidBusinessWireResponse("business.invalid_response")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise InvalidBusinessWireResponse("business.invalid_response")


class EmployeeDetailArgumentValidator:
    def validate(self, arguments: JsonObject) -> EmployeeDetailInput:
        if set(arguments) != {"employee_identifier"} or type(arguments.get("employee_identifier")) is not str:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        raw = arguments["employee_identifier"]
        assert isinstance(raw, str)
        normalized = unicodedata.normalize("NFC", raw.strip())
        if not 5 <= len(normalized) <= 64 or len(normalized.encode("utf-8")) > 192:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        if any(character.isspace() or unicodedata.category(character) == "Cc" or unicodedata.bidirectional(character) in _BIDI or character in "/\\%?#" for character in normalized):
            raise InvalidCapabilityArguments("business.invalid_arguments")
        return EmployeeDetailInput(employee_identifier=normalized)


class EmployeeDetailRequestMapper:
    def map(self, input: EmployeeDetailInput, settings: BusinessActionSettings) -> EmployeeDetailWireRequest:
        if settings.max_result_count != 1:
            raise InvalidBusinessArguments("business.invalid_arguments")
        return EmployeeDetailWireRequest(employee_identifier=input.employee_identifier)


class EmployeeDetailWireCodec:
    def encode(self, request: EmployeeDetailWireRequest) -> BusinessHttpRequest:
        encoded = quote(request.employee_identifier, safe="", encoding="utf-8", errors="strict")
        return BusinessHttpRequest(method="GET", relative_path=f"/employees/{encoded}", query=(), json_body=None)

    def decode_success(
        self,
        *,
        request: EmployeeDetailWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> EmployeeDetailWireResponse:
        if not 200 <= response.status_code < 300 or response.status_code == 204 or response.content_type != "application/json" or response.body is None or len(response.body) > 65536:
            raise InvalidBusinessWireResponse("business.invalid_response")
        try:
            raw = json.loads(
                response.body.decode("utf-8"),
                object_pairs_hook=_unique,
                parse_constant=_reject_constant,
            )
        except (UnicodeError, json.JSONDecodeError, InvalidBusinessWireResponse) as exc:
            raise InvalidBusinessWireResponse("business.invalid_response") from exc
        if type(raw) is not dict or not _TARGETS.issubset(raw):
            raise InvalidBusinessWireResponse("business.invalid_response")
        id_card = _normalize(raw["idCardNo"], minimum=5, maximum=64)
        assert isinstance(id_card, str)
        if id_card != request.employee_identifier:
            raise InvalidBusinessWireResponse("business.invalid_response")
        return EmployeeDetailWireResponse(
            id_card_no=id_card,
            member_no=_normalize(raw["memberNo"], minimum=5, maximum=64, optional=True),
            chinese_name=_required(_normalize(raw["chineseName"], minimum=1, maximum=128)),
            public_email=_normalize(raw["publicEmail"], minimum=1, maximum=254, optional=True),
            position=_normalize(raw["position"], minimum=1, maximum=256, optional=True),
        )


def _required(value: str | None) -> str:
    if value is None:
        raise InvalidBusinessWireResponse("business.invalid_response")
    return value


def _argument_text(raw: object, *, maximum: int = 128) -> str:
    if type(raw) is not str:
        raise InvalidCapabilityArguments("business.invalid_arguments")
    normalized = unicodedata.normalize("NFC", raw)
    if (
        normalized != raw
        or not 1 <= len(normalized) <= maximum
        or normalized != normalized.strip()
        or any(
            unicodedata.category(character).startswith("C")
            or unicodedata.bidirectional(character) in _BIDI
            for character in normalized
        )
    ):
        raise InvalidCapabilityArguments("business.invalid_arguments")
    return normalized


class EmployeeSearchArgumentValidator:
    def validate(self, arguments: JsonObject) -> EmployeeSearchInput:
        required = {"filters", "page", "size", "sorts"}
        if not required.issubset(arguments) or not set(arguments).issubset(required | {"keyword"}):
            raise InvalidCapabilityArguments("business.invalid_arguments")
        raw_filters = arguments["filters"]
        raw_sorts = arguments["sorts"]
        page = arguments["page"]
        size = arguments["size"]
        if (
            type(raw_filters) is not tuple
            or len(raw_filters) > 8
            or type(raw_sorts) is not tuple
            or len(raw_sorts) > 2
            or type(page) is not int
            or not 1 <= page <= 1000
            or type(size) is not int
            or not 1 <= size <= 50
        ):
            raise InvalidCapabilityArguments("business.invalid_arguments")

        contract = business_query_v2_action_contract("employee.search")
        definitions = {item.logical_name: item for item in contract.query_fields}
        filters: list[EmployeeSearchFilter] = []
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
            selected_value: str | tuple[str, ...]
            if selected_operator is BusinessQueryOperator.IN:
                raw_values = raw["value"]
                if type(raw_values) is not tuple or not 1 <= len(raw_values) <= 16:
                    raise InvalidCapabilityArguments("business.invalid_arguments")
                selected_value = tuple(_argument_text(value) for value in raw_values)
            else:
                selected_value = _argument_text(raw["value"])
            filters.append(EmployeeSearchFilter(field=field, operator=operator, value=selected_value))

        sorts: list[EmployeeSearchSort] = []
        seen: set[str] = set()
        for raw in raw_sorts:
            if not isinstance(raw, Mapping) or set(raw) != {"field", "direction"}:
                raise InvalidCapabilityArguments("business.invalid_arguments")
            field = raw["field"]
            direction = raw["direction"]
            if (
                type(field) is not str
                or field not in contract.allowed_sort_fields
                or field in seen
                or type(direction) is not str
                or direction not in {"ASC", "DESC"}
            ):
                raise InvalidCapabilityArguments("business.invalid_arguments")
            seen.add(field)
            sorts.append(EmployeeSearchSort(field=field, direction=direction))

        keyword = _argument_text(arguments["keyword"]) if "keyword" in arguments else None
        if not filters and keyword is None:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        return EmployeeSearchInput(
            filters=tuple(filters), page=page, size=size, sorts=tuple(sorts), keyword=keyword
        )


class EmployeeSearchRequestMapper:
    def map(self, input: EmployeeSearchInput, settings: BusinessActionSettings) -> EmployeeSearchWireRequest:
        if (
            settings.max_page_size is None
            or settings.max_result_count is None
            or input.size > min(settings.max_page_size, settings.max_result_count)
            or (settings.max_page is not None and input.page > settings.max_page)
            or input.keyword is not None and not settings.keyword_enabled
            or not input.filters and input.keyword is None
        ):
            raise InvalidBusinessArguments("business.invalid_arguments")
        offset = (input.page - 1) * input.size
        if offset > 2147483647:
            raise InvalidBusinessArguments("business.invalid_arguments")
        configured = {
            item.logical_name: item for item in settings.query_fields if item.enabled
        }
        allowed_filters = frozenset(settings.allowed_filter_field_ids or ())
        wire_filters: list[EmployeeSearchWireFilter] = []
        for item in input.filters:
            selected = configured.get(item.field)
            if (
                item.field not in allowed_filters
                or selected is None
                or selected.service_field is None
                or item.operator not in {operator.value for operator in selected.allowed_operators}
            ):
                raise InvalidBusinessArguments("business.invalid_arguments")
            if item.operator == BusinessQueryOperator.IN.value:
                if type(item.value) is not tuple:
                    raise InvalidBusinessArguments("business.invalid_arguments")
                wire_filters.append(
                    EmployeeSearchWireFilter(
                        field=selected.service_field, operator=item.operator, values=item.value
                    )
                )
            elif type(item.value) is str:
                wire_filters.append(
                    EmployeeSearchWireFilter(
                        field=selected.service_field, operator=item.operator, value=item.value
                    )
                )
            else:
                raise InvalidBusinessArguments("business.invalid_arguments")

        allowed_sorts = frozenset(settings.allowed_sort_field_ids or ())
        directions = frozenset(settings.allowed_sort_directions or ())
        if settings.max_sort_items is None or len(input.sorts) > settings.max_sort_items:
            raise InvalidBusinessArguments("business.invalid_arguments")
        wire_sorts: list[EmployeeSearchSort] = []
        for selected_sort in input.sorts:
            selected = configured.get(selected_sort.field)
            if (
                selected_sort.field not in allowed_sorts
                or selected is None
                or selected.service_field is None
                or selected_sort.direction not in directions
            ):
                raise InvalidBusinessArguments("business.invalid_arguments")
            wire_sorts.append(
                EmployeeSearchSort(field=selected.service_field, direction=selected_sort.direction)
            )
        return EmployeeSearchWireRequest(
            filters=tuple(wire_filters), from_index=offset, size=input.size,
            sorts=tuple(wire_sorts), keyword=input.keyword,
        )


class EmployeeSearchWireCodec:
    def encode(self, request: EmployeeSearchWireRequest) -> BusinessHttpRequest:
        filters: list[BusinessWireJsonValue] = []
        for item in request.filters:
            encoded: dict[str, BusinessWireJsonValue] = {
                "field": item.field,
                "operator": item.operator,
            }
            if item.values is not None:
                encoded["values"] = item.values
            elif item.value is not None:
                encoded["value"] = item.value
            else:
                raise InvalidBusinessArguments("business.invalid_arguments")
            filters.append(encoded)
        payload: dict[str, BusinessWireJsonValue] = {
            "filters": tuple(filters),
            "from": request.from_index,
            "size": request.size,
            "sorts": tuple(
                {"field": item.field, "direction": item.direction} for item in request.sorts
            ),
        }
        if request.keyword is not None:
            payload["keyword"] = request.keyword
        return BusinessHttpRequest(
            method="POST",
            relative_path="/employees/es/search",
            query=(),
            json_body=BusinessWireJsonEncoder().encode(payload, max_bytes=16384),
        )

    def decode_success(
        self,
        *,
        request: EmployeeSearchWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> EmployeeSearchWireResponse:
        return _decode_employee_hits(
            response=response,
            from_index=request.from_index,
            size=request.size,
            allow_partial_page=False,
        )


def _decode_employee_hits(
    *,
    response: BoundedBusinessHttpResponse,
    from_index: int,
    size: int,
    allow_partial_page: bool,
) -> EmployeeSearchWireResponse:
    content_type_parts = (response.content_type or "").split(";")
    media_type = content_type_parts[0].strip().lower()
    charset_valid = all(
        not part.strip().lower().startswith("charset=")
        or part.strip().split("=", 1)[1].strip().strip('"').casefold() == "utf-8"
        for part in content_type_parts[1:]
    )
    allowed_media_type = (
        media_type in {"application/json", "text/plain"}
        or media_type.startswith("application/") and media_type.endswith("+json")
    )
    if (
        not 200 <= response.status_code < 300
        or response.status_code == 204
        or not allowed_media_type
        or not charset_valid
        or response.body is None
        or len(response.body) > 1048576
        or response.body.startswith(b"\xef\xbb\xbf")
    ):
        raise InvalidBusinessWireResponse("business.invalid_response")
    try:
        raw = json.loads(
            response.body.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, InvalidBusinessWireResponse) as exc:
        raise InvalidBusinessWireResponse("business.invalid_response") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("hits"), dict):
        raise InvalidBusinessWireResponse("business.invalid_response")
    hits = cast(dict[str, object], raw["hits"])
    total = hits.get("total")
    rows = hits.get("hits")
    if (
        not isinstance(total, dict)
        or set(total) != {"value", "relation"}
        or type(total.get("value")) is not int
        or not 0 <= cast(int, total["value"]) <= 2**63 - 1
        or total.get("relation") not in {"eq", "gte"}
        or type(rows) is not list
        or len(rows) > size
        or cast(int, total["value"]) < len(rows)
    ):
        raise InvalidBusinessWireResponse("business.invalid_response")
    parsed = tuple(_employee_hit_record(item) for item in rows)
    records = tuple(item for item in parsed if item is not None)
    if rows and not records:
        raise InvalidBusinessWireResponse("business.invalid_response")
    return EmployeeSearchWireResponse(
        rows=records,
        total=cast(int, total["value"]),
        total_exact=total["relation"] == "eq",
        from_index=from_index,
        size=size,
        upstream_hit_count=len(rows),
        allow_partial_page=allow_partial_page,
    )


def _employee_hit_record(raw: object) -> EmployeeSearchRecord | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("_source"), dict):
        raise InvalidBusinessWireResponse("business.invalid_response")
    source = cast(dict[str, object], raw["_source"])
    missing_required_field = False
    for field in ("idCardNo", "chineseName"):
        value = source.get(field)
        if value is None:
            missing_required_field = True
            continue
        if type(value) is not str:
            raise InvalidBusinessWireResponse("business.invalid_response")
        if any(
            unicodedata.category(character) == "Cc"
            or unicodedata.bidirectional(character) in _BIDI
            for character in value
        ):
            raise InvalidBusinessWireResponse("business.invalid_response")
        if not value.strip():
            missing_required_field = True
    contact_address = _normalize(
        source.get("contactAddress"), minimum=1, maximum=256, optional=True
    )
    member_no = _normalize(source.get("memberNo"), minimum=5, maximum=64, optional=True)
    phone_no = _normalize(source.get("phoneNo"), minimum=1, maximum=128, optional=True)
    email = _normalize(source.get("email"), minimum=1, maximum=254, optional=True)
    position = _normalize(source.get("position"), minimum=1, maximum=256, optional=True)
    if missing_required_field:
        return None
    identifier = _required(_normalize(source["idCardNo"], minimum=5, maximum=64))
    name = _required(_normalize(source["chineseName"], minimum=1, maximum=128))
    return EmployeeSearchRecord(
        employee_identifier=identifier,
        chinese_name=name,
        contact_address=contact_address,
        member_no=member_no,
        phone_no=phone_no,
        email=email,
        position=position,
    )


class EmployeeSemanticSearchArgumentValidator:
    def validate(self, arguments: JsonObject) -> EmployeeSemanticSearchInput:
        if set(arguments) != {"query", "size"}:
            raise InvalidCapabilityArguments("business.invalid_arguments")
        query = _argument_text(arguments["query"], maximum=256)
        size = arguments["size"]
        if (
            type(size) is not int
            or not 1 <= size <= 50
            or classify_question(query) & (DENY_CLASSES - {QuestionDataClass.UNKNOWN})
        ):
            raise InvalidCapabilityArguments("business.invalid_arguments")
        return EmployeeSemanticSearchInput(query=query, size=size)


class EmployeeSemanticSearchRequestMapper:
    def map(
        self,
        input: EmployeeSemanticSearchInput,
        settings: BusinessActionSettings,
    ) -> EmployeeSemanticSearchWireRequest:
        if (
            settings.semantic_profile_id != "employee-default-v1"
            or settings.max_page_size is None
            or settings.max_result_count is None
            or input.size > min(settings.max_page_size, settings.max_result_count)
            or settings.fixed_page != 1
            or settings.max_page != 1
            or settings.allowed_filter_field_ids is not None
            or settings.allowed_sort_field_ids is not None
        ):
            raise InvalidBusinessArguments("business.invalid_arguments")
        return EmployeeSemanticSearchWireRequest(
            query=input.query,
            size=input.size,
            embedding_field="embedding",
            embedding_dims=1024,
            num_candidates=100,
            track_total_hits=10000,
        )


class EmployeeSemanticSearchWireCodec:
    def encode(self, request: EmployeeSemanticSearchWireRequest) -> BusinessHttpRequest:
        payload: dict[str, BusinessWireJsonValue] = {
            "queryText": request.query,
            "k": request.size,
            "embeddingField": request.embedding_field,
            "embeddingDims": request.embedding_dims,
            "numCandidates": request.num_candidates,
            "trackTotalHits": request.track_total_hits,
        }
        return BusinessHttpRequest(
            method="POST",
            relative_path="/employees/es/vector-search",
            query=(),
            json_body=BusinessWireJsonEncoder().encode(payload, max_bytes=4096),
        )

    def decode_success(
        self,
        *,
        request: EmployeeSemanticSearchWireRequest,
        response: BoundedBusinessHttpResponse,
    ) -> EmployeeSearchWireResponse:
        return _decode_employee_hits(
            response=response,
            from_index=0,
            size=request.size,
            allow_partial_page=True,
        )
