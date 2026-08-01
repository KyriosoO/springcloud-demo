from __future__ import annotations

from decimal import Decimal

import pytest

from agent_runtime.business.wire_json import (
    BusinessWireJsonEncoder,
    ExactDecimal,
    InvalidBusinessWireRequest,
)


@pytest.mark.parametrize(
    "raw,token",
    [("0", b"0"), ("-0.000", b"0"), ("100.00", b"100"), ("0.1000", b"0.1"), ("-12.3400", b"-12.34")],
)
def test_exact_decimal_is_plain_canonical_json_number(raw: str, token: bytes) -> None:
    body = BusinessWireJsonEncoder().encode(
        {"amount": ExactDecimal.from_decimal(Decimal(raw))},
        max_bytes=4096,
    )
    assert body.content == b'{"amount":' + token + b"}"


def test_wire_encoder_rejects_float_naked_decimal_and_large_exponent_before_expansion() -> None:
    encoder = BusinessWireJsonEncoder()
    with pytest.raises(InvalidBusinessWireRequest):
        encoder.encode({"amount": 0.1}, max_bytes=4096)  # type: ignore[dict-item]
    with pytest.raises(InvalidBusinessWireRequest):
        encoder.encode({"amount": Decimal("0.1")}, max_bytes=4096)  # type: ignore[dict-item]
    with pytest.raises(InvalidBusinessWireRequest, match="too_large"):
        ExactDecimal.from_decimal(Decimal("1e1000000"))


def test_wire_encoder_has_stable_utf8_key_order_and_escape_rules() -> None:
    body = BusinessWireJsonEncoder().encode({"中": "x\n", "a": "y/z"}, max_bytes=4096)
    assert body.content == b'{"a":"y/z","\xe4\xb8\xad":"x\\n"}'


def test_wire_encoder_enforces_request_boundary() -> None:
    with pytest.raises(InvalidBusinessWireRequest, match="request_too_large"):
        BusinessWireJsonEncoder().encode({"value": "x" * 4090}, max_bytes=4096)

