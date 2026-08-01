from __future__ import annotations

import json
import unicodedata
from urllib.parse import quote

from agent_runtime.capability_api.contracts import InvalidCapabilityArguments, JsonObject
from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessActionSettings,
    BusinessHttpRequest,
    InvalidBusinessArguments,
    InvalidBusinessWireResponse,
)
from agent_runtime.adapters.employee.contracts import (
    EmployeeDetailInput,
    EmployeeDetailWireRequest,
    EmployeeDetailWireResponse,
)

_BIDI = {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
_TARGETS = {"idCardNo", "memberNo", "chineseName", "publicEmail", "position", "workBaseSi"}


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
            work_base_si=_normalize(raw["workBaseSi"], minimum=1, maximum=256, optional=True),
        )


def _required(value: str | None) -> str:
    if value is None:
        raise InvalidBusinessWireResponse("business.invalid_response")
    return value
