from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest

from agent_runtime.adapters.transaction.codec import (
    TransactionListSearchArgumentValidator,
    TransactionListSearchRequestMapper,
    TransactionListSearchWireCodec,
)
from agent_runtime.adapters.transaction.contracts import TransactionListSearchWireRequest
from agent_runtime.adapters.transaction.normalizer import TransactionListSearchResponseNormalizer
from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessFailureResult,
    BusinessNoResult,
    BusinessRecordsResult,
    InvalidBusinessWireResponse,
)
from agent_runtime.business.settings import BusinessQueryConfigurationLoader


def _request() -> TransactionListSearchWireRequest:
    selected = TransactionListSearchArgumentValidator().validate({
        "filters": (
            {"field": "trans_type", "operator": "contains", "value": "PAY"},
            {"field": "amount", "operator": "gt", "value": "100.10"},
            {
                "field": "trans_date", "operator": "gt",
                "value": "2026-08-25T09:00:00+08:00",
            },
        ),
        "page": 2,
        "size": 2,
        "sorts": ({"field": "trans_date", "direction": "DESC"},),
    })
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "transaction.search"
    ]
    return TransactionListSearchRequestMapper().map(selected, settings)


def _response(body: bytes) -> BoundedBusinessHttpResponse:
    return BoundedBusinessHttpResponse(
        status_code=200, content_type="application/json", body=body
    )


def test_v2_wire_maps_offset_date_decimal_number_and_existing_java_condition() -> None:
    request = TransactionListSearchWireCodec().encode(_request())

    assert request.relative_path == "/txn/search"
    assert request.json_body is not None
    payload = json.loads(request.json_body.content, parse_float=Decimal)
    assert payload["page"] == 2
    assert payload["size"] == 2
    assert payload["sorts"] == [{"field": "transDate", "direction": "DESC"}]
    assert payload["condition"] == {
        "transTypeContains": "PAY",
        "amountGt": Decimal("100.1"),
        "transDateGt": "2026-08-25T09:00:00+08:00",
    }
    assert b'"100.1"' not in request.json_body.content


def test_v2_response_decodes_java_epoch_milliseconds_into_shanghai_offset() -> None:
    body = (
        b'{"rows":[{"transId":"TXN-0001","transType":"PAY",'
        b'"transDate":1787619600000,"amount":100.10,"transDateGt":null,'
        b'"transDateLt":null,"amountGt":null,"amountLt":null,'
        b'"transTypeContains":null}],"total":3,"totalExact":true,"page":2,"size":2}'
    )

    response = TransactionListSearchWireCodec().decode_success(
        request=_request(), response=_response(body)
    )
    normalized = TransactionListSearchResponseNormalizer().normalize_success(response)

    assert response.rows[0].trans_date == datetime.fromisoformat(
        "2026-08-25T09:00:00+08:00"
    )
    assert response.rows[0].amount == Decimal("100.10")
    assert isinstance(normalized, BusinessRecordsResult)
    assert normalized.coverage.total_count == 3
    assert normalized.coverage.returned_count == 1
    assert not normalized.coverage.truncated


def test_v2_response_decodes_production_spring_utc_milliseconds_into_same_instant() -> None:
    body = (
        b'{"rows":[{"transId":"TXN-0001","transType":"PAY",'
        b'"transDate":"2026-08-25T01:00:00.000+00:00","amount":100.10,'
        b'"transDateGt":null,"transDateLt":null,"amountGt":null,'
        b'"amountLt":null,"transTypeContains":null}],'
        b'"total":3,"totalExact":true,"page":2,"size":2}'
    )

    response = TransactionListSearchWireCodec().decode_success(
        request=_request(), response=_response(body)
    )

    assert response.rows[0].trans_date == datetime.fromisoformat(
        "2026-08-25T09:00:00+08:00"
    )
    assert response.rows[0].amount == Decimal("100.10")


@pytest.mark.parametrize(
    "body",
    (
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":"2026-08-25","amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":"2026-08-25T01:00:00.000Z","amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":"2026-08-25T09:00:00.000+08:00","amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":"2026-08-25T01:00:00.001+00:00","amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":"2026-08-25T01:00:00+00:00","amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":"2026-02-30T01:00:00.000+00:00","amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":1787619600001,"amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":true,"amount":1}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":1787619600000,"amount":"1.00"}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":1787619600000,"amount":1.001}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[{"transId":"TXN-1","transType":"PAY","transDate":1787619600000,"amount":1,"secret":"x"}],"total":3,"totalExact":true,"page":2,"size":2}',
        b'{"rows":[],"total":0,"totalExact":true,"page":1,"size":2}',
    ),
)
def test_v2_response_rejects_unverified_date_unknown_fields_and_invalid_amount(
    body: bytes,
) -> None:
    with pytest.raises(InvalidBusinessWireResponse):
        TransactionListSearchWireCodec().decode_success(
            request=_request(), response=_response(body)
        )


def test_v2_response_treats_empty_page_as_no_result_and_invalid_exact_page_as_failure() -> None:
    codec = TransactionListSearchWireCodec()
    normalizer = TransactionListSearchResponseNormalizer()
    empty = codec.decode_success(
        request=_request(),
        response=_response(
            b'{"rows":[],"total":2,"totalExact":true,"page":2,"size":2}'
        ),
    )
    invalid = codec.decode_success(
        request=_request(),
        response=_response(
            b'{"rows":[{"transId":"TXN-0001","transType":"PAY",'
            b'"transDate":1787619600000,"amount":1}],'
            b'"total":2,"totalExact":true,"page":2,"size":2}'
        ),
    )

    assert isinstance(normalizer.normalize_success(empty), BusinessNoResult)
    assert isinstance(normalizer.normalize_success(invalid), BusinessFailureResult)
