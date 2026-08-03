from __future__ import annotations

from decimal import Decimal

import pytest

from agent_runtime.adapters.transaction.codec import TransactionSearchWireCodec
from agent_runtime.adapters.transaction.contracts import (
    TransactionSearchCondition,
    TransactionSearchWireRequest,
    TransactionSort,
)
from agent_runtime.business.contracts import BoundedBusinessHttpResponse, InvalidBusinessWireResponse


def _request(size: int = 20) -> TransactionSearchWireRequest:
    return TransactionSearchWireRequest(
        condition=TransactionSearchCondition(
            trans_id=None, trans_type="PAY", trans_type_contains=None,
            amount=None, amount_gt=Decimal("100.10"), amount_lt=None,
        ),
        sorts=(TransactionSort(field="amount", direction="DESC"),), page=1, size=size,
    )


def test_transaction_request_maps_snake_to_camel_and_exact_decimal_to_number() -> None:
    request = TransactionSearchWireCodec().encode(_request())
    assert request.relative_path == "/txn/search"
    assert request.query == ()
    assert request.json_body is not None
    assert request.json_body.content == b'{"condition":{"amountGt":100.1,"transType":"PAY"},"page":1,"size":20,"sorts":[{"direction":"DESC","field":"amount"}]}'
    assert b'"100.1"' not in request.json_body.content


def test_transaction_response_reads_decimal_without_float_and_ignores_only_known_wide_date_fields() -> None:
    body = b'{"rows":[{"transId":"T0001","transType":"PAY","amount":100.10,"transDate":"2026-01-01"}],"total":1,"totalExact":true,"page":1,"size":20}'
    response = TransactionSearchWireCodec().decode_success(
        request=_request(),
        response=BoundedBusinessHttpResponse(status_code=200, content_type="application/json", body=body),
    )
    assert response.rows[0].amount == Decimal("100.10")
    assert type(response.rows[0].amount) is Decimal
    assert not hasattr(response.rows[0], "trans_date")


def test_transaction_response_rejects_unknown_row_field_and_request_echo_mismatch() -> None:
    codec = TransactionSearchWireCodec()
    for body in (
        b'{"rows":[{"transId":"T0001","transType":"PAY","amount":1,"secret":"x"}],"total":1,"totalExact":true,"page":1,"size":20}',
        b'{"rows":[{"transId":"T0001","transType":"PAY","amount":1.001}],"total":1,"totalExact":true,"page":1,"size":20}',
        b'{"rows":[{"transId":"T0001","transType":"PAY","amount":10000000000000000}],"total":1,"totalExact":true,"page":1,"size":20}',
        b'{"rows":[],"total":0,"totalExact":true,"page":2,"size":20}',
        b'\xef\xbb\xbf{"rows":[],"total":0,"totalExact":true,"page":1,"size":20}',
    ):
        with pytest.raises(InvalidBusinessWireResponse):
            codec.decode_success(request=_request(), response=BoundedBusinessHttpResponse(status_code=200, content_type="application/json", body=body))
