from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Self, TypeAlias

BUSINESS_WIRE_MAX_DEPTH = 8
BUSINESS_WIRE_MAX_COLLECTION_ITEMS = 256
EXACT_DECIMAL_MAX_TOKEN_BYTES = 128


class InvalidBusinessWireRequest(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ExactDecimal:
    value: Decimal
    _token: str

    @classmethod
    def from_decimal(cls, value: Decimal) -> Self:
        if type(value) is not Decimal or not value.is_finite():
            raise InvalidBusinessWireRequest("business.invalid_exact_decimal")
        sign, digits_tuple, raw_exponent = value.as_tuple()
        if not isinstance(raw_exponent, int):
            raise InvalidBusinessWireRequest("business.invalid_exact_decimal")
        exponent = raw_exponent
        digits = list(digits_tuple)
        if not any(digits):
            return cls(value=value, _token="0")
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        coefficient_len = len(digits)
        if exponent >= 0:
            token_len = sign + coefficient_len + exponent
        else:
            point = coefficient_len + exponent
            token_len = sign + (coefficient_len + 1 if point > 0 else 2 + (-point) + coefficient_len)
        if token_len > EXACT_DECIMAL_MAX_TOKEN_BYTES:
            raise InvalidBusinessWireRequest("business.exact_decimal_too_large")
        coefficient = "".join(str(item) for item in digits)
        if exponent >= 0:
            plain = coefficient + ("0" * exponent)
        else:
            point = len(coefficient) + exponent
            plain = coefficient[:point] + "." + coefficient[point:] if point > 0 else "0." + ("0" * (-point)) + coefficient
        token = ("-" if sign else "") + plain
        if len(token.encode("ascii")) > EXACT_DECIMAL_MAX_TOKEN_BYTES:
            raise InvalidBusinessWireRequest("business.exact_decimal_too_large")
        return cls(value=value, _token=token)


BusinessWireJsonScalar: TypeAlias = None | bool | int | str | ExactDecimal
BusinessWireJsonValue: TypeAlias = BusinessWireJsonScalar | tuple["BusinessWireJsonValue", ...] | Mapping[str, "BusinessWireJsonValue"]
BusinessWireJsonObject: TypeAlias = Mapping[str, BusinessWireJsonValue]

_BODY_TOKEN = object()


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalBusinessJsonBody:
    content: bytes
    _creation_token: object

    def __post_init__(self) -> None:
        if self._creation_token is not _BODY_TOKEN:
            raise InvalidBusinessWireRequest("business.canonical_body_factory_required")


def _string_bytes(value: str) -> bytes:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidBusinessWireRequest("business.invalid_unicode")
    parts = ['"']
    escapes = {"\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t", '"': '\\"', "\\": "\\\\"}
    for character in value:
        if character in escapes:
            parts.append(escapes[character])
        elif ord(character) < 0x20:
            parts.append(f"\\u{ord(character):04x}")
        else:
            parts.append(character)
    parts.append('"')
    return "".join(parts).encode("utf-8")


class BusinessWireJsonEncoder:
    def encode(self, body: BusinessWireJsonObject, *, max_bytes: int) -> CanonicalBusinessJsonBody:
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 1024 <= max_bytes <= 65536:
            raise InvalidBusinessWireRequest("business.invalid_request_limit")
        output = bytearray()
        ancestors: set[int] = set()

        def emit(part: bytes) -> None:
            output.extend(part)
            if len(output) > max_bytes:
                raise InvalidBusinessWireRequest("business.request_too_large")

        def write(value: object, depth: int) -> None:
            if depth > BUSINESS_WIRE_MAX_DEPTH:
                raise InvalidBusinessWireRequest("business.wire_depth_exceeded")
            if value is None:
                emit(b"null")
            elif type(value) is bool:
                emit(b"true" if value else b"false")
            elif type(value) is int:
                if not -(2**63) <= value <= 2**63 - 1:
                    raise InvalidBusinessWireRequest("business.integer_out_of_range")
                emit(str(value).encode("ascii"))
            elif type(value) is str:
                emit(_string_bytes(value))
            elif type(value) is ExactDecimal:
                emit(value._token.encode("ascii"))
            elif isinstance(value, Mapping):
                if len(value) > BUSINESS_WIRE_MAX_COLLECTION_ITEMS or any(type(key) is not str for key in value):
                    raise InvalidBusinessWireRequest("business.invalid_wire_object")
                identity = id(value)
                if identity in ancestors:
                    raise InvalidBusinessWireRequest("business.wire_cycle")
                ancestors.add(identity)
                emit(b"{")
                ordered = sorted(value.items(), key=lambda item: item[0].encode("utf-8"))
                for index, (key, item) in enumerate(ordered):
                    if index:
                        emit(b",")
                    emit(_string_bytes(key))
                    emit(b":")
                    write(item, depth + 1)
                emit(b"}")
                ancestors.remove(identity)
            elif type(value) is tuple:
                if len(value) > BUSINESS_WIRE_MAX_COLLECTION_ITEMS:
                    raise InvalidBusinessWireRequest("business.wire_collection_too_large")
                identity = id(value)
                if identity in ancestors:
                    raise InvalidBusinessWireRequest("business.wire_cycle")
                ancestors.add(identity)
                emit(b"[")
                for index, item in enumerate(value):
                    if index:
                        emit(b",")
                    write(item, depth + 1)
                emit(b"]")
                ancestors.remove(identity)
            else:
                raise InvalidBusinessWireRequest("business.wire_type_not_allowed")

        if not isinstance(body, Mapping):
            raise InvalidBusinessWireRequest("business.wire_object_required")
        write(body, 1)
        return CanonicalBusinessJsonBody(content=bytes(output), _creation_token=_BODY_TOKEN)
